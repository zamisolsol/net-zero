"use client";

import React from 'react';

const WelcomeScreen = ({ onStartScan, onEnvironmentReport }) => {
  return (
    <div className="min-h-screen bg-white">
      {/* 모바일 스타일 컨테이너 */}
      <div className="max-w-md mx-auto px-6 py-8 min-h-screen flex flex-col">
        
        {/* 메인 콘텐츠 영역 */}
        <div className="flex-1 flex flex-col justify-center items-center text-center">
          
          {/* 메인 텍스트 */}
          <div className="mb-32">
            <h1 className="text-2xl font-bold text-gray-800 mb-8">
              안녕하세요
            </h1>
            
            <div className="space-y-2">
              <p className="text-lg font-medium text-gray-600">
                환경을 생각하는 포장,
              </p>
              <p className="text-xl font-bold text-green-800">
                PACO입니다.
              </p>
            </div>
          </div>
        </div>

        {/* 하단 버튼 영역 */}
        <div className="space-y-4 pb-8">
          {/* 메인 버튼 - 상품 스캔하기 */}
          <button
            onClick={onStartScan}
            className="w-full bg-green-800 text-white py-4 rounded-full text-lg font-semibold hover:bg-green-900 transition-colors shadow-lg"
          >
            상품 스캔하기
          </button>

          {/* 서브 버튼 - 환경 리포트 확인하기 */}
          <button
            onClick={onEnvironmentReport}
            className="w-full border border-gray-300 text-gray-700 py-4 rounded-full text-lg font-medium hover:bg-gray-50 transition-colors"
          >
            환경 리포트 확인하기
          </button>
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;