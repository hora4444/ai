from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_community.retrievers.embedchain import EnsembleRetriever
from langchain_ollama import OllamaEmbeddings, ChatOllama

# 1. 벡터 스토어 로드 (기존 PERSIST_DIR 활용)
embeddings = OllamaEmbeddings(model="qwen3-embedding:0.6b")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# 2. BM25 리트리버 설정 (ChromaDB의 텍스트 데이터 활용)
all_docs = vectorstore.get()["documents"]
bm25_retriever = BM25Retriever.from_texts(all_docs)
bm25_retriever.k = 3

# 3. 하이브리드 리트리버 구성 (벡터 50% + BM25 50%)
ensemble_retriever = EnsembleRetriever(
    retrievers=[vectorstore.as_retriever(search_kwargs={"k": 3}), bm25_retriever],
    weights=[0.5, 0.5]
)

# 4. 이제 검색하면 훨씬 정확한 결과가 나옵니다.
relevant_docs = ensemble_retriever.invoke("다항식 A+B 문제 찾아줘")