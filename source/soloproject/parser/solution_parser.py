
# -*- coding: utf-8 -*-
"""
Solution (해설) PDF ingest:
- Extract per-question solution segments
- Save cropped solution images (assets) WITHOUT blank split bands
- Special case: Grade 3 elective sections (23~30) split into tracks:
  common(1~22) + calculus/geometry/probability(23~30 each)

Usage:
  python 1_solution_parser.py --input_dir data/solutions --out_dir output

Dependencies:
  pip install pymupdf
"""
from __future__ import annotations
import argparse, json, os, re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from PIL import Image
import io

import fitz  # PyMuPDF


# -----------------------------
# filename/meta
# -----------------------------
def parse_exam_filename(filename: str, grade: int) -> Optional[dict]:
    base = Path(filename).stem
    nums = re.findall(r"\d+", base)
    
    # 연도 추출 (2자리 20 -> 2020)
    if not nums: return None
    year_val = nums[0]
    year = int(year_val) if len(year_val) == 4 else 2000 + int(year_val)
    
    # 월 추출 (수능이면 11월, 아니면 파일명에 적힌 두 번째 숫자)
    if "수능" in base:
        month = 11
    elif len(nums) >= 2:
        month = int(nums[1])
    else:
        month = 1 # 기본값
        
    kind = "solution" if any(kw in base for kw in ["해설", "정답", "sol"]) else "problem"
    return {"year": year, "month": month, "grade": grade, "kind": kind, "track": "common"}


# -----------------------------
# layout / anchors
# -----------------------------
TRACK_KEYWORDS = [
    ("calculus", ["미적분"]),
    ("geometry", ["기하"]),
    ("probability", ["확률과통계", "확통"]),
]

# ANCHOR_RE = re.compile(r"^\s*(\d{1,2})\.\s*\[?\s*출제의도\s*\]?\s*")
ANCHOR_PATTERN = re.compile(r"(\d+)\s*.*?출제\s*의도")


@dataclass
class Anchor:
    qnum: int
    page: int
    rect: fitz.Rect  # bbox of anchor text (line)
    col: int         # 0=left, 1=right
    track: str       # common/calculus/geometry/probability


def _iter_spans_in_clip(page: fitz.Page, clip: Optional[fitz.Rect] = None):
    d = page.get_text("dict", clip=clip)
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            for sp in ln.get("spans", []):
                yield sp


def _page_mid_gap(page: fitz.Page) -> Tuple[float, float]:
    """
    Return (mid_x, gap_px). We keep it simple: midpoint + small fixed gap.
    """
    w = page.rect.width
    return (w / 2.0, 10.0)


def _column_rect(page: fitz.Page, col: int, margin: float = 5.0) -> fitz.Rect:
    mid, gap = _page_mid_gap(page)
    if col == 0:
        return fitz.Rect(page.rect.x0 + margin, page.rect.y0 + margin, mid - gap, page.rect.y1 - margin)
    return fitz.Rect(mid + gap, page.rect.y0 + margin, page.rect.x1 - margin, page.rect.y1 - margin)


def _detect_track_above(page: fitz.Page, y: float, clip: fitz.Rect) -> Optional[str]:
    """
    Look for elective keyword within (clip) but above y.
    Returns the last seen track keyword above y.
    """
    last = None
    # only search upper region for speed
    upper = fitz.Rect(clip.x0, clip.y0, clip.x1, max(clip.y0, y))
    text = page.get_text("text", clip=upper)
    # choose the latest track that appears in the text
    for track, kws in TRACK_KEYWORDS:
        for kw in kws:
            if kw in text:
                last = track
    return last


def find_solution_anchors(doc: fitz.Document, grade: int) -> List[Anchor]:
    # 더 유연한 정규식: 숫자와 [출제의도] 사이에 어떤 공백이나 문자가 있어도 허용
    # 예: "1 . [ 출제의도 ]", "22.[출제의도]", "3.[출제 의도]" 모두 대응
    # ANCHOR_PATTERN = re.compile(r"(\d+)\s*\.?\s*\[\s*출제\s*의도\s*\]")
    # ANCHOR_PATTERN = re.compile(r"(\d+)\s*\.?\s*출제\s*의도")
    ANCHOR_PATTERN = re.compile(r"(\d+)\s*.*?출제\s*의도")
    
    anchors: List[Anchor] = []
    current_track_context = "common" 

    for pi in range(len(doc)):
        page = doc[pi]
        mid, _ = _page_mid_gap(page)
        
        # 1. 페이지 전체 텍스트에서 트랙 힌트 찾기 (고3용)
        page_text = page.get_text("text").replace(" ", "") # 공백 제거 후 비교
        if grade == 3:
            if "확률과통계" in page_text:
                current_track_context = "probability"
            elif "미적분" in page_text:
                current_track_context = "calculus"
            elif "기하" in page_text:
                current_track_context = "geometry"

        # 2. 블록 단위로 텍스트 탐색
        d = page.get_text("dict")
        for b in d.get("blocks", []):
            if b.get("type") != 0: continue
            for ln in b.get("lines", []):
                # span들을 합칠 때 불필요한 제어문자 제거
                line_text = "".join(sp.get("text", "") for sp in ln.get("spans", [])).strip()
                
                # 매칭 시도
                m = ANCHOR_PATTERN.search(line_text) # match 대신 search 사용 (줄 중간에 있어도 찾음)
                if not m:
                    # print(f"DEBUG: page {pi} line: {line_text}")
                    continue
                
                qnum = int(m.group(1))
                bbox = fitz.Rect(ln["bbox"])
                col = 0 if bbox.x0 < mid else 1
                
                track = "common"
                if grade == 3:
                    if qnum <= 22:
                        track = "common"
                    else:
                        # 우선 현재 페이지의 context 사용
                        track = current_track_context
                        # 만약 바로 위에 "미적분" 같은 단어가 있다면 갱신
                        clip = _column_rect(page, col)
                        t = _detect_track_above(page, bbox.y0, clip)
                        if t: track = t
                
                anchors.append(Anchor(qnum=qnum, page=pi, rect=bbox, col=col, track=track))

    # 중복 제거 및 정렬 (가끔 같은 위치가 두 번 읽히는 경우 대비)
    unique_anchors = []
    seen = set()
    for a in sorted(anchors, key=lambda x: (x.page, x.col, x.rect.y0)):
        key = (a.page, a.qnum, a.track)
        if key not in seen:
            unique_anchors.append(a)
            seen.add(key)

    anchors.sort(key=lambda a: (a.page, a.col, a.rect.y0))

    return unique_anchors


# -----------------------------
# splitting to avoid blank bands
# -----------------------------
def _text_bboxes_in_rect(page: fitz.Page, rect: fitz.Rect) -> List[fitz.Rect]:
    bbs: List[fitz.Rect] = []
    d = page.get_text("dict", clip=rect)
    for b in d.get("blocks", []):
        if b.get("type") != 0:
            continue
        for ln in b.get("lines", []):
            bb = fitz.Rect(ln["bbox"])
            bbs.append(bb)
    bbs.sort(key=lambda r: r.y0)
    return bbs


def split_rect_into_3_by_gaps(page: fitz.Page, rect: fitz.Rect, n: int = 3,
                            min_gap_px: int = 45, pad_px: int = 10) -> List[fitz.Rect]:
    """
    Split rect into n chunks, but choose split lines at large vertical whitespace gaps.
    If not enough gaps, fallback to equal split with overlap.
    """
    if n <= 1:
        return [rect]

    bbs = _text_bboxes_in_rect(page, rect)
    if len(bbs) < 2:
        return [rect]

    # compute gaps between consecutive text boxes
    gaps: List[Tuple[float, float, float]] = []  # (gap_h, y_mid, y0_end)
    prev = bbs[0]
    for cur in bbs[1:]:
        gap = cur.y0 - prev.y1
        if gap >= min_gap_px:
            gaps.append((gap, (prev.y1 + cur.y0) / 2.0, prev.y1))
        prev = cur

    if len(gaps) >= (n - 1):
        # choose biggest gaps, then order by y
        gaps_sorted = sorted(gaps, key=lambda x: x[0], reverse=True)[: (n - 1)]
        cut_ys = sorted([g[1] for g in gaps_sorted])
        # build rects
        ys = [rect.y0] + cut_ys + [rect.y1]
        out: List[fitz.Rect] = []
        for i in range(n):
            y0 = ys[i] - (pad_px if i > 0 else 0)
            y1 = ys[i + 1] + (pad_px if i < n - 1 else 0)
            r = fitz.Rect(rect.x0, y0, rect.x1, y1)
            # clamp
            r.y0 = max(rect.y0, r.y0)
            r.y1 = min(rect.y1, r.y1)
            out.append(r)
        return out

    # fallback: equal split with overlap (like your _split_vert)
    h = rect.height
    overlap = max(12, int(h * 0.02))
    step = h / n
    out = []
    for i in range(n):
        y0 = rect.y0 + step * i
        y1 = rect.y0 + step * (i + 1)
        if i > 0:
            y0 -= overlap
        if i < n - 1:
            y1 += overlap
        out.append(fitz.Rect(rect.x0, y0, rect.x1, y1))
    return out


def _tighten_to_text(page: fitz.Page, rect: fitz.Rect, pad: float = 6.0) -> Optional[fitz.Rect]:
    bbs = _text_bboxes_in_rect(page, rect)
    if not bbs:
        return None
    x0 = min(bb.x0 for bb in bbs)
    y0 = min(bb.y0 for bb in bbs)
    x1 = max(bb.x1 for bb in bbs)
    y1 = max(bb.y1 for bb in bbs)
    r = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    r.x0 = max(rect.x0, r.x0); r.y0 = max(rect.y0, r.y0)
    r.x1 = min(rect.x1, r.x1); r.y1 = min(rect.y1, r.y1)
    if r.width < 30 or r.height < 30:
        return None
    return r


# -----------------------------
# segments -> assets + text
# -----------------------------
@dataclass
class Segment:
    qnum: int
    track: str
    pieces: List[dict] # List of {'page': int, 'rect': fitz.Rect}

# 1. 페이지를 좌우로 나누어 탐색하는 로직 (예시)
def get_column_rects(page):
    width = page.rect.width
    height = page.rect.height
    left_col = fitz.Rect(0, 0, width / 2, height)
    right_col = fitz.Rect(width / 2, 0, width, height)
    return [left_col, right_col]

# 2. 이미지 병합 (두 페이지에 걸친 경우)
def merge_images(img_list):
    # PIL(Pillow)을 사용하여 이미지를 세로로 이어붙이는 로직 추가
    pass

def build_segments(doc: fitz.Document, anchors: List[Anchor]) -> List[Segment]:
    segs = []
    # 1. 앵커 정렬 (페이지 -> 단 -> 높이 순)
    anchors.sort(key=lambda a: (a.page, a.col, a.rect.y0))
    
    for i in range(len(anchors)):
        curr = anchors[i]
        nxt = anchors[i+1] if i + 1 < len(anchors) else None
        pieces = []
        
        # 2. 현재 앵커부터 다음 앵커 직전까지 모든 블록 수집
        for p_idx in range(curr.page, len(doc)):
            page = doc[p_idx]
            mid = page.rect.width / 2
            # "blocks"는 (x0, y0, x1, y1, "text", block_no, block_type) 형태
            blocks = page.get_text("blocks")
            
            for b in blocks:
                b_rect = fitz.Rect(b[:4])
                b_col = 0 if b_rect.x0 < mid else 1
                
                # [필터링 1] 현재 문항 시작점보다 위에 있는 블록은 무시
                if p_idx == curr.page:
                    if b_col < curr.col: continue
                    if b_col == curr.col and b_rect.y1 < curr.rect.y0 - 5: continue
                
                # [필터링 2] 다음 문항 시작점에 도달하면 수집 중단
                if nxt and p_idx == nxt.page:
                    if b_col > nxt.col: break
                    if b_col == nxt.col and b_rect.y0 > nxt.rect.y0 - 2:
                        break
                
                # 조건을 통과한 블록의 영역을 piece로 추가
                pieces.append({'page': p_idx, 'rect': b_rect})
            
            # 다음 앵커를 만났다면 페이지 넘기기 중단
            if nxt and p_idx >= nxt.page: break

        # 3. 수집된 블록들을 단(Column)별로 그룹화하여 최종 영역 확정
        # (이 과정이 있어야 이미지가 조각나지 않고 단 단위로 깔끔하게 합쳐집니다)
        refined_pieces = []
        if pieces:
            # 같은 페이지, 같은 단의 블록들을 하나의 Rect로 병합
            # (이 로직은 render_segment_assets가 pieces를 순회하며 이미지를 만들 때 유리합니다)
            refined_pieces = pieces # 일단은 수집된 블록 그대로 전달
            
        segs.append(Segment(qnum=curr.qnum, track=curr.track, pieces=refined_pieces))
    
    return segs

def render_segment_assets(doc, seg: Segment, output_dir: Path, dpi=150) -> List[str]:

    images = []
    for piece in seg.pieces:
        page = doc[piece['page']]
        pix = page.get_pixmap(clip=piece['rect'], dpi=dpi)
        img = Image.open(io.BytesIO(pix.tobytes()))
        images.append(img)
    
    if not images: return []

    # 세로로 합치기
    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)
    
    combined = Image.new("RGB", (max_width, total_height), (255, 255, 255))
    y_offset = 0
    for img in images:
        combined.paste(img, (0, y_offset))
        y_offset += img.height
    
    # 파일명 생성 및 저장
    out_name = f"q{seg.qnum:02d}_{seg.track}.png"
    out_path = output_dir / seg.track / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    combined.save(str(out_path))
    
    return [f"{seg.track}/{out_name}"]


def extract_segment_text(page: fitz.Page, rect: fitz.Rect) -> str:
    # "text" is okay; we only need readable Korean + some symbols.
    t = page.get_text("text", clip=rect)
    # light normalize
    t = re.sub(r"\n{3,}", "\n\n", t).strip()
    return t


def build_solution_items(pdf_path: str, meta: dict) -> Dict[str, List[dict]]:
    doc = fitz.open(pdf_path)
    grade = meta['grade']
    anchors = find_solution_anchors(doc, grade)
    segs = build_segments(doc, anchors)

    tracks_items = {}
    for seg in segs:
        # --- 수정된 부분: seg.page 대신 seg.pieces를 순회합니다 ---
        full_text = ""
        for piece in seg.pieces:
            p = doc[piece['page']]
            full_text += p.get_text("text", clip=piece['rect']) + "\n"
        item = {
            "id": f"g{grade}_{meta['year']}_{meta['month']:02d}_{seg.track}_q{seg.qnum:02d}_sol",
            "grade": grade,
            "year": meta['year'],
            "month": meta['month'],
            "kind": "solution",
            "track": seg.track,
            "qnum": seg.qnum,
            "solution_text": full_text.strip(),
            "assets": []
        }
        if seg.track not in tracks_items:
            tracks_items[seg.track] = []
        tracks_items[seg.track].append(item)
    
    doc.close()
    return tracks_items


def save_jsonl(items: List[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


# -----------------------------
# main
# -----------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_dir", type=str, default="data", help="folder containing solution PDFs")
    ap.add_argument("--out_dir", type=str, default="output", help="output root")
    ap.add_argument("--dpi", type=int, default=220)
    args = ap.parse_args()

    input_dir = Path(args.input_dir)
    out_root = Path(args.out_dir)

    pdf_paths = sorted(input_dir.rglob("*.pdf"))
    if not pdf_paths:
        print("No PDFs under:", input_dir)
        return

    for pdf_path in pdf_paths:
        filename = pdf_path.name

        # grade inference from path or filename
        parts = " ".join(pdf_path.parts)
        if "고1" in parts or "g1" in parts.lower():
            grade = 1
        elif "고2" in parts or "g2" in parts.lower():
            grade = 2
        elif "고3" in parts or "g3" in parts.lower():
            grade = 3
        else:
            # fallback: user may only run one folder per grade
            grade = 3 if "고3" in filename else 1

        meta = parse_exam_filename(filename, grade)
        if meta is None:
            print("SKIP(meta parse fail):", filename)
            continue
        if meta["kind"] != "solution":
            # this script is solution-only
            continue

        print(f"PARSING SOLUTION: {filename} (g{grade})")
        tracks_items = build_solution_items(str(pdf_path), meta)
        if not tracks_items:
            print("  -> no anchors found")
            continue

        # render assets + attach
        # assets dir: output/solutions/assets/g{grade}/{year}_{month:02d}/{track}/...
        for track, items in tracks_items.items():
            assets_dir = out_root / "solutions" / "assets" / f"g{grade}" / f"{meta['year']}_{meta['month']:02d}" / track
            doc = fitz.open(str(pdf_path))
            # recompute segments to match item order
            anchors = find_solution_anchors(doc, grade)
            segs = build_segments(doc, anchors)
            # filter segs by track, keep order
            segs_t = [s for s in segs if s.track == track]
            # Attach assets to corresponding item in order (qnum may repeat across tracks but segs_t is already track-filtered)
            for it, seg in zip(items, segs_t):
                rel_assets = render_segment_assets(doc, seg, assets_dir.parent, dpi=args.dpi)
                # We saved under assets_dir.parent/<track>/name, so rel already includes <track>/...
                base_rel = Path("assets/solutions") / f"g{grade}" / f"{meta['year']}_{meta['month']:02d}"
                it["assets"] = [str((base_rel / a).as_posix()) for a in rel_assets]
        # write jsonl per track
        for track, items in tracks_items.items():
            out_path = out_root/ "solutions" / "jsonl" / f"g{grade}" / f"{meta['year']}_{meta['month']:02d}_{track}_solution.jsonl"
            save_jsonl(items, out_path)
            print("  WRITE:", out_path)

    print("DONE")


if __name__ == "__main__":
    main()