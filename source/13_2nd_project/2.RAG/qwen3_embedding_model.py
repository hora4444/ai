# build_chroma.py
import os
import argparse
from pathlib import Path
from langchain_community.document_loaders import TextLoader, PyPDFLoader

def build_vectorstore(
    input_path: str,
    persist_dir: str,
    collection_name: str = "airline_terms",
    chunk_size_tokens: int = 1500,
    chunk_overlap_tokens: int = 200,
    model_name: str = "Qwen/Qwen3-Embedding-0.6B",
    device: str | None = None,
):
    # --- LangChain loaders / splitters
    from langchain_community.document_loaders import TextLoader
    from langchain_text_splitters import TokenTextSplitter

    # --- Embeddings (HF)
    from langchain_community.embeddings import HuggingFaceEmbeddings

    # --- Chroma (new package path first, fallback to community)
    try:
        from langchain_chroma import Chroma
    except Exception:
        from langchain_community.vectorstores import Chroma

    input_path = str(Path(input_path))
    persist_dir = str(Path(persist_dir))

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    os.makedirs(persist_dir, exist_ok=True)

    # 1) Load
    # encoding="utf-8"가 안전하지만, 파일 인코딩이 다르면 errors="ignore"로 완화
    loader = TextLoader(input_path, encoding="utf-8")
    docs = loader.load()

    # 2) Split (token-based)
    splitter = TokenTextSplitter(
        encoding_name="cl100k_base",  # tiktoken 기반 토큰화
        chunk_size=chunk_size_tokens,
        chunk_overlap=chunk_overlap_tokens,
    )
    chunks = splitter.split_documents(docs)

    # 파일명 저장
    source_file = Path(input_path).name

    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = Path(input_path).stem.replace("여객운송약관", "")
        chunk.metadata["chunk_id"] = i

    # 3) Embeddings
    embed_kwargs = {}
    if device:
        embed_kwargs["model_kwargs"] = {"device": device}

    embeddings = HuggingFaceEmbeddings(
        model_name=model_name,
        **embed_kwargs,
        encode_kwargs={"normalize_embeddings": True},
    )

    # 4) Build + Persist Chroma
    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=persist_dir,
    )

    # langchain_chroma는 자동 persist되는 경우가 많지만, 안전하게 호출
    try:
        vectordb.persist()
    except Exception:
        pass

    print("✅ Done")
    print(f"- Input: {input_path}")
    print(f"- Chunks: {len(chunks)}")
    print(f"- Collection: {collection_name}")
    print(f"- Persist dir: {persist_dir}")

    return vectordb


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=str,
        default="data/에어서울국내여객운송약관.txt",
        help="Path to the .txt document",
    )
    parser.add_argument(
        "--persist_dir",
        type=str,
        default="./chroma_db",
        help="Directory to persist Chroma DB",
    )
    parser.add_argument("--collection", type=str, default="airline_terms")
    parser.add_argument("--chunk_size", type=int, default=1500)
    parser.add_argument("--chunk_overlap", type=int, default=200)
    parser.add_argument("--model", type=str, default="Qwen/Qwen3-Embedding-0.6B")
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="e.g. 'cuda', 'cpu'. If omitted, HF defaults apply.",
    )
    args = parser.parse_args()

    build_vectorstore(
        input_path=args.input,
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        chunk_size_tokens=args.chunk_size,
        chunk_overlap_tokens=args.chunk_overlap,
        model_name=args.model,
        device=args.device,
    )
