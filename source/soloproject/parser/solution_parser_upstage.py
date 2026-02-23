import os
import requests
import time
from pathlib import Path
from dotenv import load_dotenv
import fitz  # PyMuPDF

# 환경 변수 로드
load_dotenv()
UPSTAGE_API_KEY = os.getenv("UPSTAGE_KEY")

ROOT = Path("data")
OUT_ROOT = Path("output")

def parse_pdf_page(pdf_path, page_num):
    """
    업스테이지 Document Parse API를 사용하여 PDF 페이지를 직접 파싱합니다.
    """
    url = "https://api.upstage.ai/v1/document-ai/document-parse"
    headers = {"Authorization": f"Bearer {UPSTAGE_API_KEY}"}
    
    # 해당 페이지만 별도의 PDF로 임시 저장하여 전송 (정확도 향상)
    doc = fitz.open(pdf_path)
    temp_pdf = fitz.open()
    temp_pdf.insert_pdf(doc, from_page=page_num, to_page=page_num)
    pdf_bytes = temp_pdf.tobytes()
    temp_pdf.close()
    doc.close()

    files = {"document": ("page.pdf", pdf_bytes, "application/pdf")}
    # 수식을 마크다운으로 받기 위한 설정
    data = {"output_format": "markdown"} 

    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        # 결과에서 마크다운 텍스트 추출
        return result.get("content", {}).get("markdown", "")
    except Exception as e:
        print(f"    [!] 에러 발생 ({pdf_path.name}, {page_num+1}P): {e}")
        return ""

def extract_images_from_page(doc, page_num, pdf_name):
    """페이지 내의 이미지를 추출하여 저장하고 경로 리스트를 반환합니다."""
    page = doc[page_num]
    image_list = page.get_images(full=True)
    image_paths = []
    
    img_dir = OUT_ROOT / "solution_images" / pdf_name
    img_dir.mkdir(parents=True, exist_ok=True)

    for img_index, img in enumerate(image_list):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        
        img_filename = f"page_{page_num+1}_img_{img_index+1}.png"
        img_path = img_dir / img_filename
        
        with open(img_path, "wb") as f:
            f.write(image_bytes)
        image_paths.append(img_path)
        
    return image_paths

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    pdf_paths = [p for p in ROOT.rglob("*.pdf") if "해설" in p.name]

    if not pdf_paths:
        print("[!] 파일을 찾을 수 없습니다.")
        return

    for pdf_path in pdf_paths:
        print(f"[*] 처리 시작: {pdf_path.name}")
        doc = fitz.open(pdf_path)
        output_file = OUT_ROOT / f"{pdf_path.stem}_v2_res.md"

        if output_file.exists():
            print(f"[*] {pdf_path.name}은 이미 처리되어 건너뜁니다.")
            continue

        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            print(f"    - {page_num+1} / {len(doc)} 페이지 분석 중...")
            
            img_paths = extract_images_from_page(doc, page_num, pdf_path.stem)

            # 페이지 전체를 Document Parse에 전달 (열 분할 필요 없음)
            parsed_content = parse_pdf_page(pdf_path, page_num)

            img_tags = "\n".join([f"![image](images/{pdf_path.stem}/{p.name})" for p in img_paths])
            
            if parsed_content:
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## {page_num+1} Page\n\n")
                    f.write(parsed_content + "\n" + img_tags)
            
            # API 제한 방지
            time.sleep(1)
        
        doc.close()

    print("[*] 모든 작업이 완료되었습니다. 'output' 폴더를 확인하세요.")

if __name__ == "__main__":
    main()