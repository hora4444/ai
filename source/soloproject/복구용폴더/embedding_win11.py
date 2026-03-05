import json
import ollama
from pathlib import Path
import chromadb
from tqdm import tqdm
import time
from chromadb.config import Settings
# 코파일럿이 준 유틸리티 불러오기
from utils_chroma import chunks, ensure_str_metadata, backoff_sleep
import os
# Windows에서 병렬 처리 및 하드웨어 가속으로 인한 충돌 방지
os.environ["ORT_PROFILER_CONTROL"] = "0"
os.environ["ONNXRUNTIME_PROFILER_CONTROL"] = "0"
# 라이브러리가 사용하는 스레드 수를 제한하여 안정성 확보
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# --- 설정 구간 ---
BASE_DIR = Path(r"C:\ai\source\soloproject")
MODEL_NAME = "qwen3-embedding:0.6b" 
PERSIST_DIR = str(BASE_DIR / "chroma_db")

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
    q_text = item.get("question_text", "").strip()
    s_text = item.get("solution_text", "").strip()
    if "*주요 수정 사항*" in s_text:
        s_text = s_text.split("*주요 수정 사항*")[0].strip()
    return f"문제: {q_text}\n\n해설: {s_text}".strip()

def start_embedding_process():
    final_dir = BASE_DIR / "output" / "final_integrated"
    jsonl_files = sorted(list(final_dir.glob("*.jsonl")))
    print(f"📂 총 {len(jsonl_files)}개의 파일을 발견했습니다.")

    # ✅ [수정] 클라이언트는 루프 밖에서 단 한 번만 생성
    client = chromadb.PersistentClient(
        path=PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False)
    )
    collection = client.get_or_create_collection(
        name="math_problems",
        embedding_function=None 
    )
    print("🔍 기존 DB 데이터 확인 중...")
    try:
        existing_data = collection.get(include=[])
        existing_ids = set(existing_data['ids'])
    except:
        existing_ids = set()

    for jsonl_path in jsonl_files:
        # --- [1단계: 중복 체크] ---
    # 파일의 첫 번째 아이템을 살짝 열어서 이미 저장된 파일인지 확인합니다.
        first_item = None
        for item in load_jsonl(jsonl_path):
            first_item = item
            break
        
        if not first_item:
            continue
            
        check_id = f"{jsonl_path.stem}_{first_item.get('id')}"
        
        # DB에서 이 ID가 있는지 콕 집어서 확인 (매우 가벼움)
        existing = collection.get(ids=[check_id], include=[])
        
        if len(existing['ids']) > 0:
            print(f"⏩ {jsonl_path.name}: 이미 DB에 존재하므로 건너뜁니다.")
            continue

        # --- [2단계: 작업 시작] ---
        # 위에서 건너뛰지 않았다면, 이제 본격적으로 전체 데이터를 읽고 임베딩을 만듭니다.
        print(f"\n📦 작업 시작: {jsonl_path.name}")
        
        # 다시 처음부터 읽기 위해 리스트로 만듭니다.
        items = list(load_jsonl(jsonl_path))
        ids, embeddings, documents, metadatas = [], [], [], []
        
        for item in tqdm(items, desc="임베딩 생성 중"):
            text = build_text_for_embedding(item)
            if not text: continue
            
            try:
                emb = get_embedding(text)
                ids.append(f"{jsonl_path.stem}_{item.get('id')}")
                embeddings.append(emb)
                documents.append(text)
                
                safe_meta = ensure_str_metadata(item.get("metadata", {}))
                safe_meta["source_file"] = jsonl_path.name
                metadatas.append(safe_meta)
            except Exception as e:
                print(f"❌ 임베딩 실패: {e}")
            time.sleep(3)
                
            print(f"✅ {jsonl_path.name} 저장 완료! (현재 DB 총량: {collection.count()})")
        
        time.sleep(0.5)

    print("\n🚀 모든 파일 작업이 끝났습니다!")

if __name__ == "__main__":
    start_embedding_process()