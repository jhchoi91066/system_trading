"use client";

import { useState } from 'react';

export default function MonitoringButton() {
  const [isMonitoring, setIsMonitoring] = useState(false);

  const handleMonitoring = () => {
    setIsMonitoring(!isMonitoring);
    alert(isMonitoring ? '모니터링을 중지했습니다.' : 'BTC/USDT 모니터링을 시작했습니다.');
  };

  return (
    <button 
      onClick={handleMonitoring}
      className={`px-3 py-1 rounded text-xs transition-colors ${
        isMonitoring 
          ? 'bg-red-500 text-white hover:bg-red-600' 
          : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
      }`}
    >
      {isMonitoring ? '모니터링 중지' : '모니터링 시작'}
    </button>
  );
}
