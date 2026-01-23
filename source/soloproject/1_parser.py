import os
import fitz
import re
import json
from pathlib import Path
from collections import defaultdict

def parse_exam_filename(filename: str, grade):
    # 시작시 초기화
    year = None

    m_year = re.search(r"(\d{2})학년도", filename)
    if m_year:
        year = int(m_year.group(1)) + 2000
    else:
        m_year = re.search(r"(20\d{2})년", filename)
        if m_year:
            year = int(m_year.group(1))
    if year is None:
        return None

    m_month = re.search(r"(\d{1,2})월", filename)
    if m_month:
        month = int(m_month.group(1))
    else:
        # 3) 월이 없으면(예: 수능) 규칙 부여
        if "수능" in filename:
            month = 11   # 수능은 보통 11월로 통일
        else:
            return None

    if grade < 3:
        track = "common"
    else:
        if "미적분" in filename:
            track = "calculus"
        elif "기하" in filename:
            track = "geometry"
        elif "확률과통계" in filename:
            track = "probability"
        else:
            track = "common"

    return {
        "grade": grade,
        "year": year,
        "month": month,
        "track": track
    }

QUESTION_RE = re.compile(r"^\s*(\d{1,2})\.")

def extract_questions(pdf_path):
    doc = fitz.open(pdf_path)
    questions = {}
    current_q = None

    try:
        for page in doc:
            lines = page.get_text("text").splitlines()
            for line in lines:
                m = QUESTION_RE.match(line)
                if m:
                    qnum = int(m.group(1))
                    current_q = qnum
                    questions[current_q] = line + "\n"
                elif current_q:
                    questions[current_q] += line + "\n"

        return questions
    finally:
        doc.close()


def build_items(pdf_path, filename, grade, kind):
    meta = parse_exam_filename(filename, grade)
    if meta is None:
        return []
    questions = extract_questions(pdf_path)

    # 파일별 폴더 생성(충돌 방지)
    is_solution = (kind == "solution")
    safe_name = filename.replace(".pdf", "")
    assets_dir = Path("output") / "assets" / f"g{grade}"/ safe_name
    assets_by_q = render_exam_images(pdf_path, assets_dir, dpi=200, kind=kind)

    items = []
    is_common_fn = (lambda q: True) if grade <= 2 else (lambda q: q <= 22)

    for qnum, text in questions.items():
        stem, choices = split_choices(text)
        item = {
            "id": f"g{grade}_{meta['year']}_{meta['month']}_{meta['track']}_q{qnum}",
            **meta,
            "kind": kind,
            "question_number": qnum,
            "is_common": is_common_fn(qnum),
            "question_text": stem,
            "choices": choices,
            "assets": assets_by_q.get(qnum, []),
            "question_assets": [],   
            "solution_assets": [],   
        }
        if is_solution:
            item["solution_assets"] = assets_by_q.get(qnum, [])
        else:
            item["question_assets"] = assets_by_q.get(qnum, [])

        items.append(item)

    return items

CHOICE_RE = re.compile(r"(①|②|③|④|⑤)")

def split_choices(text: str):
    """
    returns: (stem, choices_list)
    - stem: 보기 제외한 문제 본문
    - choices_list: ["① ...", "② ...", ...] (없으면 [])
    """
    parts = CHOICE_RE.split(text)
    if len(parts) <= 1:
        return text.strip(), []

    stem = parts[0].strip()
    choices = []
    # parts 구조: [stem, "①", "...", "②", "...", ...]
    for i in range(1, len(parts)-1, 2):
        mark = parts[i]
        body = parts[i+1].strip()
        choices.append(f"{mark} {body}")
    return stem, choices

def save_jsonl(items, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

QNO_RE = re.compile(r"^\s*(\d{1,2})\.\s*$|^\s*(\d{1,2})\.")

def find_question_anchors(doc: fitz.Document):
    anchors = []
    for pno in range(len(doc)):
        page = doc[pno]
        d = page.get_text("dict")

        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                line_text = "".join(
                    span.get("text", "") for span in line.get("spans", [])
                ).strip()

                m = QNO_RE.match(line_text)
                if not m:
                    continue

                qnum = int(m.group(1) or m.group(2))
                x0 = line["bbox"][0]
                y0 = line["bbox"][1]

                anchors.append({
                    "qnum": qnum,
                    "page": pno,
                    "x0": x0,
                    "y0": y0
                })

    anchors.sort(key=lambda a: (a["page"], a["y0"], a["x0"]))
    return anchors

def detect_columns_by_text_blocks(page: fitz.Page, *, content_top=90, content_bottom_margin=90):

    """
    return list of (x_left, x_right) sorted by x_left
    - blocks 기반으로 x0 클러스터를 gap으로 나눠서 2~3컬럼 추정
    """
    w = page.rect.width
    h = page.rect.height
    y_min = content_top
    y_max = h - content_bottom_margin

    blocks = page.get_text("blocks")  # (x0, y0, x1, y1, "text", block_no, block_type)
    xs = []
    for (x0, y0, x1, y1, text, *_rest) in blocks:
        if y1 < y_min or y0 > y_max:
            continue
        if not text or not text.strip():
            continue
        bw = x1 - x0
        bh = y1 - y0
        # 너무 작은 조각/페이지번호 같은 잡음 제거
        if bw < 60 or bh < 10:
            continue
        xs.append(x0)

    if not xs:
        # fallback: 2컬럼 가정
        mid = w / 2
        return [(0, mid), (mid, w)]

    xs_sorted = sorted(xs)

    # x0들 사이 큰 gap 찾기 (컬럼 경계 후보)
    gaps = []
    for a, b in zip(xs_sorted, xs_sorted[1:]):
        gaps.append((b - a, (a + b) / 2))

    # "큰 gap"만 경계로 채택 (경험적으로 12~18% 폭 이상이 잘 먹힘)
    threshold = w * 0.14
    cuts = [pos for (gap, pos) in gaps if gap >= threshold]

    # 경계가 너무 많으면 큰 것 2개만 (최대 3컬럼까지)
    cuts = sorted(cuts)
    if len(cuts) > 2:
        # gap 큰 순으로 2개 선택
        cuts2 = sorted(gaps, key=lambda x: x[0], reverse=True)[:2]
        cuts = sorted([pos for _, pos in cuts2])

    # cuts로 컬럼 구간 생성
    boundaries = [0.0] + cuts + [w]
    cols = [(boundaries[i], boundaries[i+1]) for i in range(len(boundaries)-1)]

    # 너무 좁은 컬럼 제거(오검출 방지)
    cols = [c for c in cols if (c[1] - c[0]) >= w * 0.18] or cols

    return cols

def build_solution_segments_reading_order(
    doc,
    anchors,
    *,
    pad=10,
    content_top=120,
    content_bottom_margin=120,
):
    """
    해설용: '읽기 순서' (page 0: left -> right, page1: left -> right, ...)
    로 다음 앵커까지 이어서 rect들을 만든다.
    returns: dict[qnum] -> list[(pno, rect)]
    """
    from collections import defaultdict

    def col_idx(pr, x0):
        return 0 if x0 < pr.width / 2 else 1

    def col_rect(pr, col, top, bottom):
        top = max(top, content_top)
        bottom = min(bottom, pr.height - content_bottom_margin)
        mid = pr.width / 2
        overlap = pr.width * 0.02
        if col == 0:
            return fitz.Rect(0, top, mid+overlap, bottom)
        else:
            return fitz.Rect(mid-overlap, top, pr.width, bottom)

    def next_block(p, c):
        # (p,0)->(p,1)->(p+1,0)
        if c == 0:
            return (p, 1)
        return (p + 1, 0)

    # anchors에 col 부여 + 읽기 순서로 정렬
    anchors2 = []
    for a in anchors:
        pr = doc[a["page"]].rect
        anchors2.append({**a, "col": col_idx(pr, a["x0"])})
    anchors2.sort(key=lambda x: (x["page"], x["col"], x["y0"]))

    segs = defaultdict(list)

    for i, a in enumerate(anchors2):
        qnum = a["qnum"]
        p0 = a["page"]
        c0 = a["col"]
        y0 = a["y0"]

        page0 = doc[p0]
        pr0 = page0.rect
        top0 = max(y0 - pad, content_top)
        bottom_limit0 = pr0.height - content_bottom_margin

        # 다음 앵커 (없으면 문서 끝까지)
        b = anchors2[i + 1] if (i + 1 < len(anchors2)) else None

        if b is None:
            # 마지막: 현재 블록 끝까지
            segs[qnum].append((p0, (col_rect(pr0, c0, top0, bottom_limit0) & pr0)))
            # 이후 블록들(다른 컬럼/다음페이지)도 끝까지 붙이고 싶으면 여기서 확장 가능
            continue

        p1, c1 = b["page"], b["col"]
        y1 = b["y0"]

        # 같은 page/col이면 단순 컷
        if p0 == p1 and c0 == c1:
            bottom = min(max(y1 - pad, content_top), bottom_limit0)
            segs[qnum].append((p0, (col_rect(pr0, c0, top0, bottom) & pr0)))
            continue

        # 1) 시작 블록: top0 -> bottom_limit0
        segs[qnum].append((p0, (col_rect(pr0, c0, top0, bottom_limit0) & pr0)))

        # 2) 중간 블록들: (p0,c0)의 다음 블록부터 (p1,c1) 직전까지 full
        cur_p, cur_c = next_block(p0, c0)
        while (cur_p, cur_c) != (p1, c1) and cur_p < len(doc):
            pr = doc[cur_p].rect
            bottom_limit = pr.height - content_bottom_margin
            segs[qnum].append((cur_p, (col_rect(pr, cur_c, content_top, bottom_limit) & pr)))
            cur_p, cur_c = next_block(cur_p, cur_c)

        # 3) 마지막 블록(다음 앵커가 있는 블록): content_top -> next_y
        if p1 < len(doc):
            pr_last = doc[p1].rect
            bottom_limit_last = pr_last.height - content_bottom_margin
            bottom_last = min(max(y1 - pad, content_top), bottom_limit_last)
            segs[qnum].append((p1, (col_rect(pr_last, c1, content_top, bottom_last) & pr_last)))

    return segs

def build_question_segments(doc, anchors, column_mode="auto", pad=6, content_top=90, content_bottom_margin=90):
    from collections import defaultdict
    segs = defaultdict(list)

    def pick_col_from_cols(cols, x0):
        for (l, r) in cols:
            if l <= x0 < r:
                return (l, r)
        return min(cols, key=lambda c: abs((c[0] + c[1]) / 2 - x0))

    def col_rect_auto(pno, top, bottom, x0):
        page = doc[pno]
        pr = page.rect
        top = max(top, content_top)
        bottom = min(bottom, pr.height - content_bottom_margin)

        cols = detect_columns_by_text_blocks(page, content_top=content_top, content_bottom_margin=content_bottom_margin)
        l, r = pick_col_from_cols(cols, x0)
        return fitz.Rect(l, top, r, bottom)

    def col_rect_fixed(pno, top, bottom, x0):
        page = doc[pno]
        pr = page.rect
        top = max(top, content_top)
        bottom = min(bottom, pr.height - content_bottom_margin)

        w = pr.width
        mid = w / 2
        if x0 < mid:
            return fitz.Rect(0, top, mid, bottom)
        else:
            return fitz.Rect(mid, top, w, bottom)

    def make_rect(pno, top, bottom, x0):
        if column_mode == "auto":
            return col_rect_auto(pno, top, bottom, x0)
        else:
            return col_rect_fixed(pno, top, bottom, x0)

    def is_left(pno_local, x0_local):
        w = doc[pno_local].rect.width
        return x0_local < (w / 2)

    for i, a in enumerate(anchors):
        qnum = a["qnum"]
        pno = a["page"]
        x0 = a["x0"]

        page_h = doc[pno].rect.height
        content_bottom = page_h - content_bottom_margin

        y0 = max(a["y0"] - pad, content_top)
        cur_left = is_left(pno, x0)

        next_pno = pno
        next_y0 = content_bottom

        for j in range(i + 1, len(anchors)):
            b = anchors[j]
            bp = b["page"]
            bx0 = b["x0"]
            by0 = max(b["y0"] - pad, content_top)

            if bp != pno:
                next_pno = bp
                next_y0 = by0
                break

            if is_left(pno, bx0) == cur_left:
                next_pno = bp
                next_y0 = by0
                break

        next_y0 = min(next_y0, doc[next_pno].rect.height - content_bottom_margin)

        if next_pno == pno:
            rect = make_rect(pno, y0, next_y0, x0)
            segs[qnum].append((pno, rect))
        else:
            rect0 = make_rect(pno, y0, content_bottom, x0)
            segs[qnum].append((pno, rect0))

            for mid_p in range(pno + 1, next_pno):
                mid_h = doc[mid_p].rect.height
                rect_mid = make_rect(mid_p, content_top, mid_h - content_bottom_margin, x0)
                segs[qnum].append((mid_p, rect_mid))

            rect_last = make_rect(next_pno, content_top, next_y0, x0)
            segs[qnum].append((next_pno, rect_last))

    return segs

def _is_valid_rect(rect: fitz.Rect, min_size: float = 5.0) -> bool:
    # Rect 자체가 깨지거나(역전/0), 너무 작으면 저장할 의미가 없으니 스킵
    if rect is None:
        return False
    if rect.x0 >= rect.x1 or rect.y0 >= rect.y1:
        return False
    if rect.width <= min_size or rect.height <= min_size:
        return False
    return True

QNO_RE_SOL = re.compile(r"^\s*(\d{1,2})\.\s*(?:\[[^\]]+\])?")

def find_solution_anchors(doc: fitz.Document):
    anchors = []
    for pno in range(len(doc)):
        page = doc[pno]
        d = page.get_text("dict")
        for block in d.get("blocks", []):
            for line in block.get("lines", []):
                line_text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
                m = QNO_RE_SOL.match(line_text)
                if not m:
                    continue
                qnum = int(m.group(1))
                x0 = line["bbox"][0]
                y0 = line["bbox"][1]
                anchors.append({"qnum": qnum, "page": pno, "x0": x0, "y0": y0})
    return anchors

def _pick_col_index(cols, x0: float) -> int:
    """cols: [(l,r), ...] 중 x0가 속한 컬럼 인덱스 반환"""
    for i, (l, r) in enumerate(cols):
        if l <= x0 < r:
            return i
    # fallback: 가장 가까운 컬럼
    return min(range(len(cols)), key=lambda i: abs(((cols[i][0] + cols[i][1]) / 2) - x0))

def _col_rect_from_cols(cols, col_idx: int, top: float, bottom: float) -> fitz.Rect:
    l, r = cols[col_idx]
    return fitz.Rect(l, top, r, bottom)

def _split_rect_vertical(rect: fitz.Rect, n: int = 3, overlap_ratio: float = 0.02) -> list[fitz.Rect]:
    """
    rect를 세로로 n등분하되, 각 조각 사이에 overlap을 줘서 줄 단위 누락 방지
    overlap_ratio: 각 조각 높이 대비 겹침 비율
    """
    if n <= 1:
        return [rect]

    h = rect.height
    if h <= 0:
        return []

    chunk = h / n
    overlap = chunk * overlap_ratio

    out = []
    for i in range(n):
        y0 = rect.y0 + i * chunk
        y1 = rect.y0 + (i + 1) * chunk

        # overlap 적용
        if i > 0:
            y0 -= overlap
        if i < n - 1:
            y1 += overlap

        rr = fitz.Rect(rect.x0, y0, rect.x1, y1)
        out.append(rr)

    return out

def detect_columns_by_text_blocks(page: fitz.Page, *, content_top=120, content_bottom_margin=120):
    """
    페이지의 텍스트 블록 분포로 컬럼 경계를 추정.
    반환: [(left, right), ...]
    - 기본은 2컬럼을 기대하지만, 못 잡으면 1컬럼으로 fallback.
    """
    pr = page.rect
    w = pr.width
    bottom = pr.height - content_bottom_margin

    blocks = page.get_text("blocks")  # (x0,y0,x1,y1, text, block_no, block_type)
    xs = []
    for b in blocks:
        x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
        if y1 < content_top or y0 > bottom:
            continue
        # 너무 작은 블록(번호/페이지 등) 노이즈 제외
        if (x1 - x0) < 20 or (y1 - y0) < 10:
            continue
        xs.append((x0, x1))

    if not xs:
        return [(0, w)]

    # x0의 중앙값 기준으로 좌/우 컬럼 분리 시도
    mids = [((a + b) / 2) for a, b in xs]
    mid_global = sorted(mids)[len(mids) // 2]

    left_blocks = [x for x in xs if ((x[0] + x[1]) / 2) < mid_global]
    right_blocks = [x for x in xs if ((x[0] + x[1]) / 2) >= mid_global]

    # 한쪽이 거의 비면 1컬럼 처리
    if len(left_blocks) < 5 or len(right_blocks) < 5:
        return [(0, w)]

    left_l = min(x0 for x0, _ in left_blocks)
    left_r = max(x1 for _, x1 in left_blocks)
    right_l = min(x0 for x0, _ in right_blocks)
    right_r = max(x1 for _, x1 in right_blocks)

    # 컬럼 사이 갭이 너무 작으면 1컬럼 처리
    if right_l - left_r < 10:
        return [(0, w)]

    # 너무 바깥 여백까지 먹지 않도록 살짝 클램프
    left_l = max(0, left_l)
    right_r = min(w, right_r)

    return [(left_l, left_r), (right_l, right_r)]


def build_solution_segments_flow(
    doc: fitz.Document,
    anchors: list[dict],
    *,
    pad: int = 12,
    content_top: int = 140,
    content_bottom_margin: int = 140,
    split_n: int = 3,               # ✅ 무조건 3분할
    split_overlap_ratio: float = 0.02
):
    """
    해설(솔루션) 전용:
    - detect_columns_by_text_blocks(page)로 컬럼을 잡고
    - (page, col_idx, y0) 순서로 읽기 흐름 정렬
    - a(현재 앵커) -> b(다음 앵커) 사이를 'flow'로 모두 rect로 쌓음
    - 마지막에 rect가 길면 3분할해서 저장 (누락 방지)
    """
    segs = defaultdict(list)

    # page별 컬럼 캐시
    cols_cache = {}

    def get_cols(pno: int):
        if pno in cols_cache:
            return cols_cache[pno]
        page = doc[pno]
        cols = detect_columns_by_text_blocks(
            page,
            content_top=content_top,
            content_bottom_margin=content_bottom_margin
        )
        cols_cache[pno] = cols
        return cols

    # 1) anchors에 col_idx를 붙여서 flow 정렬
    anchors2 = []
    for a in anchors:
        pno = a["page"]
        cols = get_cols(pno)
        col_idx = _pick_col_index(cols, a["x0"])
        anchors2.append({**a, "col": col_idx})

    anchors2.sort(key=lambda a: (a["page"], a["col"], a["y0"]))

    # 2) a->b 구간을 flow로 rect 생성
    for i, a in enumerate(anchors2):
        qnum = a["qnum"]
        p0 = a["page"]
        col0 = a["col"]

        page0 = doc[p0]
        pr0 = page0.rect
        bottom0 = pr0.height - content_bottom_margin

        cols0 = get_cols(p0)

        top_a = max(a["y0"] - pad, content_top)

        b = anchors2[i + 1] if (i + 1) < len(anchors2) else None

        if b is None:
            # 문서 끝까지: p0부터 마지막까지 전부 flow로
            # (1) 시작 페이지: 현재 col의 top_a~bottom, 이후 col들 전부
            rect = _col_rect_from_cols(cols0, col0, top_a, bottom0) & pr0
            if rect.height > 1 and rect.width > 1:
                for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                    segs[qnum].append((p0, rr & pr0))

            for c in range(col0 + 1, len(cols0)):
                rect = _col_rect_from_cols(cols0, c, content_top, bottom0) & pr0
                if rect.height > 1 and rect.width > 1:
                    for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                        segs[qnum].append((p0, rr & pr0))

            # (2) 이후 페이지들: 모든 컬럼 전체
            for p in range(p0 + 1, len(doc)):
                page = doc[p]
                pr = page.rect
                bottom = pr.height - content_bottom_margin
                cols = get_cols(p)
                for c in range(len(cols)):
                    rect = _col_rect_from_cols(cols, c, content_top, bottom) & pr
                    if rect.height > 1 and rect.width > 1:
                        for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                            segs[qnum].append((p, rr & pr))
            continue

        # b가 있는 경우: a -> b 직전까지
        p1 = b["page"]
        col1 = b["col"]

        # --- 같은 페이지 & 같은 컬럼 ---
        if p1 == p0 and col1 == col0:
            bottom_a = min(max(b["y0"] - pad, content_top), bottom0)
            rect = _col_rect_from_cols(cols0, col0, top_a, bottom_a) & pr0
            if rect.height > 1 and rect.width > 1:
                for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                    segs[qnum].append((p0, rr & pr0))
            continue

        # --- 같은 페이지지만 다른 컬럼 (왼->오른쪽 흐름) ---
        if p1 == p0 and col1 != col0:
            # (1) 현재 컬럼: top_a ~ bottom
            rect0 = _col_rect_from_cols(cols0, col0, top_a, bottom0) & pr0
            if rect0.height > 1 and rect0.width > 1:
                for rr in _split_rect_vertical(rect0, n=split_n, overlap_ratio=split_overlap_ratio):
                    segs[qnum].append((p0, rr & pr0))

            # (2) 다음 컬럼(col1): content_top ~ b.y0-pad
            bottom_b = min(max(b["y0"] - pad, content_top), bottom0)
            rect1 = _col_rect_from_cols(cols0, col1, content_top, bottom_b) & pr0
            if rect1.height > 1 and rect1.width > 1:
                for rr in _split_rect_vertical(rect1, n=split_n, overlap_ratio=split_overlap_ratio):
                    segs[qnum].append((p0, rr & pr0))
            continue

        # --- 페이지가 넘어가는 경우: p0 -> ... -> p1 ---
        # (1) 시작 페이지 p0:
        #   - 현재 col0: top_a~bottom
        rect0 = _col_rect_from_cols(cols0, col0, top_a, bottom0) & pr0
        if rect0.height > 1 and rect0.width > 1:
            for rr in _split_rect_vertical(rect0, n=split_n, overlap_ratio=split_overlap_ratio):
                segs[qnum].append((p0, rr & pr0))

        #   - 같은 페이지의 이후 컬럼들(col0+1..끝): 전체
        for c in range(col0 + 1, len(cols0)):
            rect = _col_rect_from_cols(cols0, c, content_top, bottom0) & pr0
            if rect.height > 1 and rect.width > 1:
                for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                    segs[qnum].append((p0, rr & pr0))

        # (2) 중간 페이지들: 모든 컬럼 전체
        for p in range(p0 + 1, p1):
            page = doc[p]
            pr = page.rect
            bottom = pr.height - content_bottom_margin
            cols = get_cols(p)
            for c in range(len(cols)):
                rect = _col_rect_from_cols(cols, c, content_top, bottom) & pr
                if rect.height > 1 and rect.width > 1:
                    for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                        segs[qnum].append((p, rr & pr))

        # (3) 마지막 페이지 p1:
        page_last = doc[p1]
        pr_last = page_last.rect
        bottom_last = pr_last.height - content_bottom_margin
        cols_last = get_cols(p1)

        #   - b의 컬럼(col1)보다 "앞" 컬럼들은 full
        for c in range(0, col1):
            rect = _col_rect_from_cols(cols_last, c, content_top, bottom_last) & pr_last
            if rect.height > 1 and rect.width > 1:
                for rr in _split_rect_vertical(rect, n=split_n, overlap_ratio=split_overlap_ratio):
                    segs[qnum].append((p1, rr & pr_last))

        #   - b의 컬럼(col1): content_top ~ b.y0-pad
        bottom_b = min(max(b["y0"] - pad, content_top), bottom_last)
        rect_end = _col_rect_from_cols(cols_last, col1, content_top, bottom_b) & pr_last
        if rect_end.height > 1 and rect_end.width > 1:
            for rr in _split_rect_vertical(rect_end, n=split_n, overlap_ratio=split_overlap_ratio):
                segs[qnum].append((p1, rr & pr_last))

    return segs

def render_question_images(pdf_path: str, out_dir: Path, *, dpi: int = 200):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)

    anchors = find_question_anchors(doc)
    if not anchors:
        doc.close()
        return {}

    segs = build_question_segments(
        doc, anchors,
        column_mode="fixed",
        pad=6,
        content_top=90,
        content_bottom_margin=90,
    )

    assets_by_q = {}
    asset_type = "question_image"

    for qnum, rects in segs.items():
        assets = []
        for idx, (pno, rect) in enumerate(rects, start=1):
            page = doc[pno]
            rect = rect & page.rect
            if not _is_valid_rect(rect):
                continue
            pix = page.get_pixmap(clip=rect, dpi=dpi)
            if pix.width <= 0 or pix.height <= 0:
                continue

            img_path = out_dir / f"{asset_type}_q{qnum:02d}_p{pno+1}_{idx}.png"
            pix.save(str(img_path))
            assets.append({"type": asset_type, "path": str(img_path).replace("\\", "/"), "page": pno + 1})

        assets_by_q[qnum] = assets

    doc.close()
    return assets_by_q

def render_solution_images(pdf_path: str, out_dir: Path, *, dpi: int = 200):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)

    anchors = find_solution_anchors(doc)
    if not anchors:
        doc.close()
        return {}

    # segs = build_solution_segments_reading_order(
    #     doc, anchors,
    #     pad=10,
    #     content_top=120,
    #     content_bottom_margin=120,
    # )

    segs = build_solution_segments_3col_fixed(
    doc, anchors,
    pad=12,
    content_top=140,
    content_bottom_margin=140,
    col_fracs=(5/12, 4/12, 3/12),
    overlap_px=20,
    )

    assets_by_q = {}
    asset_type = "solution_image"

    for qnum, rects in segs.items():
        assets = []
        for idx, (pno, rect) in enumerate(rects, start=1):
            page = doc[pno]
            rect = rect & page.rect
            if not _is_valid_rect(rect):
                continue
            pix = page.get_pixmap(clip=rect, dpi=dpi)
            if pix.width <= 0 or pix.height <= 0:
                continue

            img_path = out_dir / f"{asset_type}_q{qnum:02d}_p{pno+1}_{idx}.png"
            pix.save(str(img_path))
            assets.append({"type": asset_type, "path": str(img_path).replace("\\", "/"), "page": pno + 1})

        assets_by_q[qnum] = assets

    doc.close()
    return assets_by_q

def render_exam_images(pdf_path: str, out_dir: Path, *, dpi: int = 200, kind: str = "question"):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print(f"[render_exam_images] open failed: {e}")
        return {}

    try:
        # ... anchors/segs 구성 ...
        if not anchors:
            doc.close()
            return {}

        assets_by_q = {}

        for qnum, rects in segs.items():
            assets = []
            for idx, (pno, rect) in enumerate(rects, start=1):
                page = doc[pno]
                rect = rect & page.rect
                if not _is_valid_rect(rect):
                    continue
                pix = page.get_pixmap(clip=rect, dpi=dpi)
                if pix.width <= 0 or pix.height <= 0:
                    continue

                img_path = out_dir / f"{asset_type}_q{qnum:02d}_p{pno+1}_{idx}.png"
                pix.save(str(img_path))
                assets.append({"type": asset_type, "path": str(img_path).replace("\\", "/"), "page": pno + 1})

            assets_by_q[qnum] = assets

        doc.close()
        return assets_by_q

    except Exception as e:
        print(f"[render_exam_images] failed: {e}")
        try:
            doc.close()
        except:
            pass
        return {}


ROOT = Path("data")

pdf_paths = sorted({p.resolve() for p in ROOT.rglob("*.pdf")})  # set으로 중복 제거

print("CWD:", os.getcwd())
for pdf_path in pdf_paths:
    filename = pdf_path.name

    if "고1" in pdf_path.parts:
        grade = 1
    elif "고2" in pdf_path.parts:
        grade = 2
    elif "고3" in pdf_path.parts:
        grade = 3
    else:
        print("SKIP(no grade):", pdf_path)
        continue

    is_solution = ("해설" in filename)
    kind = "solution" if is_solution else "question"

    print("PARSING:", filename, grade)

    meta = parse_exam_filename(filename, grade)
    if meta is None:
        print("  -> SKIP(meta parse fail)")
        continue

    items = build_items(str(pdf_path), filename, grade, kind)
    out_path = Path("output") / "jsonl" / f"g{grade}" / f"{meta['year']}_{meta['month']}_{meta['track']}_{kind}.jsonl"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_jsonl(items, out_path)

    print("WRITE TO:", os.path.abspath(out_path))

    print(f"  -> {len(items)} questions parsed")