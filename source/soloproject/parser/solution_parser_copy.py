import argparse, json, os, re, io
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
import fitz

# 이미지 픽셀 제한 해제
Image.MAX_IMAGE_PIXELS = None

@dataclass
class GlobalAnchor:
    qnum: int
    track: str
    global_y: float

def parse_exam_filename(filename: str, grade: int) -> Optional[dict]:
    base = Path(filename).stem
    nums = re.findall(r"\d+", base)
    year = int(nums[0]) if nums and len(nums[0]) == 4 else 2020
    month = int(nums[1]) if len(nums) >= 2 else 3
    kind = "solution" if any(kw in base for kw in ["해설", "정답", "sol"]) else "problem"
    is_suneung = "수능" in base
    return {"year": year, "month": month, "grade": grade, "kind": kind, "track": "common", "is_suneung": is_suneung}

def process_pdf_to_linear_canvas(pdf_path: str, meta: dict, dpi: int = 150):
    doc = fitz.open(pdf_path)
    all_column_images = []
    global_anchors = []
    current_total_height = 0
    scale = dpi / 72.0
    
    # [인식 강화] 고1, 고2에서 "출제의도"가 없거나 공백이 심한 경우 대비
    # 숫자 뒤에 마침표나 대괄호가 오고 '출제' 혹은 '정답' 키워드가 오는 경우를 모두 탐색
    ANCHOR_PATTERN = re.compile(r"(\d+)[\.\]\s]*\[?.*?(출제|정답|해설).*?의도?.*?\]?", re.IGNORECASE)

    for p_idx in range(len(doc)):
        page = doc[p_idx]
        w, h = page.rect.width, page.rect.height
        
        # [자동 레이아웃 판별] 수능이거나 너비가 특정 기준 이하면 2단, 아니면 3단
        if meta["is_suneung"]:
            col_rects = [fitz.Rect(0, 0, w*0.48, h), fitz.Rect(w*0.52, 0, w, h)]
        else:
            # 일반 학평용 3단 구성 (여백 포함)
            col_rects = [
                fitz.Rect(0, 0, w*0.32, h),
                fitz.Rect(w*0.34, 0, w*0.65, h),
                fitz.Rect(w*0.67, 0, w, h)
            ]

        for rect in col_rects:
            pix = page.get_pixmap(clip=rect, dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes()))
            all_column_images.append(img)
            
            # 인식은 좀 더 넓게 (텍스트 누락 방지)
            search_rect = fitz.Rect(rect.x0 - 10, 0, rect.x1 + 10, h)
            blocks = page.get_text("blocks", clip=search_rect)
            blocks.sort(key=lambda b: b[1])
            
            for b in blocks:
                # 공백과 특수문자를 제거하여 파편화된 텍스트 병합
                raw_text = re.sub(r'\s+', '', b[4])
                m = ANCHOR_PATTERN.search(raw_text)
                
                if m:
                    qnum = int(m.group(1))
                    # 중복 인식 방지 (이전 앵커와 너무 가까우면 스킵)
                    global_y = current_total_height + (b[1] * scale)
                    if not global_anchors or abs(global_anchors[-1].global_y - global_y) > 50:
                        global_anchors.append(GlobalAnchor(qnum, "common", global_y))
            
            current_total_height += img.height

    if not all_column_images: return None, [], doc

    # 3. 모든 단을 세로로 병합
    max_w = max(img.width for img in all_column_images)
    combined_img = Image.new("RGB", (max_w, current_total_height), (255, 255, 255))
    y_ptr = 0
    for img in all_column_images:
        combined_img.paste(img, (0, y_ptr))
        y_ptr += img.height
        
    return combined_img, global_anchors, doc

def process_pdf_to_linear_canvas(pdf_path: str, grade: int, dpi: int = 150):
    doc = fitz.open(pdf_path)
    all_column_images = []
    global_anchors = []
    current_total_height = 0
    scale = dpi / 72.0
    
    # 공백 제거 후 인식하는 강력한 패턴
    ANCHOR_PATTERN = re.compile(r"(\d+)[\.\[]출제.*?의도")

    for p_idx in range(len(doc)):
        page = doc[p_idx]
        w, h = page.rect.width, page.rect.height
        
        # [사용자 제안 반영: 정밀 3단 분할]
        # 단 사이의 미세한 간섭을 줄이기 위해 경계면에 아주 약간의 여백(1%)을 둡니다.
        col_rects = [
            fitz.Rect(0, 0, w * 0.32, h),           # 1열 (좌)
            fitz.Rect(w * 0.34, 0, w * 0.65, h),    # 2열 (중)
            fitz.Rect(w * 0.67, 0, w, h)            # 3열 (우)
        ]

        for col_idx, rect in enumerate(col_rects):
            # 1. 단 이미지 추출
            pix = page.get_pixmap(clip=rect, dpi=dpi)
            img = Image.open(io.BytesIO(pix.tobytes()))
            all_column_images.append(img)
            
            # 2. 앵커 인식 (인식 영역은 이미지보다 좌우로 5pt씩 더 넓게 설정해서 번호 누락 방지)
            search_rect = fitz.Rect(rect.x0 - 5, 0, rect.x1 + 5, h)
            blocks = page.get_text("blocks", clip=search_rect)
            blocks.sort(key=lambda b: b[1])
            
            for b in blocks:
                text = b[4].replace(" ", "").replace("\n", "")
                m = ANCHOR_PATTERN.search(text)
                if m:
                    qnum = int(m.group(1))
                    # 절대 Y좌표 = 지금까지 쌓인 기차의 총 높이 + 현재 조각에서의 상대 높이
                    global_y = current_total_height + (b[1] * scale)
                    global_anchors.append(GlobalAnchor(qnum, "common", global_y))
            
            # 조각 하나를 붙일 때마다 기차의 전체 높이를 갱신
            current_total_height += img.height

    # 3. 모든 조각 이미지를 하나의 거대한 세로 이미지로 병합
    if not all_column_images:
        return None, [], doc

    max_width = max(img.width for img in all_column_images)
    combined_img = Image.new("RGB", (max_width, current_total_height), (255, 255, 255))
    
    y_ptr = 0
    for c_img in all_column_images:
        combined_img.paste(c_img, (0, y_ptr))
        y_ptr += c_img.height
        
    return combined_img, global_anchors, doc

def build_solution_items(pdf_path: str, meta: dict, dpi: int, out_root: Path):
    big_canvas, anchors, doc = process_pdf_to_linear_canvas(pdf_path, meta, dpi)
    anchors.sort(key=lambda x: x.global_y)
    
    # 앵커가 아예 안 잡혔을 때의 예외 처리
    if not anchors:
        print(f"  [!] No anchors found in {Path(pdf_path).name}")
        doc.close()
        return {}

    tracks_items = {}
    for i in range(len(anchors)):
        curr = anchors[i]
        nxt = anchors[i+1] if i + 1 < len(anchors) else None
        
        # 컷팅 범위 설정 (번호 위로 30px, 다음 번호 위 20px까지)
        y0 = max(0, curr.global_y - 30)
        y1 = (nxt.global_y - 25) if nxt else big_canvas.height
        if y1 <= y0: y1 = y0 + 500 # 최소 높이 보장
        
        crop_img = big_canvas.crop((0, y0, big_canvas.width, y1))
        
        # 경로 생성 및 저장
        rel_path = Path(f"g{meta['grade']}") / f"{meta['year']}_{meta['month']:02d}" / curr.track / f"q{curr.qnum:02d}.png"
        save_path = out_root / "solutions" / "assets" / rel_path
        save_path.parent.mkdir(parents=True, exist_ok=True)
        crop_img.save(save_path)

        item = {
            "qnum": curr.qnum,
            "track": curr.track,
            "assets": [f"assets/solutions/{rel_path.as_posix()}"],
            "meta": meta
        }
        tracks_items.setdefault(curr.track, []).append(item)
    
    doc.close()
    return tracks_items

def main():
    ap = argparse.ArgumentParser()
    # 실행 파일 위치 기준 경로 설정
    base_dir = Path(__file__).resolve().parent.parent
    ap.add_argument("--input_dir", type=str, default=str(base_dir / "data"), help="folder containing PDFs")
    ap.add_argument("--out_dir", type=str, default=str(base_dir / "output"), help="output root")
    ap.add_argument("--dpi", type=int, default=200)
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out_root = Path(args.out_dir)

    pdf_paths = sorted(input_dir.rglob("*.pdf"))
    if not pdf_paths:
        print("No PDFs found under:", input_dir)
        return

    for pdf_path in pdf_paths:
        parts = " ".join(pdf_path.parts)
        if "고1" in parts or "g1" in parts.lower(): grade = 1
        elif "고2" in parts or "g2" in parts.lower(): grade = 2
        elif "고3" in parts or "g3" in parts.lower(): grade = 3
        else: grade = 1 # 기본값

        meta = parse_exam_filename(pdf_path.name, grade)
        if not meta or meta["kind"] != "solution": continue

        print(f"[*] 처리 중: {pdf_path.name}")
        tracks_items = build_solution_items(str(pdf_path), meta, args.dpi, out_root)
        
        # JSONL 저장
        for track, items in tracks_items.items():
            jsonl_dir = out_root / "solutions" / "jsonl" / f"g{grade}"
            jsonl_dir.mkdir(parents=True, exist_ok=True)
            out_name = f"{meta['year']}_{meta['month']:02d}_{track}_solution.jsonl"
            with open(jsonl_dir / out_name, "w", encoding="utf-8") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"  -> {track} 트랙 저장 완료.")

if __name__ == "__main__":
    main()