# run_math_with_directml.py
import torch
import torch_directml
from transformers import AutoTokenizer, AutoModelForCausalLM

def get_device():
    # DirectML 장치를 가져옵니다 (AMD/NVIDIA/Intel 모두 지원)
    return torch_directml.device()

def load_model(model_name: str, device):
    tokenizer = AutoTokenizer.from_pretrained(model_name, use_fast=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        torch_dtype=torch.float16,     # FP16으로 메모리 절약
    )
    # 모델을 DirectML 디바이스로 이동
    model.to(device)
    model.eval()
    return tokenizer, model

def generate_math_solution(tokenizer, model, device, prompt: str, max_new_tokens: int = 512):
    inputs = tokenizer(prompt, return_tensors="pt")
    # 입력 텐서를 DirectML로 이동
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,            # 수학 문제는 결정적 출력을 권장
            temperature=0.0,
            top_p=1.0,
            repetition_penalty=1.1,     # 중복 감소
        )
    text = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    return text

if __name__ == "__main__":
    model_name = "naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B"
    device = get_device()
    tokenizer, model = load_model(model_name, device)

    # 수학 문제 프롬프트 예시 (단계별 풀이 지시 포함)
    user_problem = "문제: x^2 + 3x + 2 = 0 을 풀어줘. 각 단계의 이유를 문장으로 설명해줘."
    system_style = (
        "역할: 너는 한국어로 답하는 수학 풀이 도우미야.\n"
        "지시: 문제를 단계별로 해결하고, 각 단계의 근거를 간결히 설명해.\n"
        "지시: 최종 답을 명확히 분리해 제시해.\n"
        "형식: 풀이, 검산, 최종답 섹션으로 나눠 작성."
    )
    prompt = f"{system_style}\n\n{user_problem}"

    result = generate_math_solution(tokenizer, model, device, prompt, max_new_tokens=400)
    print(result)
