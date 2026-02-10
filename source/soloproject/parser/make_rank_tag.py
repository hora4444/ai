import json
import ollama
from pathlib import Path
from tqdm import tqdm
import time
import re

# 설정
JSONL_DIR = Path(r"C:\ai\source\soloproject\output\jsonl\solutions\g1")
MODEL_NAME = "qwen3:4b"  # 텍스트 분석용
# MODEL_NAME = "qwen3:1.7b" # 만약 4b사용이 힘들경우

def get_difficulty_from_latex(latex_text):
    prompt = f"""
    아래 수학 문제의 해설(LaTeX)을 분석하여 난이도를 1~5단계로 평가하세요.
    1: 공식 대입형 (하)
    2: 기본 응용 (중하)
    3: 복합 개념 적용 (중)
    4: 준킬러/심화 (상)
    5: 킬러 문항 (최상)

    해설 내용:
    {latex_text} 

    답변 형식: 오직 숫자만 출력 (예: 4)
    """
    try:
        # 이미 텍스트이므로 이미지 없이 chat만 수행 (매우 빠름)
        response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        result = response['message']['content'].strip()
        match = re.search(r'[1-5]', result)
        return int(match.group()) if match else 3
    except:
        return 3
    
def analyze_problem_meta(latex_text):
    prompt = f"""
    당신은 수학교육 전문가입니다. 다음 해설을 분석하여 정보를 추출하세요.
    
    [해설]
    {latex_text[:1500]}

    [지시사항]
    1. 난이도: 1~5 사이의 숫자
    2. 주요 개념 태그: 3개 이내 (예: 이차함수, 판별식)
    3. 문항 유형: 객관식, 주관식 중 선택

    형식: JSON {"difficulty": 4, "tags": ["이차함수", "접선"], "type": "객관식"}
    """
    try:
        # 이미 텍스트이므로 이미지 없이 chat만 수행 (매우 빠름)
        response = ollama.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content'].strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result_data = json.loads(json_match.group(1))
            # 데이터 형식을 보장하기 위해 기본값과 병합
            return {
                "difficulty": result_data.get("difficulty", 3),
                "tags": result_data.get("tags", ["미분류"]),
                "type": result_data.get("type", "미분류")
            }
        return {"difficulty": 3, "tags": ["미분류"], "type": "미분류"}
    except Exception as e:
        print(f"Error analyzing meta: {e}")
        return {"difficulty": 3, "tags": ["미분류"], "type": "미분류"}

def process_evaluating():
    jsonl_files = list(JSONL_DIR.glob("*.jsonl"))
    
    for file_path in jsonl_files:
        print(f"🧐 난이도 분석 중: {file_path.name}")
        updated_rows = []
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                # 이미 수리가 완료된 텍스트를 기반으로 난이도 측정
                if not data.get("difficulty_score") or data.get("difficulty_score") == 3:
                    data["difficulty_score"] = get_difficulty_from_latex(data.get("solution_text", ""))
                updated_rows.append(data)
        
        # 파일 업데이트
        with open(file_path, 'w', encoding='utf-8') as f:
            for row in updated_rows:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
        
        print(f"✅ {file_path.name} 난이도 업데이트 완료. GPU 휴식...")
        time.sleep(5)

if __name__ == "__main__":
    process_evaluating()