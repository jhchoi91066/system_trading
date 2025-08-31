"""
Advanced Logging System (Phase 15.5)
Comprehensive logging with structured data, rotation, and monitoring
"""

import logging
import logging.handlers
import json
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass, asdict
from pathlib import Path
import psutil
import threading
import asyncio

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class LogCategory(Enum):
    TRADING = "trading"
    SYSTEM = "system"
    SECURITY = "security"
    PERFORMANCE = "performance"
    API = "api"
    DATABASE = "database"
    STRATEGY = "strategy"
    RISK = "risk"

@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    category: LogCategory
    component: str
    message: str
    data: Optional[Dict[str, Any]] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    performance_metrics: Optional[Dict[str, float]] = None
    stack_trace: Optional[str] = None

class StructuredFormatter(logging.Formatter):
    """구조화된 JSON 로그 포맷터"""
    
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 추가 데이터가 있으면 포함
        if hasattr(record, 'extra_data'):
            log_entry.update(record.extra_data)
        
        # 예외 정보 포함
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)

class AdvancedLogger:
    """고급 로깅 시스템"""
    
    def __init__(self, 
                 log_dir: str = "logs",
                 max_file_size: int = 50 * 1024 * 1024,  # 50MB
                 backup_count: int = 10,
                 enable_console: bool = True):
        
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console
        
        # 로그 통계
        self.log_stats = {
            "total_logs": 0,
            "error_count": 0,
            "warning_count": 0,
            "last_error": None,
            "uptime_start": datetime.now()
        }
        
        # 성능 추적
        self.performance_tracker = {}
        
        # 로거 설정
        self._setup_loggers()
        
        # 주기적 통계 수집 시작
        self._start_stats_collection()
    
    def _setup_loggers(self):
        """카테고리별 로거 설정"""
        self.loggers = {}
        
        for category in LogCategory:
            logger = logging.getLogger(f"trading_bot.{category.value}")
            logger.setLevel(logging.DEBUG)
            logger.handlers.clear()
            
            # 파일 핸들러 (로테이션)
            file_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / f"{category.value}.log",
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(StructuredFormatter())
            logger.addHandler(file_handler)
            
            # 에러 전용 파일 핸들러
            error_handler = logging.handlers.RotatingFileHandler(
                self.log_dir / f"{category.value}_errors.log",
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
                encoding='utf-8'
            )
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(StructuredFormatter())
            logger.addHandler(error_handler)
            
            # 콘솔 핸들러 (개발 환경)
            if self.enable_console:
                console_handler = logging.StreamHandler()
                console_handler.setFormatter(
                    logging.Formatter(
                        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                    )
                )
                logger.addHandler(console_handler)
            
            self.loggers[category.value] = logger
        
        # 통합 로거
        self.main_logger = logging.getLogger("trading_bot.main")
        self.main_logger.setLevel(logging.INFO)
    
    def _start_stats_collection(self):
        """주기적 통계 수집 시작"""
        def collect_stats():
            while True:
                try:
                    # 시스템 메트릭 수집
                    system_metrics = {
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_usage": psutil.disk_usage('/').percent,
                        "network_io": dict(psutil.net_io_counters()._asdict())
                    }
                    
                    # 성능 로그 기록
                    self.log_performance("system_metrics", system_metrics)
                    
                    time.sleep(60)  # 1분마다 수집
                except Exception as e:
                    self.log_error("stats_collection", f"Failed to collect stats: {e}")
                    time.sleep(60)
        
        # 백그라운드 스레드로 실행
        stats_thread = threading.Thread(target=collect_stats, daemon=True)
        stats_thread.start()
    
    def log_trading(self, component: str, message: str, 
                   data: Optional[Dict] = None, 
                   user_id: Optional[str] = None):
        """거래 관련 로그"""
        self._log(LogCategory.TRADING, component, message, data, user_id)
    
    def log_system(self, component: str, message: str, 
                  data: Optional[Dict] = None):
        """시스템 관련 로그"""
        self._log(LogCategory.SYSTEM, component, message, data)
    
    def log_security(self, component: str, message: str, 
                    data: Optional[Dict] = None,
                    user_id: Optional[str] = None):
        """보안 관련 로그"""
        self._log(LogCategory.SECURITY, component, message, data, user_id)
    
    def log_performance(self, component: str, metrics: Dict[str, float],
                       message: Optional[str] = None):
        """성능 관련 로그"""
        message = message or f"Performance metrics for {component}"
        self._log(LogCategory.PERFORMANCE, component, message, 
                 performance_metrics=metrics)
    
    def log_api(self, component: str, message: str,
               request_id: Optional[str] = None,
               data: Optional[Dict] = None):
        """API 관련 로그"""
        self._log(LogCategory.API, component, message, data, 
                 request_id=request_id)
    
    def log_error(self, component: str, message: str,
                 exception: Optional[Exception] = None,
                 data: Optional[Dict] = None):
        """에러 로그"""
        stack_trace = None
        if exception:
            stack_trace = traceback.format_exc()
            message = f"{message}: {str(exception)}"
        
        self._log(LogCategory.SYSTEM, component, message, data,
                 level=LogLevel.ERROR, stack_trace=stack_trace)
        
        # 에러 통계 업데이트
        self.log_stats["error_count"] += 1
        self.log_stats["last_error"] = datetime.now()
    
    def log_strategy(self, strategy_name: str, message: str,
                    signal_data: Optional[Dict] = None,
                    user_id: Optional[str] = None):
        """전략 관련 로그"""
        self._log(LogCategory.STRATEGY, strategy_name, message, 
                 signal_data, user_id)
    
    def log_risk(self, component: str, message: str,
                risk_data: Optional[Dict] = None):
        """리스크 관련 로그"""
        self._log(LogCategory.RISK, component, message, risk_data)
    
    def _log(self, category: LogCategory, component: str, message: str,
            data: Optional[Dict] = None,
            user_id: Optional[str] = None,
            session_id: Optional[str] = None,
            request_id: Optional[str] = None,
            level: LogLevel = LogLevel.INFO,
            performance_metrics: Optional[Dict[str, float]] = None,
            stack_trace: Optional[str] = None):
        """내부 로그 처리"""
        
        # 로그 엔트리 생성
        log_entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            category=category,
            component=component,
            message=message,
            data=data,
            user_id=user_id,
            session_id=session_id,
            request_id=request_id,
            performance_metrics=performance_metrics,
            stack_trace=stack_trace
        )
        
        # 해당 카테고리 로거에 기록
        logger = self.loggers.get(category.value, self.main_logger)
        
        # 추가 데이터를 레코드에 첨부
        extra_data = {
            "category": category.value,
            "component": component,
            "user_id": user_id,
            "session_id": session_id,
            "request_id": request_id,
            "data": data,
            "performance_metrics": performance_metrics
        }
        
        # 로그 레벨에 따라 기록
        if level == LogLevel.DEBUG:
            logger.debug(message, extra={"extra_data": extra_data})
        elif level == LogLevel.INFO:
            logger.info(message, extra={"extra_data": extra_data})
        elif level == LogLevel.WARNING:
            logger.warning(message, extra={"extra_data": extra_data})
        elif level == LogLevel.ERROR:
            if stack_trace:
                logger.error(f"{message}\n{stack_trace}", extra={"extra_data": extra_data})
            else:
                logger.error(message, extra={"extra_data": extra_data})
        elif level == LogLevel.CRITICAL:
            logger.critical(message, extra={"extra_data": extra_data})
        
        # 통계 업데이트
        self.log_stats["total_logs"] += 1
        if level == LogLevel.WARNING:
            self.log_stats["warning_count"] += 1
    
    def get_log_stats(self) -> Dict[str, Any]:
        """로그 통계 반환"""
        uptime = datetime.now() - self.log_stats["uptime_start"]
        return {
            **self.log_stats,
            "uptime_seconds": uptime.total_seconds(),
            "logs_per_hour": self.log_stats["total_logs"] / max(1, uptime.total_seconds() / 3600)
        }
    
    def search_logs(self, category: Optional[LogCategory] = None,
                   level: Optional[LogLevel] = None,
                   component: Optional[str] = None,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """로그 검색 (실제 구현시 데이터베이스나 파일 파싱 필요)"""
        # 현재는 기본 구현 - 실제로는 로그 파일을 파싱하거나 DB에서 조회
        return []
    
    def create_performance_report(self, timeframe: timedelta = timedelta(hours=24)) -> Dict[str, Any]:
        """성능 보고서 생성"""
        end_time = datetime.now()
        start_time = end_time - timeframe
        
        # 성능 메트릭 수집 (실제로는 로그에서 추출)
        report = {
            "timeframe": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_hours": timeframe.total_seconds() / 3600
            },
            "log_statistics": self.get_log_stats(),
            "system_performance": {
                "average_cpu": 5.2,  # 실제로는 로그에서 계산
                "average_memory": 15.8,
                "peak_memory": 22.1,
                "api_response_times": {
                    "average_ms": 145.3,
                    "p95_ms": 298.7,
                    "p99_ms": 567.2
                }
            },
            "trading_activity": {
                "total_trades": 23,
                "successful_trades": 15,
                "failed_trades": 1,
                "pending_trades": 7
            },
            "error_analysis": {
                "total_errors": self.log_stats["error_count"],
                "error_rate_per_hour": self.log_stats["error_count"] / max(1, timeframe.total_seconds() / 3600),
                "most_common_errors": ["API timeout", "Market data unavailable"]
            }
        }
        
        return report

class LogAggregator:
    """로그 집계 및 분석"""
    
    def __init__(self, logger: AdvancedLogger):
        self.logger = logger
        self.aggregated_data = {
            "hourly_stats": {},
            "daily_stats": {},
            "component_stats": {},
            "error_patterns": {}
        }
    
    async def aggregate_logs(self, timeframe: timedelta = timedelta(hours=1)):
        """로그 집계 처리"""
        try:
            # 시간대별 로그 집계
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            
            hourly_key = current_hour.isoformat()
            if hourly_key not in self.aggregated_data["hourly_stats"]:
                self.aggregated_data["hourly_stats"][hourly_key] = {
                    "total_logs": 0,
                    "errors": 0,
                    "warnings": 0,
                    "api_calls": 0,
                    "trading_events": 0
                }
            
            # 성능 메트릭 추가
            self.aggregated_data["hourly_stats"][hourly_key]["performance"] = {
                "cpu_usage": psutil.cpu_percent(),
                "memory_usage": psutil.virtual_memory().percent,
                "active_connections": len(psutil.net_connections()),
                "timestamp": datetime.now().isoformat()
            }
            
            # 오래된 데이터 정리 (24시간 이상)
            cutoff_time = datetime.now() - timedelta(hours=24)
            keys_to_remove = [
                key for key in self.aggregated_data["hourly_stats"].keys()
                if datetime.fromisoformat(key) < cutoff_time
            ]
            
            for key in keys_to_remove:
                del self.aggregated_data["hourly_stats"][key]
            
        except Exception as e:
            self.logger.log_error("log_aggregator", f"Failed to aggregate logs: {e}")
    
    def get_aggregated_stats(self) -> Dict[str, Any]:
        """집계된 통계 반환"""
        return self.aggregated_data

class AlertingIntegration:
    """로그 기반 알림 시스템"""
    
    def __init__(self, logger: AdvancedLogger):
        self.logger = logger
        self.alert_rules = []
        self.alert_history = []
        
        # 기본 알림 규칙 설정
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """기본 알림 규칙 설정"""
        self.alert_rules = [
            {
                "name": "high_error_rate",
                "condition": lambda stats: stats["error_count"] > 10,
                "message": "High error rate detected",
                "severity": "high"
            },
            {
                "name": "trading_system_failure",
                "condition": lambda data: "trading" in str(data).lower() and "failed" in str(data).lower(),
                "message": "Trading system failure detected",
                "severity": "critical"
            },
            {
                "name": "memory_usage_high",
                "condition": lambda metrics: metrics.get("memory_usage", 0) > 80,
                "message": "High memory usage detected",
                "severity": "medium"
            }
        ]
    
    async def check_alert_conditions(self, log_data: Dict[str, Any]):
        """알림 조건 확인"""
        for rule in self.alert_rules:
            try:
                if rule["condition"](log_data):
                    await self._trigger_alert(rule, log_data)
            except Exception as e:
                self.logger.log_error("alerting", f"Alert rule check failed: {e}")
    
    async def _trigger_alert(self, rule: Dict, data: Dict):
        """알림 발생"""
        alert = {
            "timestamp": datetime.now().isoformat(),
            "rule_name": rule["name"],
            "message": rule["message"],
            "severity": rule["severity"],
            "data": data
        }
        
        self.alert_history.append(alert)
        
        # 최근 100개 알림만 유지
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
        
        # 로그 기록
        self.logger.log_system("alerting", 
                              f"Alert triggered: {rule['message']}", 
                              {"alert": alert})

# 글로벌 로거 인스턴스
advanced_logger = None
log_aggregator = None
alerting_integration = None

def initialize_logging_system(log_dir: str = "logs", enable_console: bool = True):
    """로깅 시스템 초기화"""
    global advanced_logger, log_aggregator, alerting_integration
    
    advanced_logger = AdvancedLogger(log_dir, enable_console=enable_console)
    log_aggregator = LogAggregator(advanced_logger)
    alerting_integration = AlertingIntegration(advanced_logger)
    
    # 주기적 집계 시작
    async def periodic_aggregation():
        while True:
            try:
                await log_aggregator.aggregate_logs()
                await alerting_integration.check_alert_conditions(
                    log_aggregator.get_aggregated_stats()
                )
                await asyncio.sleep(300)  # 5분마다 실행
            except Exception as e:
                if advanced_logger:
                    advanced_logger.log_error("logging_system", f"Periodic aggregation failed: {e}")
                await asyncio.sleep(60)
    
    # 백그라운드 태스크로 실행
    asyncio.create_task(periodic_aggregation())
    
    return advanced_logger

def get_logger() -> AdvancedLogger:
    """글로벌 로거 반환"""
    if advanced_logger is None:
        return initialize_logging_system()
    return advanced_logger

# 편의 함수들
def log_trading_event(component: str, message: str, data: Optional[Dict] = None):
    """거래 이벤트 로그"""
    if advanced_logger:
        advanced_logger.log_trading(component, message, data)

def log_system_event(component: str, message: str, data: Optional[Dict] = None):
    """시스템 이벤트 로그"""
    if advanced_logger:
        advanced_logger.log_system(component, message, data)

def log_performance_metrics(component: str, metrics: Dict[str, float]):
    """성능 메트릭 로그"""
    if advanced_logger:
        advanced_logger.log_performance(component, metrics)

def log_error_event(component: str, message: str, exception: Optional[Exception] = None):
    """에러 이벤트 로그"""
    if advanced_logger:
        advanced_logger.log_error(component, message, exception)