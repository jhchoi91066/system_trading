"""
Retry Manager - 지능형 재시도 메커니즘
Exponential Backoff, Jitter, 조건부 재시도 지원
"""

import asyncio
import random
import time
import logging
from typing import Callable, Any, Optional, Union, Tuple, Type
from dataclasses import dataclass
from functools import wraps
import inspect

logger = logging.getLogger(__name__)

@dataclass
class RetryConfig:
    """재시도 설정"""
    max_attempts: int = 3                    # 최대 재시도 횟수
    initial_delay: float = 1.0               # 초기 대기 시간 (초)
    max_delay: float = 60.0                  # 최대 대기 시간 (초)
    exponential_base: float = 2.0            # 지수적 증가 배수
    jitter: bool = True                      # 랜덤 지터 적용 여부
    jitter_range: float = 0.1                # 지터 범위 (0.1 = ±10%)
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)  # 재시도할 예외 타입
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()        # 재시도하지 않을 예외 타입
    retry_condition: Optional[Callable] = None   # 커스텀 재시도 조건 함수

class RetryStats:
    """재시도 통계"""
    def __init__(self):
        self.total_calls = 0
        self.successful_calls = 0
        self.failed_calls = 0
        self.total_retries = 0
        self.total_delay_time = 0.0
    
    def record_call(self, success: bool, attempts: int, total_delay: float):
        """호출 결과 기록"""
        self.total_calls += 1
        if success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        self.total_retries += (attempts - 1)
        self.total_delay_time += total_delay
    
    def get_stats(self) -> dict:
        """통계 조회"""
        return {
            'total_calls': self.total_calls,
            'successful_calls': self.successful_calls,
            'failed_calls': self.failed_calls,
            'success_rate': (
                self.successful_calls / self.total_calls * 100 
                if self.total_calls > 0 else 0
            ),
            'total_retries': self.total_retries,
            'avg_retries_per_call': (
                self.total_retries / self.total_calls 
                if self.total_calls > 0 else 0
            ),
            'total_delay_time': self.total_delay_time,
            'avg_delay_per_call': (
                self.total_delay_time / self.total_calls 
                if self.total_calls > 0 else 0
            )
        }

class RetryManager:
    """재시도 관리자"""
    
    def __init__(self, name: str, config: RetryConfig = None):
        self.name = name
        self.config = config or RetryConfig()
        self.stats = RetryStats()
        
        logger.info(f"🔄 Retry Manager '{name}' initialized: max_attempts={self.config.max_attempts}")
    
    def __call__(self, func):
        """데코레이터로 사용 가능"""
        if inspect.iscoroutinefunction(func):
            return self._async_wrapper(func)
        else:
            return self._sync_wrapper(func)
    
    def _sync_wrapper(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.execute(func, *args, **kwargs)
        return wrapper
    
    def _async_wrapper(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.aexecute(func, *args, **kwargs)
        return wrapper
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """동기 함수 재시도 실행"""
        attempt = 0
        total_delay = 0.0
        last_exception = None
        
        while attempt < self.config.max_attempts:
            attempt += 1
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # 성공 기록
                self.stats.record_call(success=True, attempts=attempt, total_delay=total_delay)
                
                if attempt > 1:
                    logger.info(
                        f"✅ '{self.name}' succeeded on attempt {attempt}/{self.config.max_attempts} "
                        f"(took {execution_time:.2f}s, total delay: {total_delay:.2f}s)"
                    )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                last_exception = e
                
                # 재시도 여부 판단
                if not self._should_retry(e):
                    logger.warning(f"🔴 '{self.name}' failed with non-retryable error: {e}")
                    self.stats.record_call(success=False, attempts=attempt, total_delay=total_delay)
                    raise
                
                # 마지막 시도인 경우
                if attempt >= self.config.max_attempts:
                    logger.error(
                        f"🔴 '{self.name}' failed after {attempt} attempts "
                        f"(total delay: {total_delay:.2f}s): {e}"
                    )
                    self.stats.record_call(success=False, attempts=attempt, total_delay=total_delay)
                    raise
                
                # 다음 재시도 전 대기
                delay = self._calculate_delay(attempt)
                total_delay += delay
                
                logger.warning(
                    f"⚠️ '{self.name}' attempt {attempt}/{self.config.max_attempts} failed: {e} "
                    f"(took {execution_time:.2f}s, waiting {delay:.2f}s before retry)"
                )
                
                time.sleep(delay)
        
        # 모든 시도 실패
        self.stats.record_call(success=False, attempts=self.config.max_attempts, total_delay=total_delay)
        raise last_exception
    
    async def aexecute(self, func: Callable, *args, **kwargs) -> Any:
        """비동기 함수 재시도 실행"""
        attempt = 0
        total_delay = 0.0
        last_exception = None
        
        while attempt < self.config.max_attempts:
            attempt += 1
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # 성공 기록
                self.stats.record_call(success=True, attempts=attempt, total_delay=total_delay)
                
                if attempt > 1:
                    logger.info(
                        f"✅ '{self.name}' succeeded on attempt {attempt}/{self.config.max_attempts} "
                        f"(took {execution_time:.2f}s, total delay: {total_delay:.2f}s)"
                    )
                
                return result
                
            except Exception as e:
                execution_time = time.time() - start_time
                last_exception = e
                
                # 재시도 여부 판단
                if not self._should_retry(e):
                    logger.warning(f"🔴 '{self.name}' failed with non-retryable error: {e}")
                    self.stats.record_call(success=False, attempts=attempt, total_delay=total_delay)
                    raise
                
                # 마지막 시도인 경우
                if attempt >= self.config.max_attempts:
                    logger.error(
                        f"🔴 '{self.name}' failed after {attempt} attempts "
                        f"(total delay: {total_delay:.2f}s): {e}"
                    )
                    self.stats.record_call(success=False, attempts=attempt, total_delay=total_delay)
                    raise
                
                # 다음 재시도 전 대기
                delay = self._calculate_delay(attempt)
                total_delay += delay
                
                logger.warning(
                    f"⚠️ '{self.name}' attempt {attempt}/{self.config.max_attempts} failed: {e} "
                    f"(took {execution_time:.2f}s, waiting {delay:.2f}s before retry)"
                )
                
                await asyncio.sleep(delay)
        
        # 모든 시도 실패
        self.stats.record_call(success=False, attempts=self.config.max_attempts, total_delay=total_delay)
        raise last_exception
    
    def _should_retry(self, exception: Exception) -> bool:
        """재시도 여부 판단"""
        # 재시도하지 않을 예외 타입 체크
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False
        
        # 재시도할 예외 타입 체크
        if not isinstance(exception, self.config.retryable_exceptions):
            return False
        
        # 커스텀 재시도 조건 체크
        if self.config.retry_condition:
            return self.config.retry_condition(exception)
        
        return True
    
    def _calculate_delay(self, attempt: int) -> float:
        """재시도 대기 시간 계산 (Exponential Backoff + Jitter)"""
        # 기본 지수적 백오프
        delay = min(
            self.config.initial_delay * (self.config.exponential_base ** (attempt - 1)),
            self.config.max_delay
        )
        
        # 지터 적용 (네트워크 부하 분산)
        if self.config.jitter:
            jitter_amount = delay * self.config.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def get_status(self) -> dict:
        """현재 상태 및 통계 조회"""
        return {
            'name': self.name,
            'config': {
                'max_attempts': self.config.max_attempts,
                'initial_delay': self.config.initial_delay,
                'max_delay': self.config.max_delay,
                'exponential_base': self.config.exponential_base,
                'jitter': self.config.jitter,
                'jitter_range': self.config.jitter_range
            },
            'stats': self.stats.get_stats()
        }

# =============================================================================
# 편의 데코레이터 및 함수
# =============================================================================

def retry_with_backoff(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()
):
    """재시도 데코레이터"""
    config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions,
        non_retryable_exceptions=non_retryable_exceptions
    )
    
    def decorator(func):
        retry_manager = RetryManager(func.__name__, config)
        return retry_manager(func)
    
    return decorator

# =============================================================================
# 특화된 Retry Managers
# =============================================================================

# 네트워크 요청용 (일반적)
network_retry = RetryManager(
    'network',
    RetryConfig(
        max_attempts=3,
        initial_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=(ConnectionError, TimeoutError, OSError)
    )
)

# API 호출용 (조금 더 관대)
api_retry = RetryManager(
    'api_call',
    RetryConfig(
        max_attempts=5,
        initial_delay=0.5,
        max_delay=10.0,
        exponential_base=1.5
    )
)

# 거래소 API용 (신중함)
exchange_retry = RetryManager(
    'exchange_api',
    RetryConfig(
        max_attempts=2,
        initial_delay=2.0,
        max_delay=15.0,
        retryable_exceptions=(ConnectionError, TimeoutError)
    )
)

# 테스트 함수
async def test_retry_manager():
    """Retry Manager 테스트"""
    print("🧪 Testing Retry Manager...")
    
    # 간헐적으로 실패하는 함수
    call_count = 0
    
    @retry_with_backoff(max_attempts=4, initial_delay=0.1)
    async def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError(f"Simulated failure #{call_count}")
        return f"Success after {call_count} attempts"
    
    try:
        result = await flaky_function()
        print(f"✅ Result: {result}")
    except Exception as e:
        print(f"❌ Final failure: {e}")
    
    # 항상 실패하는 함수
    @retry_with_backoff(max_attempts=2, initial_delay=0.1)
    async def always_failing_function():
        raise ValueError("Always fails")
    
    try:
        await always_failing_function()
    except Exception as e:
        print(f"❌ Expected failure: {e}")

if __name__ == "__main__":
    asyncio.run(test_retry_manager())