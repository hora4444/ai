import chromadb
from pathlib import Path

# --- 설정 구간 ---
BASE_DIR = Path(r"C:\ai\source\soloproject")
PERSIST_DIR = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "math_questions"  # 확인하고 싶은 컬렉션명 (또는 math_solutions)

def check_embedded_data():
    # 1. ChromaDB 클라이언트 연결
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    
    try:
        # 2. 컬렉션 가져오기
        collection = client.get_collection(name=COLLECTION_NAME)
        
        # 3. 데이터 추출 (최근 5개만)
        # include=["embeddings", "documents", "metadatas"]를 설정해야 벡터값까지 보입니다.
        results = collection.get(
            limit=5,
            include=["embeddings", "documents", "metadatas"]
        )

        total_count = collection.count()
        print(f"📊 총 저장된 데이터 개수: {total_count}")
        print("-" * 50)

        if total_count == 0:
            print("데이터가 비어 있습니다.")
            return

        for i in range(len(results["ids"])):
            print(f"🔹 ID: {results['ids'][i]}")
            print(f"🔹 Metadata: {results['metadatas'][i]}")
            print(f"🔹 Text Content: {results['documents'][i][:100]}...") # 너무 길면 잘라서 출력
            
            # 임베딩(벡터) 값 확인 (상위 10개 숫자만 샘플링)
            embedding_sample = results['embeddings'][i][:10]
            print(f"🔹 Embedding Vector (Sample): {embedding_sample}")
            print(f"   (Vector Dimension: {len(results['embeddings'][i])})")
            print("-" * 50)

    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    check_embedded_data()