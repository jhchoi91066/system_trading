"use client";

import { useState, useEffect } from 'react';

interface Notification {
  id: number;
  title: string;
  message: string;
  notification_type: string;
  priority: string;
  is_read: boolean;
  created_at: string;
  data?: any;
}

interface NotificationStats {
  total_notifications: number;
  unread_notifications: number;
}

export default function NotificationsPage() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [stats, setStats] = useState<NotificationStats>({ total_notifications: 0, unread_notifications: 0 });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'unread' | 'trade' | 'risk' | 'system'>('all');

  useEffect(() => {
    fetchNotifications();
    fetchNotificationStats();
  }, [filter]);

  const fetchNotifications = async () => {
    try {
      setLoading(true);
      const unreadOnly = filter === 'unread';
      const response = await fetch(`http://127.0.0.1:8000/notifications?limit=50&unread_only=${unreadOnly}`);
      if (!response.ok) throw new Error('Failed to fetch notifications');
      
      let data = await response.json();
      
      // Filter by type if needed
      if (filter !== 'all' && filter !== 'unread') {
        data = data.filter((n: Notification) => n.notification_type === filter);
      }
      
      setNotifications(data);
    } catch (e: any) {
      setError(`Failed to fetch notifications: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchNotificationStats = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/notifications/stats');
      if (!response.ok) throw new Error('Failed to fetch notification stats');
      const data = await response.json();
      setStats(data);
    } catch (e: any) {
      console.error('Failed to fetch notification stats:', e.message);
    }
  };

  const markAsRead = async (notificationId: number) => {
    try {
      const response = await fetch(`http://127.0.0.1:8000/notifications/${notificationId}/read`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to mark notification as read');
      
      // Update local state
      setNotifications(prev => 
        prev.map(n => n.id === notificationId ? { ...n, is_read: true } : n)
      );
      
      // Update stats
      setStats(prev => ({
        ...prev,
        unread_notifications: Math.max(0, prev.unread_notifications - 1)
      }));
    } catch (e: any) {
      setError(`Failed to mark notification as read: ${e.message}`);
    }
  };

  const markAllAsRead = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/notifications/mark-all-read', {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to mark all notifications as read');
      
      // Update local state
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
      setStats(prev => ({ ...prev, unread_notifications: 0 }));
    } catch (e: any) {
      setError(`Failed to mark all notifications as read: ${e.message}`);
    }
  };

  const createTestNotification = async () => {
    try {
      const response = await fetch('http://127.0.0.1:8000/notifications/test', {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to create test notification');
      
      // Refresh notifications
      fetchNotifications();
      fetchNotificationStats();
    } catch (e: any) {
      setError(`Failed to create test notification: ${e.message}`);
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'text-red-400 bg-red-400 bg-opacity-10 border-red-400';
      case 'high': return 'text-orange-400 bg-orange-400 bg-opacity-10 border-orange-400';
      case 'medium': return 'text-blue-400 bg-blue-400 bg-opacity-10 border-blue-400';
      case 'low': return 'text-gray-400 bg-gray-400 bg-opacity-10 border-gray-400';
      default: return 'text-gray-400 bg-gray-400 bg-opacity-10 border-gray-400';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'trade': return '💹';
      case 'risk': return '⚠️';
      case 'system': return '⚙️';
      case 'performance': return '📊';
      default: return '📢';
    }
  };

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="linear-card max-w-md mx-auto text-center">
          <h2 className="text-h3 text-red-400 mb-4">Error</h2>
          <p className="text-body text-secondary mb-6">{error}</p>
          <button 
            onClick={() => {
              setError(null);
              fetchNotifications();
            }}
            className="linear-button-primary py-2 px-4"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-4xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-h1">Notifications</h1>
          <div className="flex space-x-4">
            <button
              onClick={createTestNotification}
              className="linear-button-secondary py-2 px-4"
              disabled={loading}
            >
              Create Test
            </button>
            {stats.unread_notifications > 0 && (
              <button
                onClick={markAllAsRead}
                className="linear-button-primary py-2 px-4"
                disabled={loading}
              >
                Mark All as Read
              </button>
            )}
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-2 gap-4 mb-8">
          <div className="linear-card text-center">
            <p className="text-small text-secondary mb-1">Total Notifications</p>
            <p className="text-h3 text-white">{stats.total_notifications}</p>
          </div>
          <div className="linear-card text-center">
            <p className="text-small text-secondary mb-1">Unread</p>
            <p className="text-h3 text-blue-400">{stats.unread_notifications}</p>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="linear-card mb-8">
          <div className="flex space-x-4 overflow-x-auto">
            {[
              { key: 'all', label: 'All' },
              { key: 'unread', label: 'Unread' },
              { key: 'trade', label: 'Trades' },
              { key: 'risk', label: 'Risk Alerts' },
              { key: 'system', label: 'System' }
            ].map((tab) => (
              <button
                key={tab.key}
                onClick={() => setFilter(tab.key as any)}
                className={`px-4 py-2 rounded-lg text-small font-medium whitespace-nowrap transition-colors ${
                  filter === tab.key
                    ? 'bg-blue-500 text-white'
                    : 'text-secondary hover:text-white hover:bg-gray-700'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Notifications List */}
        <div className="space-y-4">
          {loading ? (
            <div className="linear-card text-center py-8">
              <p className="text-body text-secondary">Loading notifications...</p>
            </div>
          ) : notifications.length > 0 ? (
            notifications.map((notification) => (
              <div
                key={notification.id}
                className={`linear-card cursor-pointer transition-opacity ${
                  notification.is_read ? 'opacity-70' : ''
                }`}
                onClick={() => !notification.is_read && markAsRead(notification.id)}
              >
                <div className="flex items-start space-x-4">
                  <div className="text-2xl">
                    {getTypeIcon(notification.notification_type)}
                  </div>
                  
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-body font-medium text-white">
                        {notification.title}
                      </h3>
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-1 rounded text-xs font-medium border ${getPriorityColor(notification.priority)}`}>
                          {notification.priority.toUpperCase()}
                        </span>
                        {!notification.is_read && (
                          <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                        )}
                      </div>
                    </div>
                    
                    <p className="text-small text-secondary mb-3">
                      {notification.message}
                    </p>
                    
                    <div className="flex items-center justify-between">
                      <p className="text-xs text-secondary">
                        {new Date(notification.created_at).toLocaleString()}
                      </p>
                      
                      {notification.data && Object.keys(notification.data).length > 0 && (
                        <details className="text-xs">
                          <summary className="text-secondary cursor-pointer">Details</summary>
                          <pre className="mt-2 p-2 bg-gray-800 rounded text-xs text-gray-300 overflow-x-auto">
                            {JSON.stringify(notification.data, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="linear-card text-center py-8">
              <div className="text-4xl mb-4">📭</div>
              <p className="text-body text-secondary mb-2">No notifications found</p>
              <p className="text-small text-secondary">
                {filter === 'all' 
                  ? "You don't have any notifications yet." 
                  : `No ${filter} notifications found.`}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}