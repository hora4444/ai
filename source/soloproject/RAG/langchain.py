import pickle
import faiss
import numpy as np
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableParallel
from langchain_ollama import OllamaEmbeddings

# 1. 초기 로드 및 데이터 준비
EMBEDDINGS = OllamaEmbeddings(model="qwen3-embedding:0.6b")
FAISS_INDEX_PATH = "C:/ai/source/soloproject/faiss_db/math_index.faiss"
CONTENT_PKL_PATH = "C:/ai/source/soloproject/faiss_db/math_content.pkl"

def load_custom_faiss():
    # 저장된 pkl에서 텍스트와 메타데이터 복원
    with open(CONTENT_PKL_PATH, "rb") as f:
        all_content = pickle.load(f)
    
    # Document 객체 리스트 생성
    docs = [
        Document(
            page_content=item['text'], 
            metadata={**item['metadata'], "id": item['id']}
        ) for item in all_content
    ]
    
    # LangChain용 FAISS 객체로 변환 (이미 생성된 index 파일 활용)
    # ※ 주의: FAISS.load_local은 전용 포맷이 필요하므로, 
    # 처음엔 from_documents로 메모리에 올리는 것이 장고 서버 구동 시 더 안정적입니다.
    vectorstore = FAISS.from_documents(docs, EMBEDDINGS)
    return vectorstore, docs

vectorstore, all_docs = load_custom_faiss()

# 2. 개별 리트리버 설정
faiss_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
bm25_retriever = BM25Retriever.from_documents(all_docs)
bm25_retriever.k = 3

# 3. 앙상블 로직 (Runnable용 함수)
def merge_documents(data: dict):
    """FAISS와 BM25 결과를 합치고 중복을 제거함"""
    faiss_docs = data["faiss"]
    bm25_docs = data["bm25"]
    
    combined = faiss_docs + bm25_docs
    # ID 기반 중복 제거
    unique_docs = []
    seen_ids = set()
    for doc in combined:
        doc_id = doc.metadata.get("id")
        if doc_id not in seen_ids:
            unique_docs.append(doc)
            seen_ids.add(doc_id)
    return unique_docs[:5] # 최종 TOP 5 반환

# 4. LCEL 체인 구성 (앙상블 리트리버)
ensemble_retriever = RunnableParallel(
    faiss=faiss_retriever,
    bm25=bm25_retriever
) | RunnableLambda(merge_documents)

# 5. 사용 예시 (Django View에서 호출할 부분)
# result = ensemble_retriever.invoke("복소수 z의 값을 구하는 문제")