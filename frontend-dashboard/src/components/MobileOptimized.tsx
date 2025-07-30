"use client";

import React, { ReactNode } from 'react';

// Mobile-optimized Container Component
export function MobileContainer({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`container mx-auto px-4 sm:px-6 lg:px-8 mobile-safe-area-left mobile-safe-area-right ${className}`}>
      {children}
    </div>
  );
}

// Mobile-optimized Card Component
export function MobileCard({ 
  title, 
  children, 
  className = "",
  onClick
}: { 
  title?: string;
  children: ReactNode; 
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div 
      className={`mobile-card ${onClick ? 'mobile-clickable' : ''} ${className}`}
      onClick={onClick}
    >
      {title && (
        <h3 className="text-h3 text-white mb-4">{title}</h3>
      )}
      {children}
    </div>
  );
}

// Mobile-optimized Button Group
export function MobileButtonGroup({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`mobile-button-group ${className}`}>
      {children}
    </div>
  );
}

// Mobile-optimized Form Group
export function MobileFormGroup({ 
  label, 
  children, 
  className = "",
  error
}: { 
  label: string;
  children: ReactNode; 
  className?: string;
  error?: string;
}) {
  return (
    <div className={`mobile-form-group ${className}`}>
      <label className="block text-sm font-medium text-gray-300 mb-2">
        {label}
      </label>
      {children}
      {error && (
        <p className="mt-2 text-sm text-red-400">{error}</p>
      )}
    </div>
  );
}

// Mobile-optimized Table
export function MobileTable({ 
  headers, 
  data, 
  className = "" 
}: { 
  headers: string[];
  data: (string | number | React.ReactNode)[][];
  className?: string;
}) {
  return (
    <div className="mobile-table-container">
      <table className={`mobile-table w-full text-left ${className}`}>
        <thead>
          <tr className="border-b border-gray-700">
            {headers.map((header, index) => (
              <th key={index} className="py-3 px-3 text-sm font-medium text-gray-300 first:pl-4 last:pr-4">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-b border-gray-800 last:border-b-0">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="py-3 px-3 text-sm text-white first:pl-4 last:pr-4">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Mobile-optimized Stats Grid
export function MobileStatsGrid({ stats, className = "" }: { 
  stats: Array<{ label: string; value: string | number; }>;
  className?: string;
}) {
  return (
    <div className={`mobile-stats-grid ${className}`}>
      {stats.map((stat, index) => (
        <div key={index} className="mobile-stat-card">
          <div className="mobile-stat-value">{stat.value}</div>
          <div className="mobile-stat-label">{stat.label}</div>
        </div>
      ))}
    </div>
  );
}

// Mobile-optimized Modal
export function MobileModal({ 
  isOpen, 
  onClose, 
  title, 
  children 
}: { 
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  if (!isOpen) return null;

  return (
    <div className="mobile-modal" onClick={(e) => {
      if (e.target === e.currentTarget) onClose();
    }}>
      <div className="mobile-modal-content">
        <div className="mobile-modal-header">
          <h2 className="text-lg font-semibold text-white">{title}</h2>
          <button 
            onClick={onClose}
            className="mobile-touch-target flex items-center justify-center text-gray-400 hover:text-white"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="mobile-modal-body">
          {children}
        </div>
      </div>
    </div>
  );
}

// Mobile-optimized Loading Component
export function MobileLoading({ message = "Loading..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-8">
      <div className="mobile-loading-spinner mb-4"></div>
      <p className="text-gray-400 text-sm">{message}</p>
    </div>
  );
}

// Mobile-optimized Error Component
export function MobileError({ 
  message, 
  onRetry,
  retryText = "Try Again"
}: { 
  message: string;
  onRetry?: () => void;
  retryText?: string;
}) {
  return (
    <div className="mobile-error-container">
      <svg className="mobile-error-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
      <p className="mobile-error-message">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mobile-error-retry">
          {retryText}
        </button>
      )}
    </div>
  );
}

// Mobile-optimized Horizontal Scroll Container
export function MobileHorizontalScroll({ children, className = "" }: { 
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`mobile-horizontal-scroll ${className}`}>
      {children}
    </div>
  );
}

// Mobile-optimized Navigation Menu
export function MobileNavigationMenu({ 
  items, 
  isOpen, 
  onItemClick 
}: { 
  items: Array<{ label: string; href: string; }>;
  isOpen: boolean;
  onItemClick?: (href: string) => void;
}) {
  return (
    <div className={isOpen ? 'mobile-nav-visible' : 'mobile-nav-hidden'}>
      {items.map((item, index) => (
        <a 
          key={index}
          href={item.href}
          className="mobile-nav-item"
          onClick={(e) => {
            if (onItemClick) {
              e.preventDefault();
              onItemClick(item.href);
            }
          }}
        >
          {item.label}
        </a>
      ))}
    </div>
  );
}

// Mobile-optimized Touch Target
export function MobileTouchTarget({ 
  children, 
  onClick,
  className = ""
}: { 
  children: ReactNode;
  onClick?: () => void;
  className?: string;
}) {
  return (
    <div 
      className={`mobile-touch-target flex items-center justify-center ${onClick ? 'mobile-clickable' : ''} ${className}`}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

// Mobile-optimized Chart Container
export function MobileChartContainer({ children, title }: { 
  children: ReactNode;
  title?: string;
}) {
  return (
    <div className="mobile-card">
      {title && (
        <h3 className="text-h3 text-white mb-4">{title}</h3>
      )}
      <div className="mobile-chart-container">
        <div className="mobile-chart">
          {children}
        </div>
      </div>
    </div>
  );
}