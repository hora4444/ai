from __future__ import annotations

from langchain_community.vectorstores import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_ollama import OllamaEmbeddings, ChatOllama  # noqa: F401 (필요하면 LLM 연결에 사용)

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda, RunnableParallel


# 1. 벡터 스토어 로드 (기존 PERSIST_DIR 활용)
embeddings = OllamaEmbeddings(model="qwen3-embedding:0.6b")
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)

# 2. BM25 리트리버 설정 (ChromaDB의 텍스트 데이터 활용)
all_texts = vectorstore.get()["documents"]
bm25_retriever = BM25Retriever.from_texts(all_texts)
bm25_retriever.k = 3

# 3. Vector retriever 설정
vector_retriever = vectorstore.as_retriever(search_kwargs={"k": 3})


def _doc_key(d: Document) -> str:
    """중복 제거용 키 (가능하면 metadata.id 우선, 없으면 내용 기반)."""
    mid = d.metadata.get("id") if isinstance(d.metadata, dict) else None
    return str(mid) if mid is not None else d.page_content


def _merge_weighted(results: dict, *, weights=(0.5, 0.5), k: int = 6) -> list[Document]:
    """BM25/Vector 결과를 가중치 비율로 섞고, 중복 제거 후 상위 k개 반환."""
    vec_docs: list[Document] = results.get("vector", []) or []
    bm25_docs: list[Document] = results.get("bm25", []) or []

    w_vec, w_bm25 = weights
    total = (w_vec + w_bm25) if (w_vec + w_bm25) != 0 else 1.0
    w_vec, w_bm25 = w_vec / total, w_bm25 / total

    # 목표 개수(비율 기반) — 최소 1개는 가져오도록
    n_vec = max(1, int(round(k * w_vec))) if vec_docs else 0
    n_bm25 = max(1, k - n_vec) if bm25_docs else 0

    # 한쪽이 비면 다른 쪽으로 채움
    if not vec_docs:
        n_bm25 = min(k, len(bm25_docs))
    if not bm25_docs:
        n_vec = min(k, len(vec_docs))

    # 비율에 맞춰 interleave (간단하지만 실용적인 방식)
    mixed: list[Document] = []
    i = j = 0
    while len(mixed) < k and (i < len(vec_docs) or j < len(bm25_docs)):
        if i < len(vec_docs) and (len([d for d in mixed if d in vec_docs]) < n_vec):
            mixed.append(vec_docs[i])
            i += 1
        if len(mixed) >= k:
            break
        if j < len(bm25_docs) and (len([d for d in mixed if d in bm25_docs]) < n_bm25):
            mixed.append(bm25_docs[j])
            j += 1
        # quota를 다 채웠거나 한쪽이 끝났으면 루프가 자연스럽게 남은 쪽을 채움

    # 중복 제거 + k개 컷
    seen = set()
    unique: list[Document] = []
    for d in mixed:
        key = _doc_key(d)
        if key not in seen:
            unique.append(d)
            seen.add(key)
        if len(unique) >= k:
            break
    return unique


# 4. EnsembleRetriever 대체: Runnable로 병렬 호출 후 merge
WEIGHTS = (0.5, 0.5)  # (vector, bm25)
FINAL_K = 6          # 최종 반환 개수 (각각 k=3이면 보통 6이 자연스러움)

ensemble_retriever = (
    RunnableParallel(vector=vector_retriever, bm25=bm25_retriever)
    | RunnableLambda(lambda results: _merge_weighted(results, weights=WEIGHTS, k=FINAL_K))
)

# 5. 이제 검색하면 (벡터+BM25) 하이브리드 결과가 나옵니다.
relevant_docs = ensemble_retriever.invoke("다항식 A+B 문제 찾아줘")
for d in relevant_docs:
    print(d.page_content)
