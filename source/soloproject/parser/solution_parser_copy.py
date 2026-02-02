import os
import re
import json
import fitz  # PyMuPDF
from pathlib import Path
from PIL import Image
import io

# 이미지 픽셀 제한 해제
Image.MAX_IMAGE_PIXELS = None

# [출제의도]를 찾는 강력한 패턴
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
    """해설 PDF에서 각 문항의 Y축 위치(좌표)를 추출"""
    try:
        doc = fitz.open(pdf_path)
    except:
        return []
    
    anchors = []
    current_h = 0
    scale = dpi / 72.0
    for page in doc:
        page_h = page.rect.height * scale
        blocks = page.get_text("blocks")
        for b in blocks:
            text = b[4].strip()
            clean_text = re.sub(r'\s+', '', text)
            m = ANCHOR_PATTERN.search(clean_text)
            if m:
                qnum = int(m.group(1))
                anchors.append({"qnum": qnum, "y": current_h + (b[1] * scale)})
        current_h += page_h
    doc.close()
    
    # 중복 제거 및 정렬
    seen = set()
    res = []
    for a in sorted(anchors, key=lambda x: x['y']):
        if a['qnum'] not in seen:
            res.append(a)
            seen.add(a['qnum'])
    return res

def split_with_anchors(img_path, out_dir, meta, anchors):
    img = Image.open(img_path)
    w, h = img.size
    
    # 1. 비율 계산 (PDF 좌표계를 PNG 크기에 맞춤)
    # 앵커들 중 가장 마지막 앵커의 Y좌표를 기준으로 잡거나, 
    # PDF 전체 높이 정보를 가져와서 매칭해야 합니다.
    # 여기서는 간단하게 마지막 앵커가 이미지 끝 근처라고 가정하고 비율을 보정합니다.
    
    sol_assets = {}
    rel_folder = f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}"
    target_dir = out_dir / rel_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    if not anchors:
        # 앵커가 없으면 기존처럼 균등 분할
        unit = h / 30
        for i in range(1, 31):
            y0, y1 = (i-1)*unit, i*unit
            crop = img.crop((0, y0, w, y1))
            crop.save(target_dir / f"q{i:02d}.png")
            sol_assets[i] = [f"{rel_folder}/q{i:02d}.png"]
        return sol_assets

    # 2. 앵커 기반 커팅 (이미지 범위를 벗어나지 않게 철저히 계산)
    for i, curr in enumerate(anchors):
        qnum = curr['qnum']
        
        # 시작 좌표 (이미지 높이 h를 넘지 않게)
        y0 = min(max(0, curr['y'] - 15), h - 1)
        
        # 끝 좌표 (다음 앵커가 있으면 거기까지, 없으면 이미지 끝 h까지)
        if i + 1 < len(anchors):
            y1 = min(anchors[i+1]['y'] - 15, h)
        else:
            y1 = h
            
        # [SystemError 방지] y1이 y0보다 작거나 같으면 무효 (이미지 밖)
        if y1 <= y0:
            continue

        try:
            crop = img.crop((0, y0, w, y1))
            fname = f"q{qnum:02d}.png"
            crop.save(target_dir / fname)
            sol_assets[qnum] = [f"{rel_folder}/{fname}"]
        except SystemError:
            print(f"      [경고] q{qnum} 자르기 실패: 좌표 ({y0}, {y1})가 이미지 범위({h})를 벗어남")

    return sol_assets

def extract_question_data(pdf_path, out_dir, meta):
    """문제 PDF에서 텍스트와 그림 추출"""
    doc = fitz.open(pdf_path)
    questions = {}
    q_assets = {}
    current_q = None
    q_re = re.compile(r"^\s*(\d{1,2})\.") 
    
    # 그림 저장 폴더
    rel_q_folder = f"assets/questions/g{meta['grade']}/{meta['year']}_{meta['month']}"
    (out_dir / rel_q_folder).mkdir(parents=True, exist_ok=True)

    for page_num, page in enumerate(doc):
        # 1. 텍스트 추출
        lines = page.get_text("text").splitlines()
        for line in lines:
            m = q_re.match(line)
            if m:
                current_q = int(m.group(1))
                questions[current_q] = line + "\n"
                q_assets[current_q] = []
            elif current_q:
                questions[current_q] += line + "\n"
        
        # 2. 그림 추출 (간이 버전: 페이지 내 이미지를 해당 문항에 할당)
        img_list = page.get_images()
        for img_idx, img_info in enumerate(img_list):
            xref = img_info[0]
            pix = fitz.Pixmap(doc, xref)
            if current_q:
                fname = f"p{page_num}_q{current_q}_{img_idx}.png"
                pix.save(out_dir / rel_q_folder / fname)
                q_assets[current_q].append(f"{rel_q_folder}/{fname}")
            pix = None

    doc.close()
    return questions, q_assets

def main():
    ROOT = Path("data")
    OUT = Path("output")
    OUT.mkdir(exist_ok=True)

    # 문제 PDF만 수집
    prob_files = [p for p in ROOT.rglob("*.pdf") if "해설" not in p.name and "고1" in str(p)]

    for p_path in prob_files:
        meta = parse_meta(p_path.name, 1)
        print(f"\n>>> [작업 시작] {p_path.name}")

        sol_img_path = None
        sol_pdf_path = None
        
        # 1. 파일 매칭 (None으로 초기화 후 안전하게 찾기)
        for sibling in p_path.parent.iterdir():
            if "해설" in sibling.name:
                if sibling.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                    sol_img_path = sibling
                elif sibling.suffix.lower() == '.pdf':
                    sol_pdf_path = sibling

        # 2. 에러 방지용 체크 (exists 호출 전 None인지 먼저 확인)
        if sol_img_path is not None:
            print(f"      [성공] 해설 이미지 발견: {sol_img_path.name}")
            
            # 해설 PDF가 있다면 좌표(앵커)를 따고, 없으면 None 전달
            anchors = []
            if sol_pdf_path is not None:
                print(f"      [참고] 해설 PDF를 참조하여 좌표를 계산합니다.")
                anchors = get_y_anchors_from_pdf(sol_pdf_path)
            else:
                print(f"      [알림] 해설 PDF가 없어 균등 분할 모드로 작동합니다.")

            # 이미지 커팅 (여기서 해설 이미지를 자름)
            s_assets_map = split_with_anchors(sol_img_path, OUT, meta, anchors)
            
            # 문제 파일은 PDF에서 텍스트와 그림을 추출
            q_text_map, q_assets_map = extract_question_data(p_path, OUT, meta)

            # 3. 데이터 결합 및 JSONL 저장
            final_items = []
            for qnum in range(1, 31):
                final_items.append({
                    "id": f"g1_{meta['year']}_{meta['month']}_q{qnum}",
                    "question_number": qnum,
                    "question_text": q_text_map.get(qnum, "").strip(),
                    "question_assets": q_assets_map.get(qnum, []),
                    "solution_assets": s_assets_map.get(qnum, []), # 자른 이미지 경로
                    "meta": meta
                })

            # 저장 로직
            jsonl_dir = OUT / "jsonl" / "g1"
            jsonl_dir.mkdir(parents=True, exist_ok=True)
            jsonl_path = jsonl_dir / f"{meta['year']}_{meta['month']}_combined.jsonl"
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for it in final_items:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
            print(f"      [완료] {jsonl_path.name} 저장됨")
        else:
            print(f"      [실패] 해설 이미지({p_path.stem}해설.png)가 없어 건너뜁니다.")

if __name__ == "__main__":
    main()