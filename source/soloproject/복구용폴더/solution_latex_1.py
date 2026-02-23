import os
import fitz
from pathlib import Path
import time

# GPU 대신 CPU 강제 사용 설정
os.environ["OLLAMA_NUM_GPU"] = "0"
import ollama

def process_by_pages(base_dir: str):
    target_dir = Path(base_dir) / "data" / "고1"
    pdf_files = [p for p in target_dir.glob("*.pdf") if "해설" in p.name]

    for pdf_path in pdf_files:
        doc = fitz.open(pdf_path)
        output_file = f"{pdf_path.stem}_result.md" # 마크다운 형식 권장
        
        print(f"\n--- [{pdf_path.name}] 총 {len(doc)}페이지 작업 시작 ---")

        # 파일 초기화 (기존 내용 삭제)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# {pdf_path.stem} 해설 LaTeX 변환 결과\n\n")

        for page_num in range(len(doc)):
            print(f"📄 {page_num + 1}/{len(doc)} 페이지 처리 중...", end=" ", flush=True)
            
            page = doc[page_num]
            # 해상도를 1.2~1.5 정도로 조절 (CPU 부담 완화)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
            img_bytes = pix.tobytes("png")

            prompt = f"""수학 해설지 이미지이다. 
1. 텍스트와 수식을 LaTeX 형식으로 정확히 변환하라.
2. 그림, 그래프, 도형이 있으면 반드시 <<<IMG:{pdf_path.stem}_p{page_num+1}_idx>>> 형태의 앵커를 그 위치에 삽입하라.
3. 결과는 다른 설명 없이 LaTeX/Markdown 본문만 출력하라."""

            try:
                # Ollama 호출 (타임아웃 대비를 위해 options 설정)
                response = ollama.chat(
                    model='qwen3-vl:2b',
                    messages=[{'role': 'user', 'content': prompt, 'images': [img_bytes]}],
                    options={"num_thread": 12, "num_gpu": 0, 
                             "low_vram": True,     # (지원되는 경우) VRAM 절약 모드 활성화
                             "num_ctx": 3072}
                )
                
                page_content = response['message']['content']

                # 실시간 파일 이어쓰기 (Append Mode)
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## Page {page_num + 1}\n\n")
                    f.write(page_content)
                
                print("✅ 완료")
                
                print("휴식을 위해 잠시 멈춥니다.")
                time.sleep(2)

            except Exception as e:
                print(f"❌ 에러 발생: {e}")
                # 에러 발생 시 로그를 남기고 다음 페이지로 진행
                with open(output_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n## Page {page_num + 1} [ERROR]\n{str(e)}\n")

        doc.close()
        print(f"\n🎉 모든 작업 완료! 결과 파일: {output_file}")

if __name__ == "__main__":
    process_by_pages(".")