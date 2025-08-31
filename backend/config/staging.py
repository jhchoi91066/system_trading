"""
스테이징 환경 설정
프로덕션과 유사하지만 테스트용 설정
"""

import os
from . import AppConfig, DatabaseConfig, RedisConfig, SecurityConfig, TradingConfig, Environment

def get_config() -> AppConfig:
    """스테이징 환경 설정 생성"""
    return AppConfig(
        environment=Environment.STAGING,
        debug=False,
        log_level="INFO",
        host="0.0.0.0",
        port=int(os.getenv('PORT', '8000')),
        
        database=DatabaseConfig(
            host=os.getenv('DB_HOST', 'staging-db.internal'),
            port=int(os.getenv('DB_PORT', '5432')),
            name=os.getenv('DB_NAME', 'trading_bot_staging'),
            username=os.getenv('DB_USER'),
            password=os.getenv('DB_PASSWORD'),
            ssl_mode="require",
            pool_size=10,
            max_overflow=20
        ),
        
        redis=RedisConfig(
            host=os.getenv('REDIS_HOST', 'staging-redis.internal'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD'),
            db=int(os.getenv('REDIS_DB', '0')),
            ssl=True
        ),
        
        security=SecurityConfig(
            jwt_secret=os.getenv('JWT_SECRET'),  # 필수
            encryption_key=os.getenv('ENCRYPTION_KEY'),  # 필수
            webhook_secret=os.getenv('TRADINGVIEW_WEBHOOK_SECRET'),  # 필수
            cors_origins=[
                "https://staging.trading-bot.com",
                "https://staging-dashboard.trading-bot.com"
            ],
            rate_limit_enabled=True,
            ip_whitelist=None  # 스테이징에서는 IP 제한 없음
        ),
        
        trading=TradingConfig(
            demo_mode=True,  # 스테이징에서는 데모 모드 유지
            max_position_size=5000.0,  # 최대 5000 USDT
            default_leverage=3,  # 최대 3배 레버리지
            risk_limit_percent=3.0,  # 3% 리스크 제한
            emergency_stop_enabled=True
        )
    )