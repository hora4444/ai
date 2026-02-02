import os
import re
import pytesseract
from PIL import Image
from pytesseract import Output
from pathlib import Path

# 1. 실행 파일 경로
TESS_ROOT = r'C:\Users\Admin\Tesseract-OCR'
pytesseract.pytesseract.tesseract_cmd = os.path.join(TESS_ROOT, 'tesseract.exe')

# 2. [가장 중요] 환경 변수 삭제 및 경로 직접 지정
# 시스템에 설정된 잘못된 환경 변수가 방해하지 못하도록 삭제합니다.
if 'TESSDATA_PREFIX' in os.environ:
    del os.environ['TESSDATA_PREFIX']

# 3. 경로 구분자를 역슬래시 2개(\\)로 통일 (윈도우 표준 방식)
TESSDATA_DIR = r'C:\Users\Admin\Tesseract-OCR\tessdata'

def get_anchors_via_ocr_ultra_safe(img_path):
    img = Image.open(img_path)
    w, h = img.size
    
    # [핵심 변경] 조각을 더 많이(10개), 더 많이 겹치게(1000px)
    num_splits = 10
    split_h = h // num_splits
    overlap = 1000   
    anchors = []

    TESSDATA_DIR = r'C:\Users\Admin\Tesseract-OCR\tessdata'
    # 윈도우 경로 에러 방지를 위해 따옴표 없이 설정
    cfg = f'--tessdata-dir {TESSDATA_DIR} --psm 6'

    for i in range(num_splits):
        # 겹침 로직: 이전/다음 구역과 1000픽셀씩 공유함
        y_offset = max(0, i * split_h - overlap)
        y_end = min(h, (i + 1) * split_h + overlap)
        
        part_img = img.crop((0, y_offset, w, y_end))
        print(f"      -> {i+1}/{num_splits} 구역 분석 중...")
        
        try:
            d = pytesseract.image_to_data(
                part_img, lang='kor+eng', config=cfg, output_type=Output.DICT
            )
            
            for j in range(len(d['level'])):
                text = d['text'][j].strip()
                # 키워드 필터 완화: '출제', '의도' 외에 숫자가 바로 붙어있는 경우도 탐색
                if any(key in text for key in ["출제", "의도", "해설", "정답", "풀이", "[", "【"]):
                    qnum = None
                    # 숫자 찾기 범위를 주변 15개 단어로 확장
                    for k in range(max(0, j-15), min(len(d['text']), j+15)):
                        word = d['text'][k].strip()
                        nums = re.findall(r'\d+', word)
                        if nums:
                            val = int(nums[0])
                            if 1 <= val <= 30:
                                qnum = val
                                break
                    
                    if qnum:
                        anchors.append({"qnum": qnum, "y": d['top'][j] + y_offset})
        except Exception as e:
            print(f"      [구역 {i+1} 오류] {e}")

    # 중복 제거 및 보정 (Y좌표 순서대로 정렬 후 근접한 좌표 제거)
    anchors.sort(key=lambda x: x['y'])
    unique_anchors = []
    seen_qnums = set()
    for a in anchors:
        if a['qnum'] not in seen_qnums:
            # 같은 문항이 겹침 구간에서 두 번 발견되면 첫 번째(위쪽) 것만 선택
            unique_anchors.append(a)
            seen_qnums.add(a['qnum'])
            
    print(f"      [결과] 총 {len(unique_anchors)}개 문항 좌표 확보")
    missing = [i for i in range(1, 31) if i not in seen_qnums]
    if missing:
        print(f"      [미인식 번호] {missing}")
        
    return unique_anchors

def split_with_ocr_anchors(img_path, out_dir, meta, anchors):
    """찾은 좌표를 기반으로 실제 이미지를 자릅니다."""
    img = Image.open(img_path)
    w, h = img.size
    sol_assets = {}
    rel_folder = f"assets/solutions/g{meta['grade']}/{meta['year']}_{meta['month']}"
    target_dir = out_dir / rel_folder
    target_dir.mkdir(parents=True, exist_ok=True)

    if not anchors:
        print("      [주의] 좌표를 찾지 못해 균등 분할합니다.")
        unit = h / 30
        for i in range(1, 31):
            y0, y1 = (i-1)*unit, i*unit
            crop = img.crop((0, y0, w, y1))
            crop.save(target_dir / f"q{i:02d}.png")
            sol_assets[i] = [f"{rel_folder}/q{i:02d}.png"]
        return sol_assets

    for i, curr in enumerate(anchors):
        qnum = curr['qnum']
        y0 = max(0, curr['y'] - 30) # 여백 확보
        y1 = anchors[i+1]['y'] - 30 if i+1 < len(anchors) else h
        y1 = min(y1, h)
        
        if y1 > y0:
            crop = img.crop((0, y0, w, y1))
            fname = f"q{qnum:02d}.png"
            crop.save(target_dir / fname)
            sol_assets[qnum] = [f"{rel_folder}/{fname}"]
            
    return sol_assets

def main():
    ROOT = Path("data")
    OUT = Path("output")
    OUT.mkdir(exist_ok=True)

    # '해설'이 포함되지 않은 PDF(문제지) 목록 가져오기
    prob_files = [p for p in ROOT.rglob("*.pdf") if "해설" not in p.name]

    for p_path in prob_files:
        print(f"\n>>> [작업 시작] {p_path.name}")
        
        # --- [핵심 수정] 파일명에서 정보 추출 ---
        # 예: "2021학년도11월학평(경기)" -> year=2021, month=11
        file_name = p_path.stem
        
        try:
            # 정규식으로 숫자만 뽑아내기
            years = re.findall(r'(\d{4})학년도', file_name)
            months = re.findall(r'(\d{1,2})월', file_name)
            
            year = years[0] if years else "2020" # 기본값
            month = f"{int(months[0]):02d}" if months else "11"
            grade = "1" # 필요시 파일명에서 '고1' 등을 찾아 추출 가능
        except Exception as e:
            print(f"      [주의] 파일명 파싱 실패, 기본값 사용: {e}")
            year, month, grade = "2020", "11", "1"

        # 파일마다 고유한 메타데이터 생성
        meta = {"year": year, "month": month, "grade": grade}
        print(f"      [분류] {year}년 {month}월 고{grade}")

        # 해설 PNG 찾기 (문제지명 + "해설.png")
        sol_img_path = p_path.with_name(p_path.stem + "해설.png")
        
        if not sol_img_path.exists():
            print(f"      [스킵] 해설 이미지가 없습니다: {sol_img_path.name}")
            continue

        # 분석 및 분할 실행
        anchors = get_anchors_via_ocr_ultra_safe(str(sol_img_path))
        
        # split_with_ocr_anchors 함수 안에서 meta를 사용해 폴더를 만듭니다.
        if anchors:
            split_with_ocr_anchors(str(sol_img_path), OUT, meta, anchors)
            print(f"      [완료] {p_path.name} 저장 성공")
            
if __name__ == "__main__":
    main()