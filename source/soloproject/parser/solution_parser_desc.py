import os
import re
import json
import ollama
from pathlib import Path
from PIL import Image

# --- [설정 구간] ---
BASE_DIR = Path(r"C:\ai\source\soloproject")
RAW_IMG_DIR = BASE_DIR / "data\고1"
JSONL_DIR = BASE_DIR / "output\jsonl\solutions\g1"
MODEL_NAME = "qwen3-vl:2b"
SLICE_HEIGHT = 1200
OVERLAP = 150

def process_single_file(image_path):
    """파일 하나를 조각내고 OCR해서 텍스트 반환"""
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    full_text = ""
    
    curr_y = 0
    idx = 0
    while curr_y < height:
        end_y = min(curr_y + SLICE_HEIGHT, height)
        chunk = img.crop((0, curr_y, width, end_y))
        tmp_name = f"tmp_{os.path.basename(image_path)}_{idx}.png"
        chunk.save(tmp_name)
        
        try:
            res = ollama.chat(
                model=MODEL_NAME,
                messages=[{'role': 'user', 'content': '수학 해설 LaTeX 변환. 번호 생략 금지.', 'images': [tmp_name]}]
            )
            full_text += "\n" + res['message']['content']
        finally:
            if os.path.exists(tmp_name): os.remove(tmp_name)
        
        if end_y == height: break
        curr_y += (SLICE_HEIGHT - OVERLAP)
        idx += 1
    return full_text

def backward_slicing(full_text, q_nums):
    """통합 텍스트를 내림차순(30->1)으로 잘라냄"""
    sorted_nums = sorted(q_nums, reverse=True)
    parsed_data = {}
    current_pool = full_text

    for num in sorted_nums:
        # 다양한 앵커 패턴 대응 (29. [출제의도] 또는 29. [풀이] 등)
        pattern = rf"({num}\s*[\.\s]*\[(?:출제의도|풀이|해설)\]|{num}\.\s*\n)"
        matches = list(re.finditer(pattern, current_pool))
        
        if matches:
            last_match = matches[-1] # 내림차순이므로 가장 뒤에 있는 앵커 선택
            split_idx = last_match.start()
            parsed_data[num] = current_pool[split_idx:].strip()
            current_pool = current_pool[:split_idx] # 윗부분은 남겨서 다음 루프로
        else:
            parsed_data[num] = ""
            
    return parsed_data

def main():
    # 1. 이미지 파일 목록 가져오기
    img_files = list(RAW_IMG_DIR.glob("*.jpg")) + list(RAW_IMG_DIR.glob("*.png"))
    
    for img_path in img_files:
        print(f"\n🚀 파일 처리 시작: {img_path.name}")
        
        # 2. 파일 하나에 대한 전체 텍스트 추출
        file_text = process_single_file(img_path)
        
        # 3. 파일명에서 연도 추출 (예: 2020_11_... -> 2020_11)
        # 파일명 규칙에 따라 이 부분을 수정하세요.
        match = re.search(r"(\d{4}_\d{2})", img_path.name)
        if not match: 
            print(f"⚠️ 파일명에서 연도를 찾을 수 없음: {img_path.name}")
            continue
        year_str = match.group(1)
        
        # 4. 해당 연도의 JSONL 로드
        jsonl_path = JSONL_DIR / f"{year_str}_common_solution.jsonl"
        if not jsonl_path.exists():
            print(f"⚠️ JSONL 파일 없음: {jsonl_path}")
            continue
            
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            json_data = [json.loads(line) for line in f]
        
        q_nums = [item["question_number"] for item in json_data]

        # 5. 내림차순 파싱 (이 파일 안의 내용만 잘라냄)
        print(f"✂️ {year_str} 데이터 파싱 중...")
        solution_map = backward_slicing(file_text, q_nums)

        # 6. 즉시 업데이트 및 저장 (기존 파일 덮어쓰기 또는 fixed 생성)
        output_path = JSONL_DIR / f"{year_str}_common_solution_fixed.jsonl"
        with open(output_path, 'w', encoding='utf-8') as f:
            for item in json_data:
                q_num = item["question_number"]
                if solution_map.get(q_num): # 이번 파일에서 찾은 해설이 있다면 업데이트
                    item["solution_text"] = solution_map[q_num]
                    item["ocr_ok"] = True
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        
        print(f"✅ {img_path.name} 처리 및 저장 완료!")

if __name__ == "__main__":
    main()