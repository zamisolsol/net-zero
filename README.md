
```markdown
# 📦 AI 기반 스마트 패키징 최적화 시스템

실시간 카메라 촬영을 통해 물체를 측정하고, AI가 최적 박스를 추천하는 친환경 포장 솔루션입니다.

---

## 핵심 기능

- 실시간 카메라 기반 크기 측정 (ArUco 마커)
- AI 기반 최적 박스 추천 (Azure OpenAI)
- 3D 포장 시각화 (Three.js)
- 멀티 오브젝트 측정 및 최적화
- 포장 비용 절감 및 공간 활용률 향상

---

## 시스템 구조

```

Frontend (React / Next.js)
├── 실시간 카메라 피드
├── 3D 포장 시각화
└── Socket.IO 통신

Backend Services
├── FastAPI - 메인 패킹 서버 (8002)
├── Flask - AI 추천 서버 (8001)
└── Django - 데이터 관리 서버 (8000)

````

---

## 빠른 시작 가이드

### 1. 필수 조건

- Python 3.8+
- Node.js 16+
- 웹캠 / 카메라
- 출력한 ArUco 마커

### 2. 설치 및 실행

```bash
# 저장소 클론
git clone <repository-url>
cd net-zero
````

#### 2-1. 백엔드 실행

```bash
# A. 메인 서버
cd backend
pip install -r requirements.txt
python main.py    # → http://localhost:8002

# B. AI 추천 서버
cd backend/PackageRecommender
python app.py     # → http://localhost:8001

# C. Django 서버
cd backend
python manage.py migrate
python manage.py runserver  # → http://localhost:8000
```

#### 2-2. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev       # → http://localhost:3000
```

---

## 실행 체크리스트

* [x] 메인 서버 실행
* [x] AI 추천 서버 실행
* [x] Django 서버 실행
* [x] 프론트엔드 실행
* [x] 카메라 권한 허용
* [x] ArUco 마커 준비

---

## 사용 방법

1. 브라우저(`http://localhost:3000`) 접속
2. 카메라 권한 허용 후 ArUco 마커와 물체를 함께 비추기
3. 물체 측정 및 박스 추천 실행
4. 최대 4개까지 연속 측정 가능
5. 3D 시각화와 포장비용 확인

---

## 지원 박스 규격 (우체국 기준)

| 박스명 | 규격 (mm)     | 가격     |
| --- | ----------- | ------ |
| 1호  | 220×190×90  | 700원   |
| 2호  | 270×180×150 | 800원   |
| 3호  | 350×250×100 | 900원   |
| 4호  | 340×250×210 | 1,100원 |
| 5호  | 410×310×280 | 1,300원 |
| 6호  | 520×380×340 | 1,500원 |
| 7호  | 520×480×400 | 1,700원 |
| 8호  | 620×480×400 | 1,900원 |

---

## 기술 스택

### Frontend

* React 18, Next.js
* Three.js (3D)
* Tailwind CSS
* Socket.IO Client

### Backend

* FastAPI, Flask, Django
* OpenCV
* Azure OpenAI API
* Socket.IO

---

## 디버깅 및 트러블슈팅

* **카메라 인식 안 됨**: 브라우저 권한 확인, 다른 앱 종료
* **마커 인식 실패**: 조명 확보, 정면 위치 확인
* **서버 연결 안 됨**: 3개 서버 모두 실행 여부 확인

---

## 라이선스

MIT License

---

**함께 포장의 미래를 바꿔보세요.**

