import os
from openai import AzureOpenAI

def recommend_ho(width, length, height):
    prompt = f'''
너는 포장 전문가야. 아래는 물체의 실제 크기(mm 단위)이며, 해당 물체가 가장 잘 들어갈 수 있는 우체국 택배 박스 호수를 추천해야 해.

📦 우체국 택배 박스 규격 (단위: mm):
1호: 220 x 190 x 90
2호: 270 x 180 x 150
2-1호: 350 x 250 x 100
3호: 340 x 250 x 210
4호: 410 x 310 x 280
5호: 520 x 380 x 340
6호: 520 x 480 x 400
7호: 620 x 480 x 400

📐 물체 크기:
가로: {width}  
세로: {length}  
높이: {height}

조건:
- 물체는 박스보다 각 변(가로, 세로, 높이)이 작거나 같아야 함
- 가장 작은 박스를 추천할 것
- 결과는 **호수 이름만** 출력 (예: 2호, 3호 등)
- 다른 말은 절대 출력하지 마

정답:
'''

    # 환경변수에서 Azure OpenAI 설정 가져오기
    client = AzureOpenAI(
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT")
    )
    
    response = client.chat.completions.create(
        model=os.environ.get("AZURE_OPENAI_MODEL", "gpt-4"),
        messages=[
            {"role": "system", "content": "너는 포장 추천 전문가야."},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()