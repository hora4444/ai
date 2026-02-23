# solution_parser_desc_marker.py
# 목적:
#   1) 해설 이미지를 "전체 LaTeX"로 먼저 OCR
#   2) 각 문항 시작을 강제 마커(<<<Q29>>>)로 출력하게 만들어
#      28/29처럼 '출제의도'가 앞 문항에 섞이거나, 중간 잘림으로 번호가 밀리는 문제를 최소화
#   3) 마커가 일부 누락되면 regex 기반 내림차순(30->1) 백업 파싱을 수행
#
# 사용 예:
#   python solution_parser_desc_marker.py --grade 1 --model qwen3-vl:4b
#   python solution_parser_desc_marker.py --grade 1 --only_if_jsonl_exists
#   python solution_parser_desc_marker.py --grade 1 --fallback_regex

from __future__ import annotations

import argparse
import io
import json
import re
import time
from pathlib import Path
from typing import Dict, List

from PIL import Image

try:
    import ollama
except Exception as e:
    raise RuntimeError("ollama 패키지가 필요합니다. `pip install ollama`") from e


# --------------------------
# Meta / path helpers
# --------------------------

def parse_meta_from_name(name: str, grade: int) -> Dict:
    """파일명에서 (year, month)를 최대한 복원. 실패 시 기본값."""
    year = 2020
    month = 3
    track = "common"

    m_year = re.search(r"(\d{2,4})\s*학년도", name)
    if m_year:
        val = m_year.group(1)
        year = int(val) if len(val) == 4 else int(val) + 2000

    m_month = re.search(r"(\d{1,2})\s*월", name)
    if m_month:
        month = int(m_month.group(1))
    else:
        m_ym = re.search(r"(\d{4})\s*[_\-]\s*(\d{1,2})", name)
        if m_ym:
            year = int(m_ym.group(1))
            month = int(m_ym.group(2))

    return {"grade": grade, "year": year, "month": month, "track": track}


def find_exam_images(root: Path, grade: int) -> List[Path]:
    """data 루트에서 해당 학년 해설 이미지(.png/.jpg)를 찾는다."""
    grade_tokens = [f"고{grade}", f"g{grade}"]
    candidates: List[Path] = []

    for t in grade_tokens:
        candidates += list(root.rglob(f"*{t}*/*.png"))
        candidates += list(root.rglob(f"*{t}*/*.jpg"))
        candidates += list(root.rglob(f"*{t}*/*.jpeg"))

    if not candidates:
        candidates = list(root.rglob("*.png")) + list(root.rglob("*.jpg")) + list(root.rglob("*.jpeg"))

    sols = [p for p in candidates if "해설" in p.name]
    return sorted(sols if sols else candidates)


def locate_jsonl(out_root: Path, meta: Dict) -> Path:
    """solution_parser.py 쪽과 동일 규칙."""
    return (
        out_root / "jsonl" / "solutions" / f"g{meta['grade']}" /
        f"{meta['year']}_{meta['month']}_{meta['track']}_solution.jsonl"
    )


# --------------------------
# Ollama vision
# --------------------------

def image_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ask_ollama_latex(client: "ollama.Client", model: str, img: Image.Image, prompt: str) -> str:
    img_bytes = image_to_png_bytes(img)
    res = client.chat(
        model=model,
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [img_bytes],
        }]
    )
    return res["message"]["content"]


def slice_image(img: Image.Image, slice_height: int, overlap: int) -> List[Image.Image]:
    w, h = img.size
    y = 0
    parts: List[Image.Image] = []
    while y < h:
        y2 = min(y + slice_height, h)
        parts.append(img.crop((0, y, w, y2)))
        if y2 >= h:
            break
        y = y2 - overlap
    return parts

def save_smart_slices(img_path: Path, output_dir: Path, slice_height: int = 4000, overlap: int = 500):
    """이미지를 물리적으로 자르고 저장하여 모델이 읽기 편한 환경을 만듭니다."""
    img = Image.open(img_path).convert("RGB")
    w, h = img.size
    output_dir.mkdir(parents=True, exist_ok=True)
    
    y = 0
    idx = 0
    slice_paths = []
    
    while y < h:
        y2 = min(y + slice_height, h)
        # 패딩을 고려한 크롭
        part = img.crop((0, y, w, y2))
        
        slice_name = f"{img_path.stem}_part_{idx:02d}.png"
        save_path = output_dir / slice_name
        part.save(save_path)
        slice_paths.append(save_path)
        
        if y2 >= h: break
        y = y2 - overlap  # 겹치는 구간 생성
        idx += 1
        
    return slice_paths


# def ocr_full_text(
#     client: "ollama.Client",
#     model: str,
#     img_path: Path,
#     slice_height: int,
#     overlap: int,
#     sleep: float,
#     prompt: str,
# ) -> str:
#     img = Image.open(img_path).convert("RGB")
#     parts = slice_image(img, slice_height=slice_height, overlap=overlap)

#     out_chunks: List[str] = []
#     for part in parts:
#         text = ask_ollama_latex(client, model, part, prompt)
#         out_chunks.append(text)
#         if sleep:
#             time.sleep(sleep)

#     return "\n\n".join(out_chunks)


# --------------------------
# Parsing: marker-first, fallback
# --------------------------

_MARKER_RE = re.compile(r"(?m)^\s*<<<\s*Q\s*(\d{1,2})\s*>>>\s*$")


def parse_by_markers(full_text: str) -> Dict[int, str]:
    """<<<Qn>>> 마커 기반 분리."""
    matches = list(_MARKER_RE.finditer(full_text))
    if not matches:
        return {}

    blocks: Dict[int, str] = {}
    for idx, m in enumerate(matches):
        q = int(m.group(1))
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        body = full_text[start:end].strip()
        if body:
            # 동일 번호가 여러 번 나오면 마지막이 덮어씀(가장 완전한 경우가 많음)
            blocks[q] = body
    return blocks


def _anchor_regex_for_num(num: int) -> re.Pattern:
    n = re.escape(str(num))
    pattern = rf"(?m)(^|\n)\s*{n}\s*(?:[\.．\)\]\:]|번)\s*(?:\[[^\]]{{0,40}}\])?"
    return re.compile(pattern)


def backward_slicing(full_text: str, q_nums: List[int]) -> Dict[int, str]:
    """백업: 내림차순(30->1)으로 문항 시작점을 찾아 자른다."""
    sorted_nums = sorted(set(q_nums), reverse=True)
    parsed: Dict[int, str] = {}
    pool = full_text

    for num in sorted_nums:
        pat = _anchor_regex_for_num(num)
        matches = list(pat.finditer(pool))
        if not matches:
            parsed[num] = ""
            continue

        m = matches[-1]
        split_idx = m.start()
        parsed[num] = pool[split_idx:].strip()
        pool = pool[:split_idx]

    return parsed


# --------------------------
# JSONL IO
# --------------------------

def load_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def save_jsonl(rows: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def update_solution_jsonl(jsonl_path: Path, solution_map: Dict[int, str], out_path: Path) -> int:
    data = load_jsonl(jsonl_path)
    updated = 0
    for item in data:
        q = int(item.get("question_number", 0))
        new_txt = solution_map.get(q, "")
        if new_txt and len(new_txt) >= 15:
            item["solution_text"] = new_txt
            item["solution_text_len"] = len(new_txt)
            item["ocr_ok"] = True
            item["ocr_source"] = "marker_or_fallback"
            updated += 1
    save_jsonl(data, out_path)
    return updated

# --------------------------
# Prompt builder (marker enforced)
# --------------------------

def build_marker_prompt(q_nums: List[int]) -> str:
    if q_nums:
        qs = ", ".join(str(x) for x in sorted(set(q_nums)))
        scope_line = f"대상 문항 번호는 다음 중에서만 골라라: {qs}."
    else:
        scope_line = "대상 문항 번호는 1~30이다."

    return (
        "너는 수학 해설 이미지를 LaTeX로 정확히 옮기는 역할이다.\n"
        "아래 규칙을 반드시 지켜라.\n\n"
        "규칙:\n"
        "1) 각 문항 해설의 시작을 '단독 한 줄' 마커로 표시하라: <<<Q번호>>> (예: <<<Q29>>>).\n"
        "2) 해설 본문에 그래프나 도형 등 그림이 있다면, 해당 그림의 위치를 아래 형식으로 본문 중간에 삽입하라.\n"
        "   형식: [[COORD:ymin,xmin,ymax,xmax]] (0~1000 사이의 상대 좌표값)\n"
        "3) 마커 외에 다른 설명/코멘트/머리말/맺음말은 생략하고 LaTeX 본문만 출력하라.\n"
        "4) 이미지에 보이는 문항 번호(예: 29., 29번, [출제의도] 등)는 본문에 포함해도 되지만,\n"
        "   '문항 구분'은 오직 마커(<<<Q...>>>)로만 하라.\n"
        "5) 표/수식/문장은 가능한 한 원문 구조를 유지하라.\n"
        f"6) {scope_line}\n"
    )

def extract_images_from_text(full_text: str, source_img: Image.Image, save_dir: Path, img_prefix: str) -> str:
    """텍스트 내 COORD 마커를 찾아 이미지를 자르고 경로 태그로 치환한다."""
    save_dir.mkdir(parents=True, exist_ok=True)
    w, h = source_img.size
    
    # [[COORD:ymin,xmin,ymax,xmax]] 패턴 매칭
    coord_pattern = re.compile(r"\[\[COORD:(\d+),(\d+),(\d+),(\d+)\]\]")
    
    def replace_func(match):
        try:
            ymin, xmin, ymax, xmax = map(int, match.groups())
            # 좌표 정규화 (0~1000 기준을 픽셀로 변환)
            left = (xmin / 1000) * w
            top = (ymin / 1000) * h
            right = (xmax / 1000) * w
            bottom = (ymax / 1000) * h
            
            # 이미지 자르기 및 저장
            img_name = f"{img_prefix}_{int(time.time()*1000) % 10000}.png"
            img_path = save_dir / img_name
            cropped = source_img.crop((left, top, right, bottom))
            cropped.save(img_path)
            
            return f"\n\n[IMAGE: {img_path}]\n\n"
        except Exception:
            return "[그림 추출 실패]"

    return coord_pattern.sub(replace_func, full_text)

def ocr_full_text_with_images(
    client: ollama.Client, model: str, img_path: Path, prompt: str, image_out_dir: Path
) -> str:
    """전체 OCR을 수행하고 내부의 이미지 좌표를 처리한다."""
    img = Image.open(img_path).convert("RGB")
    # 편의상 슬라이싱 없이 전체로 보거나 큰 단위로 처리 (좌표 정확도를 위해)
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    
    res = client.chat(
        model=model,
        messages=[{"role": "user", "content": prompt, "images": [img_bytes.getvalue()]}]
    )
    raw_text = res["message"]["content"]
    
    # 이미지 추출 및 텍스트 치환
    prefix = img_path.stem
    final_text = extract_images_from_text(raw_text, img, image_out_dir, prefix)
    return final_text

# --------------------------
# Main
# --------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("data"))
    ap.add_argument("--out_root", type=Path, default=Path("output"))
    ap.add_argument("--grade", type=int, default=1)
    ap.add_argument("--model", type=str, default="qwen3-vl:2b")
    ap.add_argument("--slice_height", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=150)
    ap.add_argument("--sleep", type=float, default=0.8)
    ap.add_argument("--only_if_jsonl_exists", action="store_true")
    ap.add_argument("--write_suffix", type=str, default="_marker")
    ap.add_argument("--fallback_regex", action="store_true", help="마커 누락 시 regex 백업을 강제로 사용")
    ap.add_argument("--dump_full_text", action="store_true", help="OCR 전체 텍스트를 파일로 저장")
    ap.add_argument("--dump_dir", type=Path, default=Path("output") / "debug_fulltext", help="전체 텍스트 저장 폴더")
    args = ap.parse_args()

    client = ollama.Client(timeout=None)
    images = find_exam_images(args.root, args.grade)
    print(f"[FOUND] images: {len(images)} (root={args.root})")
    args_img_dir = Path("output/images")

    for img_path in images:
        meta = parse_meta_from_name(img_path.name, grade=args.grade)
        jsonl_path = locate_jsonl(args.out_root, meta)

        if not jsonl_path.exists() and args.only_if_jsonl_exists:
            print(f"[SKIP] JSONL not found: {jsonl_path}")
            continue

        if jsonl_path.exists():
            data = load_jsonl(jsonl_path)
            q_nums = [int(x.get("question_number", 0)) for x in data if 1 <= int(x.get("question_number", 0)) <= 30]
        else:
            q_nums = list(range(1, 31))

        print(f"\n🚀 Processing: {img_path.name}  -> meta={meta}  q_nums={len(q_nums)}")

        prompt = build_marker_prompt(q_nums)
        full_text = ocr_full_text_with_images(
            client, args.model, img_path, prompt, args_img_dir
        )
        # full_text = ocr_full_text(
        #     client=client,
        #     model=args.model,
        #     img_path=img_path,
        #     slice_height=args.slice_height,
        #     overlap=args.overlap,
        #     sleep=args.sleep,
        #     prompt=prompt,
        # )

        sol_map = parse_by_markers(full_text)
        marker_hit = sum(1 for q in q_nums if sol_map.get(q))

        missing = [q for q in q_nums if not sol_map.get(q)]
        found = sorted([q for q in q_nums if sol_map.get(q)])
        if found:
            print(f"[MARKERS] found={len(found)}/{len(q_nums)} -> {found}")
        if missing:
            # 길어질 수 있어서 앞/뒤만 요약 출력
            if len(missing) <= 20:
                print(f"[MISSING] {len(missing)} -> {missing}")
            else:
                print(f"[MISSING] {len(missing)} -> head={missing[:10]} ... tail={missing[-10:]}")

        # 마커가 많이 누락되면(60% 미만) 자동으로 백업 파싱으로 빈 칸 보충
        need_fallback = marker_hit < max(3, int(0.6 * len(q_nums)))
        if args.fallback_regex or need_fallback:
            fb = backward_slicing(full_text, q_nums)
            for q in q_nums:
                if not sol_map.get(q) and fb.get(q):
                    sol_map[q] = fb[q]
            print(f"[INFO] marker_hit={marker_hit}/{len(q_nums)} -> fallback_used=True")
        else:
            print(f"[INFO] marker_hit={marker_hit}/{len(q_nums)} -> fallback_used=False")

        # 저장
        if jsonl_path.exists():
            out_path = jsonl_path.with_name(jsonl_path.stem + args.write_suffix + jsonl_path.suffix)
            updated = update_solution_jsonl(jsonl_path, sol_map, out_path)
            print(f"✅ WROTE: {out_path}  (updated={updated}/{len(q_nums)})")
        else:
            out_path = args.out_root / "debug" / f"g{args.grade}" / f"{meta['year']}_{meta['month']}_{meta['track']}_solution_marker_only.jsonl"
            rows = [{"question_number": q, "solution_text": sol_map.get(q, "")} for q in sorted(sol_map.keys())]
            save_jsonl(rows, out_path)
            print(f"✅ WROTE (marker only): {out_path}")


if __name__ == "__main__":
    main()
