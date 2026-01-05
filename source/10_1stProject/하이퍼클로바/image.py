import torch
import torch_directml
from transformers import AutoModelForCausalLM, AutoProcessor

# DirectML 디바이스 (라데온 GPU 활용)
device = torch_directml.device()

# 모델과 프로세서 로드
model_name = "naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B"
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    trust_remote_code=True
).to(device)

processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

# 대화 템플릿: 이미지 + 텍스트 지시어
vlm_chat = [
    {
        "role": "system",
        "content": [{"type": "text", "text": "너는 수학 문제 풀이 도우미야. 단계별로 풀이 과정을 설명해."}]
    },
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": "math_problem.png",   # 로컬 이미지 파일 (예: 시험지 사진)
                "filename": "math_problem.png",
                "ocr": "이미지 속 수학 문제를 읽고 텍스트로 변환해 풀이해줘."
            },
            {
                "type": "text",
                "text": "이 문제를 단계별로 풀어줘."
            }
        ]
    }
]

# 입력 변환
model_inputs = processor.apply_chat_template(
    vlm_chat,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
    add_generation_prompt=True
).to(device)

# 모델 실행
with torch.no_grad():
    output_ids = model.generate(
        **model_inputs,
        max_new_tokens=256,
        do_sample=False,
        temperature=0.0,
        repetition_penalty=1.1
    )

# 결과 출력
print(processor.batch_decode(output_ids, skip_special_tokens=True)[0])
