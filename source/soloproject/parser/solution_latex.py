import os
import io
import time
from pathlib import Path
from PIL import Image
import ollama

# 1. 환경 설정
os.environ["OLLAMA_NUM_GPU"] = "0"  # 안정성을 위해 CPU 모드 권장 (GPU 시 1로 변경)
MODEL_NAME = "qwen3-vl:2b"
IMAGE_DIR = Path(r"D:\ai\source\soloproject\data\고1\split_images") # 이미지가 있는 실제 경로로 수정
OUTPUT_FILE = IMAGE_DIR / "math_solution_final.md"

def process_split_images():
    client = ollama.Client(timeout=600.0)
    
    # 이미지 파일 목록 가져오기 (01, 02, 03 순서대로 정렬)
    img_extensions = (".png", ".jpg", ".jpeg")
    image_files = sorted([f for f in IMAGE_DIR.iterdir() if f.suffix.lower() in img_extensions])
    
    if not image_files:
        print("❌ 처리할 이미지 파일이 없습니다.")
        return

    print(f"🚀 총 {len(image_files)}개의 이미지 처리를 시작합니다.")

    # 프롬프트 설정 (사용자님의 marker 컨셉 반영)
    prompt = """너는 수학 해설 이미지를 LaTeX로 정확히 옮기는 역할이다.
이미지에 보이는 모든 텍스트와 수식을 LaTeX 형식으로 변환하라.
문항 번호가 시작되는 지점은 반드시 <<<Q번호>>> 마커를 한 줄로 적어라.
그림(그래프, 도형)이 있는 위치에는 [[COORD:ymin,xmin,ymax,xmax]] 형식으로 대략적인 좌표 앵커를 넣어라.
LaTeX 본문 외에 인사말이나 코드는 생략하라."""

    for img_path in image_files:
        print(f"📄 {img_path.name} 분석 중...", end=" ", flush=True)
        start_time = time.time()

        try:
            with open(img_path, 'rb') as f:
                img_bytes = f.read()

            response = client.chat(
                model=MODEL_NAME,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'images': [img_bytes]
                }],
                options={"num_thread": 12}
            )

            content = response['message']['content']

            # 실시간 저장 (이어쓰기)
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n\n\n")
                f.write(content)

            elapsed = time.time() - start_time
            print(f"✅ 완료 ({elapsed:.1f}초)")
            
            # 짧은 휴식 (발열 및 메모리 관리)
            time.sleep(2)

        except Exception as e:
            print(f"❌ 에러 발생 ({img_path.name}): {e}")

    print(f"\n✨ 모든 작업 완료! 결과물 확인: {OUTPUT_FILE}")

if __name__ == "__main__":
    process_split_images()