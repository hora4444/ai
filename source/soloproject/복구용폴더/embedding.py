EMBEDDING_MODEL = "Qwen/Qwen3-Embedding-0.6B"

import json
from pathlib import Path
import chromadb
from chromadb.config import Settings
from langchain_community.embeddings import HuggingFaceEmbeddings
from tqdm import tqdm


# jsonl 로더 (문제/해설 공통)
def load_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)

# ChromaDB 초기화
def get_chroma_client(persist_dir="chroma_db"):
    return chromadb.Client(
        Settings(
            persist_directory=persist_dir,
            anonymized_telemetry=False
        )
    )

COLLECTION_NAME = "math_questions"

def build_metadata(item):
    return {
        "grade": item["grade"],
        "year": item["year"],
        "month": item["month"],
        "track": item["track"],
        "is_common": item.get("is_common", item.get("track") == "common"),
        "kind": item.get("kind", "question"),  # question / solution
    }

# 임베딩용 텍스트 구성
def build_text_for_embedding(item):
    parts = []

    if "assets" in item:
            for asset in item["assets"]:
                llm_text = asset.get("text_llm", "").strip()
                if llm_text:
                    parts.append(llm_text)
    
    if not parts and item.get("question_text"):
        parts.append(item["question_text"])
    # 해설 파일의 경우 solution_text도 포함
    # if item.get("solution_text"):
    #     parts.append(item["solution_text"])

    return " ".join(parts).strip()

# ChromaDB 인제스트 코드
def ingest_jsonl_to_chroma(jsonl_dir: Path, persist_dir="chroma_db"):
    client = get_chroma_client(persist_dir)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    ids = []
    documents = []
    metadatas = []

    for jsonl_path in jsonl_dir.glob("**/*.jsonl"):
        for item in load_jsonl(jsonl_path):
            text = build_text_for_embedding(item)
            if not text:
                continue

            ids.append(item["id"])
            documents.append(text)
            metadatas.append(build_metadata(item))

    if not documents:
        print("No documents to ingest.")
        return

    embeddings = model.encode(
        documents,
        batch_size=32,
        show_progress_bar=True
    )

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas
    )

    client.persist()
    print(f"✅ Ingested {len(documents)} items into ChromaDB")

# 검색 테스트 코드
def search_chroma(query, k=5, filters=None):
    client = get_chroma_client()
    collection = client.get_collection(COLLECTION_NAME)

    results = collection.query(
        query_texts=[query],
        n_results=k,
        where=filters
    )

    return results

if __name__ == "__main__":
    jsonl_dir = Path("output/jsonl/questions/g1")
    ingest_jsonl_to_chroma(jsonl_dir)