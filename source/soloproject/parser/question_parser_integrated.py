import os
import fitz
import re
import json
import ollama
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm
import base64
import time
from PIL import Image, ImageOps
import pytesseract
from pytesseract import Output

MODEL_NAME = "qwen3-vl:4b" 
ROOT = Path("data")
OUT_ROOT = Path("output")

# Tesseract 경로 설정 (반드시 설치 경로 확인!)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def parse_exam_filename(filename: str, grade):
    year = None
    m_year = re.search(r"(\d{2})학년도", filename)
    if m_year:
        year = int(m_year.group(1)) + 2000
    else:
        m_year = re.search(r"(20\d{2})년", filename)
        if m_year:
            year = int(m_year.group(1))
    if year is None: return None

    m_month = re.search(r"(\d{1,2})월", filename)
    month = int(m_month.group(1)) if m_month else (11 if "수능" in filename else None)
    if month is None: return None

    track = "common" if grade < 3 else "unknown"
    return {"year": year, "month": month, "track": track}

def ask_ollama_vision(img_path):
    """자른 문제 이미지를 기반으로 텍스트 정제"""
    try:
        with open(img_path, 'rb') as f:
            img_bytes = f.read()
        
        res = ollama.chat(
            model=MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': '이 이미지에서 수학 문제를 추출해서 LaTeX 형식으로 깔끔하게 텍스트만 출력해줘.',
                'images': [img_bytes]
            }]
        )
        return res['message']['content']
    except Exception as e:
        return f"Error: {str(e)}"

def extract_questions_from_pdf(pdf_path, meta, grade):
    doc = fitz.open(pdf_path)
    assets_by_q = defaultdict(list)
    
    # 문항 번호 패턴 (1. 또는 1)
    qnum_re = re.compile(r'^(\d{1,2})[\s\.]*$')

    for pno in range(len(doc)):
        page = doc[pno]
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # 1. Tesseract로 텍스트 위치(좌표) 스캔
        d = pytesseract.image_to_data(img, lang='kor+eng', output_type=Output.DICT)
        anchors = []
        n_boxes = len(d['text'])
        for i in range(n_boxes):
            text = d['text'][i].strip()
            if qnum_re.match(text):
                anchors.append({
                    'qnum': int(qnum_re.match(text).group(1)),
                    'top': d['top'][i],
                    'left': d['left'][i]
                })
        
        # Y축 좌표 기준 정렬
        anchors = sorted(anchors, key=lambda x: x['top'])
        
        # 2. 앵커 좌표를 바탕으로 이미지 자르기 및 LLM 요청
        for i, anchor in enumerate(anchors):
            qnum = anchor['qnum']
            y_start = max(0, anchor['top'] - 40) # 번호 위로 약간 여유
            
            # 다음 문항이 있으면 거기까지, 없으면 페이지 끝까지
            if i < len(anchors) - 1:
                y_end = anchors[i+1]['top'] - 10
            else:
                y_end = img.height

            # [수정] 최소 높이 보장 (Factor 32 에러 방지)
            if y_end - y_start < 64: # 최소 64픽셀은 확보
                y_end = y_start + 64
            
            # 이미지 자르기 (좌우는 전체 사용 혹은 2단 분할 로직 적용 가능)
            mid_x = img.width // 2
            if anchor['left'] < mid_x:
                # 왼쪽 단 문제
                crop_img = img.crop((0, y_start, mid_x + 50, y_end))
            else:
                # 오른쪽 단 문제
                crop_img = img.crop((mid_x - 50, y_start, img.width, y_end))
            
            # [추가] 리사이즈 (가로가 너무 길면 모델이 힘들어함)
            if crop_img.width > 1200:
                new_h = int(crop_img.height * (1200 / crop_img.width))
                crop_img = crop_img.resize((1200, new_h), Image.Resampling.LANCZOS)
            # 파일 저장
            q_folder = OUT_ROOT / "assets" / "questions" / f"g{grade}" / f"{meta['year']}_{meta['month']}"
            q_folder.mkdir(parents=True, exist_ok=True)
            img_path = q_folder / f"p{pno+1}_q{qnum:02d}.png"
            crop_img.save(img_path)
            
            # 3. LLM에게 자른 이미지만 전달 (속도 향상의 핵심!)
            print(f"   - Processing Q{qnum} (Page {pno+1})...", end="\r")
            content = ask_ollama_vision(img_path)
            
            assets_by_q[qnum].append({
                "type": "question",
                "path": str(img_path).replace("\\", "/"),
                "page": pno + 1,
                "text_llm": content
            })

    doc.close()
    return assets_by_q

if __name__ == "__main__":
    pdf_paths = sorted({p.resolve() for p in ROOT.rglob("*.pdf") if "해설" not in p.name})
    for pdf_path in pdf_paths:
        # 경로에서 학년 추출 (고1, 고2 등)
        grade = None
        if "고1" in str(pdf_path): grade = 1
        elif "고2" in str(pdf_path): grade = 2
        elif "고3" in str(pdf_path): grade = 3
        
        if not grade: continue
        
        meta = parse_exam_filename(pdf_path.name, grade)
        if not meta: continue
        
        print(f"\n🚀 시작: {pdf_path.name} (학년: {grade})")
        q_assets = extract_questions_from_pdf(pdf_path, meta, grade)
        
        # JSONL 저장
        out_path = OUT_ROOT / "jsonl" / "questions" / f"g{grade}" / f"{meta['year']}_{meta['month']}_q.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            for qnum in sorted(q_assets.keys()):
                row = {
                    "id": f"g{grade}_{meta['year']}_{meta['month']}_q{qnum:02d}",
                    "question_number": qnum,
                    "assets": q_assets[qnum]
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n✅ 완료: {out_path}")