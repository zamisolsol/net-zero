import cv2
import numpy as np
import pickle
import asyncio
import base64
import requests
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import socketio
import os
import glob

# 패킹 알고리즘 import 추가
from wire_packing import solve
# from cosmos_db import save_measurement_to_cosmos  # 필요시 주석 해제

# Pydantic 모델 정의
class PackingRequest(BaseModel):
    items: List[List[int]]

class ItemDimension(BaseModel):
    width: float
    length: float  
    height: float

# OpenCV 설정 최적화 (MSMF 에러 방지)
os.environ['OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS'] = '0'
os.environ['OPENCV_VIDEOIO_PRIORITY_MSMF'] = '0'  # MSMF 우선순위 낮춤
cv2.setLogLevel(3)  # 경고 메시지 최소화

# 박스 추천 API 설정
BOX_RECOMMENDATION_URL = "http://localhost:8001/recommend"  # 박스 추천 API URL

# 우체국 택배 박스 규격 정보
BOX_SPECS = {
    "1호": {"dimensions": "220 × 190 × 90mm", "maxW": 220, "maxL": 190, "maxH": 90, "price": "700원"},
    "2호": {"dimensions": "270 × 180 × 150mm", "maxW": 270, "maxL": 180, "maxH": 150, "price": "800원"},
    "2-1호": {"dimensions": "350 × 250 × 100mm", "maxW": 350, "maxL": 250, "maxH": 100, "price": "900원"},
    "3호": {"dimensions": "340 × 250 × 210mm", "maxW": 340, "maxL": 250, "maxH": 210, "price": "1,100원"},
    "4호": {"dimensions": "410 × 310 × 280mm", "maxW": 410, "maxL": 310, "maxH": 280, "price": "1,300원"},
    "5호": {"dimensions": "520 × 380 × 340mm", "maxW": 520, "maxL": 380, "maxH": 340, "price": "1,500원"},
    "6호": {"dimensions": "520 × 480 × 400mm", "maxW": 520, "maxL": 480, "maxH": 400, "price": "1,700원"},
    "7호": {"dimensions": "620 × 480 × 400mm", "maxW": 620, "maxL": 480, "maxH": 400, "price": "1,900원"}
}

# 로컬 박스 추천 함수 (API 호출 실패 시 백업용)
def recommend_box_locally(width, length, height):
    """
    로컬에서 박스 추천을 수행하는 함수
    """
    safety_margin = 1.05  # 5% 여유 공간
    
    # 박스 순서대로 확인
    for box_name, specs in BOX_SPECS.items():
        fits_width = (width * safety_margin) <= specs["maxW"]
        fits_length = (length * safety_margin) <= specs["maxL"] 
        fits_height = (height * safety_margin) <= specs["maxH"]
        
        if fits_width and fits_length and fits_height:
            return {
                "box_name": box_name,
                "dimensions": specs["dimensions"],
                "specs": specs
            }
    
    # 모든 박스에 안 맞으면 가장 큰 박스 추천
    return {
        "box_name": "특수 포장",
        "dimensions": "표준 박스보다 큰 물체입니다",
        "specs": {"maxW": 999, "maxL": 999, "maxH": 999}
    }

async def call_box_recommendation_api(width, length, height):
    """
    박스 추천 API를 호출하는 함수 (app.py 서비스)
    """
    try:
        payload = {
            "width": float(width),
            "length": float(length), 
            "height": float(height)
        }
        
        print(f"📞 박스 추천 API 호출: {payload}")
        
        # API 호출 (timeout 설정)
        response = requests.post(
            BOX_RECOMMENDATION_URL,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API 응답: {result}")
            
            if result.get("success"):
                recommended_box_name = result["data"]["recommended_box"]
                
                # 박스 스펙 정보 추가
                if recommended_box_name in BOX_SPECS:
                    box_info = BOX_SPECS[recommended_box_name].copy()
                    box_info["box_name"] = recommended_box_name
                    
                    return {
                        "success": True,
                        "box_name": recommended_box_name,
                        "dimensions": box_info["dimensions"],
                        "price": box_info["price"],
                        "specs": {
                            "maxW": box_info["maxW"],
                            "maxL": box_info["maxL"], 
                            "maxH": box_info["maxH"]
                        },
                        "api_result": result
                    }
                else:
                    print(f"⚠️ 알 수 없는 박스 이름: {recommended_box_name}")
                    return {
                        "success": False,
                        "error": f"알 수 없는 박스: {recommended_box_name}"
                    }
            else:
                print(f"❌ API 응답 오류: {result}")
                return {
                    "success": False,
                    "error": result.get('error', 'API 응답 오류')
                }
        else:
            print(f"❌ API HTTP 오류: {response.status_code}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code} 오류"
            }
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API 연결 오류: {e}")
        return {
            "success": False,
            "error": f"연결 오류: {str(e)}"
        }
    except Exception as e:
        print(f"❌ API 호출 중 예외 발생: {e}")
        return {
            "success": False,
            "error": f"예상치 못한 오류: {str(e)}"
        }

# ----------------- 카메라 캘리브레이션 함수들 -----------------
def calibrate_camera():
    """체커보드를 이용한 카메라 캘리브레이션"""
    # 체커보드의 차원 정의
    CHECKERBOARD = (7,10)  # 체커보드 행과 열당 내부 코너 수
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    
    # 각 체커보드 이미지에 대한 3D 점 벡터를 저장할 벡터 생성
    objpoints = []
    # 각 체커보드 이미지에 대한 2D 점 벡터를 저장할 벡터 생성
    imgpoints = [] 
    
    # 3D 점의 세계 좌표 정의
    objp = np.zeros((1, CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[0,:,:2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
    
    # 주어진 디렉터리에 저장된 개별 이미지의 경로 추출
    images = glob.glob('./checkerboards/*.jpg')
    
    if not images:
        print("❌ ./checkerboards/ 디렉터리에 체커보드 이미지가 없습니다.")
        print("📸 체커보드 이미지를 촬영하여 ./checkerboards/ 폴더에 저장해주세요.")
        return None
    
    print(f"📸 {len(images)}개의 체커보드 이미지를 발견했습니다.")
    
    for fname in images:
        img = cv2.imread(fname)
        if img is None:
            continue
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 체커보드 코너 찾기
        ret, corners = cv2.findChessboardCorners(gray,
                                               CHECKERBOARD,
                                               cv2.CALIB_CB_ADAPTIVE_THRESH +
                                               cv2.CALIB_CB_FAST_CHECK +
                                               cv2.CALIB_CB_NORMALIZE_IMAGE)
        
        if ret == True:
            objpoints.append(objp)
            corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), criteria)
            imgpoints.append(corners2)
            
            print(f"✅ 체커보드 발견: {os.path.basename(fname)}")
        else:
            print(f"❌ 체커보드 미발견: {os.path.basename(fname)}")
    
    if len(objpoints) < 10:
        print(f"⚠️ 캘리브레이션을 위해서는 최소 10개의 유효한 이미지가 필요합니다. (현재: {len(objpoints)}개)")
        return None
    
    print(f"🔧 {len(objpoints)}개 이미지로 카메라 캘리브레이션을 시작합니다...")
    
    # 카메라 캘리브레이션 수행
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints,
                                                      gray.shape[::-1], None, None)
    
    if ret:
        # 결과 출력
        print("✅ 카메라 캘리브레이션 완료!")
        print("📐 Camera matrix:")
        print(mtx)
        print("\n🔍 Distortion coefficients:")
        print(dist)
        
        # 캘리브레이션 결과를 파일로 저장
        calibration_data = {
            'camera_matrix': mtx,
            'dist_coeffs': dist,
            'rvecs': rvecs,
            'tvecs': tvecs
        }
        
        with open('camera_calibration.pkl', 'wb') as f:
            pickle.dump(calibration_data, f)
        
        print("💾 캘리브레이션 데이터가 'camera_calibration.pkl'에 저장되었습니다.")
        return calibration_data
    else:
        print("❌ 카메라 캘리브레이션 실패")
        return None

def live_video_correction_demo(calibration_data):
    """실시간 비디오 왜곡 보정 데모"""
    mtx = calibration_data['camera_matrix']
    dist = calibration_data['dist_coeffs']
    
    cap = initialize_camera()
    if cap is None:
        print("❌ 데모용 카메라를 열 수 없습니다.")
        return
    
    print("🎥 실시간 왜곡 보정 데모를 시작합니다. 'q'를 눌러 종료하세요.")
    
    consecutive_failures = 0
    max_failures = 5
    
    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            consecutive_failures += 1
            if consecutive_failures >= max_failures:
                print("❌ 프레임 읽기 실패가 지속됩니다. 데모를 종료합니다.")
                break
            continue
        else:
            consecutive_failures = 0
        
        # 프레임 크기 가져오기
        h, w = frame.shape[:2]
        
        # 최적의 카메라 행렬 구하기
        newcameramtx, roi = cv2.getOptimalNewCameraMatrix(mtx, dist, (w,h), 1, (w,h))
        
        # 왜곡 보정
        dst = cv2.undistort(frame, mtx, dist, None, newcameramtx)
        
        # ROI로 이미지 자르기
        x, y, w_roi, h_roi = roi
        if all(v > 0 for v in [x, y, w_roi, h_roi]):
            dst = dst[y:y+h_roi, x:x+w_roi]
        
        # 원본과 보정된 이미지를 나란히 표시
        original = cv2.resize(frame, (640, 480))
        corrected = cv2.resize(dst, (640, 480))
        combined = np.hstack((original, corrected))
        
        # 텍스트 추가
        cv2.putText(combined, "Original", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(combined, "Corrected", (650, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 결과 표시
        cv2.imshow('Camera Calibration Demo - Original | Corrected', combined)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()

# ----------------- 캘리브레이션 데이터 로드 또는 생성 -----------------
def load_or_create_calibration():
    """캘리브레이션 데이터를 로드하거나 새로 생성"""
    try:
        with open('camera_calibration.pkl', 'rb') as f:
            calibration_data = pickle.load(f)
        print("✅ 기존 캘리브레이션 데이터 로드 성공")
        return calibration_data['camera_matrix'], calibration_data['dist_coeffs']
    except Exception as e:
        print(f"⚠️ 캘리브레이션 데이터 로드 실패: {e}")
        print("🔧 새로운 캘리브레이션을 시작합니다...")
        
        # 체커보드 디렉터리 확인
        if not os.path.exists('./checkerboards'):
            os.makedirs('./checkerboards')
            print("📁 ./checkerboards/ 디렉터리를 생성했습니다.")
            print("📸 체커보드 이미지를 촬영하여 이 폴더에 저장한 후 다시 실행해주세요.")
            return None, None
        
        calibration_data = calibrate_camera()
        if calibration_data:
            return calibration_data['camera_matrix'], calibration_data['dist_coeffs']
        else:
            print("❌ 캘리브레이션 실패. 기본값으로 진행합니다.")
            return None, None

# 캘리브레이션 데이터 로드
camera_matrix, dist_coeffs = load_or_create_calibration()

# ArUco 설정
aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_250)
aruco_params = cv2.aruco.DetectorParameters()
detector = cv2.aruco.ArucoDetector(aruco_dict, aruco_params)
marker_size = 30  # 30mm

# 마커 3D 좌표 (미리 계산)
marker_3d_edges = np.array([
    [0, 0, 0],
    [0, marker_size, 0],
    [marker_size, marker_size, 0],
    [marker_size, 0, 0]
], dtype='float32').reshape((4, 1, 3))

# ----------------- FastAPI 및 Socket.IO 설정 -----------------
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app_asgi = socketio.ASGIApp(sio, app)

# 마지막 측정값을 저장할 변수 (전역)
last_box = None
last_dim_text = ""
last_recommendation = None  # 추가: 마지막 박스 추천 결과
# 최신 프레임 공유를 위한 전역 변수와 Lock
latest_frame = None
frame_lock = asyncio.Lock()
# 왜곡 보정 맵 (전역으로 선언)
map1, map2 = None, None

# ----------------- 패킹 API 엔드포인트 추가 -----------------
@app.post("/pack/boxes")
async def get_box_data(request: Optional[PackingRequest] = None):
    """3D 패킹 알고리즘을 이용한 박스 데이터 생성"""
    try:
        print("📦 패킹 API 호출됨")
        
        # 요청 데이터에서 물체 정보 추출
        if request and request.items:
            items = [tuple(item) for item in request.items]
            print(f"📦 클라이언트에서 받은 물체 데이터: {items}")
        else:
            # 기본 테스트 데이터
            items = [(50, 30, 20), (40, 40, 15), (60, 25, 10)]
            print("📦 요청 데이터 없음 - 기본 테스트 데이터 사용")

        # 입력 데이터 검증
        if not items:
            raise ValueError("물체 데이터가 비어있습니다")
        
        for i, item in enumerate(items):
            if len(item) != 3:
                raise ValueError(f"물체 {i}의 차원 데이터가 잘못되었습니다: {item}")
            if any(x <= 0 for x in item):
                raise ValueError(f"물체 {i}의 크기가 유효하지 않습니다: {item}")

        print(f"🔧 패킹 알고리즘 실행 시작...")
        
        # 패킹 알고리즘 실행
        box, placements = solve(items)
        print(f"✅ 패킹 알고리즘 완료: 컨테이너 {box}")

        # 결과 JSON 구성
        results = []
        for idx, dim, pos in placements:
            item_data = {
                "id": idx,
                "size": {"w": dim[0], "d": dim[1], "h": dim[2]},
                "pos": {"x": pos[0], "y": pos[1], "z": pos[2]},
                "original_item": list(items[idx]) if idx < len(items) else [3, 3, 3]
            }
            results.append(item_data)
            print(f"  아이템 {idx}: {dim} at {pos}")

        # 박스 타입 결정 (크기에 따라)
        volume = box[0] * box[1] * box[2]
        if volume <= 50000:  # 50x50x20 정도
            box_type = "소형"
        elif volume <= 500000:  # 100x100x50 정도
            box_type = "중형"
        else:
            box_type = "대형"

        # 패킹 효율성 계산
        total_item_volume = sum(item[0] * item[1] * item[2] for item in items)
        efficiency = round((total_item_volume / volume) * 100, 1) if volume > 0 else 0

        print(f"📊 패킹 결과 요약:")
        print(f"  - 컨테이너 크기: {box}")
        print(f"  - 총 부피: {volume}")
        print(f"  - 효율성: {efficiency}%")
        print(f"  - 박스 타입: {box_type}")
        
        # 🔥 박스 추천 API 호출 (app.py 서비스)
        print("📦 Azure OpenAI 기반 박스 추천을 시작합니다...")
        box_recommendation = await call_box_recommendation_api(box[0], box[1], box[2])
        
        container_data = {
            "container_size": {"w": box[0], "d": box[1], "h": box[2]},
            "items": results,
            "volume": volume,
            "box_type": box_type,
            "efficiency": efficiency,
            "total_items": len(items),
            "input_items": [list(item) for item in items],
            "recommended_box": box_recommendation  # 🔥 박스 추천 결과 추가
        }
        
        if box_recommendation and box_recommendation.get("success"):
            print(f"✅ 박스 추천 완료: {box_recommendation['box_name']} ({box_recommendation['dimensions']})")
        else:
            print(f"⚠️ 박스 추천 실패: {box_recommendation.get('error', '알 수 없는 오류') if box_recommendation else 'API 응답 없음'}")
        
        # Cosmos DB에 저장 (옵션)
        try:
            # save_measurement_to_cosmos(
            #     user_id="yuni",
            #     result={
            #         "width": box[0],
            #         "length": box[1], 
            #         "height": box[2],
            #         "box_type": box_type,
            #         "volume": volume,
            #         "items_count": len(items),
            #         "efficiency": efficiency,
            #         "input_items": [list(item) for item in items],
            #         "recommended_box": box_recommendation
            #     }
            # )
            print("💾 데이터 저장 완료 (비활성화됨)")
        except Exception as e:
            print(f"⚠️ 데이터 저장 실패 (계속 진행): {e}")
        
        return container_data
    
    except Exception as e:
        print(f"❌ 패킹 데이터 생성 실패: {e}")
        import traceback
        traceback.print_exc()
        
        # 오류 발생 시 기본 응답 반환
        return {
            "error": "패킹 데이터 생성 실패",
            "message": str(e),
            "container_size": {"w": 100, "d": 100, "h": 50},
            "items": [],
            "volume": 500000,
            "box_type": "오류",
            "efficiency": 0,
            "total_items": 0,
            "input_items": [],
            "recommended_box": {
                "success": False,
                "error": "패킹 계산 실패로 인한 박스 추천 불가"
            }
        }

# ----------------- 영상 처리 및 웹소켓 통신 -----------------
def initialize_camera():
    """카메라를 안정적으로 초기화하는 함수"""
    print("📷 카메라 초기화를 시도합니다...")
    
    # 백엔드 우선순위: DirectShow -> Auto -> MSMF
    backends = [
        (cv2.CAP_DSHOW, "DirectShow"),
        (cv2.CAP_ANY, "Auto"),
        (cv2.CAP_MSMF, "MSMF")
    ]
    
    for backend, name in backends:
        print(f"🔄 {name} 백엔드로 카메라 연결 시도...")
        cap = cv2.VideoCapture(0, backend)
        
        if cap.isOpened():
            # 카메라 설정 최적화
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, 30)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 버퍼 크기 최소화
            
            # 테스트 프레임 읽기
            ret, test_frame = cap.read()
            if ret and test_frame is not None:
                print(f"✅ {name} 백엔드로 카메라 연결 성공!")
                print(f"📐 해상도: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
                return cap
            else:
                print(f"❌ {name} 백엔드: 프레임 읽기 실패")
                cap.release()
        else:
            print(f"❌ {name} 백엔드: 카메라 열기 실패")
    
    print("❌ 모든 백엔드에서 카메라 연결 실패")
    return None

async def video_stream_task():
    global last_box, last_dim_text, latest_frame, map1, map2, last_recommendation
    cap = initialize_camera()
    if cap is None:
        print("❌ 카메라를 초기화할 수 없습니다.")
        return

    # 왜곡 보정 맵을 한 번만 생성 (캘리브레이션 데이터가 있는 경우)
    if camera_matrix is not None and dist_coeffs is not None:
        h, w = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        # alpha=0 으로 설정하여 왜곡 보정 효과가 잘 보이도록 함 (주변부가 잘릴 수 있음)
        new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), 0, (w,h))
        map1, map2 = cv2.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, new_camera_matrix, (w, h), 5) # 5 = CV_32FC1
        print("✅ 왜곡 보정 맵(map1, map2) 생성 완료 (alpha=0).")
    else:
        print("⚠️ 캘리브레이션 데이터가 없어 왜곡 보정을 사용할 수 없습니다.")

    # 프레임 읽기 실패 카운터
    consecutive_failures = 0
    max_failures = 10

    while True:
        ret, frame = cap.read()
        if not ret or frame is None:
            consecutive_failures += 1
            print(f"⚠️ 프레임 읽기 실패 ({consecutive_failures}/{max_failures})")
            
            if consecutive_failures >= max_failures:
                print("🔄 카메라 재연결을 시도합니다...")
                cap.release()
                await asyncio.sleep(1)
                cap = initialize_camera()
                if cap is None:
                    print("❌ 카메라 재연결 실패. 5초 후 다시 시도합니다.")
                    await asyncio.sleep(5)
                    continue
                consecutive_failures = 0
            else:
                await asyncio.sleep(0.1)
                continue
        else:
            consecutive_failures = 0  # 성공 시 카운터 리셋

        # 최신 프레임을 thread-safe하게 저장
        async with frame_lock:
            latest_frame = frame.copy()

        # 왜곡 보정 (캘리브레이션 데이터가 있는 경우만)
        if map1 is not None and map2 is not None:
            frame_undistorted = cv2.remap(frame, map1, map2, cv2.INTER_LINEAR)
        else:
            frame_undistorted = frame
        
        # 실시간 마커 검출 (시각적 피드백용)
        corners, ids, rejected = detector.detectMarkers(frame_undistorted)
        
        # 🔥 마커 인식 상태 확인 (프론트엔드로 전달할 정보)
        marker_detected = ids is not None and len(ids) > 0
        marker_count = len(ids) if ids is not None else 0

        # 화면에 그리기
        if marker_detected and camera_matrix is not None:
            cv2.aruco.drawDetectedMarkers(frame_undistorted, corners, ids)
            for corner in corners:
                ret_pnp, rvec, tvec = cv2.solvePnP(marker_3d_edges, corner, camera_matrix, dist_coeffs)
                if ret_pnp:
                    cv2.drawFrameAxes(frame_undistorted, camera_matrix, dist_coeffs, rvec, tvec, marker_size/2)
        elif marker_detected:
            cv2.aruco.drawDetectedMarkers(frame_undistorted, corners, ids)
        
        # 측정 결과 표시
        if last_box is not None:
            cv2.drawContours(frame_undistorted, [last_box], 0, (0, 255, 0), 2)
            cv2.putText(frame_undistorted, last_dim_text, (int(last_box[1][0]), int(last_box[1][1] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
        
        # 박스 추천 결과 표시
        if last_recommendation is not None:
            recommendation_text = f"추천: {last_recommendation['box_name']}"
            cv2.putText(frame_undistorted, recommendation_text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)

        # 프레임을 JPEG로 인코딩 후 Base64로 변환
        _, buffer = cv2.imencode('.jpg', frame_undistorted)
        frame_encoded = base64.b64encode(buffer).decode('utf-8')
        
        # 🔥 클라이언트로 프레임과 마커 인식 상태 함께 전송
        await sio.emit('video_frame', {
            'image': frame_encoded,
            'marker_detected': marker_detected,  # 마커 인식 상태
            'marker_count': marker_count         # 마커 개수
        })
        await asyncio.sleep(0.03) # 프레임 속도 조절

# --- 3D 측정 로직 (향상된 버전) ---
@sio.on('measure')
async def measure_object(sid):
    global last_box, last_dim_text, latest_frame, map1, map2, last_recommendation
    
    print("📏 측정 요청 수신...")
    
    # 공유된 최신 프레임을 가져옴
    async with frame_lock:
        if latest_frame is None:
            print("❌ 측정에 사용할 프레임이 없습니다.")
            await sio.emit('measurement_result', {'dimensions': '카메라 프레임을 가져올 수 없습니다.'})
            return
        frame_for_measurement = latest_frame.copy()

    # 왜곡 보정 (캘리브레이션 데이터가 있는 경우만)
    if map1 is not None and map2 is not None:
        frame_undistorted = cv2.remap(frame_for_measurement, map1, map2, cv2.INTER_LINEAR)
    elif camera_matrix is not None and dist_coeffs is not None:
        print("⚠️ 왜곡 보정 맵이 아직 준비되지 않았습니다. 기본 보정방식을 사용합니다.")
        frame_undistorted = cv2.undistort(frame_for_measurement, camera_matrix, dist_coeffs)
    else:
        print("⚠️ 캘리브레이션 데이터가 없어 왜곡 보정을 하지 않습니다.")
        frame_undistorted = frame_for_measurement

    corners, ids, rejected = detector.detectMarkers(frame_undistorted)
    
    # 캘리브레이션 데이터가 없으면 3D 측정 불가
    if camera_matrix is None or dist_coeffs is None:
        print("⚠️ 캘리브레이션 데이터가 없어 2D 측정만 가능합니다.")
        if ids is not None and len(ids) > 0:
            await perform_2d_measurement(frame_undistorted, corners, ids)
        else:
            await sio.emit('measurement_result', {'dimensions': '마커를 먼저 인식시켜주세요.'})
        return
    
    if ids is not None and len(ids) >= 3:
        print(f"✅ {len(ids)}개의 마커 발견, 3D 측정을 시작합니다...")
        
        # --- 1. 마커 3D 위치(tvec) 구하기 ---
        marker_tvecs = []
        for corner in corners:
            ret, rvec, tvec = cv2.solvePnP(marker_3d_edges, corner, camera_matrix, dist_coeffs)
            if ret:
                marker_tvecs.append(tvec.reshape(-1))
        
        if len(marker_tvecs) < 3:
            print("❌ 유효한 마커가 3개 미만입니다.")
            await sio.emit('measurement_result', {'dimensions': '유효한 마커 3개 이상 필요합니다.'})
            return
            
        # --- 2. 평면 방정식 구하기 (마커 3개 사용) ---
        p1, p2, p3 = marker_tvecs[0], marker_tvecs[1], marker_tvecs[2]
        v1 = p2 - p1
        v2 = p3 - p1
        normal = np.cross(v1, v2)
        a, b, c = normal
        d = -np.dot(normal, p1)
        print(f"📐 평면 방정식 계수: a={a:.3f}, b={b:.3f}, c={c:.3f}, d={d:.3f}")
        
        # --- 3. 물체 윤곽선 찾기 ---
        gray = cv2.cvtColor(frame_undistorted, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            valid_contours = [cnt for cnt in contours if 100 < cv2.contourArea(cnt) < 20000]
            if valid_contours:
                # 가장 큰 윤곽선을 물체로 선택
                object_contour = max(valid_contours, key=cv2.contourArea)
                rect = cv2.minAreaRect(object_contour)
                box = cv2.boxPoints(rect)
                last_box = box.astype(np.int32)
                width_px, height_px = rect[1]
                
                # --- 4. 물체 중심 픽셀 구하기 ---
                M = cv2.moments(object_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    
                    # --- 5. 픽셀 → 3D 변환 (바닥 평면과의 교점) ---
                    uv1 = np.array([cx, cy, 1.0])
                    invK = np.linalg.inv(camera_matrix)
                    ray = invK @ uv1
                    
                    # 광선과 평면의 교점 계산
                    denominator = a*ray[0] + b*ray[1] + c*ray[2]
                    if abs(denominator) > 1e-6:  # 0으로 나누기 방지
                        t = -(a*0 + b*0 + c*0 + d) / denominator
                        P_ground = t * ray  # 바닥 평면 위의 3D 좌표
                        
                        # --- 6. 물체 윗면의 3D 좌표 추정 ---
                        # 윤곽선에서 가장 높은 y값(이미지 좌표계에서 가장 작은 y) 픽셀을 찾음
                        top_idx = np.argmin(object_contour[:,0,1])
                        top_px = object_contour[top_idx,0]
                        uv1_top = np.array([top_px[0], top_px[1], 1.0])
                        ray_top = invK @ uv1_top
                        
                        t_top = -(a*0 + b*0 + c*0 + d) / (a*ray_top[0] + b*ray_top[1] + c*ray_top[2])
                        P_top_ground = t_top * ray_top
                        
                        # 높이 계산 (Z축 차이)
                        height_3d_mm = abs(P_top_ground[2] - P_ground[2])
                        print(f"🔍 3D 높이 계산: {height_3d_mm:.1f}mm")
                    else:
                        height_3d_mm = 0
                        print("⚠️ 평면과 광선이 평행하여 높이 계산 불가")
                else:
                    height_3d_mm = 0
                    print("⚠️ 물체 중심점 계산 실패")
                
                # --- 7. 2D 크기를 mm로 변환 ---
                all_pixel_sizes = []
                for corner in corners:
                    marker_corners = corner.reshape((4, 2))
                    pixel_width = np.linalg.norm(marker_corners[1] - marker_corners[0])
                    pixel_height = np.linalg.norm(marker_corners[2] - marker_corners[1])
                    all_pixel_sizes.append((pixel_width + pixel_height) / 2.0)
                
                avg_pixel_size = np.mean(all_pixel_sizes)
                px_per_mm = avg_pixel_size / marker_size if avg_pixel_size > 0 else 1
                print(f"📐 픽셀-mm 변환 비율: {px_per_mm:.2f} px/mm")
                
                width_mm = width_px / px_per_mm
                height_2d_mm = height_px / px_per_mm
                
                # --- 8. 결과 표시 (3D 높이 포함) ---
                if height_3d_mm > 0:
                    last_dim_text = f"W: {max(width_mm, height_2d_mm):.1f}mm, L: {min(width_mm, height_2d_mm):.1f}mm, H: {height_3d_mm:.1f}mm"
                    final_width = max(width_mm, height_2d_mm)
                    final_length = min(width_mm, height_2d_mm)
                    final_height = height_3d_mm
                else:
                    last_dim_text = f"W: {max(width_mm, height_2d_mm):.1f}mm, L: {min(width_mm, height_2d_mm):.1f}mm"
                    final_width = max(width_mm, height_2d_mm)
                    final_length = min(width_mm, height_2d_mm)
                    final_height = min(width_mm, height_2d_mm) * 0.6  # 기본 높이 추정
                
                print(f"✅ 3D 측정 완료: {last_dim_text}")
                
                # 클라이언트로 측정 결과 전송 (박스 추천 제거)
                await sio.emit('measurement_result', {
                    'dimensions': last_dim_text,
                    'measurements': {
                        'width': final_width,
                        'length': final_length, 
                        'height': final_height
                    }
                })
                
            else:
                print("❌ 적절한 크기의 물체를 찾을 수 없습니다.")
                await sio.emit('measurement_result', {'dimensions': '적절한 크기의 물체를 찾을 수 없습니다.'})
        else:
            print("❌ 물체의 윤곽선을 찾을 수 없습니다.")
            await sio.emit('measurement_result', {'dimensions': '물체의 윤곽선을 찾을 수 없습니다.'})
            
    elif ids is not None and len(ids) > 0:
        print(f"⚠️ 마커 {len(ids)}개 발견 (3개 미만) - 2D 측정으로 진행합니다...")
        await perform_2d_measurement(frame_undistorted, corners, ids)
            
    else:
        print("❌ 마커가 없어 측정 불가")
        await sio.emit('measurement_result', {'dimensions': '마커를 먼저 인식시켜주세요.'})

async def perform_2d_measurement(frame_undistorted, corners, ids):
    """2D 측정 로직을 별도 함수로 분리"""
    global last_box, last_dim_text, last_recommendation
    
    # 2D 측정 로직 (기존 방식)
    all_pixel_sizes = []
    for corner in corners:
        marker_corners = corner.reshape((4, 2))
        pixel_width = np.linalg.norm(marker_corners[1] - marker_corners[0])
        pixel_height = np.linalg.norm(marker_corners[2] - marker_corners[1])
        all_pixel_sizes.append((pixel_width + pixel_height) / 2.0)
    
    avg_pixel_size = np.mean(all_pixel_sizes)
    px_per_mm = avg_pixel_size / marker_size if avg_pixel_size > 0 else 0

    if px_per_mm > 0:
        print(f"📐 픽셀-mm 변환 비율: {px_per_mm:.2f} px/mm")
        
        # 마커들의 중심점 계산
        all_centers_x = [int(np.mean([c[0] for c in corner.reshape((4, 2))])) for corner in corners]
        all_centers_y = [int(np.mean([c[1] for c in corner.reshape((4, 2))])) for corner in corners]
        area_center_x, area_center_y = int(np.mean(all_centers_x)), int(np.mean(all_centers_y))

        # 물체 윤곽선 찾기
        gray = cv2.cvtColor(frame_undistorted, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if contours:
            valid_contours = [cnt for cnt in contours if 100 < cv2.contourArea(cnt) < 20000]
            if valid_contours:
                # 마커 영역 중심에 가장 가까운 윤곽선 선택
                object_contour = min(valid_contours, key=lambda cnt: np.sqrt(
                    ((cv2.moments(cnt)['m10']/cv2.moments(cnt)['m00'] if cv2.moments(cnt)['m00'] != 0 else 0) - area_center_x)**2 + 
                    ((cv2.moments(cnt)['m01']/cv2.moments(cnt)['m00'] if cv2.moments(cnt)['m00'] != 0 else 0) - area_center_y)**2
                ))
                
                # 최소 외접 사각형 계산
                rect = cv2.minAreaRect(object_contour)
                box = cv2.boxPoints(rect)
                last_box = box.astype(np.int32)
                
                # mm 단위로 변환
                width_mm = rect[1][0] / px_per_mm
                height_mm = rect[1][1] / px_per_mm
                final_width = max(width_mm, height_mm)
                final_length = min(width_mm, height_mm)
                final_height = final_length * 0.6  # 2D에서는 높이 추정
                
                last_dim_text = f"W: {final_width:.1f}mm, L: {final_length:.1f}mm"
                
                print(f"✅ 2D 측정 완료: {last_dim_text}")
                
                # 클라이언트로 측정 결과 전송 (박스 추천 제거)
                await sio.emit('measurement_result', {
                    'dimensions': last_dim_text,
                    'measurements': {
                        'width': final_width,
                        'length': final_length,
                        'height': final_height
                    }
                })
            else:
                print("❌ 적절한 크기의 물체를 찾을 수 없습니다.")
                await sio.emit('measurement_result', {'dimensions': '적절한 크기의 물체를 찾을 수 없습니다.'})
        else:
            print("❌ 물체의 윤곽선을 찾을 수 없습니다.")
            await sio.emit('measurement_result', {'dimensions': '물체의 윤곽선을 찾을 수 없습니다.'})
    else:
        print("❌ 픽셀-mm 변환 비율을 계산할 수 없습니다.")
        await sio.emit('measurement_result', {'dimensions': '마커 크기를 인식할 수 없습니다.'})

@sio.on('clear')
async def clear_measurement(sid):
    global last_box, last_dim_text, last_recommendation
    last_box = None
    last_dim_text = ""
    last_recommendation = None
    print("🧹 측정값 초기화")
    await sio.emit('measurement_result', {'dimensions': ''})

@sio.on('connect')
async def connect(sid, environ):
    print(f"🔌 Socket.IO Client connected: {sid}")
    # 클라이언트가 연결되면 영상 스트리밍 시작
    sio.start_background_task(video_stream_task)

@sio.on('disconnect')
def disconnect(sid):
    print(f"🔌 Socket.IO Client disconnected: {sid}")

# 🏥 헬스체크 엔드포인트 추가
@app.get("/")
async def health_check():
    return {"status": "OK", "message": "Product Photo Analyzer Backend is running", "port": 8002}

@app.get("/health")
async def health():
    # 실제 카메라 상태 확인
    camera_available = False
    try:
        test_cap = initialize_camera()
        if test_cap is not None:
            camera_available = True
            test_cap.release()
    except Exception as e:
        print(f"⚠️ 카메라 상태 확인 중 오류: {e}")
    
    return {
        "status": "healthy",
        "port": 8002,
        "camera_available": camera_available,
        "calibration_loaded": camera_matrix is not None and dist_coeffs is not None,
        "marker_dict": "DICT_4X4_250",
        "marker_size_mm": marker_size,
        "box_recommendation_api": BOX_RECOMMENDATION_URL,
        "packing_api_available": True
    }

@app.post("/pack/test")
async def test_packing():
    """패킹 알고리즘 테스트용 엔드포인트"""
    print("🧪 패킹 테스트 시작")
    
    test_items = [
        [50, 30, 20],   # 물체 1: 50x30x20mm
        [40, 40, 15],   # 물체 2: 40x40x15mm  
        [60, 25, 10],   # 물체 3: 60x25x10mm
        [35, 35, 25]    # 물체 4: 35x35x25mm
    ]
    
    try:
        # 테스트 실행
        request = PackingRequest(items=test_items)
        result = await get_box_data(request)
        
        return {
            "test_data": test_items,
            "packing_result": result,
            "message": "✅ 테스트 완료",
            "success": True
        }
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return {
            "test_data": test_items,
            "error": str(e),
            "message": "❌ 테스트 실패",
            "success": False
        }

@app.get("/pack/debug")
async def debug_packing():
    """디버깅용 정보 제공"""
    try:
        # wire_packing 모듈 직접 테스트
        from wire_packing import test_packing
        
        print("🔍 wire_packing 모듈 직접 테스트")
        box_size, placements = test_packing()
        
        if box_size and placements:
            return {
                "module_test": "success",
                "box_size": box_size,
                "placements": [
                    {
                        "item_idx": p[0],
                        "size": p[1], 
                        "position": p[2]
                    } for p in placements
                ],
                "message": "wire_packing 모듈 정상 동작"
            }
        else:
            return {
                "module_test": "failed",
                "message": "wire_packing 모듈 테스트 실패"
            }
            
    except Exception as e:
        import traceback
        return {
            "module_test": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "message": f"wire_packing 모듈 오류: {e}"
        }

@app.post("/pack/simple")
async def simple_pack(items: List[List[int]]):
    """간단한 패킹 테스트"""
    try:
        print(f"🎯 간단한 패킹 테스트: {items}")
        
        # 직접 solve 함수 호출
        from wire_packing import solve
        
        items_tuples = [tuple(item) for item in items]
        box, placements = solve(items_tuples)
        
        return {
            "input": items,
            "box": box,
            "placements": [
                {
                    "id": p[0],
                    "size": p[1],
                    "pos": p[2]
                } for p in placements
            ],
            "success": True
        }
        
    except Exception as e:
        print(f"❌ 간단한 패킹 실패: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "input": items,
            "error": str(e),
            "success": False
        }

# 🔧 캘리브레이션 관련 엔드포인트
@app.get("/calibration/status")
async def calibration_status():
    """캘리브레이션 상태 확인"""
    return {
        "calibration_loaded": camera_matrix is not None and dist_coeffs is not None,
        "calibration_file_exists": os.path.exists('camera_calibration.pkl'),
        "checkerboard_images_count": len(glob.glob('./checkerboards/*.jpg'))
    }

@app.post("/calibration/run")
async def run_calibration():
    """새로운 캘리브레이션 실행"""
    global camera_matrix, dist_coeffs, map1, map2
    
    try:
        calibration_data = calibrate_camera()
        if calibration_data:
            camera_matrix = calibration_data['camera_matrix']
            dist_coeffs = calibration_data['dist_coeffs']
            
            # 왜곡 보정 맵 재생성
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                h, w = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)), int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, (w, h), 0, (w,h))
                map1, map2 = cv2.initUndistortRectifyMap(camera_matrix, dist_coeffs, None, new_camera_matrix, (w, h), 5)
                cap.release()
            
            return {"status": "success", "message": "캘리브레이션이 성공적으로 완료되었습니다."}
        else:
            return {"status": "error", "message": "캘리브레이션에 실패했습니다. 체커보드 이미지를 확인해주세요."}
    except Exception as e:
        return {"status": "error", "message": f"캘리브레이션 중 오류 발생: {str(e)}"}

@app.get("/calibration/demo")
async def calibration_demo():
    """왜곡 보정 데모 실행 (별도 창에서)"""
    if camera_matrix is not None and dist_coeffs is not None:
        try:
            # 별도 스레드에서 데모 실행 (블로킹 방지)
            import threading
            calibration_data = {'camera_matrix': camera_matrix, 'dist_coeffs': dist_coeffs}
            demo_thread = threading.Thread(target=live_video_correction_demo, args=(calibration_data,))
            demo_thread.daemon = True
            demo_thread.start()
            return {"status": "success", "message": "왜곡 보정 데모가 시작되었습니다. 새 창을 확인하세요."}
        except Exception as e:
            return {"status": "error", "message": f"데모 실행 중 오류: {str(e)}"}
    else:
        return {"status": "error", "message": "캘리브레이션 데이터가 없습니다. 먼저 캘리브레이션을 실행해주세요."}

if __name__ == '__main__':
    import uvicorn
    print("🚀 통합 상품 포장 분석기 백엔드 서버를 시작합니다...")
    print("📡 Socket.IO 서버: ws://127.0.0.1:8002")
    print("🌐 HTTP API: http://127.0.0.1:8002")
    print("❤️ 헬스체크: http://127.0.0.1:8002/health")
    print("📦 패킹 API: http://127.0.0.1:8002/pack/boxes")
    print("🔧 캘리브레이션 상태: http://127.0.0.1:8002/calibration/status")
    print("📏 측정 모드: 3D (마커 3개 이상) + 2D (마커 1-2개) 하이브리드")
    print(f"🤖 AI 박스 추천 API: {BOX_RECOMMENDATION_URL}")
    
    print("\n🔧 카메라 에러 발생 시 해결 방법:")
    print("1. 다른 카메라 앱(Skype, Teams 등) 종료")
    print("2. 웹캠 드라이버 업데이트")
    print("3. USB 포트 변경")
    print("4. Windows 카메라 앱에서 카메라 테스트")
    
    if camera_matrix is None or dist_coeffs is None:
        print("\n⚠️ 캘리브레이션 데이터가 없습니다!")
        print("📸 체커보드 이미지를 ./checkerboards/ 폴더에 넣고")
        print("🔧 POST /calibration/run 엔드포인트를 호출하여 캘리브레이션을 수행하세요.")
    else:
        print("\n✅ 캘리브레이션 데이터 로드 완료 - 3D 측정 가능")
    
    print("\n🤖 AI 박스 추천 시스템:")
    print("✅ Azure OpenAI 기반 지능형 박스 추천")
    print("🔄 AI 실패 시 로컬 계산 자동 백업")
    print("📦 전체 물체 측정 완료 후 최적화")
    
    print("\n🎯 3D 패킹 시뮬레이션:")
    print("✅ /pack/boxes 엔드포인트로 3D 패킹 데이터 제공")
    print("🔄 패킹 효율성 및 박스 타입 자동 계산")
    print("🤖 패킹 완료 후 AI가 최적 박스 추천")
    
    print("\n🔗 관련 서비스:")
    print("📍 main.py (포트 8002): 카메라, 측정, 패킹")
    print("🤖 app.py (포트 8001): AI 박스 추천")
    print("💡 두 서비스 모두 실행되어야 정상 작동")
    
    uvicorn.run(app_asgi, host="127.0.0.1", port=8002)