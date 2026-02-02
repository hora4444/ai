import os
import re
import json
import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import io

# 이미지 픽셀 제한 해제
Image.MAX_IMAGE_PIXELS = None

# [출제의도]를 포함한 더 강력한 패턴
ANCHOR_PATTERN = re.compile(r"(\d+)[\.\]\s]*\[?(출제|정답|해설).*?의도.*?\]?", re.IGNORECASE)

def parse_meta(filename: str, grade: int):
    year = 2020
    m_year = re.search(r"(\d{2,4})학년도", filename)
    if m_year:
        val = m_year.group(1)
        year = int(val) if len(val) == 4 else int(val) + 2000
    m_month = re.search(r"(\d{1,2})월", filename)
    month = int(m_month.group(1)) if m_month else 3
    return {"grade": grade, "year": year, "month": month, "track": "common"}

def get_y_anchors_from_pdf(pdf_path, dpi=200):
    """해설 PDF에서 [출제의도]가 있는 Y좌표를 추출합니다."""
    doc = fitz.open(pdf_path)
    anchors = []
    current_h = 0
    scale = dpi / 72.0  # PDF 포인트 -> 픽셀 변환

    for page in doc:
        page_h = page.rect.height * scale
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4].strip()
            # 공백 제거 후 패턴 매칭 (예: [출제 의도] 대응)
            clean_text = re.sub(r'\s+', '', text)
            m = ANCHOR_PATTERN.search(clean_text)
            if m:
                qnum = int(m.group(1))
                # 앵커 정보 저장
                anchors.append({
                    "qnum": qnum, 
                    "y": current_h + (b[1] * scale)
                })
        current_h += page_h
    doc.close()
    # 문항 번호 순으로 정렬하고 중복 제거(한 문항에 여러 앵커 방지)
    seen = set()
    unique_anchors = []
    for a in sorted(anchors, key=lambda x: x['y']):
        if a['qnum'] not in seen:
            unique_anchors.append(a)
            seen.add(a['qnum'])
    return unique_anchors

def split_with_anchors(img_path, out_dir, meta, anchors):
    """추출된 앵커 좌표를 기반으로 통합 이미지를 정밀하게 자릅니다."""
    img = Image.open(img_path)
    w, h = img.size
    
    sol_assets = {}
    rel_folder = f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}"
    target_dir = out_dir / rel_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    print(f"      -> 앵커 기반 커팅 시작 (총 {len(anchors)}개 문항 감지)")
    
    for i in range(len(anchors)):
        curr = anchors[i]
        qnum = curr['qnum']
        
        # 현재 문항 시작 (약간 위쪽 여백)
        y0 = max(0, curr['y'] - 15)
        # 다음 문항 시작 전까지 자름
        y1 = anchors[i+1]['y'] - 15 if i+1 < len(anchors) else h
        
        # 이미지 크롭 및 저장
        crop = img.crop((0, y0, w, y1))
        file_name = f"q{qnum:02d}.png"
        crop.save(target_dir / file_name)
        sol_assets[qnum] = [f"{rel_folder}/{file_name}"]

    return sol_assets

def extract_question_data(pdf_path):
    doc = fitz.open(pdf_path)
    questions = {}
    current_q = None
    q_re = re.compile(r"^\s*(\d{1,2})\.") 

    for page in doc:
        lines = page.get_text("text").splitlines()
        for line in lines:
            m = q_re.match(line)
            if m:
                current_q = int(m.group(1))
                questions[current_q] = line + "\n"
            elif current_q:
                questions[current_q] += line + "\n"
    doc.close()
    return questions

def main():
    ROOT = Path("data")
    OUT = Path("output")
    OUT.mkdir(exist_ok=True)

    # 1. 고1 문제 PDF 탐색
    all_pdfs = list(ROOT.rglob("*.pdf"))
    prob_files = [p for p in all_pdfs if "해설" not in p.name and ("고1" in str(p) or "g1" in str(p).lower())]

    print(f"[*] 발견된 문제지: {len(prob_files)}개")

    for p_path in prob_files:
        meta = parse_meta(p_path.name, 1)
        print(f"\n>>> [작업 시작] {p_path.name}")
        
        # 2. 통합 이미지와 해설 PDF 쌍 찾기
        sol_img_path = None
        sol_pdf_path = None
        
        # 현재 문제 파일이 있는 폴더의 모든 파일을 뒤져서 매칭되는 해설을 찾음
        for sibling in p_path.parent.iterdir():
            if sibling.suffix.lower() in ['.pdf'] and "해설" in sibling.name:
                # 문제 파일명 앞부분이 포함되어 있는지 확인 (더 유연한 매칭)
                if p_path.stem[:10] in sibling.name: 
                    sol_pdf_path = sibling
            
            if sibling.suffix.lower() in ['.png', '.jpg', '.jpeg'] and "해설" in sibling.name:
                if p_path.stem[:10] in sibling.name:
                    sol_img_path = sibling

        # 디버깅용 로그 추가
        if not sol_img_path or not sol_pdf_path:
            print(f"      [검색결과] PDF: {sol_pdf_path.name if sol_pdf_path else '없음'}, 이미지: {sol_img_path.name if sol_img_path else '없음'}")

        if sol_img_path.exists() and sol_pdf_path.exists():
            # 앵커 좌표 추출 후 이미지 커팅
            anchors = get_y_anchors_from_pdf(sol_pdf_path)
            s_assets_map = split_with_anchors(sol_img_path, OUT, meta, anchors)
            
            # 문제 텍스트 추출
            q_text_map = extract_question_data(p_path)

            # JSONL 저장
            final_items = []
            for qnum in range(1, 31):
                final_items.append({
                    "id": f"g1_{meta['year']}_{meta['month']}_q{qnum}",
                    "question_number": qnum,
                    "question_text": q_text_map.get(qnum, "").strip(),
                    "solution_assets": s_assets_map.get(qnum, []),
                    "meta": meta
                })

            jsonl_dir = OUT / "jsonl" / "g1"
            jsonl_dir.mkdir(parents=True, exist_ok=True)
            jsonl_path = jsonl_dir / f"{meta['year']}_{meta['month']}_combined.jsonl"
            
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for it in final_items:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            print(f"      [완료] 통합 JSONL 저장됨: {jsonl_path.name}")
        else:
            print(f"      [주의] 해설 이미지 또는 PDF가 없습니다. (경로 확인 필요)")

if __name__ == "__main__":
    print("=== 스크립트 엔진 시작 ===")
    main()