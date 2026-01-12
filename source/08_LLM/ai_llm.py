import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ai_functions import categorize_content, extract_articles_from_docs, format_documents
import cohere

load_dotenv()
PINECONE_INDEX_NAME = "better-rag-index"
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

def get_llm(model = "gpt-4o-mini"):
    llm = ChatOpenAI(model = model)
    return llm

def get_dictionary_chain(llm):
    # 3. 키워드 사전 활용
    keyword_dict  = [
        "사람을 나타내는 표현 -> 거주자",
        "직장인 -> 근로소득이 있는 거주자", 
        "월급쟁이 -> 근로소득이 있는 거주자",
        "회사원 -> 근로소득이 있는 거주자",
        "연봉 -> 종합소득",
        "월급 -> 근로소득",
        "세금 -> 소득세",
        "공제받다 -> 공제를 적용받다",
        "얼마나 내야하나 -> 세액은 얼마인가",
        "계산해줘 -> 계산하면 얼마인가"
    ]
    prompt = ChatPromptTemplate.from_template(f"""사용자의 질문을 보고, 우리의 사전을 참고해서 
    사용자의 질문을 변경해 주세요. 만약 변경할 필요가 없을경우, 사용자의 질문을 변경하지 않아도 됩니다.
    그런 경우에는 질문만 리턴해 주세요.
    사전 : {keyword_dict}
    질문 : {{question}}""")
    keyword_chain = prompt | llm | StrOutputParser()
    return keyword_chain

def get_retriever(normalized_query, model="text-embedding-3-large", k=15):
    # Retriever 생성    
    embedding = OpenAIEmbeddings(model=model)
    vector_database = PineconeVectorStore(
        embedding=embedding,  # 질문을 임베딩하여 유사도 검색
        index_name=PINECONE_INDEX_NAME
    )
    filter_condition = {"category": {"$in": categorize_content(normalized_query)}}
    retriever = vector_database.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k, "filter": filter_condition}
    )
    return retriever

def rerank_by_title(query: str, documents: list, top_k: int = 4) -> list:
    """
    Cohere의 Rerank API를 사용한 문서 재정렬
    Args:
        query: 사용자 질문
        documents: 검색된 Document 객체 리스트
        top_k: 반환할 문서 개수 (기본값은 4)    
    Returns:
        list: title 유사도 기준으로 재정렬된 Document 리스트
    """
    # Cohere 클라이언트 초기화
    co = cohere.Client(api_key=COHERE_API_KEY)
    # Document 객체에서 텍스트 추출 (뭐 title이 있으니 title도 포함함)
    docs_text = [doc.metadata.get('title', '') +" "+doc.page_content for doc in documents]
    # docs_text = [doc.page_content for doc in documents]
    # Cohere Rerank API 호출
    results = co.rerank(
        model="rerank-multilingual-v3.0",  # 한국어 지원 모델
        query=query,
        documents=docs_text,
        top_n=top_k,
        # return_documents=False  # 문서 내용은 반환하지 않음 (인덱스만)
    )    
    # 재정렬된 문서 반환
    reranked_docs = [documents[r.index] for r in results.results]
    return reranked_docs
    
def rag_chain(llm):
    # 프롬프트 템플릿
    template = f"""당신은 최고의 한국 소득세 전문가입니다.
    다음 문맥을 참고하여 질문에 답하세요.
    답을 모르면 모른다고 답하세요.
    최대 3문장으로 간결하게 답변하세요.
    질문 : {{query}}
    문맥 : {{context}}
    답변 : """
    prompt = ChatPromptTemplate.from_template(template)
    # RAG 체인 구성 (LCEL 방식)
    prompt_chain = prompt | llm  | StrOutputParser()
    return prompt_chain

#  재사용 가능한 함수로 만들기
def ask_with_reference_rerank(query: str, chat_history:list=None, k: int = 15, top_k:int=4, ):
    """
    질문에 답변하고 참조 조항을 함께 반환하는 함수
    
    Args:
        question: 사용자 질문
        k: 검색할 문서 개수 (기본값 3)
    query, 표준화된 query, 생성된 답변, 참조조항 출력
    """
    # 1. LLM과 임베딩 초기화
    llm = get_llm()   

    # ★ 여기에 추가 
    # chat_history에 질문이 있으면 query 재구성
    if chat_history:
        history_list = [f"{'사용자' if msg['role']=='user' else 'AI'}: {msg['content']}"  for msg in chat_history]
        history_text = "\n".join(history_list)
        # query 재구성
        rewrite_prompt = ChatPromptTemplate.from_template(
            """이전 대화를 참고하여 질문을 재구성해 주세요
            이전 대화 : {history_text}
            현재 질문 : {question}
            재구성된 질문 : """
        )
        query = (rewrite_prompt | llm | StrOutputParser()).invoke({"history_text":history_text,
                                                                "question": query})

    keyword_chain = get_dictionary_chain(llm=llm)
    # 질문 표준화
    normalized_query = keyword_chain.invoke({"question": query})
    # Retriever 생성
    retriever = get_retriever(normalized_query=normalized_query)
    # 문서 검색
    documents = retriever.invoke(normalized_query)
    # query와 유사도가 높은 title로 RERANK된 문서 검색
    reranked_documents = rerank_by_title(query=normalized_query, documents=documents, top_k=top_k)
    # 참조 조항 추출
    referenced_articles = extract_articles_from_docs(reranked_documents)
    prompt_chain = rag_chain(llm=llm)
    
    # 7. 실행
    answer = prompt_chain.invoke({"context":format_documents(reranked_documents), 
                                "query":normalized_query})
    result = "\n\n".join([f"☑️ 답변: {answer}", 
                            f"📌 참조: {referenced_articles}", 
                            "* 위의 답변은 AI에 의해 작성된 답변이므로 약간의 차이가 날 수 있습니다 *"])
    return result