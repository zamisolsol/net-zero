"use client";

import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';

const EnvironmentReport = ({ onBack }) => {
  const [startYear, setStartYear] = useState('2025.05');
  const [endYear, setEndYear] = useState('2025.05');
  const [isDownloading, setIsDownloading] = useState(false);

  const handlePdfDownload = async () => {
    try {
      setIsDownloading(true);
      
      console.log('PDF 페이지로 이동...');
      
      // 새 창에서 PDF 페이지 열기
      window.open('http://127.0.0.1:8000/report/', '_blank');
      
      console.log('PDF 페이지 열기 완료');
      
    } catch (error) {
      console.error('PDF 페이지 열기 오류:', error);
      alert('PDF 페이지를 열 수 없습니다. 다시 시도해주세요.');
    } finally {
      // 잠시 후 로딩 상태 해제
      setTimeout(() => {
        setIsDownloading(false);
      }, 1000);
    }
  };

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-md mx-auto px-6 py-8">
        {/* 헤더 */}
        <div className="flex items-center mb-8">
          <button 
            onClick={onBack}
            className="text-gray-600 hover:text-gray-800 transition-colors mr-4"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-xl font-bold text-green-800">리포트</h1>
        </div>

        {/* 날짜 선택 */}
        <div className="mb-8">
          <div className="flex items-center gap-4 mb-4">
            <div className="relative">
              <select 
                value={startYear}
                onChange={(e) => setStartYear(e.target.value)}
                className="appearance-none bg-white border border-gray-300 rounded-lg px-4 py-2 pr-8 text-gray-700 focus:outline-none focus:border-green-500"
              >
                <option value="2025.05">2025.05</option>
                <option value="2025.04">2025.04</option>
                <option value="2025.03">2025.03</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
            </div>
            
            <span className="text-gray-500">~</span>
            
            <div className="relative">
              <select 
                value={endYear}
                onChange={(e) => setEndYear(e.target.value)}
                className="appearance-none bg-white border border-gray-300 rounded-lg px-4 py-2 pr-8 text-gray-700 focus:outline-none focus:border-green-500"
              >
                <option value="2025.05">2025.05</option>
                <option value="2025.04">2025.04</option>
                <option value="2025.03">2025.03</option>
              </select>
              <ChevronDown className="absolute right-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none" />
            </div>
          </div>
          
          <div className="text-lg font-medium text-gray-800">
            2025.05.01 ~ 2025.05.31
          </div>
        </div>

        {/* 통계 카드들 */}
        <div className="space-y-8 mb-16">
          {/* 총 포장 수 */}
          <div>
            <div className="text-lg font-medium text-gray-600 mb-2">총 포장 수</div>
            <div className="text-4xl font-bold text-green-800">60,000건</div>
          </div>

          {/* 탄소 절감량 */}
          <div>
            <div className="text-lg font-medium text-gray-600 mb-2">탄소 절감량</div>
            <div className="text-4xl font-bold text-green-800">10.8ton CO₂</div>
          </div>

          {/* 포장비 절감액 */}
          <div>
            <div className="text-lg font-medium text-gray-600 mb-2">포장비 절감액</div>
            <div className="text-4xl font-bold text-green-800">2,400,000원</div>
          </div>
        </div>

        {/* PDF 다운로드 버튼 */}
        <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2 w-full max-w-md px-6">
          <button 
            onClick={handlePdfDownload}
            disabled={isDownloading}
            className="w-full bg-green-800 text-white py-4 rounded-full text-lg font-semibold hover:bg-green-900 transition-colors shadow-lg disabled:bg-gray-400 disabled:cursor-not-allowed"
          >
            {isDownloading ? '다운로드 중...' : 'PDF 다운로드'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default EnvironmentReport;