import chromadb
from rank_bm25 import BM25Okapi
from pathlib import Path
import numpy as np

# 설정 (기존 embedding.py와 동일하게 유지)
BASE_DIR = Path(r"C:\ai\source\soloproject")
PERSIST_DIR = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "math_questions"

def run_bm25_search(query, top_k=5):
    # 1. ChromaDB 클라이언트 연결
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)
    
    # 2. 전체 데이터 로드 (BM25 인덱싱용)
    # include=["documents", "metadatas"]를 사용하여 텍스트와 메타데이터를 가져옵니다.
    all_data = collection.get(include=["documents", "metadatas"])
    documents = all_data["documents"]
    metadatas = all_data["metadatas"]
    ids = all_data["ids"]

    if not documents:
        print("데이터가 비어 있습니다.")
        return

    # 3. 토큰화 및 BM25 인덱싱
    # 수학 문제는 공백 외에도 수식 기호가 중요하므로 나중에는 더 정교한 토큰화가 필요하지만, 
    # 현재는 공백 기준으로 기본 테스트를 진행합니다.
    tokenized_corpus = [doc.split() for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)

    # 4. 쿼리 검색
    tokenized_query = query.split()
    doc_scores = bm25.get_scores(tokenized_query)
    
    # 5. 결과 정렬
    top_n_indices = np.argsort(doc_scores)[::-1][:top_k]

    print(f"\n🔍 BM25 검색 결과 (쿼리: '{query}')")
    print("=" * 50)
    for idx in top_n_indices:
        score = doc_scores[idx]
        if score > 0:  # 관련성이 있는 것만 출력
            print(f"🔹 ID: {ids[idx]} (점수: {score:.4f})")
            print(f"🔹 태그: {metadatas[idx].get('tags', 'N/A')}")
            print(f"🔹 내용: {documents[idx][:100]}...")
            print("-" * 50)

if __name__ == "__main__":
    # 파일명을 bm25_finder.py 등으로 변경한 뒤 실행하세요.
    test_query = "다항식 A + B"
    run_bm25_search(test_query)