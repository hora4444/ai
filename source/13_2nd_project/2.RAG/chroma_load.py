from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="Qwen/Qwen3-Embedding-0.6B",
    encode_kwargs={"normalize_embeddings": True},
)

db = Chroma(
    persist_directory=r"C:\Users\Admin\Desktop\files\chroma_db",
    collection_name="airline_terms",
    embedding_function=embeddings,
)

col = db._collection
print(col.peek()["embeddings"][0].shape)

peek = col.peek(limit=3)

for i in range(len(peek["documents"])):
    print(f"\n--- chunk {i} ---")
    print(peek["documents"][i][:500])   # 앞 500자만

docs = db.similarity_search(
    "What are the refund rules for unused tickets?",
    k=3
)

for i, d in enumerate(docs):
    print(f"\n=== result {i} ===")
    print(d.page_content[:500])