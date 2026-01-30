import os
import json
import sys
import django


sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
# 1. Django 환경 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makeQnS.settings') # 프로젝트명 확인!
django.setup()

from preprocessing.models import MockExamQuestion, QuestionImage

def import_jsonl_data():
    
    base_path = r"C:\ai\source\soloproject\output\questions\jsonl" # 경로 수정
    print(f"탐색 시작 경로: {base_path}")
    
    count = 0
    # 이제 g1, g2, g3가 jsonl 폴더 안에 자식으로 있으므로:
    for grade in ['g1', 'g2', 'g3']:
        target_dir = os.path.join(base_path, grade) # 학년 폴더가 바로 아래 있음
        print(f"체크 중인 폴더: {target_dir}")
        
        if not os.path.exists(target_dir):
            print(f"❌ 폴더를 찾을 수 없음: {target_dir}")
            continue
            
        for file_name in os.listdir(target_dir):
            if file_name.endswith('.jsonl'):
                file_path = os.path.join(target_dir, file_name)
                print(f"📂 읽는 중: {file_name}")
                
                # 파일명(2020_3_...)에서 연도/월 추출
                try:
                    name_parts = file_name.split('_')
                    year = int(name_parts[0])
                    month = int(name_parts[1])
                except (ValueError, IndexError):
                    print(f"⚠️ 파일명 형식 이상: {file_name}")
                    continue
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        data = json.loads(line)
                        
                        # 문제 데이터 저장
                        question, created = MockExamQuestion.objects.update_or_create(
                            question_id=data['id'],
                            defaults={
                                'grade': int(grade[1]), # 'g1'에서 '1' 추출
                                'year': year,
                                'month': month,
                                'raw_text': data['question_text'],
                            }
                        )
                        
                        # 이미지 경로 저장
                        for asset in data.get('assets', []):
                            # 이미지 경로도 jsonl 상위의 images 폴더에 있다면 확인 필요!
                            # 일단 JSONL에 적힌 상대 경로를 기반으로 절대 경로 생성
                            abs_img_path = os.path.abspath(os.path.join(r"C:\ai\source\soloproject", asset['path']))
                            QuestionImage.objects.get_or_create(
                                question=question,
                                image_path=abs_img_path
                            )
                        count += 1

    print(f"\n✅ 총 {count}개의 데이터가 DB에 입고되었습니다!")

def import_all_jsonls():
    base_path = r"C:\ai\source\soloproject\output\questions"
    print(f"탐색 시작 경로: {base_path}") # 추가
    
    count = 0
    for grade in ['g1', 'g2', 'g3']:
        target_dir = os.path.join(base_path, grade, 'jsonl')
        print(f"체크 중인 폴더: {target_dir}") # 추가
        
        if not os.path.exists(target_dir):
            print(f"❌ 폴더를 찾을 수 없음: {target_dir}") # 추가
            continue

if __name__ == "__main__":
    import_jsonl_data()
    # import_all_jsonls() # 경로확인용