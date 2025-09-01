"use client";

import { useState } from 'react';

export default function MonitoringButton() {
  const [isMonitoring, setIsMonitoring] = useState(false);

  const handleMonitoring = () => {
    setIsMonitoring(!isMonitoring);
    alert(isMonitoring ? 'Monitoring stopped.' : 'BTC/USDT monitoring started.');
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
      {isMonitoring ? 'Stop Monitoring' : 'Start Monitoring'}
    </button>
  );
}
