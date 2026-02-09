import json
import ollama
from pathlib import Path
import shutil

BASE_DIR = Path(r"C:\ai\source\soloproject")
JSONL_DIR = BASE_DIR / "output" / "jsonl" / "questions" / "g1"
MODEL_NAME = 'qwen3-vl:2b' # 2b 모델 권장

client = ollama.Client(timeout=None)

def preprocess_and_merge_assets(data):
    """
    assets와 question_assets를 통합하고 중복을 제거하는 헬퍼 함수
    """
    # 두 자산 리스트 합치기
    all_assets = data.get('assets', []) + data.get('question_assets', [])
    
    unique_assets = {}
    for asset in all_assets:
        path = asset.get('path')
        if not path: continue
        
        if path not in unique_assets:
            unique_assets[path] = asset
        else:
            # 이미 존재한다면 text_llm이 있는 데이터를 우선 보존
            if not unique_assets[path].get('text_llm') and asset.get('text_llm'):
                unique_assets[path] = asset
    
    # 통합된 리스트를 assets에 넣고 question_assets는 제거
    data['assets'] = list(unique_assets.values())
    if 'question_assets' in data:
        del data['question_assets']
        
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
                        if asset.get('type') == 'question_image':
                            # 이미 LaTeX가 있다면 스킵
                            if asset.get('text_llm') and asset.get('text_llm').strip():
                                skipped_count += 1
                                continue

                            img_path_str = asset.get('path')

                            # 캐시 확인
                            if img_path_str in processed_images:
                                asset['text_llm'] = processed_images[img_path_str]
                                repaired_count += 1
                                continue

                            # 실제 이미지 경로 확인
                            relative_path = img_path_str.replace('output/', '', 1)
                            full_img_path = BASE_DIR / "output" / relative_path
                            
                            if not full_img_path.exists():
                                continue
                            
                            # LLM 호출
                            try:
                                print(f"  [>] {data['id']} 변환 중... ({full_img_path.name})")
                                response = client.chat(
                                    model=MODEL_NAME,
                                    messages=[{
                                        'role': 'user',
                                        'content': "이 수학 문제 이미지의 모든 텍스트와 수식을 LaTeX 형식으로 정확히 추출해줘. 다른 설명 없이 텍스트 결과만 보여줘.",
                                        'images': [str(full_img_path)]
                                    }]
                                )
                                text_result = response['message']['content'].strip()
                                asset['text_llm'] = text_result
                                processed_images[img_path_str] = text_result
                                repaired_count += 1
                            except Exception as e:
                                print(f"  [!] 오류 발생 ({data['id']}): {e}")
                
                updated_lines.append(data)
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            for line in updated_lines:
                f.write(json.dumps(line, ensure_ascii=False) + '\n')
        
        print(f"--- {file_path.name} 완료! (보정: {repaired_count}건 / 건너뜀: {skipped_count}건) ---\n")

if __name__ == "__main__":
    repair_all_jsonls()