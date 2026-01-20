import os
import fitz
import re

def parse_exam_filename(filename: str):
    m_year = re.search(r"(\d{2})학년도", filename)
    if not m_year:
        return None
    year = int(m_year.group(1)) + 2000

    m_month = re.search(r"(\d{1,2})월", filename)
    if not m_month:
        # 예: 수능 파일, 예비시행 등 (월이 없는 케이스)
        return None
    month = int(m_month.group(1))

    if "미적분" in filename:
        track = "calculus"
    elif "기하" in filename:
        track = "geometry"
    elif "확률과통계" in filename:
        track = "probability"
    else:
        track = "common"

    return {
        "grade": 3,
        "year": year,
        "month": month,
        "track": track
    }

QUESTION_RE = re.compile(r"^\s*(\d{1,2})\.")

def extract_questions(pdf_path):
    doc = fitz.open(pdf_path)
    questions = {}
    current_q = None

    for page in doc:
        lines = page.get_text("text").splitlines()
        for line in lines:
            m = QUESTION_RE.match(line)
            if m:
                qnum = int(m.group(1))
                current_q = qnum
                questions[current_q] = line + "\n"
            elif current_q:
                questions[current_q] += line + "\n"

    return questions


def build_items(pdf_path, filename):
    meta = parse_exam_filename(filename)
    questions = extract_questions(pdf_path)

    items = []
    for qnum, text in questions.items():
        items.append({
            "id": f"g3_{meta['year']}_{meta['month']}_{meta['track']}_q{qnum}",
            **meta,
            "question_number": qnum,
            "is_common": qnum <= 22,
            "question_text": text.strip(),
            "choices": []
        })

    return items

PDF_DIR = r"C:\ai\source\soloproject\data\고3"

for filename in os.listdir(PDF_DIR):
    if not filename.endswith(".pdf"):
        continue

    pdf_path = os.path.join(PDF_DIR, filename)

    items = build_items(
        pdf_path=pdf_path,
        filename=filename
    )

    print(filename, len(items))
