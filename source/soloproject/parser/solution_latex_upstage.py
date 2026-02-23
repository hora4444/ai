import os
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
UPSTAGE_API_KEY = os.getenv("UPSTAGE_KEY")

client = OpenAI(
    api_key=UPSTAGE_API_KEY,
    base_url="https://api.upstage.ai/v1/solar"
)

# 입력 폴더(기존 md)와 출력 폴더 설정
IN_ROOT = Path("output") 
OUT_ROOT = Path("output/solution_latex")

def fix_latex_with_solar(raw_text):
    if not raw_text.strip():
        return ""
        
    prompt = f"""
    다음은 OCR로 추출되어 깨진 글자가 포함된 수학 해설 텍스트입니다. 
    1. '' 같은 깨진 특수문자를 올바른 수학 기호($x^2$ 등)로 복원하세요.
    2. 모든 수식은 반드시 $...$ 또는 $$...$$를 사용하여 LaTeX 형식으로 작성하세요.
    3. 한글 설명과 문제 번호는 그대로 유지하세요.

    텍스트:
    {raw_text}
    """
    
    try:
        response = client.chat.completions.create(
            model="solar-pro3", # 모델명 확인!
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"    [!] 에러 발생: {e}")
        return raw_text

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    # 기존에 생성된 v2 마크다운 파일들 찾기
    md_files = [p for p in IN_ROOT.glob("*_v2_res.md")]

    for md_path in md_files:
        print(f"[*] 처리 시작: {md_path.name}")
        
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 페이지별로 분할 (## 기준으로 나눔)
        pages = content.split("##")
        final_results = []

        for page in pages:
            if not page.strip(): continue
            
            print(f"    - 섹션 처리 중... ({len(page)}자)")
            # Solar 모델로 라텍싱 교정
            fixed_page = fix_latex_with_solar(page)
            final_results.append(f"##{fixed_page}")
            
            # API 제한 방지
            print("API 제한 방지차원 휴식")
            time.sleep(5)

        # 새 파일로 저장
        output_file = OUT_ROOT / f"{md_path.stem}_final.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(final_results))
            
        print(f"[*] 완료: {output_file.name}")

if __name__ == "__main__":
    main()