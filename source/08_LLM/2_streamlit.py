# vscode에서 ctrol+shift+p애서 llm 인터프리터 선택
# 실행 ctrl+j : powershall 터미널 -> command prompt에서 streamlit run 소스파일명 
import streamlit as st
st.set_page_config(page_title='첫번째 데모')

st.title('나의 첫 stream 웹')
st.header('웹 앱을 만들기 위한 강력하고 사용하기 쉬운 라이브러리')
st.subheader('streamlit에 오신 것을 환영합니다.')
st.text('이것은 일반 텍스트 입니다.')
st.write('write함수를 이용하여 텍스트 표시')
st.markdown('---')
message = st.text_area('요약글을 입력하세요')
if st.button('요약'):
    st.info('버튼 클릭했네')

if prompt := st.chat_input('챗 입력 받기'):
    st.chat_message('user').write(prompt)
