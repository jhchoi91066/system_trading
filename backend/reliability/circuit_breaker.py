"""
Circuit Breaker 패턴 구현
시스템 장애 시 자동 차단 및 복구 메커니즘
"""

import time
import logging
import asyncio
from enum import Enum
from typing import Callable, Any, Dict, Optional, Union
from dataclasses import dataclass, field
from functools import wraps
import threading

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit Breaker 상태"""
    CLOSED = "closed"        # 정상 상태 (요청 허용)
    OPEN = "open"           # 장애 상태 (요청 차단)
    HALF_OPEN = "half_open" # 복구 테스트 상태

@dataclass
class CircuitBreakerConfig:
    """Circuit Breaker 설정"""
    failure_threshold: int = 5          # 실패 임계값
    recovery_timeout: float = 60.0      # 복구 대기 시간 (초)
    expected_exception: tuple = (Exception,)  # 감지할 예외 타입들
    success_threshold: int = 3          # HALF_OPEN에서 CLOSED로 전환할 성공 횟수
    timeout: float = 30.0               # 요청 타임아웃
    
@dataclass
class CircuitBreakerStats:
    """Circuit Breaker 통계"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    state_changes: Dict[str, int] = field(default_factory=lambda: {
        'closed_to_open': 0,
        'open_to_half_open': 0,
        'half_open_to_closed': 0,
        'half_open_to_open': 0
    })

class CircuitBreakerError(Exception):
    """Circuit Breaker 관련 예외"""
    pass

class CircuitBreakerOpenError(CircuitBreakerError):
    """Circuit가 OPEN 상태일 때 발생하는 예외"""
    pass

class CircuitBreaker:
    """
    Circuit Breaker 패턴 구현
    
    시스템 장애 시 자동으로 요청을 차단하고,
    일정 시간 후 복구를 시도하는 메커니즘
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._lock = threading.RLock()
        
        logger.info(f"🔌 Circuit Breaker '{name}' initialized: {self.config}")
    
    def __call__(self, func):
        """데코레이터로 사용 가능"""
        if asyncio.iscoroutinefunction(func):
            return self._async_wrapper(func)
        else:
            return self._sync_wrapper(func)
    
    def _sync_wrapper(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.call(func, *args, **kwargs)
        return wrapper
    
    def _async_wrapper(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await self.acall(func, *args, **kwargs)
        return wrapper
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """동기 함수 호출"""
        with self._lock:
            self._check_state()
            
            if self.state == CircuitState.OPEN:
                self._record_request(success=False)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Will retry after {self.config.recovery_timeout}s"
                )
            
            start_time = time.time()
            try:
                # 타임아웃 처리는 외부에서 구현하거나 함수 내부에서 처리
                result = func(*args, **kwargs)
                self._record_success()
                return result
                
            except self.config.expected_exception as e:
                execution_time = time.time() - start_time
                self._record_failure()
                logger.warning(
                    f"🔴 Circuit breaker '{self.name}' recorded failure: {e} "
                    f"(took {execution_time:.2f}s)"
                )
                raise
    
    async def acall(self, func: Callable, *args, **kwargs) -> Any:
        """비동기 함수 호출"""
        with self._lock:
            self._check_state()
            
            if self.state == CircuitState.OPEN:
                self._record_request(success=False)
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Will retry after {self.config.recovery_timeout}s"
                )
        
        start_time = time.time()
        try:
            # 비동기 타임아웃 처리
            result = await asyncio.wait_for(
                func(*args, **kwargs), 
                timeout=self.config.timeout
            )
            self._record_success()
            return result
            
        except asyncio.TimeoutError:
            self._record_failure()
            logger.warning(f"🔴 Circuit breaker '{self.name}' timeout after {self.config.timeout}s")
            raise
            
        except self.config.expected_exception as e:
            execution_time = time.time() - start_time
            self._record_failure()
            logger.warning(
                f"🔴 Circuit breaker '{self.name}' recorded failure: {e} "
                f"(took {execution_time:.2f}s)"
            )
            raise
    
    def _check_state(self):
        """현재 상태 확인 및 상태 전환 처리"""
        current_time = time.time()
        
        if self.state == CircuitState.OPEN:
            if (self.stats.last_failure_time and 
                current_time - self.stats.last_failure_time >= self.config.recovery_timeout):
                self._transition_to_half_open()
        
        elif self.state == CircuitState.HALF_OPEN:
            if self.stats.consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()
    
    def _record_success(self):
        """성공 기록"""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            
            # HALF_OPEN에서 충분한 성공 시 CLOSED로 전환
            if (self.state == CircuitState.HALF_OPEN and 
                self.stats.consecutive_successes >= self.config.success_threshold):
                self._transition_to_closed()
    
    def _record_failure(self):
        """실패 기록"""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.failed_requests += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = time.time()
            
            # 실패 임계값 초과 시 OPEN으로 전환
            if (self.state == CircuitState.CLOSED and 
                self.stats.consecutive_failures >= self.config.failure_threshold):
                self._transition_to_open()
            
            # HALF_OPEN에서 실패 시 즉시 OPEN으로 전환
            elif self.state == CircuitState.HALF_OPEN:
                self._transition_to_open()
    
    def _record_request(self, success: bool):
        """요청 기록 (성공/실패 구분 없이)"""
        with self._lock:
            self.stats.total_requests += 1
    
    def _transition_to_open(self):
        """OPEN 상태로 전환"""
        if self.state != CircuitState.OPEN:
            old_state = self.state
            self.state = CircuitState.OPEN
            self.stats.state_changes[f'{old_state.value}_to_open'] += 1
            logger.error(f"🔴 Circuit breaker '{self.name}' opened: {self.stats.consecutive_failures} consecutive failures")
    
    def _transition_to_half_open(self):
        """HALF_OPEN 상태로 전환"""
        if self.state != CircuitState.HALF_OPEN:
            old_state = self.state
            self.state = CircuitState.HALF_OPEN
            self.stats.state_changes[f'{old_state.value}_to_half_open'] += 1
            self.stats.consecutive_successes = 0
            self.stats.consecutive_failures = 0
            logger.info(f"🟡 Circuit breaker '{self.name}' half-opened: testing recovery")
    
    def _transition_to_closed(self):
        """CLOSED 상태로 전환"""
        if self.state != CircuitState.CLOSED:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.stats.state_changes[f'{old_state.value}_to_closed'] += 1
            self.stats.consecutive_failures = 0
            logger.info(f"✅ Circuit breaker '{self.name}' closed: recovery successful")
    
    def reset(self):
        """Circuit Breaker 상태 리셋"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats.consecutive_failures = 0
            self.stats.consecutive_successes = 0
            logger.info(f"🔄 Circuit breaker '{self.name}' manually reset")
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 및 통계 조회"""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'stats': {
                    'total_requests': self.stats.total_requests,
                    'successful_requests': self.stats.successful_requests,
                    'failed_requests': self.stats.failed_requests,
                    'success_rate': (
                        self.stats.successful_requests / self.stats.total_requests * 100
                        if self.stats.total_requests > 0 else 0
                    ),
                    'consecutive_failures': self.stats.consecutive_failures,
                    'consecutive_successes': self.stats.consecutive_successes,
                    'last_failure_time': self.stats.last_failure_time,
                    'state_changes': dict(self.stats.state_changes)
                },
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'success_threshold': self.config.success_threshold,
                    'timeout': self.config.timeout
                }
            }

# =============================================================================
# 글로벌 Circuit Breakers
# =============================================================================

# 거래소 API용 Circuit Breakers
exchange_breaker = CircuitBreaker(
    'exchange_api',
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
        timeout=10.0
    )
)

# 데이터베이스용 Circuit Breaker
database_breaker = CircuitBreaker(
    'database',
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60.0,
        timeout=5.0
    )
)

# 외부 서비스용 Circuit Breaker
external_service_breaker = CircuitBreaker(
    'external_service',
    CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout=120.0,
        timeout=15.0
    )
)

# =============================================================================
# 편의 데코레이터
# =============================================================================

def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Circuit Breaker 데코레이터"""
    breaker = CircuitBreaker(name, config)
    return breaker

# 테스트 함수
async def test_circuit_breaker():
    """Circuit Breaker 테스트"""
    print("🧪 Testing Circuit Breaker...")
    
    # 실패하는 함수
    @circuit_breaker('test_breaker', CircuitBreakerConfig(failure_threshold=2, recovery_timeout=5.0))
    async def failing_function():
        raise Exception("Test failure")
    
    # 성공하는 함수
    @circuit_breaker('test_breaker_success', CircuitBreakerConfig(failure_threshold=3))
    async def success_function():
        return "Success!"
    
    # 실패 테스트
    for i in range(5):
        try:
            await failing_function()
        except Exception as e:
            print(f"Attempt {i+1}: {e}")
    
    # 성공 테스트
    try:
        result = await success_function()
        print(f"✅ Success: {result}")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_circuit_breaker())