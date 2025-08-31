"""
환경별 설정 관리 시스템
Development/Staging/Production 환경 분리
"""

import os
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum

class Environment(Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    host: str
    port: int
    name: str
    username: str
    password: str
    ssl_mode: str = "prefer"
    pool_size: int = 10
    max_overflow: int = 20

@dataclass
class RedisConfig:
    """Redis 설정"""
    host: str = "localhost"
    port: int = 6379
    password: str = ""
    db: int = 0
    ssl: bool = False

@dataclass
class SecurityConfig:
    """보안 설정"""
    jwt_secret: str
    encryption_key: str
    webhook_secret: str
    cors_origins: list
    rate_limit_enabled: bool = True
    ip_whitelist: list = None

@dataclass
class TradingConfig:
    """거래 설정"""
    demo_mode: bool
    max_position_size: float
    default_leverage: int
    risk_limit_percent: float
    emergency_stop_enabled: bool = True

@dataclass
class AppConfig:
    """전체 애플리케이션 설정"""
    environment: Environment
    debug: bool
    log_level: str
    host: str
    port: int
    database: DatabaseConfig
    redis: RedisConfig
    security: SecurityConfig
    trading: TradingConfig
    
def get_current_environment() -> Environment:
    """현재 환경 감지"""
    env_name = os.getenv('ENVIRONMENT', 'development').lower()
    try:
        return Environment(env_name)
    except ValueError:
        return Environment.DEVELOPMENT

def load_config() -> AppConfig:
    """환경별 설정 로드"""
    env = get_current_environment()
    
    if env == Environment.PRODUCTION:
        from .production import get_config
    elif env == Environment.STAGING:
        from .staging import get_config
    else:
        from .development import get_config
    
    return get_config()