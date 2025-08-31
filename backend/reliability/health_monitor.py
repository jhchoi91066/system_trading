"""
Health Monitor - 시스템 건강성 모니터링 및 알림
실시간 메트릭 수집, 임계값 모니터링, 자동 알림
"""

import asyncio
import time
import logging
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict
import json

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """건강 상태"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    DOWN = "down"

class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class HealthThreshold:
    """건강성 임계값"""
    warning: float
    critical: float
    duration: int = 60  # 임계값 지속 시간 (초)

@dataclass
class HealthMetric:
    """건강성 메트릭"""
    name: str
    value: float
    timestamp: float
    status: HealthStatus
    threshold: Optional[HealthThreshold] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class HealthAlert:
    """건강성 알림"""
    metric_name: str
    level: AlertLevel
    message: str
    timestamp: float
    value: float
    threshold: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class HealthCollector:
    """건강성 메트릭 수집기"""
    
    def __init__(self):
        self.collectors: Dict[str, Callable] = {}
        self._register_default_collectors()
    
    def _register_default_collectors(self):
        """기본 수집기들 등록"""
        self.collectors.update({
            'cpu_usage': self._collect_cpu_usage,
            'memory_usage': self._collect_memory_usage,
            'disk_usage': self._collect_disk_usage,
            'network_io': self._collect_network_io,
            'process_status': self._collect_process_status
        })
    
    def _collect_cpu_usage(self) -> float:
        """CPU 사용률 수집"""
        return psutil.cpu_percent(interval=1)
    
    def _collect_memory_usage(self) -> Dict[str, float]:
        """메모리 사용률 수집"""
        memory = psutil.virtual_memory()
        return {
            'percent': memory.percent,
            'used_gb': memory.used / (1024**3),
            'available_gb': memory.available / (1024**3)
        }
    
    def _collect_disk_usage(self) -> Dict[str, float]:
        """디스크 사용률 수집"""
        disk = psutil.disk_usage('/')
        return {
            'percent': (disk.used / disk.total) * 100,
            'used_gb': disk.used / (1024**3),
            'free_gb': disk.free / (1024**3)
        }
    
    def _collect_network_io(self) -> Dict[str, float]:
        """네트워크 I/O 수집"""
        net_io = psutil.net_io_counters()
        return {
            'bytes_sent': net_io.bytes_sent,
            'bytes_recv': net_io.bytes_recv,
            'packets_sent': net_io.packets_sent,
            'packets_recv': net_io.packets_recv
        }
    
    def _collect_process_status(self) -> Dict[str, Any]:
        """프로세스 상태 수집"""
        process = psutil.Process()
        return {
            'pid': process.pid,
            'cpu_percent': process.cpu_percent(),
            'memory_percent': process.memory_percent(),
            'num_threads': process.num_threads(),
            'create_time': process.create_time()
        }
    
    def register_collector(self, name: str, collector: Callable):
        """커스텀 수집기 등록"""
        self.collectors[name] = collector
        logger.info(f"📊 Health collector '{name}' registered")
    
    def collect_all(self) -> Dict[str, Any]:
        """모든 메트릭 수집"""
        metrics = {}
        for name, collector in self.collectors.items():
            try:
                metrics[name] = collector()
            except Exception as e:
                logger.error(f"🔴 Failed to collect metric '{name}': {e}")
                metrics[name] = None
        return metrics

class HealthMonitor:
    """건강성 모니터링 시스템"""
    
    def __init__(self, name: str = "system"):
        self.name = name
        self.collector = HealthCollector()
        self.thresholds: Dict[str, HealthThreshold] = {}
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.alerts: deque = deque(maxlen=1000)
        self.alert_handlers: List[Callable] = []
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.monitor_interval = 30  # 30초마다 체크
        
        # 기본 임계값 설정
        self._setup_default_thresholds()
        
        logger.info(f"🩺 Health Monitor '{name}' initialized")
    
    def _setup_default_thresholds(self):
        """기본 임계값 설정"""
        self.thresholds.update({
            'cpu_usage': HealthThreshold(warning=70.0, critical=90.0),
            'memory_usage.percent': HealthThreshold(warning=80.0, critical=95.0),
            'disk_usage.percent': HealthThreshold(warning=85.0, critical=95.0)
        })
    
    def set_threshold(self, metric_name: str, threshold: HealthThreshold):
        """임계값 설정"""
        self.thresholds[metric_name] = threshold
        logger.info(f"🎯 Threshold set for '{metric_name}': warning={threshold.warning}, critical={threshold.critical}")
    
    def add_alert_handler(self, handler: Callable[[HealthAlert], None]):
        """알림 핸들러 추가"""
        self.alert_handlers.append(handler)
        logger.info(f"📢 Alert handler added: {handler.__name__}")
    
    def register_custom_metric(self, name: str, collector: Callable):
        """커스텀 메트릭 등록"""
        self.collector.register_collector(name, collector)
    
    async def start_monitoring(self):
        """모니터링 시작"""
        if self.running:
            logger.warning("⚠️ Health monitoring already running")
            return
        
        self.running = True
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info(f"🚀 Health monitoring started (interval: {self.monitor_interval}s)")
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        if not self.running:
            return
        
        self.running = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Health monitoring stopped")
    
    async def _monitor_loop(self):
        """모니터링 메인 루프"""
        while self.running:
            try:
                await self._collect_and_evaluate()
                await asyncio.sleep(self.monitor_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"🔴 Health monitoring error: {e}")
                await asyncio.sleep(self.monitor_interval)
    
    async def _collect_and_evaluate(self):
        """메트릭 수집 및 평가"""
        timestamp = time.time()
        
        # 메트릭 수집
        raw_metrics = self.collector.collect_all()
        
        # 메트릭 평가 및 저장
        for metric_path, value in self._flatten_metrics(raw_metrics).items():
            if value is None:
                continue
                
            # 상태 평가
            status = self._evaluate_metric_status(metric_path, value)
            
            # 메트릭 객체 생성
            metric = HealthMetric(
                name=metric_path,
                value=value,
                timestamp=timestamp,
                status=status,
                threshold=self.thresholds.get(metric_path)
            )
            
            # 히스토리에 저장
            self.metrics_history[metric_path].append(metric)
            
            # 알림 확인
            await self._check_alerts(metric)
    
    def _flatten_metrics(self, metrics: Dict[str, Any], prefix: str = "") -> Dict[str, float]:
        """중첩된 메트릭을 평면화"""
        flattened = {}
        
        for key, value in metrics.items():
            full_key = f"{prefix}.{key}" if prefix else key
            
            if isinstance(value, dict):
                flattened.update(self._flatten_metrics(value, full_key))
            elif isinstance(value, (int, float)):
                flattened[full_key] = float(value)
        
        return flattened
    
    def _evaluate_metric_status(self, metric_path: str, value: float) -> HealthStatus:
        """메트릭 상태 평가"""
        threshold = self.thresholds.get(metric_path)
        if not threshold:
            return HealthStatus.HEALTHY
        
        if value >= threshold.critical:
            return HealthStatus.CRITICAL
        elif value >= threshold.warning:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    async def _check_alerts(self, metric: HealthMetric):
        """알림 확인 및 발송"""
        if metric.status in [HealthStatus.WARNING, HealthStatus.CRITICAL]:
            # 중복 알림 방지 (같은 메트릭의 최근 알림 확인)
            if self._should_send_alert(metric):
                alert = HealthAlert(
                    metric_name=metric.name,
                    level=AlertLevel.WARNING if metric.status == HealthStatus.WARNING else AlertLevel.CRITICAL,
                    message=self._generate_alert_message(metric),
                    timestamp=metric.timestamp,
                    value=metric.value,
                    threshold=metric.threshold.warning if metric.status == HealthStatus.WARNING else metric.threshold.critical
                )
                
                # 알림 저장
                self.alerts.append(alert)
                
                # 핸들러에 알림 전송
                await self._send_alert(alert)
    
    def _should_send_alert(self, metric: HealthMetric) -> bool:
        """알림 발송 여부 판단 (중복 방지)"""
        # 최근 5분 내 같은 메트릭의 알림이 있는지 확인
        cutoff_time = metric.timestamp - 300  # 5분
        
        for alert in reversed(self.alerts):
            if alert.timestamp < cutoff_time:
                break
            if alert.metric_name == metric.name and alert.level.value in ['warning', 'critical']:
                return False
        
        return True
    
    def _generate_alert_message(self, metric: HealthMetric) -> str:
        """알림 메시지 생성"""
        threshold_value = (
            metric.threshold.warning if metric.status == HealthStatus.WARNING 
            else metric.threshold.critical
        )
        
        return (
            f"{metric.name} is {metric.status.value}: "
            f"current value {metric.value:.2f} exceeds {metric.status.value} threshold {threshold_value:.2f}"
        )
    
    async def _send_alert(self, alert: HealthAlert):
        """알림 전송"""
        logger.warning(f"🚨 ALERT [{alert.level.value.upper()}] {alert.message}")
        
        # 등록된 핸들러들에 알림 전송
        for handler in self.alert_handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(alert)
                else:
                    handler(alert)
            except Exception as e:
                logger.error(f"🔴 Alert handler error: {e}")
    
    def get_current_status(self) -> Dict[str, Any]:
        """현재 상태 조회"""
        current_time = time.time()
        overall_status = HealthStatus.HEALTHY
        
        # 최근 메트릭들 확인
        current_metrics = {}
        for metric_name, history in self.metrics_history.items():
            if history and current_time - history[-1].timestamp < 300:  # 5분 내
                latest_metric = history[-1]
                current_metrics[metric_name] = {
                    'value': latest_metric.value,
                    'status': latest_metric.status.value,
                    'timestamp': latest_metric.timestamp
                }
                
                # 전체 상태 업데이트
                if latest_metric.status == HealthStatus.CRITICAL:
                    overall_status = HealthStatus.CRITICAL
                elif latest_metric.status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
                    overall_status = HealthStatus.WARNING
        
        # 최근 알림들
        recent_alerts = [
            {
                'metric_name': alert.metric_name,
                'level': alert.level.value,
                'message': alert.message,
                'timestamp': alert.timestamp,
                'value': alert.value
            }
            for alert in list(self.alerts)[-10:]  # 최근 10개
        ]
        
        return {
            'name': self.name,
            'overall_status': overall_status.value,
            'timestamp': current_time,
            'metrics': current_metrics,
            'recent_alerts': recent_alerts,
            'monitoring_active': self.running
        }
    
    def get_metric_history(self, metric_name: str, duration_minutes: int = 60) -> List[Dict[str, Any]]:
        """메트릭 히스토리 조회"""
        if metric_name not in self.metrics_history:
            return []
        
        cutoff_time = time.time() - (duration_minutes * 60)
        
        return [
            {
                'value': metric.value,
                'status': metric.status.value,
                'timestamp': metric.timestamp
            }
            for metric in self.metrics_history[metric_name]
            if metric.timestamp >= cutoff_time
        ]

# =============================================================================
# 알림 핸들러들
# =============================================================================

def console_alert_handler(alert: HealthAlert):
    """콘솔 알림 핸들러"""
    timestamp = datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')
    print(f"🚨 [{timestamp}] {alert.level.value.upper()}: {alert.message}")

def log_alert_handler(alert: HealthAlert):
    """로그 알림 핸들러"""
    if alert.level == AlertLevel.CRITICAL:
        logger.critical(f"🚨 {alert.message}")
    elif alert.level == AlertLevel.ERROR:
        logger.error(f"⚠️ {alert.message}")
    else:
        logger.warning(f"⚠️ {alert.message}")

async def webhook_alert_handler(alert: HealthAlert, webhook_url: str):
    """웹훅 알림 핸들러 (예시)"""
    import aiohttp
    
    payload = {
        'metric_name': alert.metric_name,
        'level': alert.level.value,
        'message': alert.message,
        'timestamp': alert.timestamp,
        'value': alert.value
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as response:
                if response.status == 200:
                    logger.info(f"📤 Alert sent to webhook: {alert.metric_name}")
                else:
                    logger.error(f"🔴 Failed to send alert to webhook: {response.status}")
    except Exception as e:
        logger.error(f"🔴 Webhook alert error: {e}")

# 글로벌 건강성 모니터
health_monitor = HealthMonitor("trading_bot")

# 기본 핸들러 등록
health_monitor.add_alert_handler(console_alert_handler)
health_monitor.add_alert_handler(log_alert_handler)

# 테스트 함수
async def test_health_monitor():
    """Health Monitor 테스트"""
    print("🧪 Testing Health Monitor...")
    
    # 커스텀 메트릭 등록
    def custom_metric():
        import random
        return random.uniform(50, 100)
    
    health_monitor.register_custom_metric('custom_test', custom_metric)
    health_monitor.set_threshold('custom_test', HealthThreshold(warning=75.0, critical=90.0))
    
    # 모니터링 시작
    await health_monitor.start_monitoring()
    
    # 10초 대기
    await asyncio.sleep(10)
    
    # 상태 확인
    status = health_monitor.get_current_status()
    print(f"💊 Health Status: {status['overall_status']}")
    print(f"📊 Active Metrics: {len(status['metrics'])}")
    
    # 모니터링 중지
    await health_monitor.stop_monitoring()

if __name__ == "__main__":
    asyncio.run(test_health_monitor())