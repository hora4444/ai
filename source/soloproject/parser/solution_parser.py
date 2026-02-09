import re
import os
import json
import numpy as np
from pathlib import Path
import ollama
import cv2
import io
from PIL import Image, ImageOps
Image.MAX_IMAGE_PIXELS = None

# ---- Optional: OCR deps ----
try:
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

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
client = ollama.Client(timeout=None)
# =========================
# HARD-CODED PATHS (question_parser 스타일)
# =========================
ROOT = Path("data")          # 입력 루트
OUT_ROOT = Path("output")    # 출력 루트 (하드코딩)
MODEL_NAME = 'qwen3-vl:4b'

def get_smart_split_points(image_path, max_chunk_height=1800):
    """
    OpenCV와 Tesseract를 활용해 수식이 잘리지 않는 최적의 절단 지점을 계산합니다.
    """
    img = cv2.imread(str(image_path))
    if img is None: return []
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 1. 문제 번호 위치 탐색 (앵커 포인트)
    d = pytesseract.image_to_data(gray, output_type=Output.DICT)
    split_candidates = []
    for i in range(len(d['text'])):
        text = d['text'][i].strip()
        if re.match(r'^\d+\.?$', text): # 숫자로 된 문제 번호 찾기
            split_candidates.append(d['top'][i])

    # 2. 번호 사이가 너무 길거나 수식이 있을 경우를 대비한 '여백' 기반 절단
    final_splits = [0]
    last_split = 0
    
    # 임계치(max_chunk_height)마다 자를 지점을 검토
    check_points = split_candidates if split_candidates else list(range(max_chunk_height, h, max_chunk_height))
    for target_y in check_points:
        if target_y - last_split < 500: continue # 너무 짧게 자르는 것 방지
        
        # 여백 탐색 (번호 위쪽 또는 해당 지점 주변 100px)
        search_start = max(0, target_y - 100)
        search_range = gray[search_start:min(h, target_y + 20), :]
        row_sums = np.sum(search_range, axis=1)
        
        # 가장 하얀 줄(픽셀 합 최대) 찾기
        best_gap_relative = np.argmax(row_sums)
        best_gap_absolute = search_start + best_gap_relative
        
        final_splits.append(best_gap_absolute)
        last_split = best_gap_absolute
            
    final_splits.append(h)
    return sorted(list(set(final_splits)))

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
# TESS_ROOT = r"C:\Users\Admin\Tesseract-OCR"  # 예: r"C:\Program Files\Tesseract-OCR"
TESS_ROOT = r"C:\Program Files\Tesseract-OCR"
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


def ask_ollama_vision(img_input):
    """기존 Tesseract 대신 Ollama qwen3-vl:4b 사용"""
    try:
        if isinstance(img_input, Image.Image):
            # PIL 이미지를 바이트로 변환
            img_byte_arr = io.BytesIO()
            img_input.save(img_byte_arr, format='PNG')
            img_final = img_byte_arr.getvalue()
        else:
            # 경로일 경우 파일 읽기
            with open(img_input, 'rb') as f:
                img_final = f.read()

        res = client.chat(
            model=MODEL_NAME,
            messages=[{
                'role': 'user', 
                'content': '이 수학 해설 이미지 조각의 내용을 LaTeX로 추출해줘. 인사말이나 "여기 있습니다" 같은 문구 없이 본문만 출력해.',
                'images': [img_final]
            }]
        )
        return res['message']['content']
    except Exception as e:
        print(f"      [!] LLM 호출 오류: {e}")
        return None
    
def process_solution_with_splitting(abs_png):
    """
    이미지가 길면 쪼개서 처리하고, 짧으면 그냥 처리하는 통합 함수
    """
    # 1. 이미지 크기 확인
    with Image.open(abs_png) as tmp_img:
        width, height = tmp_img.size
    
    # 세로가 2000px 이하로 짧으면 그냥 한 번에 처리
    if height < 2000:
        return ask_ollama_vision(abs_png)

    # 2. 길 경우 스마트 절단 수행
    print(f"    [>] 이미지가 길어({height}px) 지능적 분할을 시작합니다...")
    splits = get_smart_split_points(abs_png)
    full_img = Image.open(abs_png)
    
    parts_results = []
    for i in range(len(splits)-1):
        top = splits[i]
        bottom = splits[i+1]
        
        # 약간의 오버랩(5px)을 주어 문맥 유지
        crop_img = full_img.crop((0, max(0, top-5), full_img.width, min(full_img.height, bottom+5)))
        
        # 디버깅용 (필요시 주석 해제하여 절단면 확인 가능)
        # crop_img.save(f"output/debug_q_{i}.png")
        
        print(f"      - 조각 {i+1}/{len(splits)-1} 처리 중...")
        part_text = ask_ollama_vision(crop_img)
        if part_text:
            parts_results.append(part_text)
            
    return "\n\n".join(parts_results)

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
                # sol_text = ocr_solution_text(abs_png) # 기존 OCR 대신
                print(f"\n[작업 시작] {qid}")
                sol_text = process_solution_with_splitting(abs_png)    # Ollama 호출
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