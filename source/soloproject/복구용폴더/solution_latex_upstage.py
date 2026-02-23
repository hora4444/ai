import os
import io
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
import fitz  # PyMuPDF

# 환경 변수 로드
load_dotenv()
UPSTAGE_API_KEY = os.getenv("UPSTAGE_KEY")

ROOT = Path("data")
OUT_ROOT = Path("output")

def call_upstage_document_ai(image_bytes):
    """
    업스테이지 Document AI API를 호출하여 이미지 내 텍스트와 수식을 마크다운으로 변환합니다.
    """
    # 수학 수식 조판을 위해 'document-parse' 모델 사용을 강력 추천합니다.
    # 단순 OCR보다 수식 보존 능력이 뛰어납니다.
    url = "https://api.upstage.ai/v1/document-ai/document-parse"
    headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}
    
    # 파일을 메모리에서 직접 전송
    files = {"document": ("column.png", image_bytes, "image/png")}
    data = {"output_format": "markdown"} # 수식을 LaTeX($$)로 받기 위해 마크다운 설정
    
    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        
        # Document Parse 모델의 경우 'content' 필드 안에 'markdown' 결과가 들어있습니다.
        return result.get("content", {}).get("markdown", "")
    except Exception as e:
        print(f"[!] API 호출 오류: {e}")
        return ""

def process_hybrid_column(page, rect, col_index):
    """
    특정 열 영역을 이미지로 캡처하여 업스테이지 AI에게 전달합니다.
    """
    # 1. 해당 영역을 고해상도로 캡처
    pix = page.get_pixmap(clip=rect, matrix=fitz.Matrix(2, 2))
    img_bytes = pix.tobytes("png")

    # 2. 업스테이지 Document AI 호출 (수식 및 텍스트 추출)
    print(f"    [>] API 요청 중...")
    parsed_content = call_upstage_document_ai(img_bytes)
    
    return parsed_content

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    # '해설'이 포함된 PDF 찾기
    pdf_paths = [p for p in ROOT.rglob("*.pdf") if "해설" in p.name]

    if not pdf_paths:
        print("[!] 처리할 PDF 파일을 찾지 못했습니다. 'data' 폴더를 확인하세요.")
        return

    for pdf_path in pdf_paths:
        doc = fitz.open(pdf_path)
        output_file = OUT_ROOT / f"{pdf_path.stem}_res.md"
        
        # 기존 파일이 있다면 삭제 후 새로 생성
        if output_file.exists():
            output_file.unlink()

        for page_num in range(len(doc)):
            page = doc[page_num]
            p_rect = page.rect
            
            # 페이지 레이아웃 설정 (여백 제외 실제 내용 영역)
            margin_lr = p_rect.width * 0.1
            margin_tb = p_rect.height * 0.1
            content_box = fitz.Rect(margin_lr, margin_tb, p_rect.width - margin_lr, p_rect.height - margin_tb)
            
            col_width = content_box.width / 3
            page_results = []

            for i in range(3):
                col_rect = fitz.Rect(content_box.x0 + (col_width * i), content_box.y0, 
                                     content_box.x0 + (col_width * (i+1)), content_box.y1)
                
                print(f"[*] {pdf_path.name} - {page_num+1}페이지 {i+1}열 처리 중...")
                col_result = process_hybrid_column(page, col_rect, i)
                
                if col_result:
                    # 열 구분 정보를 포함하여 저장
                    page_results.append(f"\n\n### {page_num+1}P {i+1}열\n\n{col_result}")
                
                # API 요율 제한 방지를 위한 짧은 휴식
                time.sleep(1)

            # 한 페이지 처리가 끝나면 즉시 파일에 쓰기 (데이터 손실 방지)
            with open(output_file, "a", encoding="utf-8") as f:
                f.write("\n".join(page_results))

    print("[*] 모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()