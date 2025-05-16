from fastapi import FastAPI
import sys
import os
import google.generativeai as genai
from fastapi.responses import FileResponse

# FastAPI 애플리케이션 초기화
app = FastAPI()

# Generative Model 초기화
model = None

# 환경 변수에서 API 키 가져오기
api_key = os.getenv('GEMINI_API_KEY')
if api_key is None:
    raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")

# Gemini API 초기화 함수 정의
def configure_genai(api_key: str):
    global model
    model = genai.GenerativeModel('gemini-1.5-flash')
    genai.configure(api_key=api_key)  # API 키를 사용하여 Gemini API 설정

# Gemini API 초기화
configure_genai(api_key)

# 홈 페이지 엔드포인트
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
    """
    주어진 지역과 연도에 대해 추천 작물을 제공하는 엔드포인트
    """
    prompt = f"{year}년 기준 {region} 지역에서 기후 변화에 잘 적응하고 수익성이 높은 작물 3가지를 추천해 주세요. " \
             f"작물마다 추천 이유도 함께 설명해 주세요. 답변은 한국어로 해주세요."
    response = model.generate_content(prompt)

    return {"recommended_crops": response.text}

# 병해충 예측 엔드포인트
@app.get("/pest_prediction/")
async def get_pest_prediction(crop: str, region: str, year: int, month: str):
    """
    주어진 작물, 지역, 연도, 월에 대해 병해충 발생 가능성 및 대응 정보를 제공
    """
    prompt = f"{year}년 {month} 기준 {region} 지역의 {crop} 재배 시 발생할 수 있는 병해충을 예측하고, " \
             f"대응 방법과 예방 전략을 한국어로 설명해 주세요."
    response = model.generate_content(prompt)

    return {"predicted_pests": response.text}

# 기후 시나리오 안내 엔드포인트
@app.get("/climate_scenario/")
async def get_climate_scenario(region: str, year: int):
    """
    지역과 연도 기반 기후 변화 시나리오 및 작물 추천 제공
    """
    prompt = f"{year}년 {region} 지역의 기후 변화 시나리오를 설명하고, 이에 적합한 작물을 추천해 주세요. " \
             f"답변은 한국어로 해주세요."
    response = model.generate_content(prompt)

    return {"climate_scenario": response.text}

# 서버 실행
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
