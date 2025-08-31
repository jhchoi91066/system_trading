"""
개발 환경 설정
로컬 개발용 설정 - 보안이 느슨하고 디버깅 활성화
"""

import os
from . import AppConfig, DatabaseConfig, RedisConfig, SecurityConfig, TradingConfig, Environment

def get_config() -> AppConfig:
    """개발 환경 설정 생성"""
    return AppConfig(
        environment=Environment.DEVELOPMENT,
        debug=True,
        log_level="DEBUG",
        host="0.0.0.0",
        port=int(os.getenv('PORT', '8000')),
        
        database=DatabaseConfig(
            host=os.getenv('DB_HOST', 'localhost'),
            port=int(os.getenv('DB_PORT', '5432')),
            name=os.getenv('DB_NAME', 'trading_bot_dev'),
            username=os.getenv('DB_USER', 'postgres'),
            password=os.getenv('DB_PASSWORD', 'dev_password'),
            ssl_mode="disable",  # 개발환경에서는 SSL 비활성화
            pool_size=5,
            max_overflow=10
        ),
        
        redis=RedisConfig(
            host=os.getenv('REDIS_HOST', 'localhost'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD', ''),
            db=0,
            ssl=False
        ),
        
        security=SecurityConfig(
            jwt_secret=os.getenv('JWT_SECRET', 'dev-jwt-secret-change-in-production'),
            encryption_key=os.getenv('ENCRYPTION_KEY', 'dev-encryption-key'),
            webhook_secret=os.getenv('TRADINGVIEW_WEBHOOK_SECRET', 'dev_webhook_secret'),
            cors_origins=[
                "http://localhost:3000",
                "http://localhost:3001", 
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                "*"  # 개발환경에서는 모든 오리진 허용
            ],
            rate_limit_enabled=True,
            ip_whitelist=None  # 개발환경에서는 IP 제한 없음
        ),
        
        trading=TradingConfig(
            demo_mode=True,  # 개발환경에서는 항상 데모 모드
            max_position_size=1000.0,  # 최대 1000 USDT
            default_leverage=1,  # 개발환경에서는 레버리지 1배
            risk_limit_percent=2.0,  # 2% 리스크 제한
            emergency_stop_enabled=True
        )
    )