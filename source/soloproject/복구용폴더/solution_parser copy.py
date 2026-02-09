import re
import os
import json
import numpy as np
from pathlib import Path
import ollama
import cv2
from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = None

# ---- Optional: OCR deps ----
try:
    import cv2
    import pytesseract
    from pytesseract import Output
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

# ---- Optional: PDF fallback deps (rarely needed) ----
try:
    import fitz  # PyMuPDF
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False


# =========================
# HARD-CODED PATHS (question_parser 스타일)
# =========================
ROOT = Path("data")          # 입력 루트
OUT_ROOT = Path("output")    # 출력 루트 (하드코딩)

def is_solution_header_like(pil_crop: Image.Image) -> bool:
    """
    '정답표/해설 헤더' 같은 조각을 스킵하기 위한 가벼운 판별.
    - '해설'이 있는데 문항번호 패턴(1., 2) 등)이 없으면 헤더로 간주
    """
    w, h = pil_crop.size

    # OCR 비용 줄이려고 상단~중앙 일부만 본다 (해설 헤더는 보통 상단에 있음)
    roi = pil_crop.crop((0, 0, w, min(h, 260)))

    # 너무 큰 이미지는 OCR 전 다운스케일(속도↑)
    maxw = 900
    if roi.size[0] > maxw:
        ratio = maxw / roi.size[0]
        roi = roi.resize((maxw, int(roi.size[1] * ratio)))

    txt = pytesseract.image_to_string(roi, lang="kor+eng")
    txt = txt.replace(" ", "")

    has_haesul = ("해설" in txt)

    # 문항 시작 패턴(대충)  "1." "12." "1)" "12)" "1．" 등
    has_qnum = bool(re.search(r"(^|\n)([1-9]|[12]\d|30)[\.\)\］\]．]", txt))

    # 해설 헤더는 보통 '해설' 있고 문항번호가 없다
    if has_haesul and not has_qnum:
        return True

    # 정답표(숫자 밀집) 케이스도 대충 차단(숫자가 너무 많고 문항 패턴이 없으면)
    digits = sum(ch.isdigit() for ch in txt)
    if digits >= 25 and not has_qnum:
        return True

    return False

# (선택) tesseract 설치 경로를 코드에 고정하고 싶으면 여기만 수정
# PATH 환경변수로 tesseract가 잡혀 있으면 None으로 두면 됨.
TESS_ROOT = r"C:\Users\Admin\Tesseract-OCR"  # 예: r"C:\Program Files\Tesseract-OCR"
# TESS_ROOT = None


# =========================
# Utils
# =========================

def trim_to_content(pil_img: Image.Image, black_thr: int = 10, white_thr: int = 245, pad: int = 20) -> Image.Image:
    """
    검정 패딩/흰 여백을 제외하고 '내용(글자/수식/선)'이 있는 영역만 남긴다.
    - black_thr: 이 값 이하는 검정 배경으로 간주(제외)
    - white_thr: 이 값 이상은 흰 여백으로 간주(제외)
    - pad: bbox 주변 여유(너무 딱 붙는 걸 방지)
    """
    g = pil_img.convert("L")
    arr = np.array(g)

    # 내용: 너무 검정도 아니고, 너무 흰 것도 아닌 픽셀들
    content = (arr > black_thr) & (arr < white_thr)

    if not content.any():
        return pil_img

    ys, xs = np.where(content)
    x0, x1 = xs.min(), xs.max() + 1
    y0, y1 = ys.min(), ys.max() + 1

    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(pil_img.size[0], x1 + pad)
    y1 = min(pil_img.size[1], y1 + pad)

    return pil_img.crop((x0, y0, x1, y1))

def save_jsonl(rows, out_path: Path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# =========================
# Meta parsing (yyyy학년도 m월)
# =========================
def parse_meta(filename: str, grade: int):
    year = 2020
    m_year = re.search(r"(\d{2,4})학년도", filename)
    if m_year:
        val = m_year.group(1)
        year = int(val) if len(val) == 4 else int(val) + 2000

    m_month = re.search(r"(\d{1,2})월", filename)
    month = int(m_month.group(1)) if m_month else 3

    return {"grade": grade, "year": year, "month": month, "track": "common"}


# =========================
# Auto find solution PNG
# =========================
def find_solution_png_for_question_pdf(pdf_path: Path) -> Path | None:
    """
    문제 PDF와 같은 폴더에 있는 해설 PNG를 찾는다.
    기본 규칙: <문제파일명>.pdf -> <문제파일명>해설.png
    """
    base = pdf_path.with_suffix("")
    cand = Path(str(base) + "해설.png")
    if cand.exists():
        return cand

    for p in pdf_path.parent.glob("*.png"):
        if "해설" in p.name and p.stem.replace("해설", "").startswith(base.name):
            return p
    return None


# =========================
# OCR Anchors (PNG only)
# =========================
QNUM_TOKEN_RE = re.compile(r"^\s*(\d{1,2})\s*[\.\)\]]\s*$")  # "1." "1)" "1]"
_TEMP_DIR = Path(".tmp_solution_parser")


def _save_temp(pil_img: Image.Image) -> Path:
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    p = _TEMP_DIR / "roi.png"
    pil_img.save(p)
    return p


def _preprocess_for_ocr(pil_img: Image.Image, scale: float = 0.55, left_ratio: float = 0.50):
    img = pil_img.convert("L")
    w, h = img.size

    roi = img.crop((0, 0, int(w * left_ratio), h))
    if scale != 1.0:
        roi = roi.resize((max(1, int(roi.size[0] * scale)), max(1, int(roi.size[1] * scale))))

    arr = cv2.cvtColor(cv2.imread(str(_save_temp(roi))), cv2.COLOR_BGR2GRAY)
    arr = cv2.GaussianBlur(arr, (3, 3), 0)
    _, th = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th, scale

def get_anchors_from_solution_png(png_path: str):
    if TESS_ROOT:
        pytesseract.pytesseract.tesseract_cmd = os.path.join(TESS_ROOT, "tesseract.exe")
    
    pil = Image.open(png_path)
    w, h = pil.size
    anchors = {}

    # 1. 원본 화질 유지를 위한 5등분 중첩 스캔 (인식률 95% 이상 목표)
    num_sections = 5
    section_h = h // num_sections
    overlap = 1000 

    for i in range(num_sections):
        y_start = max(0, i * section_h - overlap)
        y_end = min(h, (i + 1) * section_h + overlap)
        
        # 번호가 있는 왼쪽 영역만 스캔
        roi = pil.crop((0, y_start, int(w * 0.3), y_end))
        data = pytesseract.image_to_data(roi, lang="kor+eng", output_type=Output.DICT, config="--psm 6")

        for j, txt in enumerate(data.get("text", [])):
            t = txt.strip()
            # 숫자 뒤에 점이나 괄호가 붙은 정교한 패턴 (1. 2. 1) 등)
            m = re.match(r"^(\d{1,2})[\.\)\]]?$", t)
            if m:
                qnum = int(m.group(1))
                if 1 <= qnum <= 30:
                    abs_y = data["top"][j] + y_start
                    # 같은 번호가 여러 번 잡히면 가장 위쪽 좌표 저장
                    if qnum not in anchors or abs_y < anchors[qnum]:
                        anchors[qnum] = abs_y

    return [{"qnum": k, "y": anchors[k]} for k in sorted(anchors.keys())]

# def split_solution_png_by_anchors(png_path: str, meta: dict, anchors: list):
#     img = Image.open(png_path)
#     w, h = img.size
#     sol_assets = {}
    
#     # 저장 경로
#     rel_folder = f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}"
#     target_dir = OUT_ROOT / rel_folder
#     target_dir.mkdir(parents=True, exist_ok=True)

#     # [수정] 1번의 시작점 설정 (이미지 최상단 혹은 정답표 아래 - 여기서는 상단 5% 지점 가정)
#     # 보통 정답표가 위에 있으므로 1번 출제의도 이전까지는 정답표 영역일 수 있습니다.
    
#     for i in range(len(anchors)):
#         qnum = anchors[i]['qnum']
        
#         # 시작점(y0): 현재 문항의 [출제의도] 위쪽
#         y0 = max(0, anchors[i]['y'] - 50) 
        
#         # 끝점(y1): 다음 문항의 [출제의도] 바로 위까지
#         if i + 1 < len(anchors):
#             y1 = anchors[i+1]['y'] - 55
#         else:
#             y1 = h # 마지막 문항은 끝까지
            
#         crop = img.crop((0, y0, w, y1))
#         # 내용물에 맞춰 흰 여백 제거
#         crop = trim_to_content(crop) 

#         fname = f"q{qnum:02d}.png"
#         crop.save(target_dir / fname)
#         sol_assets[qnum] = [f"{rel_folder}/{fname}"]
        
#     return sol_assets

# 2. 실제 자르기 함수 (1번 문항에 정답표 포함)
def split_solution_png_by_anchors(png_path: str, meta: dict, anchors: list):
    img = Image.open(png_path)
    gray = img.convert('L')
    arr = np.array(gray)
    w, h = img.size
    
    # 흰색 판정 (조금 더 엄격하게 245)
    row_means = np.mean(arr, axis=1)
    is_white = row_means > 245 

    target_dir = OUT_ROOT / f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}"
    target_dir.mkdir(parents=True, exist_ok=True)
    sol_assets = {}

    # 각 문항의 실제 '물리적' 경계선을 저장할 리스트
    boundaries = [0] # 1번의 시작은 0

    for i in range(len(anchors) - 1):
        # 현재 번호와 다음 번호 사이의 '최적 절단면' 찾기
        curr_y = anchors[i]['y']
        next_y = anchors[i+1]['y']
        
        search_start = curr_y + 100
        search_end = next_y - 20
        
        white_indices = np.where(is_white[search_start:search_end])[0]
        
        if len(white_indices) > 0:
            # [핵심] 하얀 공간의 '마지막'이 아니라 '중앙'을 자릅니다.
            # 이렇게 하면 앞 문제의 마지막 줄과 뒷 문제의 번호 사이에 완충 지대가 생깁니다.
            mid_white = white_indices[len(white_indices) // 2]
            boundaries.append(search_start + mid_white)
        else:
            # 하얀 공간을 못 찾으면 번호 사이의 70% 지점을 자름 (안전장치)
            boundaries.append(int(curr_y + (next_y - curr_y) * 0.7))
            
    boundaries.append(h) # 마지막은 이미지 끝

    # 결정된 경계선대로 크롭
    for i in range(len(anchors)):
        y0 = boundaries[i]
        y1 = boundaries[i+1]
        
        # 1번 문항일 때만 특별히 y0를 0으로 고정 (정답표 포함)
        if i == 0: y0 = 0

        crop = img.crop((0, y0, w, y1))
        
        # trim_to_content를 하되 pad를 40으로 넉넉히 주어 
        # 글자 외곽이 잘리는 현상을 방지합니다.
        crop = trim_to_content(crop, pad=40)

        qnum = anchors[i]['qnum']
        fname = f"q{qnum:02d}.png"
        crop.save(target_dir / fname)
        sol_assets[qnum] = [f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}/{fname}"]

    return sol_assets
# =========================
# Anchor normalization/fill
# =========================
def normalize_and_fill_anchors(anchors, img_h: int):
    if not anchors:
        return []

    qy = {a["qnum"]: int(max(0, min(img_h - 1, a["y"]))) for a in anchors}

    min_gap = 130

    prev_y = None
    for q in sorted(list(qy.keys())):
        if prev_y is None:
            prev_y = qy[q]
            continue

        if qy[q] - prev_y < min_gap:
            # 이전 문항과 너무 가까움 → 가짜 앵커
            del qy[q]
        else:
            prev_y = qy[q]

    missing = [q for q in range(1, 31) if q not in qy]
    for q in missing:
        prev_q = max([p for p in qy.keys() if p < q], default=None)
        next_q = min([n for n in qy.keys() if n > q], default=None)

        if prev_q is None and next_q is None:
            continue
        elif prev_q is None:
            qy[q] = max(0, qy[next_q] - 50)
        elif next_q is None:
            qy[q] = min(img_h - 1, qy[prev_q] + 50)
        else:
            t = (q - prev_q) / (next_q - prev_q)
            qy[q] = int(qy[prev_q] + t * (qy[next_q] - qy[prev_q]))

    final = [{"qnum": q, "y": qy[q]} for q in range(1, 31)]
    for i in range(1, len(final)):
        if final[i]["y"] <= final[i - 1]["y"]:
            final[i]["y"] = min(img_h - 1, final[i - 1]["y"] + 10)
    return final

# def pil_to_bgr(pil_img: Image.Image) -> np.ndarray:
#     """PIL(RGB or L) -> OpenCV BGR ndarray"""
#     if pil_img.mode != "RGB":
#         pil_img = pil_img.convert("RGB")
#     arr = np.array(pil_img)              # RGB
#     return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

# def bgr_to_pil(img_bgr: np.ndarray) -> Image.Image:
#     """OpenCV BGR -> PIL RGB"""
#     rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
#     return Image.fromarray(rgb)

def pil_to_bgr(pil_img: Image.Image) -> np.ndarray:
    rgb = np.array(pil_img.convert("RGB"))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

def bgr_to_pil(bgr: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)

def trim_black_margins(img_bgr, black_thresh=20, margin=2, pad=0):
    """
    '검정 여백' 제거.
    - margin: bbox를 아주 조금 확장(안전)
    - pad: bbox를 넉넉히 확장(글자 잘림 방지)
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    mask = gray > black_thresh
    coords = np.column_stack(np.where(mask))
    if coords.size == 0:
        return img_bgr

    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0)

    h, w = gray.shape

    # 기본 margin 확장
    y0 = max(0, y0 - margin)
    x0 = max(0, x0 - margin)
    y1 = min(h - 1, y1 + margin)
    x1 = min(w - 1, x1 + margin)

    # ✅ pad는 margin보다 더 크게 확장
    if pad and pad > 0:
        y0 = max(0, y0 - pad)
        x0 = max(0, x0 - pad)
        y1 = min(h - 1, y1 + pad)
        x1 = min(w - 1, x1 + pad)

    return img_bgr[y0:y1+1, x0:x1+1]

# =========================
# Crop PNG -> output/assets/solutions/...
# =========================
def split_solution_png_by_anchors(
    png_path: str,
    meta: dict,
    anchors,
    min_height=240,
    pad_top=20,
    overlap_bottom=40,     # ✅ 다음 문제 제목이 조금 들어와도 허용(권장 20~80)
    bottom_margin=0,       # ✅ "next_y - margin" 방식은 겹침을 싫어할 때만 사용
    trim_pad=10,           # ✅ trim 이후 최종 패딩(진짜로 남는 패딩)
    black_thresh=20,
):
    img = Image.open(png_path).convert("RGB")
    w, h = img.size

    rel_folder = f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}"
    target_dir = OUT_ROOT / rel_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    sol_assets = {}

    for i, curr in enumerate(anchors):
        qnum = curr["qnum"]
        y0 = max(0, curr["y"] - pad_top)

        if i == len(anchors) - 1:
            y1 = h
        else:
            next_y = anchors[i + 1]["y"]

            # ✅ A안(추천): "겹침 허용" (다음 제목이 조금 들어와도 OK)
            y1 = min(h, next_y + overlap_bottom)

            # 만약 겹침 싫으면 아래처럼 쓰는 방식(기존 방식)
            # y1 = min(h, max(next_y - bottom_margin, y0 + min_height))

            # 그래도 너무 짧게 잘리는 건 방어
            y1 = min(h, max(y1, y0 + min_height))

        if y1 - y0 < 80:
            continue

        crop_pil = img.crop((0, y0, w, y1))

        # ✅ trim_black_margins는 cv2(BGR)로 처리
        crop_bgr = pil_to_bgr(crop_pil)
        crop_bgr = trim_black_margins(
            crop_bgr,
            black_thresh=black_thresh,
            margin=2,   # bbox 확장
            pad=0       # 여기서는 pad로 확장하지 말고(혼동 방지) 아래에서 expand로 처리
        )
        crop_pil = bgr_to_pil(crop_bgr)

        # ✅ 최종 패딩: 이건 trim 이후에도 절대 안 깎임
        if trim_pad > 0:
            crop_pil = ImageOps.expand(crop_pil, border=(trim_pad, trim_pad, trim_pad, trim_pad), fill="white")

        fname = f"q{qnum:02d}.png"
        crop_pil.save(target_dir / fname)
        sol_assets[qnum] = [f"{rel_folder}/{fname}"]

    return sol_assets


def ocr_solution_text(png_file: Path) -> str | None:
    if not OCR_AVAILABLE:
        return None

    # PIL -> OpenCV 전처리
    pil = Image.open(png_file).convert("L")

    import numpy as np
    arr = np.array(pil)

    # (선택) 글자 선명하게: 이진화 + 확대
    import cv2
    arr = cv2.resize(arr, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
    _, bin_img = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Tesseract 옵션 (상황 따라 튜닝)
    config = "--psm 6"
    try:
        txt = pytesseract.image_to_string(bin_img, lang="kor+eng", config=config)
    except Exception:
        # kor 데이터 없거나 하면 fallback
        txt = pytesseract.image_to_string(bin_img, config=config)

    # 너무 지저분한 공백 정리(가벼운 수준)
    txt = "\n".join(line.rstrip() for line in txt.splitlines()).strip()
    return txt or None



# =========================
# Batch main (question_parser처럼 그냥 실행)
# =========================
def main():
    if OCR_AVAILABLE and TESS_ROOT:
        pytesseract.pytesseract.tesseract_cmd = os.path.join(TESS_ROOT, "tesseract.exe")

    pdf_paths = sorted({p.resolve() for p in ROOT.rglob("*.pdf")})
    print("CWD:", os.getcwd())
    print("FOUND PDFs:", len(pdf_paths))

    for pdf_path in pdf_paths:
        filename = pdf_path.name

        # 고1만
        if "고1" in pdf_path.parts:
            grade = 1
        else:
            continue

        # 문제 pdf만(해설 pdf는 스킵)
        if "해설" in filename:
            continue

        sol_png = find_solution_png_for_question_pdf(pdf_path)
        if sol_png is None:
            print("NO solution png:", pdf_path)
            continue

        meta = parse_meta(sol_png.name, grade=grade)

        img = Image.open(sol_png)
        w, h = img.size
        print(f"[RUN] {pdf_path.name} -> {sol_png.name} ({w}x{h})")

        anchors = []
        if OCR_AVAILABLE:
            anchors = get_anchors_from_solution_png(str(sol_png))
            print(f"  OCR anchors: {len(anchors)}")
        else:
            print("  WARN: OCR not available (opencv-python, pytesseract 필요)")

        if not anchors:
            print("  WARN: fallback equal split")
            anchors = [{"qnum": i, "y": int((i - 1) * (h / 30))} for i in range(1, 31)]

        anchors = normalize_and_fill_anchors(anchors, img_h=h)
        sol_assets = split_solution_png_by_anchors(str(sol_png), meta, anchors)

        # ✅ solution jsonl 저장(하드코딩 경로)
        s_out_path = (
            OUT_ROOT
            / "jsonl"
            / "solutions"
            / f"g{grade}"
            / f"{meta['year']}_{meta['month']}_{meta['track']}_solution.jsonl"
        )

        rows = []
        for qnum in range(1, 31):
            if qnum in sol_assets:
                qid = f"g{grade}_{meta['year']}_{meta['month']}_{meta['track']}_q{qnum:02d}"
                rel = sol_assets[qnum][0]
                abs_png = OUT_ROOT / rel  # output/assets/... 로 합쳐짐

                sol_text = ocr_solution_text(abs_png)
                rows.append({
                    "id": qid,
                    "grade": grade,
                    "year": meta["year"],
                    "month": meta["month"],
                    "track": meta["track"],
                    "question_number": qnum,
                    "solution_assets": sol_assets[qnum],
                    "solution_text": sol_text,
                    "solution_text_len": 0 if sol_text is None else len(sol_text),
                    "ocr_ok": bool(sol_text and len(sol_text) >= 30),
                })

        save_jsonl(rows, s_out_path)
        print("  -> WRITE solutions jsonl:", s_out_path)
        print("  -> cropped:", len(sol_assets))

    print("[DONE] batch complete")


if __name__ == "__main__":
    main()