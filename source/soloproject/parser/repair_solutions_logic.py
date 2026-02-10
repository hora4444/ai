import json
import ollama
from pathlib import Path
import shutil
import re
import time
import io
from PIL import Image

BASE_DIR = Path(r"C:\ai\source\soloproject")
JSONL_DIR = BASE_DIR / "output" / "jsonl" / "solutions" / "g1"
# MODEL_NAME = 'qwen3-vl:2b' # 2b 모델 권장
MODEL_NAME = 'qwen3-vl:4b' # 2회차용

client = ollama.Client(timeout=None)

def clean_llm_result(text):
    if not text: return ""
    # 1. <think> 태그와 그 안의 내용 삭제
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    # 2. ```latex ... ``` 마크다운 블록 제거 및 내용만 추출
    text = re.sub(r'```(?:latex|markdown|)\n?(.*?)\n?```', r'\1', text, flags=re.DOTALL)
    return text.strip()

def preprocess_and_merge_assets(data):
    """
    assets와 solution_assets를 통합하고 중복을 제거하는 헬퍼 함수
    """
    # 두 자산 리스트 합치기
    if 'solution_assets' in data:
        new_assets = []
        for raw_path in data['solution_assets']:
            # 1. 경로 보정: "assets/..." -> "output/assets/..." (실제 파일 위치에 맞게)
            corrected_path = f"output/{raw_path}"
            
            # 2. 구조 통일: 질문 파일과 똑같은 딕셔너리 형태로 만듦
            new_assets.append({
                "path": corrected_path,
                "type": "solution_image",
                "text_llm": "" # 여기에 4b 결과가 담길 예정
            })
        
        # 3. 이제 'assets'라는 키로 똑같이 접근할 수 있게 됨
        data['assets'] = new_assets
        
    return data

def repair_all_jsonls():
    jsonl_files = list(JSONL_DIR.glob("*.jsonl"))
    
    if not jsonl_files:
        print(f"JSONL 파일을 찾을 수 없습니다: {JSONL_DIR}")
        return

    for file_path in jsonl_files:
        print(f"\n--- 파일 작업 시작: {file_path.name} ---")
        
        # 백업 생성
        backup_path = file_path.with_suffix(".jsonl.bak")
        shutil.copy(file_path, backup_path)
        
        updated_lines = []
        repaired_count = 0
        skipped_count = 0
        processed_images = {} # 캐싱용
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                
                # [1단계] 데이터 구조 통합 실행
                data = preprocess_and_merge_assets(data)
                
                # [2단계] 통합된 assets에 대해서만 LLM 작업 수행
                if 'assets' in data:
                    for asset in data['assets']:
                        if asset.get('type') == 'solution_image':

                            img_path_str = asset.get('path')
                            if not img_path_str: 
                                continue

                            if img_path_str in processed_images:
                                asset['text_llm'] = processed_images[img_path_str]
                                continue

                            # 1. 일단 기존에 작업된 텍스트를 가져옵니다.
                            text_result = asset.get('text_llm', "").strip()

                            # 2. [보정 조건 정의] 이 조건 중 하나라도 해당하면 'is_bad'는 True가 됩니다.
                            is_bad = (
                                not text_result or                  # 내용이 아예 없거나
                                len(text_result) < 40 or            # 내용이 너무 짧거나
                                "<think>" in text_result or          # <think> 태그가 남아있거나
                                "To solve" in text_result or        # "To solve this..." 같은 영문 서술이 있거나
                                "I understand" in text_result or      # 모델의 혼잣말이 섞여 있는 경우
                                "the " in text_result               # "the" 같은 불필요한 영어 단어가 포함된 경우
                            )

                            # 3. [스마트 스킵] 내용이 존재하면서 동시에 '나쁘지 않을(Good)' 때만 스킵합니다.
                            if text_result and not is_bad:
                                skipped_count += 1
                                # print(f"  [-] 건너뜀 (이미 양호함): {data['id']}")
                                continue
                            # 실제 이미지 경로 확인
                            full_img_path = BASE_DIR / asset['path']
                            if not full_img_path.exists():
                                print(f"  [!] 파일을 찾을 수 없음: {full_img_path}")
                                continue
                            
                            # LLM 호출
                            try:
                                print(f"  [>] {data['id']} 해설 변환 중... ({full_img_path.name})")
                                
                                # 루프 없이 원본 경로를 바로 전달
                                response = client.chat(
                                    model=MODEL_NAME,
                                    messages=[{
                                        'role': 'user',
                                        'content': """이 이미지에서 수학 해설 텍스트를 추출하세요. 
                                                    반드시 다음 규칙을 지키세요:
                                                    1. 한국어로만 답변할 것.
                                                    2. 인사말, 'I understand', 'Sure' 같은 영어 서술은 절대 금지.
                                                    3. 생각 과정(<think>)을 출력하지 말고 오직 최종 LaTeX 결과만 출력할 것.
                                                    4. 수식은 반드시 $...$로 감쌀 것.""",
                                        'images': [str(full_img_path)]
                                    }]
                                )

                                text_result = response['message']['content'].strip()
                                cleaned_text = clean_llm_result(text_result)

                                # 해설 품질 체크 (기준을 조금 유연하게 조정 가능)
                                is_bad = (
                                    not cleaned_text or 
                                    len(cleaned_text) < 20 or  # 해설은 문제보다 짧을 수 있으므로 20으로 조정 제안
                                    "the " in cleaned_text.lower() or
                                    "To solve" in cleaned_text or
                                    "I understand" in cleaned_text
                                )

                                if not is_bad:
                                    asset['text_llm'] = cleaned_text
                                    processed_images[img_path_str] = cleaned_text
                                    print(f"  [√] 성공: {data['id']}")
                                else:
                                    # 실패 시에도 일단 기록은 남기되 로그로 알림
                                    asset['text_llm'] = cleaned_text
                                    print(f"  [!] 주의: {data['id']} 품질 부적합 (수동 확인 필요)")

                                repaired_count += 1
                                print("  [wait] GPU 냉각을 위해 잠시 쉽니다...")
                                time.sleep(1.5)

                            except Exception as e:
                                print(f"  [!] 오류 발생 ({data['id']}): {e}")
                                print("  [wait] GPU 냉각을 위해 잠시 쉽니다...")
                                time.sleep(1.5)
                        if repaired_count % 10 == 0 and repaired_count > 0:
                            print("--- 10문항 처리 완료: 10초간 GPU 휴식 ---")
                            time.sleep(10)
                
                updated_lines.append(data)
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in updated_lines:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
        
        print(f"--- {file_path.name} 완료! (보정: {repaired_count}건 / 건너뜀: {skipped_count}건) ---\n")

if __name__ == "__main__":
    repair_all_jsonls()