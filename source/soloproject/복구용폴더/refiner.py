import ollama
import json
import base64
from pathlib import Path
from tqdm import tqdm

OUT_ROOT = Path("output")
MODEL_NAME = "seed-vision"

def refine_with_image(mode="solutions"):
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
                    asset = item[asset_key][0]
                    # 경로 문제 방지를 위해 절대 경로로 변환
                    img_rel_path = asset['path'] if isinstance(asset, dict) else asset
                    abs_img_path = (OUT_ROOT / img_rel_path).resolve()
                    
                    if abs_img_path.exists():
                        prompt = (
                            "너는 수학 교육 전문가야. 이 이미지에 있는 수학 내용을 "
                            "LaTeX 수식을 사용하여 단계별로 친절하게 설명해줘."
                        )

                        try:
                            # 💡 이미지를 직접 바이너리로 읽어서 전달 (가장 확실함)
                            with open(abs_img_path, 'rb') as img_file:
                                img_data = img_file.read()

                            response = ollama.chat(
                                model=MODEL_NAME,
                                messages=[{
                                    'role': 'user',
                                    'content': prompt,
                                    'images': [img_data] # 경로 대신 이미지 바이너리 데이터 전달
                                }]
                            )
                            
                            content = response['message']['content']
                            # 만약 모델이 "이미지가 없다"는 식으로 대답했다면 로그 출력
                            if "이미지" in content and "없" in content:
                                print(f"\n⚠️ 경고: 모델이 이미지를 인식하지 못한 것 같습니다 ({item['id']})")
                            
                            item[f"{mode[:-1]}_text_llm"] = content
                            
                        except Exception as e:
                            print(f"\n❌ API 에러: {e}")
                
                out.write(json.dumps(item, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    refine_with_image("solutions")