EMBEDDING_MODEL = "intfloat/multilingual-e5-base"

import json
from pathlib import Path
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
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

COLLECTION_NAME = "math_exam_items"

def build_metadata(item):
    return {
        "grade": item["grade"],
        "year": item["year"],
        "month": item["month"],
        "track": item["track"],
        "is_common": item["is_common"],
        "kind": item.get("kind", "question"),  # question / solution
    }

# 임베딩용 텍스트 구성
def build_text_for_embedding(item):
    parts = []

    if item.get("question_text"):
        parts.append(item["question_text"])

    choices = item.get("choices", [])
    if choices:
        parts.append("선택지: " + " ".join(choices))

    return "\n".join(parts).strip()

# ChromaDB 인제스트 코드
def ingest_jsonl_to_chroma(jsonl_dir: Path, persist_dir="chroma_db"):
    client = get_chroma_client(persist_dir)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    model = SentenceTransformer(EMBEDDING_MODEL)

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
    jsonl_dir = Path("output/jsonl")
    ingest_jsonl_to_chroma(jsonl_dir)