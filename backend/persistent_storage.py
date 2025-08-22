"""
Persistent storage manager for Bitcoin Trading Bot
Provides JSON file-based storage with automatic backup and recovery
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Any, Optional
from threading import Lock
import asyncio

class PersistentStorage:
    def __init__(self, storage_dir: str = "data"):
        self.storage_dir = storage_dir
        self.backup_dir = os.path.join(storage_dir, "backups")
        self.locks = {}
        
        # Ensure directories exist
        os.makedirs(storage_dir, exist_ok=True)
        os.makedirs(self.backup_dir, exist_ok=True)
        
        # Storage file paths
        self.files = {
            'api_keys': os.path.join(storage_dir, 'api_keys.json'),
            'notifications': os.path.join(storage_dir, 'notifications.json'),
            'active_strategies': os.path.join(storage_dir, 'active_strategies.json'),
            'fund_management': os.path.join(storage_dir, 'fund_management.json'),
            'trading_history': os.path.join(storage_dir, 'trading_history.json'),
            'user_settings': os.path.join(storage_dir, 'user_settings.json')
        }
        
        # Initialize locks for each storage file
        for key in self.files:
            self.locks[key] = Lock()
        
        # Load or initialize all storage files
        self._initialize_storage()
    
    def _initialize_storage(self):
        """Initialize storage files with default data if they don't exist"""
        default_data = {
            'api_keys': [],
            'notifications': [],
            'active_strategies': [],
            'fund_management': {},
            'trading_history': [],
            'user_settings': {}
        }
        
        for key, file_path in self.files.items():
            if not os.path.exists(file_path):
                self._write_json(file_path, default_data[key])
    
    def _read_json(self, file_path: str) -> Any:
        """Read JSON data from file with error handling"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error reading {file_path}: {e}")
            return None
    
    def _write_json(self, file_path: str, data: Any) -> bool:
        """Write JSON data to file with atomic operation and backup"""
        try:
            # Create backup before writing
            if os.path.exists(file_path):
                backup_filename = f"{os.path.basename(file_path)}.{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
                backup_path = os.path.join(self.backup_dir, backup_filename)
                shutil.copy2(file_path, backup_path)
                
                # Keep only last 5 backups per file
                self._cleanup_backups(os.path.basename(file_path))
            
            # Atomic write using temporary file
            temp_path = file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            
            # Move temp file to final location
            shutil.move(temp_path, file_path)
            return True
        except Exception as e:
            print(f"Error writing {file_path}: {e}")
            return False
    
    def _cleanup_backups(self, filename: str, keep_count: int = 5):
        """Keep only the most recent backup files"""
        try:
            backup_files = [f for f in os.listdir(self.backup_dir) if f.startswith(filename)]
            backup_files.sort(reverse=True)  # Most recent first
            
            for old_backup in backup_files[keep_count:]:
                os.remove(os.path.join(self.backup_dir, old_backup))
        except Exception as e:
            print(f"Error cleaning up backups: {e}")
    
    # API Keys Storage
    def get_api_keys(self, user_id: str) -> List[Dict]:
        """Get API keys for a user"""
        with self.locks['api_keys']:
            data = self._read_json(self.files['api_keys']) or []
            return [key for key in data if key.get('user_id') == user_id]
    
    def add_api_key(self, api_key_data: Dict) -> bool:
        """Add new API key"""
        with self.locks['api_keys']:
            data = self._read_json(self.files['api_keys']) or []
            data.append({
                **api_key_data,
                'created_at': datetime.now().isoformat()
            })
            return self._write_json(self.files['api_keys'], data)
    
    def delete_api_key(self, user_id: str, key_id: int) -> bool:
        """Delete API key"""
        with self.locks['api_keys']:
            data = self._read_json(self.files['api_keys']) or []
            original_length = len(data)
            data = [key for key in data if not (key.get('user_id') == user_id and key.get('id') == key_id)]
            
            if len(data) < original_length:
                return self._write_json(self.files['api_keys'], data)
            return False
    
    # Notifications Storage
    def get_notifications(self, user_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get notifications for a user"""
        with self.locks['notifications']:
            data = self._read_json(self.files['notifications']) or []
            user_notifications = [n for n in data if n.get('user_id') == user_id]
            user_notifications.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            if limit:
                return user_notifications[:limit]
            return user_notifications
    
    def add_notification(self, notification_data: Dict) -> bool:
        """Add new notification"""
        with self.locks['notifications']:
            data = self._read_json(self.files['notifications']) or []
            data.append({
                **notification_data,
                'created_at': datetime.now().isoformat()
            })
            return self._write_json(self.files['notifications'], data)
    
    def mark_notification_read(self, user_id: str, notification_id: int) -> bool:
        """Mark notification as read"""
        with self.locks['notifications']:
            data = self._read_json(self.files['notifications']) or []
            for notification in data:
                if (notification.get('user_id') == user_id and 
                    notification.get('id') == notification_id):
                    notification['is_read'] = True
                    return self._write_json(self.files['notifications'], data)
            return False
    
    # Active Strategies Storage
    def get_active_strategies(self, user_id: str) -> List[Dict]:
        """Get active strategies for a user"""
        with self.locks['active_strategies']:
            data = self._read_json(self.files['active_strategies']) or []
            return [s for s in data if s.get('user_id') == user_id and s.get('is_active', False)]
    
    def add_active_strategy(self, strategy_data: Dict) -> bool:
        """Add new active strategy"""
        with self.locks['active_strategies']:
            data = self._read_json(self.files['active_strategies']) or []
            data.append({
                **strategy_data,
                'created_at': datetime.now().isoformat()
            })
            return self._write_json(self.files['active_strategies'], data)
    
    def deactivate_strategy(self, user_id: str, strategy_id: int) -> bool:
        """Deactivate a strategy"""
        with self.locks['active_strategies']:
            data = self._read_json(self.files['active_strategies']) or []
            for strategy in data:
                if (strategy.get('user_id') == user_id and 
                    strategy.get('id') == strategy_id):
                    strategy['is_active'] = False
                    strategy['deactivated_at'] = datetime.now().isoformat()
                    return self._write_json(self.files['active_strategies'], data)
            return False
    
    # Fund Management Storage
    def get_fund_settings(self, user_id: str) -> Dict:
        """Get fund management settings for a user"""
        with self.locks['fund_management']:
            data = self._read_json(self.files['fund_management']) or {}
            return data.get(user_id, {
                'total_capital': 10000.0,
                'max_risk_per_trade': 2.0,
                'max_daily_loss': 5.0,
                'max_portfolio_risk': 10.0,
                'position_sizing_method': 'fixed',
                'rebalance_frequency': 'daily',
                'emergency_stop_loss': 20.0
            })
    
    def save_fund_settings(self, user_id: str, settings: Dict) -> bool:
        """Save fund management settings for a user"""
        with self.locks['fund_management']:
            data = self._read_json(self.files['fund_management']) or {}
            data[user_id] = {
                **settings,
                'updated_at': datetime.now().isoformat()
            }
            return self._write_json(self.files['fund_management'], data)
    
    # Trading History Storage
    def get_trading_history(self, user_id: str, limit: Optional[int] = None, strategy_id: Optional[int] = None) -> List[Dict]:
        """Get trading history for a user, optionally filtered by strategy_id"""
        with self.locks['trading_history']:
            data = self._read_json(self.files['trading_history']) or []
            user_trades = [t for t in data if t.get('user_id') == user_id]
            
            # Filter by strategy_id if provided
            if strategy_id is not None:
                user_trades = [t for t in user_trades if t.get('strategy_id') == strategy_id]
            
            user_trades.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            
            if limit:
                return user_trades[:limit]
            return user_trades
    
    def add_trade(self, trade_data: Dict) -> bool:
        """Add new trade to history"""
        with self.locks['trading_history']:
            data = self._read_json(self.files['trading_history']) or []
            data.append({
                **trade_data,
                'created_at': datetime.now().isoformat()
            })
            return self._write_json(self.files['trading_history'], data)
    
    # User Settings Storage
    def get_user_settings(self, user_id: str) -> Dict:
        """Get user settings"""
        with self.locks['user_settings']:
            data = self._read_json(self.files['user_settings']) or {}
            return data.get(user_id, {})
    
    def save_user_settings(self, user_id: str, settings: Dict) -> bool:
        """Save user settings"""
        with self.locks['user_settings']:
            data = self._read_json(self.files['user_settings']) or {}
            data[user_id] = {
                **settings,
                'updated_at': datetime.now().isoformat()
            }
            return self._write_json(self.files['user_settings'], data)
    
    # Data Management
    def export_all_data(self, user_id: str) -> Dict:
        """Export all user data for backup"""
        return {
            'api_keys': self.get_api_keys(user_id),
            'notifications': self.get_notifications(user_id),
            'active_strategies': self.get_active_strategies(user_id),
            'fund_management': self.get_fund_settings(user_id),
            'trading_history': self.get_trading_history(user_id),
            'user_settings': self.get_user_settings(user_id),
            'exported_at': datetime.now().isoformat()
        }
    
    def get_storage_stats(self) -> Dict:
        """Get storage statistics"""
        stats = {}
        for key, file_path in self.files.items():
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                data = self._read_json(file_path)
                item_count = len(data) if isinstance(data, (list, dict)) else 0
                
                stats[key] = {
                    'file_size_bytes': file_size,
                    'item_count': item_count,
                    'last_modified': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
                }
        
        return stats

# Global persistent storage instance
persistent_storage = PersistentStorage()