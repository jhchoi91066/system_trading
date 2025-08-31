"""
프로덕션 환경 설정
최고 수준의 보안과 성능 최적화
"""

import os
from . import AppConfig, DatabaseConfig, RedisConfig, SecurityConfig, TradingConfig, Environment

def get_config() -> AppConfig:
    """프로덕션 환경 설정 생성"""
    
    # 필수 환경변수 체크
    required_vars = [
        'DB_HOST', 'DB_PASSWORD', 'JWT_SECRET', 
        'ENCRYPTION_KEY', 'TRADINGVIEW_WEBHOOK_SECRET'
    ]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise EnvironmentError(f"Missing required environment variables: {missing_vars}")
    
    return AppConfig(
        environment=Environment.PRODUCTION,
        debug=False,
        log_level="WARNING",  # 프로덕션에서는 경고 이상만 로그
        host="0.0.0.0",
        port=int(os.getenv('PORT', '8000')),
        
        database=DatabaseConfig(
            host=os.getenv('DB_HOST'),
            port=int(os.getenv('DB_PORT', '5432')),
            name=os.getenv('DB_NAME', 'trading_bot'),
            username=os.getenv('DB_USER', 'trading_user'),
            password=os.getenv('DB_PASSWORD'),
            ssl_mode="require",  # 프로덕션에서는 SSL 필수
            pool_size=20,
            max_overflow=40
        ),
        
        redis=RedisConfig(
            host=os.getenv('REDIS_HOST'),
            port=int(os.getenv('REDIS_PORT', '6379')),
            password=os.getenv('REDIS_PASSWORD'),
            db=int(os.getenv('REDIS_DB', '0')),
            ssl=True  # 프로덕션에서는 SSL 필수
        ),
        
        security=SecurityConfig(
            jwt_secret=os.getenv('JWT_SECRET'),
            encryption_key=os.getenv('ENCRYPTION_KEY'),
            webhook_secret=os.getenv('TRADINGVIEW_WEBHOOK_SECRET'),
            cors_origins=[
                os.getenv('FRONTEND_URL', 'https://trading-bot.com'),
                os.getenv('DASHBOARD_URL', 'https://dashboard.trading-bot.com')
            ],
            rate_limit_enabled=True,
            ip_whitelist=os.getenv('IP_WHITELIST', '').split(',') if os.getenv('IP_WHITELIST') else None
        ),
        
        trading=TradingConfig(
            demo_mode=os.getenv('DEMO_MODE', 'false').lower() == 'true',
            max_position_size=float(os.getenv('MAX_POSITION_SIZE', '10000.0')),
            default_leverage=int(os.getenv('DEFAULT_LEVERAGE', '5')),
            risk_limit_percent=float(os.getenv('RISK_LIMIT_PCT', '5.0')),
            emergency_stop_enabled=True
        )
    )