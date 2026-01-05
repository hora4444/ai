from flask import Flask, request, jsonify
import torch
import torch_directml
from transformers import AutoModelForCausalLM, AutoProcessor

app = Flask(__name__)

# DirectML 디바이스
device = torch_directml.device()

# 모델 로드
model_name = "naver-hyperclovax/HyperCLOVAX-SEED-Vision-Instruct-3B"
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype=torch.float16, trust_remote_code=True).to(device)
processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)

@app.route("/solve", methods=["POST"])
def solve_math():
    # 텍스트와 이미지 입력 받기
    text_prompt = request.form.get("prompt", "")
    image_file = request.files.get("image")

    vlm_chat = [
        {"role": "system", "content": [{"type": "text", "text": "너는 수학 문제 풀이 도우미야. 단계별로 풀이 과정을 설명해."}]},
        {"role": "user", "content": []}
    ]

    if image_file:
        vlm_chat[1]["content"].append({
            "type": "image",
            "image": image_file,  # 파일 객체 그대로 전달 가능
            "filename": image_file.filename,
            "ocr": "이미지 속 수학 문제를 읽고 풀이해줘."
        })
    if text_prompt:
        vlm_chat[1]["content"].append({"type": "text", "text": text_prompt})

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
        output_ids = model.generate(**model_inputs, max_new_tokens=256, do_sample=False, temperature=0.0)

    result = processor.batch_decode(output_ids, skip_special_tokens=True)[0]
    return jsonify({"result": result})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)


# POST /solve 엔드포인트에 prompt(텍스트)와 image(파일)로 요청을 보내면 결과를 JSON으로 반환합니다.