import chromadb
from rank_bm25 import BM25Okapi
from pathlib import Path

# 설정
BASE_DIR = Path(r"C:\ai\source\soloproject")
PERSIST_DIR = str(BASE_DIR / "chroma_db")
COLLECTION_NAME = "math_questions"

def run_hybrid_search_test(query):
    client = chromadb.PersistentClient(path=PERSIST_DIR)
    collection = client.get_collection(name=COLLECTION_NAME)

    # 1. BM25용 전체 문서(Documents) 가져오기
    all_data = collection.get(include=["documents", "metadatas"])
    documents = all_data["documents"]
    
    # 2. 토큰화 (간단하게 공백 기준, 수학 기호 고려 필요)
    tokenized_corpus = [doc.split(" ") for doc in documents]
    bm25 = BM25Okapi(tokenized_corpus)

    # 3. BM25 검색 수행
    tokenized_query = query.split(" ")
    bm25_scores = bm25.get_scores(tokenized_query)
    
    # 4. 결과 정렬 및 출력 (상위 3개)
    top_n = 3
    import numpy as np
    top_indices = np.argsort(bm25_scores)[::-1][:top_n]

    print(f"\n🔍 쿼리: '{query}'에 대한 BM25 검색 결과")
    for idx in top_indices:
        print(f"ID: {all_data['ids'][idx]} | 점수: {bm25_scores[idx]:.4f}")
        print(f"내용: {documents[idx][:100]}...")
        print("-" * 30)

if __name__ == "__main__":
    # 테스트 쿼리 (현재 DB에 있는 단어 위주)
    run_hybrid_search_test("다항식 A + B")