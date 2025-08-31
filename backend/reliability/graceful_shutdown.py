"""
Graceful Shutdown - 우아한 종료 및 복구
시스템 종료 시 리소스 정리 및 데이터 무결성 보장
"""

import asyncio
import signal
import logging
import threading
import time
from typing import List, Callable, Any, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from contextlib import asynccontextmanager
import atexit

logger = logging.getLogger(__name__)

class ShutdownPhase(Enum):
    """종료 단계"""
    RUNNING = "running"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    GRACEFUL_SHUTDOWN = "graceful_shutdown"
    FORCE_SHUTDOWN = "force_shutdown"
    SHUTDOWN_COMPLETE = "shutdown_complete"

@dataclass
class ShutdownHandler:
    """종료 핸들러"""
    name: str
    handler: Callable
    priority: int = 0  # 높을수록 먼저 실행
    timeout: float = 30.0  # 핸들러 타임아웃
    is_async: bool = False

class GracefulShutdown:
    """우아한 종료 관리자"""
    
    def __init__(self, name: str = "system", graceful_timeout: float = 30.0):
        self.name = name
        self.graceful_timeout = graceful_timeout
        self.phase = ShutdownPhase.RUNNING
        self.shutdown_handlers: List[ShutdownHandler] = []
        self.shutdown_event = asyncio.Event()
        self._shutdown_requested = False
        self._force_shutdown = False
        
        # 시그널 핸들러 등록
        self._setup_signal_handlers()
        
        # 프로세스 종료 시 정리 함수 등록
        atexit.register(self._cleanup_on_exit)
        
        logger.info(f"🛡️ Graceful Shutdown Manager '{name}' initialized (timeout: {graceful_timeout}s)")
    
    def _setup_signal_handlers(self):
        """시그널 핸들러 설정"""
        try:
            # SIGTERM (정상 종료 요청)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # SIGINT (Ctrl+C)
            signal.signal(signal.SIGINT, self._signal_handler)
            
            # Unix에서만 사용 가능한 시그널들
            if hasattr(signal, 'SIGHUP'):
                signal.signal(signal.SIGHUP, self._signal_handler)
            
            logger.info("📡 Signal handlers registered")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to register signal handlers: {e}")
    
    def _signal_handler(self, signum, frame):
        """시그널 핸들러"""
        signal_name = signal.Signals(signum).name
        logger.info(f"🔔 Received signal {signal_name} ({signum})")
        
        if not self._shutdown_requested:
            self._shutdown_requested = True
            self.phase = ShutdownPhase.SHUTDOWN_REQUESTED
            
            # 비동기 이벤트 설정 (메인 루프에서 처리)
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(self.shutdown_event.set)
            except RuntimeError:
                # 메인 루프가 없으면 동기적으로 종료
                self._perform_sync_shutdown()
    
    def register_handler(
        self, 
        name: str, 
        handler: Callable, 
        priority: int = 0, 
        timeout: float = 30.0,
        is_async: bool = None
    ):
        """종료 핸들러 등록"""
        if is_async is None:
            is_async = asyncio.iscoroutinefunction(handler)
        
        shutdown_handler = ShutdownHandler(
            name=name,
            handler=handler,
            priority=priority,
            timeout=timeout,
            is_async=is_async
        )
        
        self.shutdown_handlers.append(shutdown_handler)
        
        # 우선순위 순으로 정렬 (높은 우선순위가 먼저)
        self.shutdown_handlers.sort(key=lambda h: h.priority, reverse=True)
        
        logger.info(f"🔧 Shutdown handler '{name}' registered (priority: {priority}, async: {is_async})")
    
    async def wait_for_shutdown(self):
        """종료 신호 대기"""
        await self.shutdown_event.wait()
        logger.info("🛑 Shutdown signal received, starting graceful shutdown...")
        await self.shutdown()
    
    async def shutdown(self, force: bool = False):
        """우아한 종료 실행"""
        if self.phase in [ShutdownPhase.GRACEFUL_SHUTDOWN, ShutdownPhase.FORCE_SHUTDOWN, ShutdownPhase.SHUTDOWN_COMPLETE]:
            logger.warning("⚠️ Shutdown already in progress or complete")
            return
        
        start_time = time.time()
        
        if force:
            self.phase = ShutdownPhase.FORCE_SHUTDOWN
            logger.warning("⚡ Force shutdown requested")
        else:
            self.phase = ShutdownPhase.GRACEFUL_SHUTDOWN
            logger.info("🕊️ Graceful shutdown started")
        
        # 핸들러들 실행
        success_count = 0
        for handler in self.shutdown_handlers:
            try:
                handler_start = time.time()
                
                logger.info(f"🔄 Executing shutdown handler: {handler.name}")
                
                if handler.is_async:
                    await asyncio.wait_for(handler.handler(), timeout=handler.timeout)
                else:
                    # 동기 핸들러를 별도 스레드에서 실행
                    await asyncio.get_event_loop().run_in_executor(
                        None, 
                        self._run_sync_handler_with_timeout, 
                        handler.handler, 
                        handler.timeout
                    )
                
                handler_time = time.time() - handler_start
                logger.info(f"✅ Shutdown handler '{handler.name}' completed ({handler_time:.2f}s)")
                success_count += 1
                
            except asyncio.TimeoutError:
                logger.error(f"⏰ Shutdown handler '{handler.name}' timed out after {handler.timeout}s")
            except Exception as e:
                logger.error(f"🔴 Shutdown handler '{handler.name}' failed: {e}")
            
            # Force shutdown인 경우 더 빠르게 처리
            if force and time.time() - start_time > self.graceful_timeout / 2:
                logger.warning("⚡ Force shutdown timeout, stopping handler execution")
                break
        
        total_time = time.time() - start_time
        self.phase = ShutdownPhase.SHUTDOWN_COMPLETE
        
        logger.info(
            f"🏁 Shutdown completed: {success_count}/{len(self.shutdown_handlers)} handlers succeeded "
            f"(total time: {total_time:.2f}s)"
        )
    
    def _run_sync_handler_with_timeout(self, handler: Callable, timeout: float):
        """타임아웃이 있는 동기 핸들러 실행"""
        import threading
        
        result = None
        exception = None
        
        def target():
            nonlocal result, exception
            try:
                result = handler()
            except Exception as e:
                exception = e
        
        thread = threading.Thread(target=target)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            raise asyncio.TimeoutError(f"Handler timed out after {timeout}s")
        
        if exception:
            raise exception
        
        return result
    
    def _perform_sync_shutdown(self):
        """동기적 종료 수행 (비상시)"""
        logger.warning("⚡ Performing synchronous emergency shutdown")
        
        for handler in self.shutdown_handlers:
            if not handler.is_async:
                try:
                    handler.handler()
                    logger.info(f"✅ Emergency handler '{handler.name}' completed")
                except Exception as e:
                    logger.error(f"🔴 Emergency handler '{handler.name}' failed: {e}")
    
    def _cleanup_on_exit(self):
        """프로세스 종료 시 정리"""
        if self.phase != ShutdownPhase.SHUTDOWN_COMPLETE:
            logger.warning("🚨 Process exiting without graceful shutdown, performing cleanup")
            self._perform_sync_shutdown()
    
    def request_shutdown(self):
        """프로그래밍 방식으로 종료 요청"""
        if not self._shutdown_requested:
            logger.info("📝 Shutdown requested programmatically")
            self._shutdown_requested = True
            self.phase = ShutdownPhase.SHUTDOWN_REQUESTED
            self.shutdown_event.set()
    
    def is_shutting_down(self) -> bool:
        """종료 중인지 확인"""
        return self.phase in [
            ShutdownPhase.SHUTDOWN_REQUESTED,
            ShutdownPhase.GRACEFUL_SHUTDOWN,
            ShutdownPhase.FORCE_SHUTDOWN
        ]
    
    def is_shutdown_complete(self) -> bool:
        """종료 완료 여부 확인"""
        return self.phase == ShutdownPhase.SHUTDOWN_COMPLETE
    
    def get_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        return {
            'name': self.name,
            'phase': self.phase.value,
            'shutdown_requested': self._shutdown_requested,
            'handlers_count': len(self.shutdown_handlers),
            'handlers': [
                {
                    'name': h.name,
                    'priority': h.priority,
                    'timeout': h.timeout,
                    'is_async': h.is_async
                }
                for h in self.shutdown_handlers
            ]
        }

# =============================================================================
# 컨텍스트 매니저
# =============================================================================

@asynccontextmanager
async def graceful_shutdown_context(shutdown_manager: GracefulShutdown):
    """Graceful Shutdown 컨텍스트 매니저"""
    try:
        # 백그라운드에서 종료 신호 대기
        shutdown_task = asyncio.create_task(shutdown_manager.wait_for_shutdown())
        yield shutdown_manager
    except KeyboardInterrupt:
        logger.info("⌨️ KeyboardInterrupt received")
        shutdown_manager.request_shutdown()
    finally:
        # 정리 작업
        if not shutdown_manager.is_shutdown_complete():
            await shutdown_manager.shutdown()
        
        # 대기 중인 태스크 정리
        if 'shutdown_task' in locals() and not shutdown_task.done():
            shutdown_task.cancel()

# =============================================================================
# 글로벌 Shutdown Manager
# =============================================================================

shutdown_manager = GracefulShutdown("trading_bot", graceful_timeout=60.0)

# =============================================================================
# 일반적인 종료 핸들러들
# =============================================================================

def register_database_cleanup(db_connection):
    """데이터베이스 연결 정리 핸들러"""
    async def cleanup():
        logger.info("🗄️ Closing database connections...")
        if hasattr(db_connection, 'close'):
            await db_connection.close()
        elif hasattr(db_connection, 'disconnect'):
            await db_connection.disconnect()
        logger.info("✅ Database connections closed")
    
    shutdown_manager.register_handler("database_cleanup", cleanup, priority=90)

def register_websocket_cleanup(websocket_manager):
    """WebSocket 연결 정리 핸들러"""
    async def cleanup():
        logger.info("🔌 Closing WebSocket connections...")
        if hasattr(websocket_manager, 'disconnect_all'):
            await websocket_manager.disconnect_all()
        logger.info("✅ WebSocket connections closed")
    
    shutdown_manager.register_handler("websocket_cleanup", cleanup, priority=80)

def register_cache_cleanup(cache_manager):
    """캐시 정리 핸들러"""
    async def cleanup():
        logger.info("🧹 Flushing cache data...")
        if hasattr(cache_manager, 'flush'):
            await cache_manager.flush()
        logger.info("✅ Cache flushed")
    
    shutdown_manager.register_handler("cache_cleanup", cleanup, priority=70)

def register_file_cleanup(file_paths: List[str]):
    """임시 파일 정리 핸들러"""
    def cleanup():
        import os
        logger.info("🗂️ Cleaning up temporary files...")
        cleaned_count = 0
        for path in file_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    cleaned_count += 1
            except Exception as e:
                logger.error(f"Failed to remove {path}: {e}")
        logger.info(f"✅ Cleaned up {cleaned_count} temporary files")
    
    shutdown_manager.register_handler("file_cleanup", cleanup, priority=60, is_async=False)

# 테스트 함수
async def test_graceful_shutdown():
    """Graceful Shutdown 테스트"""
    print("🧪 Testing Graceful Shutdown...")
    
    # 테스트용 핸들러들 등록
    async def async_handler():
        logger.info("🔄 Async handler running...")
        await asyncio.sleep(1)
        logger.info("✅ Async handler completed")
    
    def sync_handler():
        logger.info("🔄 Sync handler running...")
        time.sleep(0.5)
        logger.info("✅ Sync handler completed")
    
    test_manager = GracefulShutdown("test", graceful_timeout=10.0)
    test_manager.register_handler("async_test", async_handler, priority=10)
    test_manager.register_handler("sync_test", sync_handler, priority=5, is_async=False)
    
    # 상태 확인
    status = test_manager.get_status()
    print(f"📊 Handlers registered: {status['handlers_count']}")
    
    # 종료 시뮬레이션
    await test_manager.shutdown()
    print(f"🏁 Shutdown phase: {test_manager.phase.value}")

if __name__ == "__main__":
    asyncio.run(test_graceful_shutdown())