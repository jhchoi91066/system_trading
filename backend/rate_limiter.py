"""
Rate Limiting 시스템 - API 호출 제한 및 DDoS 방어
Redis 기반 고성능 레이트 리미터
"""

import logging
import time
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from functools import wraps
from fastapi import HTTPException, Request
import redis
import asyncio

logger = logging.getLogger(__name__)

class RateLimiter:
    """Redis 기반 고성능 레이트 리미터"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        try:
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("✅ Redis connection established for rate limiting")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available, using memory-based fallback: {e}")
            self.redis_client = None
            self._memory_cache = {}  # 메모리 기반 폴백
    
    def _get_client_key(self, request: Request, identifier: str = None) -> str:
        """클라이언트 식별 키 생성"""
        if identifier:
            return f"rate_limit:{identifier}"
            
        # IP 주소 기반 식별
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else 'unknown'
        
        return f"rate_limit:{client_ip}"
    
    def _memory_check_limit(self, key: str, max_requests: int, window_seconds: int) -> Dict[str, Any]:
        """메모리 기반 레이트 리미팅 (Redis 대체)"""
        current_time = time.time()
        
        if key not in self._memory_cache:
            self._memory_cache[key] = []
        
        # 윈도우 밖의 오래된 요청 제거
        self._memory_cache[key] = [
            timestamp for timestamp in self._memory_cache[key]
            if current_time - timestamp < window_seconds
        ]
        
        # 현재 요청 수
        current_requests = len(self._memory_cache[key])
        
        if current_requests >= max_requests:
            # 가장 오래된 요청 시간으로부터 리셋 시간 계산
            oldest_request = min(self._memory_cache[key]) if self._memory_cache[key] else current_time
            reset_time = oldest_request + window_seconds
            
            return {
                'allowed': False,
                'current_requests': current_requests,
                'limit': max_requests,
                'window_seconds': window_seconds,
                'reset_time': reset_time,
                'retry_after': int(reset_time - current_time)
            }
        
        # 요청 허용 - 현재 시간 추가
        self._memory_cache[key].append(current_time)
        
        return {
            'allowed': True,
            'current_requests': current_requests + 1,
            'limit': max_requests,
            'window_seconds': window_seconds,
            'reset_time': current_time + window_seconds,
            'retry_after': 0
        }
    
    def check_rate_limit(self, 
                        request: Request, 
                        max_requests: int, 
                        window_seconds: int,
                        identifier: str = None) -> Dict[str, Any]:
        """레이트 리미트 확인"""
        
        key = self._get_client_key(request, identifier)
        
        if self.redis_client is None:
            return self._memory_check_limit(key, max_requests, window_seconds)
        
        try:
            # Redis sliding window log 구현
            current_time = time.time()
            window_start = current_time - window_seconds
            
            pipe = self.redis_client.pipeline()
            
            # 윈도우 밖의 오래된 요청 제거
            pipe.zremrangebyscore(key, 0, window_start)
            
            # 현재 요청 수 확인
            pipe.zcard(key)
            
            # 현재 시간을 스코어로 하여 요청 기록
            pipe.zadd(key, {str(current_time): current_time})
            
            # TTL 설정
            pipe.expire(key, window_seconds + 1)
            
            results = pipe.execute()
            current_requests = results[1]  # zcard 결과
            
            if current_requests > max_requests:
                # 가장 오래된 요청 시간 조회
                oldest = self.redis_client.zrange(key, 0, 0, withscores=True)
                oldest_time = oldest[0][1] if oldest else current_time
                reset_time = oldest_time + window_seconds
                
                return {
                    'allowed': False,
                    'current_requests': current_requests,
                    'limit': max_requests,
                    'window_seconds': window_seconds,
                    'reset_time': reset_time,
                    'retry_after': int(reset_time - current_time)
                }
            
            return {
                'allowed': True,
                'current_requests': current_requests,
                'limit': max_requests,
                'window_seconds': window_seconds,
                'reset_time': current_time + window_seconds,
                'retry_after': 0
            }
            
        except Exception as e:
            logger.error(f"🔴 Redis rate limit check failed: {e}")
            # Redis 실패 시 메모리 폴백
            return self._memory_check_limit(key, max_requests, window_seconds)
    
    def get_rate_limit_status(self, request: Request, identifier: str = None) -> Dict[str, Any]:
        """현재 레이트 리미트 상태 조회"""
        key = self._get_client_key(request, identifier)
        
        if self.redis_client is None:
            # 메모리 버전
            if key in self._memory_cache:
                current_time = time.time()
                # 유효한 요청만 카운트
                valid_requests = [
                    timestamp for timestamp in self._memory_cache[key]
                    if current_time - timestamp < 3600  # 1시간 윈도우
                ]
                return {
                    'requests_made': len(valid_requests),
                    'window_seconds': 3600,
                    'last_request': max(valid_requests) if valid_requests else 0
                }
            return {'requests_made': 0, 'window_seconds': 3600, 'last_request': 0}
        
        try:
            current_time = time.time()
            window_start = current_time - 3600  # 1시간
            
            # 윈도우 내 요청 수
            request_count = self.redis_client.zcount(key, window_start, current_time)
            
            # 마지막 요청 시간
            last_requests = self.redis_client.zrevrange(key, 0, 0, withscores=True)
            last_request_time = last_requests[0][1] if last_requests else 0
            
            return {
                'requests_made': request_count,
                'window_seconds': 3600,
                'last_request': last_request_time
            }
            
        except Exception as e:
            logger.error(f"🔴 Rate limit status check failed: {e}")
            return {'requests_made': 0, 'window_seconds': 3600, 'last_request': 0}

# 글로벌 레이트 리미터 인스턴스
rate_limiter = RateLimiter()

# =============================================================================
# 데코레이터 함수들
# =============================================================================

def rate_limit(max_requests: int, window_seconds: int, identifier_func=None):
    """레이트 리미트 데코레이터"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # FastAPI에서 Request 객체 찾기
            request = None
            for arg in args:
                if hasattr(arg, 'client') and hasattr(arg, 'headers'):
                    request = arg
                    break
            
            if not request:
                # Request를 찾을 수 없으면 제한 없이 실행
                return await func(*args, **kwargs)
            
            # 식별자 생성
            identifier = None
            if identifier_func:
                identifier = identifier_func(request)
            
            # 레이트 리미트 확인
            result = rate_limiter.check_rate_limit(
                request, max_requests, window_seconds, identifier
            )
            
            if not result['allowed']:
                logger.warning(
                    f"🔴 Rate limit exceeded: {result['current_requests']}/{result['limit']} "
                    f"in {result['window_seconds']}s window"
                )
                raise HTTPException(
                    status_code=429,
                    detail={
                        'error': 'Rate limit exceeded',
                        'limit': result['limit'],
                        'window_seconds': result['window_seconds'],
                        'retry_after': result['retry_after'],
                        'current_requests': result['current_requests']
                    },
                    headers={'Retry-After': str(result['retry_after'])}
                )
            
            # 요청 허용
            logger.debug(f"✅ Rate limit OK: {result['current_requests']}/{result['limit']}")
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator

def trading_rate_limit(func):
    """거래 API 전용 레이트 리미트 (엄격함)"""
    return rate_limit(max_requests=100, window_seconds=60)(func)

def general_rate_limit(func):
    """일반 API 레이트 리미트"""
    return rate_limit(max_requests=1000, window_seconds=60)(func)

def webhook_rate_limit(func):
    """웹훅 전용 레이트 리미트"""
    return rate_limit(max_requests=60, window_seconds=60)(func)

# =============================================================================
# 블랙리스트 관리
# =============================================================================

class IPBlacklist:
    """IP 블랙리스트 관리"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client or rate_limiter.redis_client
        self.memory_blacklist = set()
    
    def add_to_blacklist(self, ip: str, duration_seconds: int = 3600, reason: str = "Rate limit violation"):
        """IP를 블랙리스트에 추가"""
        if self.redis_client:
            try:
                key = f"blacklist:{ip}"
                self.redis_client.setex(key, duration_seconds, json.dumps({
                    'reason': reason,
                    'added_at': datetime.utcnow().isoformat(),
                    'expires_at': (datetime.utcnow() + timedelta(seconds=duration_seconds)).isoformat()
                }))
                logger.warning(f"🚫 IP {ip} blacklisted for {duration_seconds}s: {reason}")
                return True
            except Exception as e:
                logger.error(f"Failed to add IP to Redis blacklist: {e}")
        
        # 메모리 폴백
        self.memory_blacklist.add(ip)
        logger.warning(f"🚫 IP {ip} added to memory blacklist: {reason}")
        return True
    
    def is_blacklisted(self, ip: str) -> bool:
        """IP가 블랙리스트에 있는지 확인"""
        if self.redis_client:
            try:
                key = f"blacklist:{ip}"
                return bool(self.redis_client.exists(key))
            except Exception as e:
                logger.error(f"Failed to check Redis blacklist: {e}")
        
        # 메모리 폴백
        return ip in self.memory_blacklist
    
    def remove_from_blacklist(self, ip: str) -> bool:
        """IP를 블랙리스트에서 제거"""
        if self.redis_client:
            try:
                key = f"blacklist:{ip}"
                result = self.redis_client.delete(key)
                if result:
                    logger.info(f"✅ IP {ip} removed from blacklist")
                return bool(result)
            except Exception as e:
                logger.error(f"Failed to remove IP from Redis blacklist: {e}")
        
        # 메모리 폴백
        if ip in self.memory_blacklist:
            self.memory_blacklist.remove(ip)
            logger.info(f"✅ IP {ip} removed from memory blacklist")
            return True
        return False

# 글로벌 IP 블랙리스트 인스턴스
ip_blacklist = IPBlacklist()

def check_blacklist(func):
    """IP 블랙리스트 확인 데코레이터"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Request 객체 찾기
        request = None
        for arg in args:
            if hasattr(arg, 'client') and hasattr(arg, 'headers'):
                request = arg
                break
        
        if request:
            client_ip = request.client.host if request.client else 'unknown'
            
            if ip_blacklist.is_blacklisted(client_ip):
                logger.warning(f"🚫 Blocked request from blacklisted IP: {client_ip}")
                raise HTTPException(
                    status_code=403,
                    detail={'error': 'IP address is blacklisted'}
                )
        
        return await func(*args, **kwargs)
    return wrapper

# 테스트 함수
async def test_rate_limiter():
    """레이트 리미터 테스트"""
    print("🧪 Testing rate limiter...")
    
    # 가짜 Request 객체
    class MockRequest:
        def __init__(self, ip):
            self.client = type('client', (), {'host': ip})()
            self.headers = {}
    
    test_request = MockRequest("127.0.0.1")
    
    # 10개 요청 테스트 (제한: 5req/10s)
    allowed_count = 0
    for i in range(10):
        result = rate_limiter.check_rate_limit(test_request, 5, 10)
        if result['allowed']:
            allowed_count += 1
            print(f"✅ Request {i+1}: Allowed ({result['current_requests']}/{result['limit']})")
        else:
            print(f"🔴 Request {i+1}: Blocked (retry after {result['retry_after']}s)")
    
    print(f"🎯 Result: {allowed_count}/10 requests allowed")

if __name__ == "__main__":
    asyncio.run(test_rate_limiter())