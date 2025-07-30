"""
실시간 데이터 갱신 최적화 시스템
Bitcoin Trading Bot에서 WebSocket 연결과 데이터 전송을 최적화
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict
import hashlib
import threading
import time

class RealtimeDataOptimizer:
    def __init__(self):
        self.data_cache = {}  # 사용자별 데이터 캐시
        self.data_hash_cache = {}  # 데이터 해시 캐시 (변경 감지용)
        self.last_update_time = {}  # 마지막 업데이트 시간
        self.update_intervals = {
            'portfolio_stats': 10,  # 10초마다 포트폴리오 통계
            'active_strategies': 30,  # 30초마다 활성 전략
            'notifications': 5,  # 5초마다 알림 확인
            'performance_data': 60  # 60초마다 성과 데이터
        }
        self.batch_updates = defaultdict(dict)  # 배치 업데이트용
        self.lock = threading.Lock()
        self.data_fetchers = {}  # 등록된 데이터 페처들
        
    def should_update(self, user_id: str, data_type: str) -> bool:
        """특정 데이터 타입의 업데이트가 필요한지 확인"""
        now = time.time()
        last_update_key = f"{user_id}:{data_type}"
        last_update = self.last_update_time.get(last_update_key, 0)
        interval = self.update_intervals.get(data_type, 30)
        
        return (now - last_update) >= interval
    
    def get_data_hash(self, data: Any) -> str:
        """데이터의 해시값 계산 (변경 감지용)"""
        try:
            data_str = json.dumps(data, sort_keys=True, default=str)
            return hashlib.md5(data_str.encode()).hexdigest()
        except:
            return str(hash(str(data)))
    
    def has_data_changed(self, user_id: str, data_type: str, new_data: Any) -> bool:
        """데이터가 변경되었는지 확인"""
        cache_key = f"{user_id}:{data_type}"
        new_hash = self.get_data_hash(new_data)
        old_hash = self.data_hash_cache.get(cache_key)
        
        if old_hash != new_hash:
            self.data_hash_cache[cache_key] = new_hash
            return True
        return False
    
    def cache_data(self, user_id: str, data_type: str, data: Any):
        """데이터를 캐시에 저장"""
        with self.lock:
            cache_key = f"{user_id}:{data_type}"
            self.data_cache[cache_key] = {
                'data': data,
                'timestamp': datetime.now().isoformat(),
                'cached_at': time.time()
            }
            self.last_update_time[cache_key] = time.time()
    
    def get_cached_data(self, user_id: str, data_type: str) -> Optional[Dict]:
        """캐시에서 데이터 조회"""
        cache_key = f"{user_id}:{data_type}"
        return self.data_cache.get(cache_key)
    
    def add_to_batch(self, user_id: str, data_type: str, data: Any):
        """배치 업데이트에 데이터 추가"""
        with self.lock:
            self.batch_updates[user_id][data_type] = data
    
    def get_batch_updates(self, user_id: str) -> Dict:
        """사용자의 배치 업데이트 데이터 가져오기"""
        with self.lock:
            updates = self.batch_updates[user_id].copy()
            self.batch_updates[user_id].clear()
            return updates
    
    def has_batch_updates(self, user_id: str) -> bool:
        """사용자에게 배치 업데이트가 있는지 확인"""
        return bool(self.batch_updates.get(user_id))
    
    def cleanup_old_cache(self, max_age_hours: int = 2):
        """오래된 캐시 데이터 정리"""
        now = time.time()
        max_age_seconds = max_age_hours * 3600
        
        with self.lock:
            # 데이터 캐시 정리
            keys_to_remove = []
            for key, cached_item in self.data_cache.items():
                if (now - cached_item.get('cached_at', 0)) > max_age_seconds:
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                self.data_cache.pop(key, None)
                self.data_hash_cache.pop(key, None)
                self.last_update_time.pop(key, None)
    
    def get_cache_stats(self, user_id: str) -> Dict:
        """사용자별 캐시 통계 조회"""
        with self.lock:
            user_cache_keys = [key for key in self.data_cache.keys() if key.startswith(f"{user_id}:")]
            user_hash_keys = [key for key in self.data_hash_cache.keys() if key.startswith(f"{user_id}:")]
            
            stats = {
                'cached_data_types': len(user_cache_keys),
                'total_cache_size': len(self.data_cache),
                'registered_fetchers': list(self.data_fetchers.keys()),
                'cache_keys': user_cache_keys,
                'last_update_times': {
                    key: self.last_update_time.get(key, 0) 
                    for key in user_cache_keys
                },
                'has_batch_updates': self.has_batch_updates(user_id)
            }
            
            return stats
    
    async def get_optimized_data(self, user_id: str, data_type: str, data_fetcher, force_update: bool = False) -> Any:
        """최적화된 데이터 조회 (캐시 우선, 필요시 새로 조회)"""
        # 강제 업데이트가 아니고 업데이트가 필요하지 않으면 캐시 사용
        if not force_update and not self.should_update(user_id, data_type):
            cached = self.get_cached_data(user_id, data_type)
            if cached:
                return cached['data']
        
        # 새 데이터 조회
        try:
            new_data = await data_fetcher(user_id)
            
            # 데이터가 변경된 경우에만 캐시 업데이트 및 배치에 추가
            if self.has_data_changed(user_id, data_type, new_data):
                self.cache_data(user_id, data_type, new_data)
                self.add_to_batch(user_id, data_type, new_data)
            
            return new_data
        except Exception as e:
            print(f"Error fetching {data_type} for user {user_id}: {e}")
            # 에러 발생시 캐시된 데이터 반환
            cached = self.get_cached_data(user_id, data_type)
            return cached['data'] if cached else None

    def register_data_fetcher(self, data_type: str, fetcher_func):
        """데이터 페처 함수를 등록합니다."""
        self.data_fetchers[data_type] = fetcher_func

    async def get_all_optimized_data(self, user_id: str) -> Dict[str, Any]:
        """모든 최적화된 데이터를 한 번에 가져옵니다."""
        data = {}
        for data_type in self.data_fetchers.keys():
            data[data_type] = await self.get_optimized_data(user_id, data_type, self.data_fetchers[data_type])
        return data

    async def get_all_optimized_data_with_versions(self, user_id: str) -> (Dict[str, Any], Dict[str, str]):
        """모든 최적화된 데이터와 그 버전을 가져옵니다."""
        data = {}
        versions = {}
        for data_type in self.data_fetchers.keys():
            cached_item = self.get_cached_data(user_id, data_type)
            if cached_item:
                data[data_type] = cached_item['data']
                versions[data_type] = self.data_hash_cache.get(f"{user_id}:{data_type}", "")
            else:
                # 캐시된 데이터가 없으면 raw fetcher를 통해 가져옴
                data[data_type] = await self.get_optimized_data(user_id, data_type, self.data_fetchers[data_type])
                versions[data_type] = self.data_hash_cache.get(f"{user_id}:{data_type}", "")
        return data, versions

class ConnectionHealthMonitor:
    def __init__(self):
        self.connection_stats = {}  # 연결별 통계
        self.error_counts = defaultdict(int)  # 연결별 에러 카운트
        self.last_ping_time = {}  # 마지막 ping 시간
        
    def record_connection(self, user_id: str):
        """새 연결 기록"""
        self.connection_stats[user_id] = {
            'connected_at': datetime.now().isoformat(),
            'message_count': 0,
            'last_activity': datetime.now().isoformat(),
            'ping_response_times': []
        }
        self.error_counts[user_id] = 0
        
    def record_activity(self, user_id: str, activity_type: str = 'message'):
        """연결 활동 기록"""
        if user_id in self.connection_stats:
            self.connection_stats[user_id]['last_activity'] = datetime.now().isoformat()
            self.connection_stats[user_id]['message_count'] += 1
            
    def record_ping(self, user_id: str):
        """Ping 전송 기록"""
        self.last_ping_time[user_id] = time.time()
        
    def record_pong(self, user_id: str):
        """Pong 응답 기록 및 응답 시간 계산"""
        if user_id in self.last_ping_time:
            response_time = time.time() - self.last_ping_time[user_id]
            if user_id in self.connection_stats:
                self.connection_stats[user_id]['ping_response_times'].append(response_time)
                # 최근 10개의 응답시간만 유지
                if len(self.connection_stats[user_id]['ping_response_times']) > 10:
                    self.connection_stats[user_id]['ping_response_times'].pop(0)
                    
    def record_error(self, user_id: str):
        """에러 발생 기록"""
        self.error_counts[user_id] += 1
        
    def is_connection_healthy(self, user_id: str) -> bool:
        """연결이 건강한 상태인지 확인"""
        if user_id not in self.connection_stats:
            return False
            
        # 에러율 확인 (10개 이상 에러시 비정상)
        if self.error_counts[user_id] >= 10:
            return False
            
        # 마지막 활동 시간 확인 (5분 이상 비활성시 비정상)
        last_activity = datetime.fromisoformat(self.connection_stats[user_id]['last_activity'])
        if (datetime.now() - last_activity).total_seconds() > 300:
            return False
            
        return True
        
    def get_connection_info(self, user_id: str) -> Dict:
        """연결 정보 조회"""
        return {
            'stats': self.connection_stats.get(user_id, {}),
            'error_count': self.error_counts.get(user_id, 0),
            'is_healthy': self.is_connection_healthy(user_id)
        }
        
    def cleanup_disconnected(self, active_user_ids: List[str]):
        """연결이 끊어진 사용자의 데이터 정리"""
        all_user_ids = set(self.connection_stats.keys())
        disconnected_users = all_user_ids - set(active_user_ids)
        
        for user_id in disconnected_users:
            self.connection_stats.pop(user_id, None)
            self.error_counts.pop(user_id, None)
            self.last_ping_time.pop(user_id, None)

async def run_periodic_updates():
    """주기적으로 데이터를 업데이트하고 캐시를 관리하는 백그라운드 태스크"""
    
    while True:
        try:
            # 모든 활성 사용자 ID 가져오기
            active_user_ids = list(connection_monitor.connection_stats.keys())
            
            for user_id in active_user_ids:
                # 등록된 모든 데이터 타입 업데이트
                for data_type, fetcher_func in realtime_optimizer.data_fetchers.items():
                    # strategy_perf_{id}와 같은 동적 키 처리
                    if data_type.startswith('strategy_perf_'):
                        strategy_id = int(data_type.split('_')[2])
                        await realtime_optimizer.get_optimized_data(user_id, data_type, 
                                                                    lambda u_id=user_id, s_id=strategy_id: realtime_optimizer.data_fetchers[data_type](u_id, s_id), 
                                                                    force_update=True)
                    else:
                        await realtime_optimizer.get_optimized_data(user_id, data_type, fetcher_func, force_update=True)
            
            # 5초마다 업데이트 주기
            await asyncio.sleep(5)
        except Exception as e:
            print(f"Error in run_periodic_updates: {e}")
            await asyncio.sleep(10) # 오류 발생 시 더 길게 대기

# 전역 인스턴스
realtime_optimizer = RealtimeDataOptimizer()
connection_monitor = ConnectionHealthMonitor()

# 정기적인 캐시 정리를 위한 백그라운드 태스크
async def cleanup_task():
    """백그라운드에서 정기적으로 캐시와 연결 정보 정리"""
    while True:
        try:
            # 2시간마다 캐시 정리
            realtime_optimizer.cleanup_old_cache(max_age_hours=2)
            print("Cache cleanup completed")
            
            # 30분 대기
            await asyncio.sleep(1800)
        except Exception as e:
            print(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)