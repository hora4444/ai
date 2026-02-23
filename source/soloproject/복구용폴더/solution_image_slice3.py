import os
from pathlib import Path
from PIL import Image, ImageOps
import numpy as np

# 1. 경로 설정
ORIGINAL_DIR = Path(r"C:\ai\source\soloproject\data\고1\해설\2020학년도3월학평(서울)")
SAFE_SPLIT_DIR = ORIGINAL_DIR / "safe_split_final"
SAFE_SPLIT_DIR.mkdir(exist_ok=True)

def find_safe_cut_line(image_np, target_y, search_range=200):
    """
    target_y 주변에서 픽셀 값이 모두 흰색(255)에 가까운 행을 찾습니다.
    """
    height, width = image_np.shape
    start = max(0, target_y - search_range)
    end = min(height, target_y + search_range)
    
    # 각 행의 평균 밝기 계산 (255에 가까울수록 흰색 여백)
    row_means = np.mean(image_np[start:end], axis=1)
    
    # 가장 밝은(흰색에 가까운) 행의 인덱스 찾기
    best_offset = np.argmax(row_means)
    return start + best_offset

def split_images_safely(num_parts=3):
    img_extensions = (".png", ".jpg", ".jpeg")
    image_files = [f for f in ORIGINAL_DIR.iterdir() if f.suffix.lower() in img_extensions]

    for img_path in image_files:
        with Image.open(img_path) as img:
            # 그레이스케일로 변환하여 여백 계산 최적화
            gray_img = ImageOps.grayscale(img)
            img_np = np.array(gray_img)
            
            width, height = img.size
            cut_points = [0]
            
            # 자를 지점 탐색
            for i in range(1, num_parts):
                target_y = (height // num_parts) * i
                safe_y = find_safe_cut_line(img_np, target_y)
                cut_points.append(safe_y)
            
            cut_points.append(height)
            
            # 실제 자르기 및 저장
            for i in range(len(cut_points) - 1):
                top = cut_points[i]
                bottom = cut_points[i+1]
                
                cropped_img = img.crop((0, top, width, bottom))
                save_name = f"{img_path.stem}_safe_{i+1}{img_path.suffix}"
                cropped_img.save(SAFE_SPLIT_DIR / save_name)
                
        print(f"✅ {img_path.name} -> 수식 보호 분할 완료")

def split_images_by_margin(img_path, max_height=1200):
    with Image.open(img_path) as img:
        gray_img = ImageOps.grayscale(img)
        img_np = np.array(gray_img)
        width, height = img.size
        
        start_y = 0
        part_idx = 1
        
        while start_y < height:
            # 남은 부분이 max_height보다 작으면 종료
            if start_y + max_height >= height:
                img.crop((0, start_y, width, height)).save(
                    SAFE_SPLIT_DIR / f"{img_path.stem}_p{part_idx}{img_path.suffix}")
                break
            
            # 자를 목표 지점
            target_y = start_y + max_height
            
            # 목표 지점 주변(위아래 300px)에서 가장 깨끗한 여백 찾기
            search_start = max(0, target_y - 300)
            search_end = min(height, target_y + 300)
            row_means = np.mean(img_np[search_start:search_end], axis=1)
            
            # 가장 흰색(255)에 가까운 행 선택
            best_offset = np.argmax(row_means)
            safe_cut_y = search_start + best_offset
            
            # 자르기 및 저장
            img.crop((0, start_y, width, safe_cut_y)).save(
                SAFE_SPLIT_DIR / f"{img_path.stem}_p{part_idx}{img_path.suffix}")
            
            start_y = safe_cut_y
            part_idx += 1

if __name__ == "__main__":
    split_images_safely(num_parts=3)