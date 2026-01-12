# 인터프리터 선택(ctrl+shift+p) -> 인터프리터 : llm -> ctrl+j :streamlit run 7_aibot.py
# docs.streamlit.io
import streamlit as st
from ai_llm import ask_with_reference_rerank

st.set_page_config(page_title='소득세 챗봇', page_icon='💰')
st.title('💰소득세 챗봇')
st.caption("소득세 챗봇을 이용해 질문에 답하고 참조조항을 함께 반환합니다.")

# 저장될 대화 이력을 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []

# 대화이력 저장
for msg in st.session_state.messages:
    st.chat_message(msg['role']).write(msg['content'])

# 사용자 질문 입력
if user_question := st.chat_input(placeholder='소득세에 관련된 질문을 입력하세요'):
    st.chat_message("user").write(user_question)

    # 사용자 질문을 session에 추가하고 출력
    st.session_state.messages.append({'role':'user', 'content':user_question})

    # AI 응답을 받아 ssession에 추가하고 출력
    with st.spinner('응답을 기다리는 중...'):
        answer = ask_with_reference_rerank(user_question, chat_history=st.session_state.messages[:-1])
        st.session_state.messages.append({'role':'ai', 'content':answer})
        st.chat_message("ai").write(answer)
