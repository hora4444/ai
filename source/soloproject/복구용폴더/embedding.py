import json
import ollama
from pathlib import Path
import chromadb
from tqdm import tqdm
import time
import re

# --- 설정 구간 ---
BASE_DIR = Path(r"C:\ai\source\soloproject")
MODEL_NAME = "qwen3-embedding:0.6b" 
PERSIST_DIR = "chroma_db"

# ✅ Ollama 임베딩 함수 (task_type 적용)
def get_embedding(text, task_type="passage"):
    prefixed_text = f"{task_type}: {text}"
    response = ollama.embed(model=MODEL_NAME, input=prefixed_text)
    return response['embeddings'][0]

def load_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

def build_text_for_embedding(item):
    parts = []
    if "assets" in item:
        for asset in item["assets"]:
            llm_text = asset.get("text_llm", "").strip()
            if llm_text:
                parts.append(llm_text)
    
    if not parts:
        fallback = item.get("question_text") or item.get("solution_text")
        if fallback: parts.append(fallback)
        
    return " ".join(parts).strip()

# ✅ 통합 메타데이터 빌더
def build_metadata(item, kind):
    difficulty = item.get("difficulty")  # 나중에 해설 파서가 넣어줄 키
    
    if difficulty is None:
        # 임시 난이도 로직 (문제 파싱 데이터만 있을 때)
        score = item.get("score", 0)
        if score == 2: difficulty = 1
        elif score == 4: difficulty = 4
        else: difficulty = 3 # 기본값

    # 2. 태그 및 유형 처리 (evaluator가 만든 키가 없으면 빈 리스트/값 할당)
    tags = item.get("tags", [])
    problem_type = item.get("type", "객관식" if kind == "question" else "미분류")

    return {
        "grade": item.get("grade", 0),
        "year": item.get("year", 0),
        "month": item.get("month", 0), # 추가
        "track": item.get("track", "unknown"),
        "is_common": item.get("is_common", item.get("track") == "common"),
        "kind": kind, # 문제인지 해설인지 저장
        "difficulty": difficulty,  # ✅ LLM이 판단한 난이도 (1~5)
        "tags": ", ".join(tags) if isinstance(tags, list) else str(tags), # 리스트를 문자열로 변환하여 저장
        "problem_type": problem_type,
        # ✅ 매핑용 키 추가: 해설 데이터일 경우 연결된 문제 ID를 저장
        "pair_id": item.get("id")
    }

def ingest_to_chroma(jsonl_dir: Path, collection_name: str, kind: str):
    # PersistentClient 사용 (경로 자동 저장)
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_or_create_collection(name=collection_name)

    jsonl_files = list(jsonl_dir.glob("**/*.jsonl"))
    
    for jsonl_path in jsonl_files:
        print(f"📦 처리 중: {jsonl_path.name} ({kind})")
        items = list(load_jsonl(jsonl_path))
        
        for item in tqdm(items):
            text = build_text_for_embedding(item)
            if not text: continue

            # Ollama를 통한 GPU 가속 임베딩 생성
            embedding = get_embedding(text, task_type="passage")

            collection.add(
                ids=[item["id"]],
                embeddings=[embedding],
                documents=[text],
                metadatas=[build_metadata(item, kind)] # 정의한 함수 활용
            )
        print("  [wait] GPU 냉각을 위해 잠시 쉽니다...")
        time.sleep(2)
    print(f"✨ {collection_name} 컬렉션 저장 완료!\n")

if __name__ == "__main__":
    # 1. 문제(Questions) 데이터 처리
    q_dir = BASE_DIR / "output" / "jsonl" / "questions" / "g1"
    if q_dir.exists():
        ingest_to_chroma(q_dir, "math_questions", "question")
    else:
        print(f"⚠️ 경로 없음: {q_dir}")

    # 2. 해설(Solutions) 데이터 처리
    s_dir = BASE_DIR / "output" / "jsonl" / "solutions" / "g1"
    if s_dir.exists():
        ingest_to_chroma(s_dir, "math_solutions", "solution")
    else:
        print(f"⚠️ 경로 없음: {s_dir}")