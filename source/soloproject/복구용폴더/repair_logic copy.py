import os
import django
import sys
import time
from transformers import NougatProcessor, VisionEncoderDecoderModel
from PIL import Image
import torch
from django.db.models import Q

# ==========================================
# 1. Django 환경 초기화
# ==========================================
sys.path.append(os.path.dirname(os.path.abspath(__file__)) + "/..")
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'makeQnS.settings')
django.setup()

from preprocessing.models import MockExamQuestion

def pick_torch_device(prefer_gpu: bool = True):
    """
    우선순위:
    1) CUDA (NVIDIA)
    2) DirectML (AMD/Intel on Windows) - torch-directml 설치 시
    3) CPU
    """
    if prefer_gpu and torch.cuda.is_available():
        return "cuda", None

    # (선택) Windows에서 AMD GPU 쓰려면 torch-directml
    if prefer_gpu:
        try:
            import torch_directml
            dml = torch_directml.device()
            return "dml", dml
        except Exception:
            pass

    return "cpu", None

# ==========================================
# 2. 수선 로직 클래스
# ==========================================
class QuestionRepairer:
    def __init__(self):
        self.device_kind, self.dml_device = pick_torch_device(prefer_gpu=True)
        self.model_name = "facebook/nougat-small"
        print(f"[{self.device_kind}] 모델 로딩 중: {self.model_name}...")
        
        self.processor = NougatProcessor.from_pretrained(self.model_name)
        self.model = VisionEncoderDecoderModel.from_pretrained(self.model_name).to(self.device_kind)

        if self.device_kind == "cuda":
            self.model = self.model.to("cuda")
        elif self.device_kind == "dml":
            self.model = self.model.to(self.dml_device)  # ✅ 핵심
        else:
            self.model = self.model.to("cpu")

        self.model.eval()

        print("✅ 모델 로딩 완료!")

    def repair_single_question(self, question_obj):
        assets = question_obj.images.all()
        if not assets:
            return None

        try:
            # 1. 모든 유효 이미지 열기
            valid_images = []
            for asset in assets:
                if os.path.exists(asset.image_path):
                    valid_images.append(Image.open(asset.image_path).convert("RGB"))
            
            if not valid_images:
                print(f"\n⚠️ 이미지를 찾을 수 없음: {question_obj.question_id}")
                return None

            # 2. 이미지가 여러 개라면 세로로 합치기
            if len(valid_images) > 1:
                widths, heights = zip(*(i.size for i in valid_images))
                max_width = max(widths)
                total_height = sum(heights)
                combined_img = Image.new('RGB', (max_width, total_height), (255, 255, 255))
                y_offset = 0
                for im in valid_images:
                    combined_img.paste(im, (0, y_offset))
                    y_offset += im.size[1]
                final_img = combined_img
            else:
                final_img = valid_images[0]

            # 3. AI 추론
            pixel_values = self.processor(final_img, return_tensors="pt").pixel_values
            if self.device_kind == "cuda":
                pixel_values = pixel_values.to("cuda")
            elif self.device_kind == "dml":
                pixel_values = pixel_values.to(self.dml_device)
            else:
                pixel_values = pixel_values.to("cpu")
            outputs = self.model.generate(
                pixel_values,
                min_length=1,
                max_new_tokens=200,
                bad_words_ids=[[self.processor.tokenizer.unk_token_id]],
            )
            
            latex_text = self.processor.batch_decode(outputs, skip_special_tokens=True)[0]
            return self.processor.post_process_generation(latex_text)
            
        except Exception as e:
            print(f"\n❌ AI 변환 중 오류 ({question_obj.question_id}): {e}")
            return None

# ==========================================
# 3. 전체 실행 함수
# ==========================================
def run_auto_repair():
    repairer = QuestionRepairer()
    targets = MockExamQuestion.objects.filter(Q(cleaned_latex__isnull=True) | Q(cleaned_latex=""))
    total_count = targets.count()
    
    if total_count == 0:
        print("✨ 모든 문제가 수선되어 있습니다.")
        return

    print(f"🚀 총 {total_count}개의 문제를 수선하기 시작합니다.")

    for idx, q in enumerate(targets, 1):
        print(f"[{idx}/{total_count}] 수선 중: {q.question_id}...", end="\r")
        
        result = repairer.repair_single_question(q)
        
        if result:
            # DB 잠금 대비 재시도 로직
            for i in range(5):
                try:
                    q.cleaned_latex = result
                    q.save()
                    break
                except Exception as e:
                    if 'locked' in str(e).lower():
                        time.sleep(1)
                    else:
                        print(f"\n저장 실패: {e}")
                        break
        else:
            # 실패 시 빈 문자열이라도 넣어 다음 루프 때 건너뛰게 하려면 아래 주석 해제
            # q.cleaned_latex = "ERROR"
            # q.save()
            pass

if __name__ == "__main__":
    run_auto_repair()