# ctrl+shift+p -> 파이썬 인터프리터 선택 -> llm가상환경 선택
# 내일 -> 웹버전(입력된 데이터를 1줄로 요약해서 보여주기)
# 실행 ctrl+j
from dotenv import load_dotenv
from openai import OpenAI
def askGPT(prompt):
    'GPT에게 요청하여 prompt내용을 1줄 요약하여 return'
    load_dotenv()
    client = OpenAI()
    response = client.chat.completions.create(
        model='gpt-4.1-nano',
        messages=[
            {'role':'system','content':'당신은 한국어로 된 텍스트를 잘 요약해 주는 전문어시스턴트입니다.'},
            {'role':'user','content':prompt}
        ]
    )
    return response.choices[0].message.content
if __name__ == '__main__':
    message = input('요약할 글을 입력하세요')
    if message:
        prompt = f'''your task is to summarize the text sentences in Korean lunguage.
        Summarize in 1 line. Use the format of a bullet point.
        text : {message}'''
        result = askGPT(prompt)
        print('--요약입니다.--')
        print(result)