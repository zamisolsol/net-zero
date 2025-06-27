from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, validator
import logging
import os
import json
from pathlib import Path
from openai import AzureOpenAI
from typing import Dict, Any

def load_local_settings():
    """
    local.settings.json 파일을 로드하여 환경변수로 설정
    """
    settings_file = Path("local.settings.json")
    
    if settings_file.exists():
        try:
            with open(settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                
            # Values 섹션의 모든 키-값을 환경변수로 설정
            if "Values" in settings:
                for key, value in settings["Values"].items():
                    os.environ[key] = str(value)
                    
            logging.info("✅ local.settings.json 파일을 성공적으로 로드했습니다.")
            
        except Exception as e:
            logging.warning(f"⚠️ local.settings.json 파일 로드 실패: {str(e)}")
    else:
        logging.info("ℹ️ local.settings.json 파일이 없습니다. 환경변수를 직접 사용합니다.")

# local.settings.json 로드
load_local_settings()

app = FastAPI(title="AI 택배 박스 추천 API", version="2.0.2")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic 모델 정의
class PackageRequest(BaseModel):
    width: float
    length: float
    height: float
    
    @validator('width', 'length', 'height')
    def validate_positive(cls, v):
        if v <= 0:
            raise ValueError('크기는 0보다 큰 값이어야 합니다.')
        return v

class PackageResponse(BaseModel):
    success: bool
    data: Dict[str, Any] = None
    error: str = None
    error_code: str = None

def recommend_ho(width: float, length: float, height: float) -> str:
    """
    물체 크기에 맞는 우체국 택배 박스 호수를 추천하는 함수
    Azure OpenAI를 사용해서 AI가 최적의 박스를 선택
    """
    prompt = f'''
너는 포장 전문가야. 아래는 물체의 실제 크기(mm 단위)이며, 해당 물체가 가장 잘 들어갈 수 있는 우체국 택배 박스 호수를 추천해야 해.

📦 우체국 택배 박스 규격 (단위: mm):
1호: 220 x 190 x 90
2호: 270 x 180 x 150
3호: 350 x 250 x 100
4호: 340 x 250 x 210
5호: 410 x 310 x 280
6호: 520 x 380 x 340
7호: 520 x 480 x 400
8호: 620 x 480 x 400

📐 물체 크기:
가로: {width}mm
세로: {length}mm
높이: {height}mm

조건:
- 물체는 박스보다 각 변(가로, 세로, 높이)이 작거나 같아야 함
- 가장 작은 박스를 추천할 것
- 여유 공간을 고려하여 약간의 마진을 둘 것
- 결과는 **호수 이름만** 출력 (예: "1호", "2호", "7호" 등)
- 다른 말은 절대 출력하지 마
- 만약 모든 박스에 안 들어가면 "특수 포장"이라고 답해

정답:
'''

    try:
        # 환경변수에서 Azure OpenAI 설정 가져오기
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        
        if not api_key or not endpoint:
            raise ValueError("Azure OpenAI 설정이 누락되었습니다. API_KEY 또는 ENDPOINT를 확인하세요.")
        
        # 클라이언트 생성
        client = AzureOpenAI(
            api_key=api_key,
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_endpoint=endpoint
        )
        
        logger.info(f"🤖 Azure OpenAI API 호출 시작 - 물체 크기: {width}x{length}x{height}mm")
        
        # 메시지 구성
        messages = [
            {"role": "system", "content": "너는 포장 추천 전문가야. 정확한 박스 호수만 답변해."},
            {"role": "user", "content": prompt}
        ]
        
        # 모델명 확인
        model_name = os.environ.get("AZURE_OPENAI_MODEL", "gpt-4")
        logger.info(f"🧠 사용 모델: {model_name}")
        
        # API 호출 - 기본 파라미터만 사용
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
        except Exception as api_error:
            logger.error(f"❌ 첫 번째 API 호출 실패: {str(api_error)}")
            
            # 더 기본적인 파라미터로 재시도
            try:
                logger.info("🔄 temperature 없이 재시도...")
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages
                )
            except Exception as retry_error:
                logger.error(f"❌ 재시도도 실패: {str(retry_error)}")
                raise retry_error
        
        # 응답 처리
        result = response.choices[0].message.content.strip()
        logger.info(f"✅ AI 추천 결과: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Azure OpenAI API 호출 실패: {str(e)}")
        logger.error(f"❌ 에러 타입: {type(e).__name__}")
        raise e

@app.post("/recommend", response_model=PackageResponse)
async def recommend_package(request: PackageRequest):
    """
    AI 기반 택배 박스 추천 API 엔드포인트
    """
    logger.info('🚀 AI 박스 추천 요청 처리 시작')
    
    try:
        logger.info(f'📐 입력 물체 크기: {request.width}mm × {request.length}mm × {request.height}mm')
        
        # AI 박스 추천 함수 호출
        recommended_box = recommend_ho(request.width, request.length, request.height)
        
        logger.info(f'🎯 AI 추천 결과: {recommended_box}')
        
        # 추천 결과 검증
        valid_boxes = ["1호", "2호", "3호", "4호", "5호", "6호", "7호", "8호", "특수 포장"]
        if recommended_box not in valid_boxes:
            logger.warning(f"⚠️ 예상치 못한 AI 응답: {recommended_box}")
            # AI가 예상치 못한 답변을 한 경우 파싱 시도
            for box in valid_boxes:
                if box in recommended_box:
                    recommended_box = box
                    logger.info(f"🔧 파싱된 결과: {recommended_box}")
                    break
            else:
                # 파싱도 실패한 경우 특수 포장으로 처리
                recommended_box = "특수 포장"
                logger.warning(f"🔧 파싱 실패, 특수 포장으로 처리: {recommended_box}")
        
        # 성공 응답
        response_data = PackageResponse(
            success=True,
            data={
                "recommended_box": recommended_box,
                "input": {
                    "width": request.width,
                    "length": request.length,
                    "height": request.height
                },
                "ai_engine": "Azure OpenAI",
                "model": os.environ.get("AZURE_OPENAI_MODEL", "gpt-4")
            }
        )
        
        logger.info(f'✅ 응답 전송 완료: {recommended_box}')
        return response_data
        
    except ValueError as ve:
        # 설정 오류
        logger.error(f'⚙️ 설정 오류: {str(ve)}')
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "AI 서비스 설정 오류입니다. 관리자에게 문의하세요.",
                "error_code": "CONFIG_ERROR"
            }
        )
        
    except Exception as e:
        logger.error(f'❌ AI 추천 실행 중 오류 발생: {str(e)}', exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": "AI 박스 추천 서비스에서 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
                "error_code": "AI_SERVICE_ERROR"
            }
        )

@app.on_event("startup")
async def startup_event():
    """
    앱 시작시 실행되는 이벤트
    """
    logger.info("=== 🤖 AI 택배 박스 추천 API 시작 ===")
    
    # 필수 환경변수 확인
    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.environ.get(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ 필수 환경변수가 설정되지 않았습니다: {missing_vars}")
        logger.error("🔧 local.settings.json 파일을 확인하거나 환경변수를 직접 설정해주세요.")
        logger.error("📄 local.settings.json 예시:")
        logger.error("""{
  "Values": {
    "AZURE_OPENAI_API_KEY": "your-api-key",
    "AZURE_OPENAI_ENDPOINT": "https://your-resource.openai.azure.com",
    "AZURE_OPENAI_MODEL": "gpt-4"
  }
}""")
    else:
        logger.info("✅ 모든 필수 환경변수가 설정되었습니다.")
        logger.info(f"🌐 Azure OpenAI Endpoint: {os.environ.get('AZURE_OPENAI_ENDPOINT')}")
        logger.info(f"🧠 Azure OpenAI Model: {os.environ.get('AZURE_OPENAI_MODEL', 'gpt-4')}")
        logger.info(f"📡 API Version: {os.environ.get('AZURE_OPENAI_API_VERSION', '2024-02-15-preview')}")

@app.get("/health")
async def health_check():
    """
    헬스 체크 엔드포인트
    """
    # Azure OpenAI 설정 상태 확인
    has_api_key = bool(os.environ.get("AZURE_OPENAI_API_KEY"))
    has_endpoint = bool(os.environ.get("AZURE_OPENAI_ENDPOINT"))
    
    return {
        "status": "healthy" if (has_api_key and has_endpoint) else "unhealthy",
        "service": "ai-package-recommendation",
        "version": "2.0.2",
        "azure_openai": {
            "configured": has_api_key and has_endpoint,
            "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", "NOT_SET"),
            "model": os.environ.get("AZURE_OPENAI_MODEL", "gpt-4"),
            "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        },
        "supported_boxes": ["1호", "2호", "3호", "4호", "5호", "6호", "7호", "8호", "특수 포장"]
    }

@app.get("/")
async def root():
    """
    루트 엔드포인트
    """
    return {
        "message": "🤖 AI 택배 박스 추천 API가 정상적으로 실행 중입니다.",
        "version": "2.0.2",
        "endpoints": {
            "recommend": "/recommend (POST) - AI 박스 추천",
            "health": "/health (GET) - 상태 확인"
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 AI 박스 추천 서비스 시작 - 포트 8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)