import ollama
import json
import base64
from pathlib import Path
from tqdm import tqdm

OUT_ROOT = Path("output")
MODEL_NAME = "seed-vision"

def refine_with_image(mode="questions"): # 기본값을 questions로 변경
    input_dir = OUT_ROOT / "jsonl" / mode / "g1"
    output_dir = OUT_ROOT / "jsonl" / f"{mode}_refined" / "g1"
    output_dir.mkdir(parents=True, exist_ok=True)

    jsonl_files = list(input_dir.glob("*.jsonl"))
    
    for jsonl_path in jsonl_files:
        output_path = output_dir / jsonl_path.name.replace(".jsonl", "_refined.jsonl")
        print(f"\n[작업 시작] {mode}: {jsonl_path.name}")

        with open(jsonl_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        with open(output_path, 'w', encoding='utf-8') as out:
            for line in tqdm(lines, desc=f"{mode} 처리 중"):
                item = json.loads(line)
                asset_key = "question_assets" if mode == "questions" else "solution_assets"
                
                if item.get(asset_key):
                    # 💡 수정된 부분: 이미지 경로를 정확히 가져옴
                    asset = item[asset_key][0]
                    abs_img_path = Path(asset['path']) 

                    if not abs_img_path.exists():
                        # 상대 경로일 경우를 대비해 OUT_ROOT와 결합 시도
                        abs_img_path = OUT_ROOT.parent / asset['path']

                    prompt = (
                        "너는 수학 교육 전문가야. 이 이미지에 있는 수학 내용을 "
                        "LaTeX 수식을 사용하여 단계별로 친절하게 설명해줘."
                    )

                    try:
                        # 💡 이미지를 바이너리로 읽어서 Ollama에 전달
                        if abs_img_path.exists():
                            with open(abs_img_path, 'rb') as img_file:
                                img_data = img_file.read()

                            response = ollama.chat(
                                model=MODEL_NAME,
                                messages=[{
                                    'role': 'user',
                                    'content': prompt,
                                    'images': [img_data] 
                                }]
                            )
                            
                            content = response['message']['content']
                            
                            # 모델의 환각(이미지 없음 대답) 체크
                            if "이미지" in content and "없" in content:
                                print(f"\n⚠️ 경고: 모델이 이미지를 인식하지 못한 것 같습니다 ({item['id']})")
                            
                            # 필드명 결정 (question_text_llm 또는 solution_text_llm)
                            field_name = "question_text_llm" if mode == "questions" else "solution_text_llm"
                            item[field_name] = content
                        else:
                            print(f"\n❌ 파일을 찾을 수 없음: {abs_img_path}")

                    except Exception as e:
                        print(f"\n❌ API 에러: {e}")
                
                out.write(json.dumps(item, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    # 두 모드 모두 순차적으로 실행되도록 변경
    refine_with_image("questions")
    refine_with_image("solutions")