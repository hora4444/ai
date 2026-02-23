import os
import io
import time
from pathlib import Path
from PIL import Image
import ollama
from ollama import Client

# 1. 환경 설정
os.environ["OLLAMA_NUM_GPU"] = "1"  # 안정성을 위해 CPU 모드 권장 (GPU 시 1로 변경)
# MODEL_NAME = "minicpm-v:8b"
# MODEL_NAME = "qwen3-vl:4b"
MODEL_NAME ="granite3.2-vision"
IMAGE_DIR = Path(r"C:\ai\source\soloproject\data\고1\해설\2020학년도3월학평(서울)\safe_split_final") # 이미지가 있는 실제 경로로 수정
OUTPUT_FILE = IMAGE_DIR / "math_solution_final.md"


def process_split_images():
    client = Client(host='http://localhost:11434', timeout=1200.0)
    
    # 이미지 파일 목록 가져오기 (01, 02, 03 순서대로 정렬)
    img_extensions = (".png", ".jpg", ".jpeg")
    image_files = sorted([f for f in IMAGE_DIR.iterdir() if f.suffix.lower() in img_extensions])
    
    if not image_files:
        print("❌ 처리할 이미지 파일이 없습니다.")
        return

    print(f"🚀 총 {len(image_files)}개의 이미지 처리를 시작합니다.")

    # 프롬프트 설정 (사용자님의 marker 컨셉 반영)
    prompt = """수학 해설 이미지를 한 줄 한 줄 정밀하게 디지털 문서로 변환하라.
1. 이미지에 포함된 **모든 텍스트 지문과 수식**을 하나도 빠짐없이 그대로 출력하라.
2. 모든 수식은 반드시 $...$ 또는 $$...$$ 기호로 감싸라.
3. "설명", "풀이", "참고" 등의 지문 텍스트도 원래 위치에 맞춰서 적어라.
4. 문항 번호는 반드시 ### 문항 0번 형식으로 구분하라.
5. 도형이 있다면 [참고 도형: {img_path.name}] 표시를 남겨라.
6. AI의 개인적인 의견은 넣지 말고 이미지 내용만 출력하라."""

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
                options={"num_ctx": 8192,        # [중요] 최소 4096 이상, 8192 권장 (이미지+수식용)
                        "num_gpu": 50,          # [중요] 모든 레이어를 GPU에 올리도록 큰 값 설정
                        "temperature": 0,       # 수학 문제이므로 정확도를 위해 0
                        "num_predict": 2048,    # 답변이 길어질 수 있으므로 충분히 확보
                        "top_p": 0.9,
                        }
            )
            content = response.get('message', {}).get('content', "").strip()

            # 답변이 비어있는지 체크하는 로직 추가
            if not content:
                print(f"⚠️ {img_path.name}: 모델이 빈 답변을 반환했습니다. (컨텍스트 부족 가능성)")
            else:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                    f.write(f"\n\n### 파일명: {img_path.name}\n") # 추적을 위해 파일명 추가
                    f.write(content)
                    f.write(f"\n\n---\n")   

            elapsed = time.time() - start_time
            print(f"✅ 완료 ({elapsed:.1f}초)")
            
            # 짧은 휴식 (발열 및 메모리 관리)
            print("잠시휴식")
            time.sleep(10)

        except Exception as e:
            print(f"❌ 에러 발생 ({img_path.name}): {e}")
            print("잠시휴식")
            time.sleep(10)

    print(f"\n✨ 모든 작업 완료! 결과물 확인: {OUTPUT_FILE}")

if __name__ == "__main__":
    process_split_images()