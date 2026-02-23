import json
import re
from pathlib import Path
import ollama
# 설정
IN_ROOT = Path("output")  # 최종 마크다운 파일이 있는 폴더
OUT_ROOT = Path("output/jsonl/solutions") # 저장할 jsonl 폴더

def parse_markdown_to_jsonl(md_path):
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    # '## 숫자.' 패턴으로 문항별 분할
    # 예: "## 1." 또는 "### 1." 등으로 시작하는 해설 덩어리들을 찾습니다.
    pattern = re.compile(r'###?\s+(\d+)\.\s+(.*?)(?=\n###?\s+\d+\.|\Z)', re.DOTALL)
    matches = pattern.findall(content)
    
    jsonl_data = []
    for q_num, solution_content in matches:
        # 문제 ID 생성 (예: 2020_11_19)
        file_id = md_path.stem.replace("해설", "").replace("_v2_res_final", "")
        q_id = f"{file_id}_{q_num}"
        
        # 해설 텍스트 정제
        solution_text = solution_content.strip()
        
        jsonl_data.append({
            "id": q_id,
            "solution_text": solution_text,
            "metadata": {
                "source": md_path.name,
                "q_num": q_num
            }
        })
    return jsonl_data

def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    md_files = list(IN_ROOT.glob("*_final.md"))

    for md_path in md_files:
        print(f"[*] 파싱 중: {md_path.name}")
        data = parse_markdown_to_jsonl(md_path)
        
        output_jsonl = OUT_ROOT / f"{md_path.stem}.jsonl"
        with open(output_jsonl, "w", encoding="utf-8") as f:
            for entry in data:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        print(f"    - 저장 완료: {output_jsonl.name} ({len(data)}개 문항)")

if __name__ == "__main__":
    main()