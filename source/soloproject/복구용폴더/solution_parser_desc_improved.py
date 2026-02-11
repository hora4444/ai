# solution_parser_desc_improved.py
# - 기존 solution_parser.py(앵커 기반 이미지 크롭)와 solution_parser_desc.py(전체 LaTeX 후 30->1 파싱) 장점을 합친 개선본
# - "파일을 찾을 수 없음"의 주 원인(하드코딩 경로, JSONL 파일명 규칙 불일치, 임시파일 전달 방식)을 제거
# - Ollama Python SDK에는 "이미지 파일 경로 문자열" 대신 bytes를 전달(안전/OS 독립)

from __future__ import annotations

import argparse
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Tuple, Optional

from PIL import Image

try:
    import ollama
except Exception as e:
    raise RuntimeError(
        "ollama Python 패키지가 필요합니다. `pip install ollama` 후 다시 실행하세요."
    ) from e


# --------------------------
# Meta / path helpers
# --------------------------

def parse_meta_from_name(name: str, grade: int) -> Dict:
    """
    다양한 파일명에서 (year, month)를 최대한 복원.
    우선순위:
        1) '2020학년도 3월' 패턴
        2) '2020_03' 또는 '2020-3' 등
        3) 실패 시 (2020, 3) 기본값
    """
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

    # track 추론(필요하면 확장)
    if "가형" in name or "나형" in name:
        track = "track"  # placeholder (프로젝트 규칙에 맞게 바꾸세요)

    return {"grade": grade, "year": year, "month": month, "track": track}


def find_exam_images(root: Path, grade: int) -> List[Path]:
    """
    data 루트에서 해당 학년의 해설 이미지(.png/.jpg)를 찾는다.
    - 기존 solution_parser.py는 PDF 옆의 '*해설.png'를 찾는 방식이었고,
        solution_parser_desc.py는 data/고1 아래 모든 jpg/png를 보는 방식이었다.
    - 여기서는 '해설' 키워드가 들어간 이미지만 우선 대상으로 삼되,
        없으면 학년 폴더 내 이미지를 모두 처리하도록 옵션 제공.
    """
    grade_folder_tokens = [f"고{grade}", f"g{grade}"]
    candidates = []
    for token in grade_folder_tokens:
        candidates.extend(root.rglob(f"*{token}*/*.png"))
        candidates.extend(root.rglob(f"*{token}*/*.jpg"))
        candidates.extend(root.rglob(f"*{token}*/*.jpeg"))

    # 폴더 토큰 탐색이 비었으면 그냥 전부에서 해설 이미지 위주로
    if not candidates:
        candidates = list(root.rglob("*.png")) + list(root.rglob("*.jpg")) + list(root.rglob("*.jpeg"))

    # 해설 키워드 우선
    sol = [p for p in candidates if "해설" in p.name]
    return sorted(sol if sol else candidates)


def locate_jsonl(out_root: Path, meta: Dict) -> Path:
    """
    solution_parser.py의 저장 규칙과 정렬:
        output/jsonl/solutions/g{grade}/{year}_{month}_{track}_solution.jsonl
    month는 0-padding 없음(예: 2020_3_common_solution.jsonl)
    """
    return (
        out_root
        / "jsonl"
        / "solutions"
        / f"g{meta['grade']}"
        / f"{meta['year']}_{meta['month']}_{meta['track']}_solution.jsonl"
    )


# --------------------------
# Ollama vision
# --------------------------

def image_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def ask_ollama_latex(client: "ollama.Client", model: str, img: Image.Image, prompt: str) -> str:
    """
    Ollama에 bytes로 이미지 전달.
    """
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


def ocr_full_text(
    client: "ollama.Client",
    model: str,
    img_path: Path,
    slice_height: int,
    overlap: int,
    sleep: float,
    prompt: str,
) -> str:
    img = Image.open(img_path).convert("RGB")
    parts = slice_image(img, slice_height=slice_height, overlap=overlap)

    out_chunks: List[str] = []
    for i, part in enumerate(parts, 1):
        text = ask_ollama_latex(client, model, part, prompt)
        out_chunks.append(text)
        if sleep:
            time.sleep(sleep)

    return "\n\n".join(out_chunks)


# --------------------------
# Backward parsing (30 -> 1)
# --------------------------

def _anchor_regex_for_num(num: int) -> re.Pattern:
    """
    VLM 출력이 일정하지 않아서 앵커 패턴을 넓게 잡는다.
    예) "29.", "29 )", "29]", "29．", "29번", "29. [풀이]" 등
    """
    n = re.escape(str(num))
    # 문장 중간 오탐을 줄이려고 줄 시작/줄바꿈 기준을 포함
    pattern = rf"(?m)(^|\n)\s*{n}\s*(?:[\.．\)\]\:]|번)\s*(?:\[[^\]]{{0,40}}\])?"
    return re.compile(pattern)


def backward_slicing(full_text: str, q_nums: List[int]) -> Dict[int, str]:
    """
    내림차순으로 각 문항의 시작점을 찾아서 잘라낸다.
    - "가장 마지막 매치"를 잡는 방식 유지
    - 매치가 없으면 빈 문자열
    """
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
# JSONL update
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
            updated += 1
    save_jsonl(data, out_path)
    return updated


# --------------------------
# Main
# --------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("data"), help="입력 data 루트(기본: data)")
    ap.add_argument("--out_root", type=Path, default=Path("output"), help="출력 output 루트(기본: output)")
    ap.add_argument("--grade", type=int, default=1, help="학년(기본: 1)")
    ap.add_argument("--model", type=str, default="qwen3-vl:2b", help="Ollama 비전 모델명")
    ap.add_argument("--slice_height", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=150)
    ap.add_argument("--sleep", type=float, default=0.8, help="조각 처리 사이 sleep(기본 0.8s)")
    ap.add_argument("--only_if_jsonl_exists", action="store_true", help="대상 JSONL 없으면 해당 이미지는 스킵")
    ap.add_argument("--prompt", type=str, default="수학 해설 이미지를 LaTeX로 변환해줘. 군더더기 문장 없이 본문만. 문항 번호는 생략하지 마.",
                    help="VLM 프롬프트")
    ap.add_argument("--write_suffix", type=str, default="_desc_fixed",
                    help="출력 JSONL suffix(기본: _desc_fixed)")
    args = ap.parse_args()

    client = ollama.Client(timeout=None)

    images = find_exam_images(args.root, args.grade)
    print(f"[FOUND] images: {len(images)} (root={args.root})")

    for img_path in images:
        meta = parse_meta_from_name(img_path.name, grade=args.grade)

        jsonl_path = locate_jsonl(args.out_root, meta)
        if not jsonl_path.exists():
            msg = f"[SKIP] JSONL not found: {jsonl_path}"
            if args.only_if_jsonl_exists:
                print(msg)
                continue
            else:
                # JSONL이 없으면 q1~30으로라도 파싱 시도(저장은 별도 파일)
                print(msg + "  (will parse anyway with q1~30)")
                q_nums = list(range(1, 31))
        else:
            data = load_jsonl(jsonl_path)
            q_nums = [int(x.get("question_number", 0)) for x in data if 1 <= int(x.get("question_number", 0)) <= 30]

        print(f"\n🚀 Processing: {img_path.name}  -> meta={meta}  q_nums={len(q_nums)}")

        full_text = ocr_full_text(
            client=client,
            model=args.model,
            img_path=img_path,
            slice_height=args.slice_height,
            overlap=args.overlap,
            sleep=args.sleep,
            prompt=args.prompt,
        )

        sol_map = backward_slicing(full_text, q_nums)

        # 저장
        if jsonl_path.exists():
            out_path = jsonl_path.with_name(jsonl_path.stem + args.write_suffix + jsonl_path.suffix)
            updated = update_solution_jsonl(jsonl_path, sol_map, out_path)
            print(f"✅ WROTE: {out_path}  (updated={updated}/{len(q_nums)})")
        else:
            # JSONL이 없으면 파싱 결과만 별도 저장
            out_path = args.out_root / "debug" / f"g{args.grade}" / f"{meta['year']}_{meta['month']}_{meta['track']}_solution_desc_only.jsonl"
            rows = [{"question_number": q, "solution_text": sol_map.get(q, "")} for q in sorted(sol_map.keys())]
            save_jsonl(rows, out_path)
            print(f"✅ WROTE (desc only): {out_path}")


if __name__ == "__main__":
    main()
