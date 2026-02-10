import re
import os
import json
import numpy as np
import time
from pathlib import Path
import ollama
import cv2
from PIL import Image, ImageOps
from tqdm import tqdm

# 상수 설정
MODEL_NAME = "qwen3-vl:4b"
ROOT = Path("data")
OUT_ROOT = Path("output")
Image.MAX_IMAGE_PIXELS = None

def ask_ollama_vision(img_path):
    """이미지 바이너리를 읽어 Ollama에 전달 (LaTeX 정제 요청)"""
    try:
        with open(img_path, 'rb') as f:
            img_data = f.read()
        res = ollama.chat(
            model=MODEL_NAME,
            messages=[{
                'role': 'user',
                'content': ("이 수학 문제 이미지의 내용을 그대로 텍스트로 변환해줘. "
                            "한글 본문은 빠짐없이 적고, 수식은 반드시 LaTeX($$ 또는 $)로 감싸줘. "),
                'images': [img_data]
            }]
        )
        return res['message']['content']
    except Exception as e:
        print(f"\n[Ollama Error] {e}")
        return ""

def split_solution_png_by_anchors(png_path, meta, anchors):
    """앵커(문제번호 위치)를 기준으로 전체 해설 이미지를 문항별로 자름"""
    pil_img = Image.open(png_path)
    w, h = pil_img.size
    
    # 앵커를 y좌표 기준으로 정렬
    anchors_sorted = sorted(anchors, key=lambda x: x['y'])
    sol_assets = {}

    for i, anchor in enumerate(anchors_sorted):
        qnum = anchor['qnum']
        y_start = max(0, anchor['y'] - 10) # 앵커보다 약간 위부터 자름
        
        # 다음 앵커가 있으면 거기까지, 없으면 이미지 끝까지
        if i < len(anchors_sorted) - 1:
            y_end = anchors_sorted[i+1]['y'] - 10
        else:
            y_end = h
        
        if y_end <= y_start: continue
            
        crop = pil_img.crop((0, y_start, w, y_end))
        
        # 저장 경로 설정
        asset_rel_dir = Path("assets") / "solutions" / f"g1" / f"{meta['year']}_{meta['month']}"
        asset_abs_dir = OUT_ROOT / asset_rel_dir
        asset_abs_dir.mkdir(parents=True, exist_ok=True)
        
        img_name = f"sol_q{qnum:02d}.png"
        img_path = asset_abs_dir / img_name
        crop.save(str(img_path))
        
        sol_assets[qnum] = [str(asset_rel_dir / img_name).replace("\\", "/")]
        
    return sol_assets

def process_single_pdf_solution(pdf_path):
    """해설지 PDF 하나를 처리하여 이미지 저장 및 JSONL 생성"""
    import fitz # 로컬 임포트
    
    # 파일명 분석 (기존 로직)
    filename = pdf_path.name
    m_year = re.search(r"(\d{2})학년도", filename)
    year = int(m_year.group(1)) + 2000 if m_year else 2020
    m_month = re.search(r"(\d{1,2})월", filename)
    month = int(m_month.group(1)) if m_month else 11
    meta = {"year": year, "month": month, "track": "common"}
    grade = 1

    doc = fitz.open(pdf_path)
    all_sol_assets = {}

    print(f"\n📄 {filename} 처리 중...")
    
    for pno in range(len(doc)):
        page = doc[pno]
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        temp_png = OUT_ROOT / "temp_page.png"
        pix.save(str(temp_png))
        
        # 앵커 감지 (문제 번호 1., 2. 패턴 찾기)
        text_page = page.get_text("words")
        anchors = []
        for word in text_page:
            m = re.match(r"^(\d+)\.", word[4])
            if m:
                # fitz 좌표를 이미지 좌표로 변환 (2배 확대 반영)
                anchors.append({'qnum': int(m.group(1)), 'y': word[1] * 2})
        
        if anchors:
            page_assets = split_solution_png_by_anchors(temp_png, meta, anchors)
            all_sol_assets.update(page_assets)
        
        if temp_png.exists(): os.remove(temp_png)

    # 최종 정제 및 JSONL 작성
    s_out_path = OUT_ROOT / "jsonl" / "solutions" / "g1" / f"{meta['year']}_{meta['month']}_solution.jsonl"
    s_out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(s_out_path, "w", encoding="utf-8") as f:
        for qnum in tqdm(range(1, 31), desc="Ollama 정제 중"):
            if qnum in all_sol_assets:
                img_rel_path = all_sol_assets[qnum][0]
                abs_path = OUT_ROOT / img_rel_path
                
                # Ollama 시각 지능 활용
                sol_text = ask_ollama_vision(abs_path)
                
                row = {
                    "id": f"g1_{meta['year']}_{meta['month']}_q{qnum:02d}",
                    "year": meta["year"],
                    "month": meta["month"],
                    "question_number": qnum,
                    "solution_assets": all_sol_assets[qnum],
                    "solution_text_llm": sol_text
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

                print("GPU 휴식을 위해 잠시 멈춥니다.")
                time.sleep(1.5)
    doc.close()

if __name__ == "__main__":
    # data 폴더 내 '해설'이 포함된 PDF 검색
    sol_pdfs = list(ROOT.rglob("*해설*.pdf"))
    for pdf in sol_pdfs:
        process_single_pdf_solution(pdf)