from fastapi import FastAPI
import os
import google.generativeai as genai
from fastapi.responses import FileResponse
import re

# FastAPI 앱 초기화
app = FastAPI()

# 모델 초기화
model = None
api_key = os.getenv('GEMINI_API_KEY')
if api_key is None:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

def configure_genai(api_key: str):
    global model
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

configure_genai(api_key)

# 작물 추천 응답 파싱 함수
def parse_crop_recommendation(text: str):
    lines = re.findall(r"\d+\.\s*([^\n:]+)[\s:：]+(.+?)(?=\n\d+\.|\Z)", text, re.DOTALL)
    return [{"crop": crop.strip(), "reason": reason.strip()} for crop, reason in lines]


# 작물 추천 응답 파싱 함수
def parse_pest_prediction(text: str):
    # 응답에서 각 병해충 블록을 추출 (마크다운 형식으로 출력된 내용 처리)
    # 참고 부분을 제외하기 위해 패턴 수정
    blocks = re.findall(r'(\d+\.\s*\*\*[^*]+\*\*\s*[\s\S]+?)(?=\d+\.\s*\*\*|\*\*참고:|\Z)', text, re.MULTILINE)
    
    result = []
    for block in blocks:
        # 병해충명 - 앞뒤의 ** 제거
        pest_match = re.search(r'\d+\.\s*\*\*([^*]+)\*\*', block)
        pest = pest_match.group(1).strip() if pest_match else "알 수 없음"

        # 상세한 설명 추출
        desc_match = re.search(r'\*\s*\*\*상세한\s*설명:\*\*\s*([\s\S]+?)(?=\s*\*\s*\*\*대응\s*방법:)', block)

        # 대응 방법 추출
        response_match = re.search(r'\*\s*\*\*대응\s*방법:\*\*\s*([\s\S]+?)(?=\s*\*\s*\*\*예방\s*전략:)', block)

        # 예방 전략 추출
        prevention_match = re.search(r'\*\s*\*\*예방\s*전략:\*\*\s*([\s\S]+?)(?=\s*\*\s*\*\*위험\s*수준:)', block)

        # 위험 수준 추출
        risk_match = re.search(r'\*?\s*\*?\s*위험\s*수준\s*(?:\([^)]*\))?\s*[:：]\s*([\s\S]+?)(?=\n\s*\n|\Z)', block)

        # 결과 추출 및 정제
        description = desc_match.group(1).strip() if desc_match else "정보 없음"
        response = response_match.group(1).strip() if response_match else "정보 없음"
        prevention = prevention_match.group(1).strip() if prevention_match else "정보 없음"
        risk = risk_match.group(1).strip() if risk_match else "정보 없음"

        # 위험 수준에서 ** 마크 제거 (있는 경우)
        risk = re.sub(r'^\s*\*\*\s*|\s*\*\*\s*$', '', risk)

        # response와 prevention을 합쳐서 guide 필드로 생성
        guide = f"{response}\n\n{prevention}"

        result.append({
            "pest": pest,
            "description": description,
            "guide": guide,
            "riskLevel": risk
        })

    return result


def parse_climate_scenario(text: str):
    summary_match = re.search(r"Summary:\s*(.+?)(?=\nRecommendation:|\Z)", text, re.DOTALL)
    recommendation_match = re.search(r"Recommendation:\s*(.+)", text, re.DOTALL)

    summary = summary_match.group(1).strip() if summary_match else ""
    recommendation = recommendation_match.group(1).strip() if recommendation_match else ""

    return {
        "summary": summary,
        "recommendationNote": recommendation
    }

# 홈 페이지
@app.get("/")
async def root():
    return {"message": "Welcome to the Crop Recommendation API!"}

# favicon.ico 처리
@app.get("/favicon.ico")
async def favicon():
    return FileResponse(os.path.join(os.getcwd(), "favicon.ico"))

# 작물 추천 엔드포인트
@app.get("/crop_recommendation/")
async def get_crop_recommendation(region: str, year: int):
    prompt = f"{year}년 기준 {region} 지역에서 기후 변화에 잘 적응하고 수익성  높은 작물 3가지를 추천해줘. " \
             f"각 작물에 대해 추천 이유도 함께 짧게 설명해줘. 한국어로 번호 목록 형식으로 짧게 답변해줘."
    response = model.generate_content(prompt)
    parsed = parse_crop_recommendation(response.text)
    return {"recommended_crops": parsed}

# 병해충 예측 엔드포인트
@app.get("/pest_prediction/")
async def get_pest_prediction(crop: str, region: str, si: str, year: int, month: str):
    full_location = f"{region} {si}"
    prompt = f"""{year}년 {month} 기준 {full_location} 지역의 {crop} 재배 시 발생할 수 있는 주요 병해충 3가지를 예측하고
             각 병해충에 대해 상세한 설명, 짧은 대응 방법, 예방 전략, 위험 수준(위험/주의요망/양호)을 포함해서 한국어로 번호 목록 형식으로 정리해 주세요.
    각 항목은 다음과 같이 짧게 구성:
    1. 병해충명
    * 상세한 설명:
    * 대응 방법: 
    * 예방 전략:
    * 위험 수준 (위험 / 주의요망 / 양호):
    """
    response = model.generate_content(prompt)
    parsed = parse_pest_prediction(response.text)
    # print(response.text)
    return {"predicted_pests": parsed}

# 기후 시나리오 안내
@app.get("/climate_scenario/")
async def get_climate_scenario(region: str, year: int):
    prompt = f"""
    {year}년 {region} 지역의 기후 변화 시나리오를 짧게 요약하고, 그에 따른 작물 재배 전략 및 대응 방안을 아래 형식에 맞춰 한국어로 짧게  작성해줘.
    형식:
    Summary: [한 문장 요약]
    Recommendation: [한 문장 대응 전략]
    """
    response = model.generate_content(prompt)
    parsed = parse_climate_scenario(response.text)
    return parsed

# 로컬 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
