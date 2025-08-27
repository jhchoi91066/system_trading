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
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 5;

  const connectWs = async () => {
    const token = await getToken();
    if (!token) {
      setError("Authentication token not available.");
      return;
    }

    // Close existing connection if any
    if (ws.current) {
      ws.current.close();
    }

    try {
      ws.current = new WebSocket('ws://127.0.0.1:8002/ws/monitoring');
      const currentWs = ws.current;

      currentWs.onopen = () => {
        console.log('✅ WebSocket connected');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        
        // Send simplified auth message to avoid "control frame too long" error
        currentWs.send(JSON.stringify({ type: "auth" }));
      };

      currentWs.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log('Received WebSocket message:', message.type);
          
          switch (message.type) {
            case 'initial_data':
            case 'monitoring_update':
              if (message.data && typeof message.data === 'object') {
                setData(prevData => ({
                  ...prevData,
                  portfolio_stats: message.data.portfolio_stats || prevData.portfolio_stats,
                  active_strategies: Array.isArray(message.data.active_strategies) ? message.data.active_strategies : prevData.active_strategies,
                  performance_data: message.data.performance_data && typeof message.data.performance_data === 'object' ? 
                    message.data.performance_data : prevData.performance_data,
                  notifications: Array.isArray(message.data.notifications) ? message.data.notifications : prevData.notifications,
                }));
              }
              break;
            case 'new_notification':
              setData(prevData => ({
                ...prevData,
                notifications: [message.data, ...prevData.notifications],
              }));
              break;
            case 'pong':
              console.log('Received pong from server');
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
        setError('WebSocket connection failed. Attempting to reconnect...');
        setIsConnected(false);
      };

      currentWs.onclose = (event) => {
        console.log('❌ WebSocket disconnected', event.code, event.reason);
        setIsConnected(false);
        
        // Implement reconnection with exponential backoff
        if (reconnectAttempts.current < maxReconnectAttempts) {
          reconnectAttempts.current++;
          const delay = Math.pow(2, reconnectAttempts.current) * 1000; // Exponential backoff
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttempts.current}/${maxReconnectAttempts})`);
          
          reconnectTimeout.current = setTimeout(() => {
            if (isLoaded && isSignedIn) {
              connectWs();
            }
          }, delay);
        } else {
          setError('WebSocket connection failed after multiple attempts. Real-time updates are disabled.');
        }
      };

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setError('Failed to establish WebSocket connection.');
      setIsConnected(false);
    }
  };

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    connectWs();

    // Cleanup function
    return () => {
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current);
      }
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [isLoaded, isSignedIn]);

  // Heartbeat to keep connection alive
  useEffect(() => {
    if (!isConnected) return;

    const heartbeatInterval = setInterval(() => {
      if (ws.current && ws.current.readyState === WebSocket.OPEN) {
        ws.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000); // Send ping every 30 seconds

    return () => clearInterval(heartbeatInterval);
  }, [isConnected]);

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
