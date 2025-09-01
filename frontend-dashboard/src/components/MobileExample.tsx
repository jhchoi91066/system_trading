"use client";

import React, { useState } from 'react';
import { 
  MobileContainer, 
  MobileCard, 
  MobileButtonGroup, 
  MobileFormGroup,
  MobileTable,
  MobileStatsGrid,
  MobileModal,
  MobileLoading,
  MobileError,
  MobileChartContainer
} from './MobileOptimized';

export default function MobileExample() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [showError, setShowError] = useState(false);

  const statsData = [
    { label: "Total Profit", value: "$1,234.56" },
    { label: "Trade Count", value: "42" },
    { label: "Win Rate", value: "68%" },
    { label: "Daily Return", value: "+2.3%" }
  ];

  const tableData = [
    ["BTC/USDT", "$45,230", "+2.3%", "12:34"],
    ["ETH/USDT", "$2,890", "-1.1%", "12:35"],
    ["ADA/USDT", "$0.42", "+5.7%", "12:36"]
  ];

  const handleRetry = () => {
    setShowError(false);
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 2000);
  };

  return (
    <MobileContainer>
      <MobileCard title="Mobile Components Demo">
        <MobileStatsGrid stats={statsData} className="mb-6" />
        
        <MobileButtonGroup className="mb-6">
          <button 
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium"
            onClick={() => setIsModalOpen(true)}
          >
            Open Modal
          </button>
          <button 
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-md font-medium"
            onClick={() => setIsLoading(true)}
          >
            Show Loading
          </button>
          <button 
            className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-md font-medium"
            onClick={() => setShowError(true)}
          >
            Show Error
          </button>
        </MobileButtonGroup>

        <MobileFormGroup label="Example Input" className="mb-6">
          <input 
            type="text" 
            className="linear-input w-full"
            placeholder="Enter some text..."
          />
        </MobileFormGroup>

        <MobileTable 
          headers={["Symbol", "Price", "Change", "Time"]}
          data={tableData}
          className="mb-6"
        />

        <MobileChartContainer title="Price Chart">
          <div className="h-64 bg-gray-700 rounded-md flex items-center justify-center text-gray-400">
            Chart Placeholder
          </div>
        </MobileChartContainer>

        {isLoading && <MobileLoading message="Loading data..." />}
        
        {showError && (
          <MobileError 
            message="Failed to load data. Please try again."
            onRetry={handleRetry}
            retryText="Retry"
          />
        )}
      </MobileCard>

      <MobileModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Mobile Modal Example"
      >
        <div className="space-y-4">
          <p className="text-gray-300">
            This is a mobile-optimized modal that works great on touch devices.
            It slides up from the bottom on mobile and appears centered on desktop.
          </p>
          <MobileButtonGroup>
            <button 
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-md font-medium"
              onClick={() => setIsModalOpen(false)}
            >
              Close Modal
            </button>
          </MobileButtonGroup>
        </div>
      </MobileModal>
    </MobileContainer>
  );
}