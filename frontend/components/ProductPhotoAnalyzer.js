"use client";

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { Camera, Package, CheckCircle } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

// 카메라 위치 계산 함수
function calculateOptimalCameraPosition(containerSize) {
  const { w, d, h } = containerSize;
  const maxDimension = Math.max(w, d, h);
  const distance = maxDimension * 2.5; // 최대 치수의 2.5배 거리
  
  return {
    position: [distance * 0.7, distance * 0.8, distance * 0.7],
    fov: 45,
    minDistance: maxDimension * 0.5,
    maxDistance: maxDimension * 4
  };
}

// 3D 박스 컴포넌트
function Box({ position, size, color, opacity = 0.8 }) {
  const boxGeometry = new THREE.BoxGeometry(size.w, size.h, size.d);
  
  return (
    <mesh position={[position.x + size.w/2, position.z + size.h/2, position.y + size.d/2]}>
      <boxGeometry args={[size.w, size.h, size.d]} />
      <meshStandardMaterial 
        color={color} 
        transparent 
        opacity={opacity}
      />
      {/* 박스 테두리도 제거 */}
    </mesh>
  );
}

// 3D 패킹 시각화 컴포넌트
function PackingVisualization3D({ containerData }) {
  const colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FECA57', '#FF9FF3', '#54A0FF', '#5F27CD'];

  if (!containerData) {
    return (
      <div className="w-full h-64 bg-gray-100 rounded-xl flex items-center justify-center">
        <div className="text-gray-500">3D 모델 로딩 중...</div>
      </div>
    );
  }

  // 컨테이너 크기에 따른 최적 카메라 설정
  const cameraSettings = calculateOptimalCameraPosition(containerData.container_size);

  return (
    <div className="w-full h-64 rounded-xl overflow-hidden shadow-lg">
      <Canvas 
        camera={{ 
          position: cameraSettings.position, 
          fov: cameraSettings.fov 
        }}
        style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}
      >
        <Suspense fallback={null}>
          <ambientLight intensity={0.7} />
          <directionalLight position={[10, 10, 5]} intensity={0.9} />
          <directionalLight position={[-10, -10, -5]} intensity={0.4} />
          
          <OrbitControls 
            enablePan={true}
            enableZoom={true}
            enableRotate={true}
            maxPolarAngle={Math.PI * 0.8}
            minDistance={cameraSettings.minDistance}
            maxDistance={cameraSettings.maxDistance}
            target={[
              containerData.container_size.w / 2, 
              containerData.container_size.h / 2, 
              containerData.container_size.d / 2
            ]}
          />

          {/* 바닥 격자 제거 */}
          
          {/* 컨테이너 외곽선 제거 */}

          {/* 패킹된 아이템들만 표시 */}
          {containerData.items.map((item, index) => (
            <Box
              key={index}
              position={item.pos}
              size={item.size}
              color={colors[index % colors.length]}
              opacity={0.9}
            />
          ))}
        </Suspense>
      </Canvas>
    </div>
  );
}

const ProductPhotoAnalyzer = ({ onBack }) => {
  const [currentStep, setCurrentStep] = useState('initial');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [videoStream, setVideoStream] = useState(null);
  const [measurementResult, setMeasurementResult] = useState('');
  const [productDimensions, setProductDimensions] = useState(null);
  const [recommendedBox, setRecommendedBox] = useState(null);
  const [markerDetected, setMarkerDetected] = useState(false);
  const [packagingSimulation, setPackagingSimulation] = useState(null);
  const [packingData, setPackingData] = useState(null);
  const [isPackingLoading, setIsPackingLoading] = useState(false);
  
  // 다중 촬영 관련 state
  const [measuredItems, setMeasuredItems] = useState([]);
  const [showMoreItemsPopup, setShowMoreItemsPopup] = useState(false);
  const [currentItemIndex, setCurrentItemIndex] = useState(1);
  
  // 디버깅 관련 함수들
  const [debugResults, setDebugResults] = useState(null);
  const [isDebugLoading, setIsDebugLoading] = useState(false);
  const [showDebugPanel, setShowDebugPanel] = useState(false);

  const runDebugTest = async (endpoint, data = null) => {
    setIsDebugLoading(true);
    try {
      const options = {
        method: data ? 'POST' : 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      };
      
      if (data) {
        options.body = JSON.stringify(data);
      }

      console.log(`🧪 디버그 테스트 실행: ${endpoint}`);
      const response = await fetch(`http://localhost:8002${endpoint}`, options);
      const result = await response.json();
      
      setDebugResults({
        endpoint,
        status: response.status,
        success: response.ok,
        data: result,
        timestamp: new Date().toLocaleTimeString()
      });
      
      console.log(`✅ 디버그 테스트 완료: ${endpoint}`, result);
    } catch (error) {
      console.error(`❌ 디버그 테스트 실패: ${endpoint}`, error);
      setDebugResults({
        endpoint,
        success: false,
        error: error.message,
        timestamp: new Date().toLocaleTimeString()
      });
    } finally {
      setIsDebugLoading(false);
    }
  };
  
  const socketRef = useRef(null);
  const videoRef = useRef(null);

  // 우체국 택배 박스 규격 (백엔드와 동기화)
  const boxSizes = [
    { 
      name: '1호 박스', 
      dimensions: '220 × 190 × 90mm', 
      maxW: 220, maxL: 190, maxH: 90,
      volume: 3762000,
      price: '700원',
      id: 1,
      image: '/images/001.jpg'
    },
    { 
      name: '2호 박스', 
      dimensions: '270 × 180 × 150mm', 
      maxW: 270, maxL: 180, maxH: 150,
      volume: 7290000,
      price: '800원',
      id: 2,
      image: '/images/002.jpg'
    },
    { 
      name: '3호 박스', 
      dimensions: '350 × 250 × 100mm', 
      maxW: 350, maxL: 250, maxH: 100,
      volume: 8750000,
      price: '900원',
      id: 21,
      image: '/images/003.jpg'
    },
    { 
      name: '4호 박스', 
      dimensions: '340 × 250 × 210mm', 
      maxW: 340, maxL: 250, maxH: 210,
      volume: 17850000,
      price: '1,100원',
      id: 3,
      image: '/images/004.jpg'
    },
    { 
      name: '5호 박스', 
      dimensions: '410 × 310 × 280mm', 
      maxW: 410, maxL: 310, maxH: 280,
      volume: 35588000,
      price: '1,300원',
      id: 4,
      image: '/images/005.jpg'
    },
    { 
      name: '6호 박스', 
      dimensions: '520 × 380 × 340mm', 
      maxW: 520, maxL: 380, maxH: 340,
      volume: 67123200,
      price: '1,500원',
      id: 5,
      image: '/images/006.jpg'
    },
    { 
      name: '7호 박스', 
      dimensions: '520 × 480 × 400mm', 
      maxW: 520, maxL: 480, maxH: 400,
      volume: 99840000,
      price: '1,700원',
      id: 6,
      image: '/images/007.jpg'
    },
    { 
      name: '8호 박스', 
      dimensions: '620 × 480 × 400mm', 
      maxW: 620, maxL: 480, maxH: 400,
      volume: 119040000,
      price: '1,900원',
      id: 7,
      image: '/images/008.jpg'
    }
  ];

  // Socket.IO 연결 설정
  useEffect(() => {
    connectToCamera();
    
    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
    };
  }, []);

  const connectToCamera = async () => {
    setConnectionStatus('connecting');
    
    try {
      const io = (await import('socket.io-client')).default;
      
      socketRef.current = io('http://127.0.0.1:8002', {
        transports: ['websocket', 'polling']
      });

      socketRef.current.on('connect', () => {
        console.log('카메라 서버에 연결됨');
        setConnectionStatus('connected');
      });

      socketRef.current.on('disconnect', () => {
        console.log('카메라 서버 연결 끊김');
        setConnectionStatus('disconnected');
        setVideoStream(null);
        setMarkerDetected(false);
      });

      socketRef.current.on('video_frame', (data) => {
        if (data.image) {
          setVideoStream(`data:image/jpeg;base64,${data.image}`);
        }
        if (data.marker_detected !== undefined) {
          setMarkerDetected(data.marker_detected);
        }
      });

      socketRef.current.on('measurement_result', (data) => {
        console.log('측정 결과 수신:', data);
        
        setMeasurementResult(data.dimensions);
        
        // 측정된 물체 크기 정보 처리 (박스 추천은 제거)
        if (data.measurements) {
          setProductDimensions({
            width: data.measurements.width,
            length: data.measurements.length,
            height: data.measurements.height,
            volume: data.measurements.width * data.measurements.length * data.measurements.height
          });
        }
        
        // 측정 성공 시 결과 단계로 이동
        if (data.dimensions && 
            data.dimensions !== '마커를 먼저 인식시켜주세요.' && 
            !data.dimensions.includes('실패') && 
            !data.dimensions.includes('찾을 수 없습니다') && 
            !data.dimensions.includes('인식할 수 없습니다')) {
          
          // 첫 번째 물체 측정 완료 시 팝업 표시
          if (measuredItems.length === 0) {
            setShowMoreItemsPopup(true);
          } else {
            // 추가 물체 측정 완료 시 바로 결과로 이동
            setCurrentStep('result');
          }
        } else {
          setCurrentStep('initial');
          if (data.dimensions !== '마커를 먼저 인식시켜주세요.' && data.dimensions !== '') {
            alert(`측정에 실패했습니다: ${data.dimensions}`);
          }
        }
      });

      socketRef.current.on('connect_error', (error) => {
        console.error('연결 오류:', error);
        setConnectionStatus('disconnected');
      });

    } catch (error) {
      console.error('Socket.IO 로드 오류:', error);
      setConnectionStatus('disconnected');
    }
  };

  const disconnectCamera = () => {
    if (socketRef.current) {
      socketRef.current.disconnect();
    }
    setConnectionStatus('disconnected');
    setVideoStream(null);
    setMeasurementResult('');
    setMarkerDetected(false);
  };

  const generatePackagingSimulation = () => {
    if (!productDimensions || !recommendedBox) return null;

    // 랜덤으로 1-3개의 추가 물체 생성 (원래 물체보다 작게)
    const numItems = Math.floor(Math.random() * 3) + 1;
    const items = [{
      id: 'main',
      width: productDimensions.width,
      length: productDimensions.length,
      height: productDimensions.height,
      color: '#3B82F6',
      name: '측정된 상품'
    }];

    // 추가 물체들 생성
    for (let i = 0; i < numItems; i++) {
      const scale = 0.3 + Math.random() * 0.4; // 30-70% 크기
      items.push({
        id: `item${i + 1}`,
        width: productDimensions.width * scale,
        length: productDimensions.length * scale,
        height: productDimensions.height * scale,
        color: ['#EF4444', '#10B981', '#F59E0B', '#8B5CF6'][i % 4],
        name: `상품 ${i + 1}`
      });
    }

    // 간단한 포장 배치 알고리즘
    const boxWidth = recommendedBox.specs?.maxW || recommendedBox.maxW || 350;
    const boxLength = recommendedBox.specs?.maxL || recommendedBox.maxL || 250;
    const boxHeight = recommendedBox.specs?.maxH || recommendedBox.maxH || 210;
    
    const placedItems = [];
    let currentX = 10, currentY = 10, currentZ = 10;
    let maxHeightInRow = 0;

    items.forEach((item, index) => {
      // 현재 위치에 배치 가능한지 확인
      if (currentX + item.width > boxWidth - 10) {
        // 다음 줄로
        currentX = 10;
        currentY += maxHeightInRow + 5;
        maxHeightInRow = 0;
      }

      if (currentY + item.length > boxLength - 10) {
        // 다음 층으로
        currentY = 10;
        currentZ += maxHeightInRow + 5;
        maxHeightInRow = 0;
      }

      placedItems.push({
        ...item,
        x: currentX,
        y: currentY,
        z: currentZ
      });

      currentX += item.width + 5;
      maxHeightInRow = Math.max(maxHeightInRow, item.height);
    });

    return {
      items: placedItems,
      box: { width: boxWidth, length: boxLength, height: boxHeight },
      efficiency: Math.min(95, 65 + Math.random() * 20) // 65-85% 효율성
    };
  };

  const handleAnalyze = () => {
    if (socketRef.current && connectionStatus === 'connected' && markerDetected) {
      setCurrentStep('analyzing');
      socketRef.current.emit('measure');
    } else if (!markerDetected) {
      alert('ArUco 마커를 먼저 인식시켜주세요.');
    } else {
      alert('카메라가 연결되지 않았습니다.');
    }
  };

  const handleClearMeasurement = () => {
    if (socketRef.current) {
      socketRef.current.emit('clear');
    }
    setMeasurementResult('');
    setProductDimensions(null);
    setRecommendedBox(null);
  };

  const handleUsePackaging = async () => {
    setCurrentStep('packaging_loading');
    setIsPackingLoading(true);
    
    try {
      // 측정된 물체들의 데이터를 백엔드로 전송
      const itemsToSend = measuredItems.map(item => [
        Math.round(item.width),
        Math.round(item.length), 
        Math.round(item.height)
      ]);

      console.log('🚀 전송할 물체 데이터:', itemsToSend);
      console.log('📊 총 물체 개수:', measuredItems.length);

      // 백엔드에서 패킹 데이터 가져오기
      const response = await fetch('http://localhost:8002/pack/boxes', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          items: itemsToSend
        })
      });
      
      console.log('📡 백엔드 응답 상태:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('✅ 받은 패킹 데이터:', data);
        
        // 오류 응답 확인
        if (data.error) {
          throw new Error(data.message || '패킹 데이터에 오류가 있습니다');
        }
        
        setPackingData(data);
        
        // 🔥 백엔드에서 받은 박스 추천 결과 처리
        if (data.recommended_box && data.recommended_box.success) {
          const backendRecommendation = data.recommended_box;
          const recommendedBoxInfo = {
            name: backendRecommendation.box_name,
            dimensions: backendRecommendation.dimensions,
            price: backendRecommendation.price,
            specs: backendRecommendation.specs,
            // 프론트엔드 박스 정보와 매칭해서 이미지 추가
            ...findBoxImageById(backendRecommendation.box_name)
          };
          
          setRecommendedBox(recommendedBoxInfo);
          console.log('📦 Azure OpenAI 추천 박스:', recommendedBoxInfo);
        } else {
          // AI 추천 실패 시 로컬 추천 사용
          console.log('⚠️ AI 박스 추천 실패, 로컬 추천 사용:', data.recommended_box?.error);
          const containerSize = data.container_size;
          const fallbackBoxInfo = findBestBoxForContainer(containerSize);
          setRecommendedBox({
            ...fallbackBoxInfo,
            fallback: true,
            ai_error: data.recommended_box?.error
          });
        }
        
        // 최종 측정된 물체 목록은 이미 업데이트됨
        
        // 로딩 시간 후 결과 화면으로 이동
        setTimeout(() => {
          setCurrentStep('packaging_result');
          setIsPackingLoading(false);
        }, 2000);
      } else {
        const errorText = await response.text();
        throw new Error(`서버 오류 (${response.status}): ${errorText}`);
      }
    } catch (error) {
      console.error('❌ 패킹 데이터 로딩 실패:', error);
      
      // 오류 메시지 표시
      alert(`패킹 시뮬레이션 오류: ${error.message}`);
      
      // 실패 시 기존 시뮬레이션 사용
      const simulation = generatePackagingSimulation();
      setPackagingSimulation(simulation);
      
      setTimeout(() => {
        setCurrentStep('packaging_result');
        setIsPackingLoading(false);
      }, 1000);
    }
  };

  // 박스 이름으로 프론트엔드 박스 정보 찾기 (이미지 등)
  const findBoxImageById = (boxName) => {
    const frontendBox = boxSizes.find(box => 
      box.name.includes(boxName) || 
      boxName.includes(box.name.replace(' 박스', ''))
    );
    
    return frontendBox ? {
      image: frontendBox.image,
      id: frontendBox.id,
      volume: frontendBox.volume
    } : {
      image: null,
      id: 'unknown'
    };
  };

  // 컨테이너 크기에 맞는 최적 박스 찾기 함수 (fallback용)
  const findBestBoxForContainer = (containerSize) => {
    const { w, d, h } = containerSize;
    const safetyMargin = 1.05; // 5% 여유 공간
    
    // 박스 크기 순서대로 확인
    for (const box of boxSizes) {
      const fitsWidth = (w * safetyMargin) <= box.maxW;
      const fitsLength = (d * safetyMargin) <= box.maxL;
      const fitsHeight = (h * safetyMargin) <= box.maxH;
      
      if (fitsWidth && fitsLength && fitsHeight) {
        return {
          name: box.name,
          dimensions: box.dimensions,
          specs: {
            maxW: box.maxW,
            maxL: box.maxL,
            maxH: box.maxH
          },
          price: box.price,
          image: box.image,
          id: box.id,
          volume: box.volume
        };
      }
    }
    
    // 모든 박스에 안 맞으면 특수 포장 추천
    return {
      name: '특수 포장',
      dimensions: '표준 박스보다 큰 물체입니다',
      specs: { maxW: 999, maxL: 999, maxH: 999 },
      price: '별도 문의',
      image: null,
      id: 'special'
    };
  };

  // 다중 촬영 관련 함수들
  const handleAddMoreItems = () => {
    // 현재 측정된 물체를 배열에 추가
    if (productDimensions) {
      const newItem = {
        id: currentItemIndex,
        width: productDimensions.width,
        length: productDimensions.length,
        height: productDimensions.height,
        name: `물체 ${currentItemIndex}`
      };
      setMeasuredItems(prev => [...prev, newItem]);
      setCurrentItemIndex(prev => prev + 1);
      // 현재 측정 정보 초기화 (중복 카운트 방지)
      setProductDimensions(null);
    }

    setShowMoreItemsPopup(false);
    
    // 최대 4개까지만 허용
    if (measuredItems.length + 1 >= 4) {
      setCurrentStep('result');
    } else {
      // 다음 물체 촬영을 위해 초기화
      handleClearMeasurement();
      setCurrentStep('initial');
    }
  };

  const handleNoMoreItems = () => {
    // 현재 측정된 물체를 배열에 추가하고 결과로 이동
    if (productDimensions) {
      const newItem = {
        id: currentItemIndex,
        width: productDimensions.width,
        length: productDimensions.length,
        height: productDimensions.height,
        name: `물체 ${currentItemIndex}`
      };
      setMeasuredItems(prev => [...prev, newItem]);
      // 현재 측정 정보 초기화 (중복 카운트 방지)
      setProductDimensions(null);
    }

    setShowMoreItemsPopup(false);
    setCurrentStep('result');
  };

  const handleRestart = () => {
    handleClearMeasurement();
    setCurrentStep('initial');
    setPackagingSimulation(null);
    setPackingData(null);
    setIsPackingLoading(false);
    setRecommendedBox(null); // 박스 추천 초기화 추가
    
    // 다중 촬영 관련 state 초기화
    setMeasuredItems([]);
    setShowMoreItemsPopup(false);
    setCurrentItemIndex(1);
    
    // 디버그 관련 state 초기화
    setShowDebugPanel(false);
    setDebugResults(null);
  
    // 웰컴 페이지로 돌아가기
    if (onBack) {
      onBack();
   }
  };

  const renderContent = () => {
    switch (currentStep) {
      case 'initial':
        return (
          <div className="flex flex-col items-center px-6">
            <h1 className="text-4xl font-bold text-green-800 mb-4">상품촬영</h1>
            
            {/* 촬영 진행 상태 표시 */}
            {measuredItems.length > 0 && (
              <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                <p className="text-blue-700 text-center font-medium">
                  추가 물체 촬영 중 ({measuredItems.length}/4개 완료)
                </p>
                <div className="flex justify-center gap-2 mt-2">
                  {Array.from({length: 4}, (_, i) => (
                    <div
                      key={i}
                      className={`w-3 h-3 rounded-full ${
                        i < measuredItems.length ? 'bg-blue-500' : 
                        i === measuredItems.length ? 'bg-blue-300 animate-pulse' : 'bg-gray-300'
                      }`}
                    />
                  ))}
                </div>
              </div>
            )}
            
            <p className="text-green-700 mb-12 text-center text-lg">
              {measuredItems.length === 0 
                ? '상품을 중앙에 맞춰서 촬영해주세요.'
                : `${measuredItems.length + 1}번째 물체를 촬영해주세요.`
              }
            </p>
            
            <div className="relative w-full max-w-md mx-auto mb-12">
              <div className={`relative rounded-3xl overflow-hidden ${
                connectionStatus === 'connected' 
                  ? markerDetected 
                    ? 'ring-4 ring-green-800' 
                    : 'ring-4 ring-red-500'
                  : 'ring-4 ring-gray-300'
              }`}>
                {videoStream && connectionStatus === 'connected' ? (
                  <img 
                    ref={videoRef}
                    src={videoStream}
                    alt="Camera feed" 
                    className="w-full h-80 object-cover"
                  />
                ) : (
                  <div className="w-full h-80 bg-gray-100 flex items-center justify-center">
                    <div className="text-center">
                      <Camera className="w-16 h-16 mx-auto mb-4 text-gray-400" />
                      <p className="text-gray-500 text-lg">
                        {connectionStatus === 'connecting' ? '카메라 연결 중...' : '카메라를 연결하는 중입니다'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
              
              {connectionStatus === 'connected' && (
                <div className={`absolute top-4 left-4 px-3 py-1 rounded-full text-white text-sm font-medium ${
                  markerDetected ? 'bg-green-800' : 'bg-red-500'
                }`}>
                  {markerDetected ? '✓ 마커 인식됨' : '마커를 찾는 중...'}
                </div>
              )}
            </div>
            
            <div className="flex flex-col gap-4 w-full max-w-sm">
              <button 
                onClick={handleAnalyze}
                disabled={!markerDetected || connectionStatus !== 'connected'}
                className={`px-12 py-4 rounded-full text-lg font-semibold transition-all duration-200 ${
                  markerDetected && connectionStatus === 'connected'
                    ? 'bg-green-800 text-white hover:bg-green-900 shadow-lg' 
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                분석하기
              </button>
              
              <button 
                onClick={handleRestart}
                className="text-green-800 py-2 text-lg hover:text-green-900 transition-colors"
              >
                재분석하기
              </button>
            </div>
          </div>
        );

      case 'analyzing':
        return (
          <div className="flex flex-col items-center px-6">
            <h1 className="text-4xl font-bold text-green-800 mb-8">상품촬영</h1>
            <p className="text-green-700 mb-12 text-center text-xl">상품을 분석중입니다.</p>
            
            <div className="relative w-full max-w-md mx-auto mb-12">
              <div className="relative rounded-3xl overflow-hidden">
                <img 
                  src={videoStream || "https://images.unsplash.com/photo-1611930022073-b7a4ba5fcccd?w=400"}
                  alt="Analyzing product" 
                  className="w-full h-80 object-cover opacity-75"
                />
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="bg-white/95 px-6 py-3 rounded-full flex items-center gap-3 shadow-lg">
                    <div className="w-5 h-5 border-2 border-gray-300 border-t-green-800 rounded-full animate-spin"></div>
                    <span className="text-gray-700 font-medium text-lg">분석중...</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case 'result':
        const totalMeasuredItems = measuredItems.length;
        
        return (
          <div className="flex flex-col items-center px-6">
            <div className="text-center">
              <h2 className="text-green-800 text-3xl font-bold mb-3">측정 완료</h2>
              <h1 className="text-4xl font-bold text-gray-900 mb-2">
                {totalMeasuredItems}개 물체 측정됨
              </h1>
              <p className="text-xl text-gray-600 mb-6">
                포장 최적화를 위해 분석을 진행하세요
              </p>
            </div>

            <div className="w-full max-w-xl mx-auto mb-6">
              <div className="flex justify-center">
                <div className="relative">
                  <div className="w-96 h-72 bg-gradient-to-br from-green-100 to-green-200 rounded-lg shadow-lg flex items-center justify-center">
                    <div className="text-center">
                      <Package className="w-24 h-24 text-green-700 mx-auto mb-4" />
                      <span className="text-2xl font-bold text-green-800">
                        📦 {totalMeasuredItems}개 물체
                      </span>
                      <p className="text-green-600 mt-2">최적 포장 계산 준비 완료</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="space-y-2 mb-6 w-full max-w-xl">
              <div className="flex items-center justify-center text-lg">
                <span className="text-green-800 mr-3 text-4xl font-bold">✓</span>
                <span className="text-gray-700">
                  총 {totalMeasuredItems}개 물체 측정 완료
                </span>
              </div>
              
              {/* 측정된 물체들 */}
              {measuredItems.map((item, index) => (
                <div key={item.id} className="flex items-center justify-center text-sm bg-gray-50 rounded-lg p-2">
                  <span className="text-green-600 mr-2 text-lg font-bold">📦</span>
                  <span className="text-gray-600">
                    {item.name}: {item.width.toFixed(0)} × {item.length.toFixed(0)} × {item.height.toFixed(0)}mm
                  </span>
                </div>
              ))}
              
              <div className="flex items-center justify-center text-lg">
                <span className="text-green-800 mr-3 text-4xl font-bold">🎯</span>
                <span className="text-gray-700">
                  AI 분석으로 최적 박스 크기 계산 준비됨
                </span>
              </div>
              
              <div className="flex items-center justify-center text-lg">
                <span className="text-green-800 mr-3 text-4xl font-bold">♻️</span>
                <span className="text-gray-700">
                  포장재 낭비 최소화 및 배송비 절감
                </span>
              </div>
            </div>
            
            <p className="text-green-800 text-center mb-8 px-4 text-lg leading-relaxed max-w-xl mx-auto font-medium">
              모든 물체를 고려한 최적의 박스 크기와<br />
              포장 배치를 AI가 계산해드립니다.
            </p>
            
            <div className="flex flex-col gap-6 w-full max-w-md">
              <button 
                onClick={handleUsePackaging}
                disabled={totalMeasuredItems === 0}
                className={`px-12 py-5 rounded-full text-2xl font-semibold transition-colors shadow-lg ${
                  totalMeasuredItems > 0
                    ? 'bg-green-800 text-white hover:bg-green-900' 
                    : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                }`}
              >
                최적 포장 계산하기
              </button>
              <button 
                onClick={handleRestart}
                className="text-green-800 py-5 text-2xl font-semibold hover:text-green-900 transition-colors shadow-md rounded-full border border-green-300 hover:border-green-400"
              >
                재분석하기
              </button>
            </div>

            {measurementResult && (
              <div className="mt-6 p-4 bg-gray-50 rounded-xl w-full max-w-xl">
                <h3 className="font-semibold text-gray-800 mb-2 text-lg">최근 측정 결과</h3>
                <p className="text-gray-600">{measurementResult}</p>
                <p className="text-sm text-gray-500 mt-2">
                  * 최종 박스 추천은 모든 물체를 고려하여 계산됩니다
                </p>
              </div>
            )}
          </div>
        );

      case 'packaging_loading':
        return (
          <div className="flex flex-col items-center px-6 pt-16">
            <div className="text-center mb-12">
              <h1 className="text-4xl font-bold text-green-800 mb-4">포장 방법 분석 중</h1>
              <p className="text-xl text-green-600">최적의 포장 방법을 계산하고 있습니다...</p>
            </div>

            {/* 시네마틱 로딩 애니메이션 */}
            <div className="relative w-80 h-80 mb-12">
              {/* 외곽 원형 애니메이션 */}
              <div className="absolute inset-0 rounded-full border-4 border-gray-200"></div>
              <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-green-600 animate-spin"></div>
              
              {/* 중앙 박스 애니메이션 */}
              <div className="absolute inset-12 bg-gradient-to-br from-green-100 to-green-200 rounded-full flex items-center justify-center">
                <Package className="w-24 h-24 text-green-700 animate-pulse" />
              </div>
              
              {/* 내부 회전 애니메이션 */}
              <div className="absolute inset-8 rounded-full border-2 border-transparent border-r-green-400 animate-spin" style={{animationDirection: 'reverse', animationDuration: '3s'}}></div>
            </div>

            {/* 진행 단계 표시 */}
            <div className="space-y-4 text-center">
              <div className="flex items-center justify-center gap-3">
                <div className="w-3 h-3 bg-green-600 rounded-full animate-pulse"></div>
                <span className="text-green-700 font-medium">상품 크기 분석 완료</span>
              </div>
              <div className="flex items-center justify-center gap-3">
                <div className="w-3 h-3 bg-green-600 rounded-full animate-pulse" style={{animationDelay: '0.5s'}}></div>
                <span className="text-green-700 font-medium">박스 크기 최적화 완료</span>
              </div>
              <div className="flex items-center justify-center gap-3">
                <div className="w-3 h-3 bg-green-600 rounded-full animate-pulse" style={{animationDelay: '1s'}}></div>
                <span className="text-green-500">포장 배치 계산 중</span>
              </div>
            </div>
          </div>
        );

      case 'packaging_result':
        const totalMeasuredItemsResult = measuredItems.length;
        
        return (
          <div className="flex flex-col items-center px-6">
            {/* 뒤로가기 버튼과 제목 */}
            <div className="w-full max-w-md mx-auto mb-8">
              <div className="flex items-center mb-6">
                <button 
                  onClick={handleRestart}
                  className="text-gray-600 hover:text-gray-800 transition-colors"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
                <h1 className="text-xl font-bold text-green-800 text-center flex-1">최적 포장 결과</h1>
              </div>
            </div>

            {/* 추천 박스 정보 */}
            {recommendedBox && (
              <div className="w-full max-w-md mx-auto mb-6">
                <div className="text-center mb-4">
                  <h2 className="text-2xl font-bold text-green-800 mb-2">
                    {recommendedBox.fallback ? '추천 박스 (로컬 계산)' : '추천 박스 (AI 분석)'}
                  </h2>
                  <h3 className="text-xl font-semibold text-gray-900">{recommendedBox.name}</h3>
                  <p className="text-gray-600">{recommendedBox.dimensions}</p>
                  {recommendedBox.price && (
                    <p className="text-green-600 font-medium">{recommendedBox.price}</p>
                  )}
                </div>
                
                <div className="flex justify-center mb-4">
                  {recommendedBox.image ? (
                    <img 
                      src={recommendedBox.image} 
                      alt={recommendedBox.name}
                      className="w-48 h-36 object-contain rounded-lg"
                      onError={(e) => {
                        e.target.style.display = 'none';
                        e.target.nextSibling.style.display = 'flex';
                      }}
                    />
                  ) : null}
                  <div 
                    className="w-48 h-36 bg-amber-200 rounded-lg shadow-lg flex items-center justify-center"
                    style={{display: recommendedBox.image ? 'none' : 'flex'}}
                  >
                    <span className="text-4xl font-bold text-gray-800">
                      {recommendedBox.id !== 'special' ? recommendedBox.id : '📦'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* 3D 박스 시각화 */}
            <div className="w-full max-w-md mx-auto mb-8">
              {isPackingLoading ? (
                <div className="w-full h-64 bg-gray-100 rounded-xl flex items-center justify-center">
                  <div className="flex flex-col items-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600 mb-2"></div>
                    <span className="text-gray-600">3D 모델 생성 중...</span>
                  </div>
                </div>
              ) : (
                <PackingVisualization3D containerData={packingData} />
              )}
              
              {/* 패킹 효율성 정보 */}
              {packingData && (
                <div className="mt-4 p-3 bg-green-50 rounded-lg">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-green-700 font-medium">패킹 효율성</span>
                    <span className="text-green-800 font-bold">{packingData.efficiency}%</span>
                  </div>
                  <div className="flex justify-between items-center text-sm mt-1">
                    <span className="text-green-700 font-medium">박스 타입</span>
                    <span className="text-green-800">{packingData.box_type}</span>
                  </div>
                  {recommendedBox && recommendedBox.name !== '특수 포장' && (
                    <div className="flex justify-between items-center text-sm mt-1">
                      <span className="text-green-700 font-medium">추천 박스</span>
                      <span className="text-green-800">{recommendedBox.name}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* 상품 정보 */}
            <div className="w-full max-w-md mx-auto space-y-4 text-left">
              <div className="flex justify-between items-center">
                <span className="text-gray-600 font-medium">총 상품 수</span>
                <span className="text-gray-800">{totalMeasuredItemsResult}개</span>
              </div>
              
              {/* 측정된 각 물체별 정보 */}
              {measuredItems.map((item, index) => (
                <div key={item.id} className="bg-gray-50 rounded-lg p-3 space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600 font-medium">{item.name}</span>
                    <span className="text-sm text-gray-500">#{item.id}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-600 text-sm">규격</span>
                    <span className="text-gray-800 text-sm">
                      {item.width.toFixed(0)} × {item.length.toFixed(0)} × {item.height.toFixed(0)} mm
                    </span>
                  </div>
                </div>
              ))}

              {/* 구분선 */}
              <div className="border-t border-gray-300 my-6"></div>

              <div className="flex justify-between items-center">
                <span className="text-green-700 font-medium">계산된 상자 규격</span>
                <span className="text-gray-800">
                  {packingData 
                    ? `${packingData.container_size.w} × ${packingData.container_size.d} × ${packingData.container_size.h} mm`
                    : '계산 중...'
                  }
                </span>
              </div>
              
              {recommendedBox && (
                <div className="flex justify-between items-center">
                  <span className="text-green-700 font-medium">실제 사용 박스</span>
                  <span className="text-gray-800">{recommendedBox.name}</span>
                </div>
              )}
              
              <div className="flex justify-between items-center">
                <span className="text-green-700 font-medium">파손위험도</span>
                <span className="text-gray-800">낮음</span>
              </div>
              
              <div className="flex justify-between items-center">
                <span className="text-green-700 font-medium">완충재</span>
                <span className="text-gray-800">종이류</span>
              </div>

              {recommendedBox?.price && recommendedBox.price !== '별도 문의' && (
                <div className="flex justify-between items-center">
                  <span className="text-green-700 font-medium">포장 비용</span>
                  <span className="text-gray-800">{recommendedBox.price}</span>
                </div>
              )}

              {/* 개선 효과 */}
              <div className="mt-8 space-y-3">
                <div className="flex items-center justify-center text-lg">
                  <span className="text-green-800 mr-3 text-4xl font-bold">📦</span>
                  <span className="text-gray-700">
                    총 {totalMeasuredItemsResult}개 물체 동시 최적화 완료
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-gray-800">3D 패킹으로 공간 효율성 {packingData?.efficiency || 85}% 달성</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-gray-800">일반 포장 대비 완충재 30% 절감</span>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-gray-800">최적 박스 선택으로 배송비 절약</span>
                </div>
              </div>
            </div>

            {/* 버튼 */}
            <div className="w-full max-w-md mx-auto mt-12">
              <button 
                onClick={handleRestart}
                className="w-full bg-green-800 text-white py-4 rounded-full text-lg font-semibold hover:bg-green-900 transition-colors shadow-lg"
              >
                다음 상품 스캔하기
              </button>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="mx-auto w-full max-w-4xl px-4 py-12 md:py-20">
        {renderContent()}
        
        {/* 다중 촬영 팝업 */}
        {showMoreItemsPopup && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-2xl p-8 max-w-md w-full mx-4 shadow-2xl">
              <div className="text-center">
                <Package className="w-16 h-16 mx-auto mb-4 text-green-600" />
                <h2 className="text-2xl font-bold text-gray-900 mb-4">
                  물체 측정 완료!
                </h2>
                <p className="text-gray-600 mb-2">
                  현재 측정된 물체: {measuredItems.length + 1}개
                </p>
                <p className="text-gray-600 mb-6">
                  추가로 물체를 촬영하시겠습니까?<br />
                  <span className="text-sm text-gray-500">(최대 4개까지 가능)</span>
                </p>
                
                <div className="flex gap-3">
                  <button
                    onClick={handleNoMoreItems}
                    className="flex-1 px-6 py-3 border border-gray-300 rounded-full text-gray-700 font-semibold hover:bg-gray-50 transition-colors"
                  >
                    아니오
                  </button>
                  <button
                    onClick={handleAddMoreItems}
                    disabled={measuredItems.length + 1 >= 4}
                    className={`flex-1 px-6 py-3 rounded-full font-semibold transition-colors ${
                      measuredItems.length + 1 >= 4
                        ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        : 'bg-green-600 text-white hover:bg-green-700'
                    }`}
                  >
                    네 ({4 - (measuredItems.length + 1)}개 더 가능)
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 디버그 패널 */}
        {showDebugPanel && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-xl font-bold">🐛 패킹 시스템 디버깅</h2>
                <button
                  onClick={() => setShowDebugPanel(false)}
                  className="text-gray-500 hover:text-gray-700 text-xl"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-4">
                {/* 테스트 버튼들 */}
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => runDebugTest('/health')}
                    className="bg-blue-500 text-white px-4 py-2 rounded hover:bg-blue-600 disabled:bg-gray-400"
                    disabled={isDebugLoading}
                  >
                    헬스체크
                  </button>
                  
                  <button
                    onClick={() => runDebugTest('/pack/test')}
                    className="bg-green-500 text-white px-4 py-2 rounded hover:bg-green-600 disabled:bg-gray-400"
                    disabled={isDebugLoading}
                  >
                    패킹 테스트
                  </button>
                  
                  <button
                    onClick={() => runDebugTest('/pack/debug')}
                    className="bg-purple-500 text-white px-4 py-2 rounded hover:bg-purple-600 disabled:bg-gray-400"
                    disabled={isDebugLoading}
                  >
                    모듈 디버그
                  </button>
                  
                  <button
                    onClick={() => runDebugTest('/pack/simple', [[30, 20, 10], [40, 30, 15]])}
                    className="bg-orange-500 text-white px-4 py-2 rounded hover:bg-orange-600 disabled:bg-gray-400"
                    disabled={isDebugLoading}
                  >
                    간단한 패킹
                  </button>
                </div>
                
                {/* AI 박스 추천 테스트 */}
                <div className="border-t pt-4">
                  <h4 className="font-semibold mb-3 text-gray-800">🤖 AI 박스 추천 테스트 (app.py)</h4>
                  <div className="grid grid-cols-1 gap-2">
                    <button
                      onClick={async () => {
                        try {
                          const response = await fetch('http://localhost:8001/health');
                          const result = await response.json();
                          setDebugResults({
                            endpoint: 'app.py /health',
                            status: response.status,
                            success: response.ok,
                            data: result,
                            timestamp: new Date().toLocaleTimeString()
                          });
                        } catch (error) {
                          setDebugResults({
                            endpoint: 'app.py /health',
                            success: false,
                            error: error.message,
                            timestamp: new Date().toLocaleTimeString()
                          });
                        }
                      }}
                      className="bg-cyan-500 text-white px-4 py-2 rounded hover:bg-cyan-600 disabled:bg-gray-400"
                      disabled={isDebugLoading}
                    >
                      app.py 헬스체크
                    </button>
                    
                    <button
                      onClick={async () => {
                        try {
                          const testData = {
                            width: 100,
                            length: 80,
                            height: 50
                          };
                          const response = await fetch('http://localhost:8001/recommend', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(testData)
                          });
                          const result = await response.json();
                          setDebugResults({
                            endpoint: 'app.py /recommend',
                            status: response.status,
                            success: response.ok,
                            data: result,
                            testInput: testData,
                            timestamp: new Date().toLocaleTimeString()
                          });
                        } catch (error) {
                          setDebugResults({
                            endpoint: 'app.py /recommend',
                            success: false,
                            error: error.message,
                            timestamp: new Date().toLocaleTimeString()
                          });
                        }
                      }}
                      className="bg-cyan-600 text-white px-4 py-2 rounded hover:bg-cyan-700 disabled:bg-gray-400"
                      disabled={isDebugLoading}
                    >
                      AI 박스 추천 테스트
                    </button>
                  </div>
                </div>

                {/* 현재 측정된 물체로 테스트 */}
                {measuredItems.length > 0 && (
                  <button
                    onClick={() => {
                      const items = measuredItems.map(item => [
                        Math.round(item.width),
                        Math.round(item.length),
                        Math.round(item.height)
                      ]);
                      runDebugTest('/pack/simple', items);
                    }}
                    className="w-full bg-indigo-500 text-white px-4 py-2 rounded hover:bg-indigo-600 disabled:bg-gray-400"
                    disabled={isDebugLoading}
                  >
                    현재 측정된 물체들로 테스트 ({measuredItems.length}개)
                  </button>
                )}

                {/* 로딩 상태 */}
                {isDebugLoading && (
                  <div className="text-center py-4">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                    <p className="mt-2 text-gray-600">테스트 실행 중...</p>
                  </div>
                )}

                {/* 테스트 결과 */}
                {debugResults && (
                  <div className="mt-6">
                    <h3 className="font-semibold mb-2">
                      테스트 결과 ({debugResults.timestamp})
                    </h3>
                    
                    <div className={`p-4 rounded border ${debugResults.success ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                      <div className="mb-2">
                        <span className="font-medium">엔드포인트:</span> {debugResults.endpoint}
                      </div>
                      
                      {debugResults.status && (
                        <div className="mb-2">
                          <span className="font-medium">상태:</span> {debugResults.status}
                        </div>
                      )}
                      
                      {debugResults.error ? (
                        <div>
                          <span className="font-medium text-red-600">오류:</span>
                          <pre className="mt-1 text-sm bg-red-100 p-2 rounded overflow-x-auto">
                            {debugResults.error}
                          </pre>
                        </div>
                      ) : (
                        <div>
                          <span className="font-medium text-green-600">응답:</span>
                          <pre className="mt-1 text-sm bg-gray-100 p-2 rounded overflow-x-auto max-h-64 overflow-y-auto">
                            {JSON.stringify(debugResults.data, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* 디버깅 팁 */}
                <div className="mt-6 p-4 bg-blue-50 rounded border border-blue-200">
                  <h4 className="font-semibold text-blue-800 mb-2">🔍 디버깅 가이드</h4>
                  <ul className="text-sm text-blue-700 space-y-1">
                    <li>• <strong>헬스체크</strong>: main.py 서버 상태 및 설정 확인</li>
                    <li>• <strong>패킹 테스트</strong>: 미리 정의된 데이터로 전체 패킹 플로우 테스트</li>
                    <li>• <strong>모듈 디버그</strong>: wire_packing 모듈 직접 테스트</li>
                    <li>• <strong>간단한 패킹</strong>: 기본적인 패킹 알고리즘만 테스트</li>
                    <li>• <strong>app.py 헬스체크</strong>: AI 박스 추천 서비스 상태 확인</li>
                    <li>• <strong>AI 박스 추천 테스트</strong>: Azure OpenAI 기반 박스 추천 직접 테스트</li>
                  </ul>
                  <div className="mt-3 p-2 bg-yellow-100 rounded text-yellow-800 text-xs">
                    ⚠️ AI 박스 추천이 실패하면 자동으로 로컬 계산으로 fallback됩니다.
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* 디버그 버튼 (하단 우측) */}
      {!showDebugPanel && (
        <button
          onClick={() => setShowDebugPanel(true)}
          className="fixed bottom-4 right-4 bg-red-600 text-white px-4 py-2 rounded-full text-sm font-bold z-40 shadow-lg hover:bg-red-700"
        >
          🐛 DEBUG
        </button>
      )}
    </div>
  );
};

export default ProductPhotoAnalyzer;