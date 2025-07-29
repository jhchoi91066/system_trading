"use client";

import React, { createContext, useContext, useEffect, useState, useRef, ReactNode } from 'react';
import { useAuth } from '@clerk/nextjs';

// 데이터 타입 정의
interface PortfolioStats {
  total_capital: number;
  total_allocated: number;
  available_capital: number;
  active_strategies: number;
  recent_trades_count: number;
  allocation_percentage: number;
}

interface ActiveStrategy {
  id: number;
  user_id: string;
  strategy_id: number;
  exchange_name: string;
  symbol: string;
  allocated_capital: number;
  is_active: boolean;
  // ... 기타 필드
}

interface StrategyPerformance {
    strategy_id: number;
    total_trades: number;
    winning_trades: number;
    win_rate: number;
}

interface Notification {
  id: number;
  title: string;
  message: string;
  notification_type: string;
  priority: string;
  is_read: boolean;
  created_at: string;
}

interface RealtimeData {
  portfolio_stats: PortfolioStats | null;
  active_strategies: ActiveStrategy[];
  performance_data: Record<string, StrategyPerformance>;
  notifications: Notification[];
}

interface WebSocketContextType {
  data: RealtimeData;
  isConnected: boolean;
  error: string | null;
  sendMessage: (message: any) => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const [data, setData] = useState<RealtimeData>({
    portfolio_stats: null,
    active_strategies: [],
    performance_data: {},
    notifications: [],
  });
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const ws = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    const connectWs = async () => {
      const token = await getToken();
      if (!token) {
        setError("Authentication token not available.");
        return;
      }

      ws.current = new WebSocket('ws://127.0.0.1:8000/ws/monitoring');
      const currentWs = ws.current;

      currentWs.onopen = () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setError(null);
        // Send the token as the first message
        currentWs.send(JSON.stringify({ type: "auth", token: token }));
      };

      currentWs.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Received WebSocket message:', message.type, message.data);
          
          switch (message.type) {
            case 'initial_data':
            case 'monitoring_update':
              setData(prevData => ({ ...prevData, ...message.data }));
              break;
            case 'new_notification':
              setData(prevData => ({
                ...prevData,
                notifications: [message.data, ...prevData.notifications],
              }));
              break;
            default:
              console.warn('Unknown WebSocket message type:', message.type);
          }
        } catch (e) {
          console.error('Error processing WebSocket message:', e);
        }
      };

      currentWs.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection failed. Real-time updates are disabled.');
        setIsConnected(false);
      };

      currentWs.onclose = () => {
        console.log('❌ WebSocket disconnected');
        setIsConnected(false);
        // Optionally, you can implement a reconnect mechanism here
      };

      // Cleanup on component unmount
      return () => {
        currentWs.close();
      };
    };

    connectWs();

    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [isLoaded, isSignedIn, getToken]);

  const sendMessage = (message: any) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected. Message not sent:', message);
    }
  };

  const value = {
    data,
    isConnected,
    error,
    sendMessage,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};
