"""
환경 관리자 - 다중 환경 설정 및 시크릿 관리
Phase 15.1.3: Environment Separation
"""

import os
import logging
from typing import Optional, Dict, Any
from dataclasses import asdict
from dotenv import load_dotenv
from config import load_config, AppConfig, Environment

logger = logging.getLogger(__name__)

class EnvironmentManager:
    """환경별 설정 및 시크릿 관리"""
    
    def __init__(self):
        self.config: Optional[AppConfig] = None
        self._load_environment()
    
    def _load_environment(self):
        """환경변수 및 설정 로드"""
        try:
            # 환경별 .env 파일 로드
            env = os.getenv('ENVIRONMENT', 'development')
            env_file = f'.env.{env}'
            
            if os.path.exists(env_file):
                load_dotenv(env_file, override=True)
                logger.info(f"✅ Loaded environment file: {env_file}")
            else:
                # 기본 .env 파일 로드
                load_dotenv('.env', override=False)
                logger.warning(f"⚠️ Environment file {env_file} not found, using .env")
            
            # 설정 객체 생성
            self.config = load_config()
            logger.info(f"🌍 Environment loaded: {self.config.environment.value}")
            
        except Exception as e:
            logger.error(f"🔴 Failed to load environment: {e}")
            raise
    
    def get_config(self) -> AppConfig:
        """현재 환경 설정 반환"""
        if not self.config:
            self._load_environment()
        return self.config
    
    def is_production(self) -> bool:
        """프로덕션 환경인지 확인"""
        return self.config.environment == Environment.PRODUCTION
    
    def is_development(self) -> bool:
        """개발 환경인지 확인"""
        return self.config.environment == Environment.DEVELOPMENT
    
    def is_staging(self) -> bool:
        """스테이징 환경인지 확인"""
        return self.config.environment == Environment.STAGING
    
    def get_database_url(self) -> str:
        """데이터베이스 연결 URL 생성"""
        db = self.config.database
        return (f"postgresql://{db.username}:{db.password}"
                f"@{db.host}:{db.port}/{db.name}?sslmode={db.ssl_mode}")
    
    def get_redis_url(self) -> str:
        """Redis 연결 URL 생성"""
        redis = self.config.redis
        protocol = "rediss" if redis.ssl else "redis"
        auth = f":{redis.password}@" if redis.password else ""
        return f"{protocol}://{auth}{redis.host}:{redis.port}/{redis.db}"
    
    def validate_required_secrets(self) -> Dict[str, bool]:
        """필수 시크릿 검증"""
        validation_result = {}
        
        # JWT 시크릿 검증
        jwt_secret = self.config.security.jwt_secret
        validation_result['jwt_secret'] = (
            jwt_secret and 
            len(jwt_secret) >= 32 and 
            jwt_secret != 'dev-jwt-secret-change-in-production'
        )
        
        # 암호화 키 검증
        enc_key = self.config.security.encryption_key
        validation_result['encryption_key'] = (
            enc_key and 
            len(enc_key) >= 16 and 
            enc_key != 'dev-encryption-key'
        )
        
        # 웹훅 시크릿 검증
        webhook_secret = self.config.security.webhook_secret
        validation_result['webhook_secret'] = (
            webhook_secret and 
            len(webhook_secret) >= 16 and 
            webhook_secret != 'dev_webhook_secret'
        )
        
        # 프로덕션에서는 더 엄격한 검증
        if self.is_production():
            # API 키 검증
            api_key = os.getenv('BINGX_API_KEY', '')
            secret_key = os.getenv('BINGX_SECRET_KEY', '')
            
            validation_result['bingx_api_key'] = (
                api_key and 
                len(api_key) >= 20 and 
                not api_key.startswith('demo')
            )
            
            validation_result['bingx_secret_key'] = (
                secret_key and 
                len(secret_key) >= 20 and 
                not secret_key.startswith('demo')
            )
        
        return validation_result
    
    def get_security_summary(self) -> Dict[str, Any]:
        """보안 설정 요약 (민감한 정보 제외)"""
        validation = self.validate_required_secrets()
        
        return {
            'environment': self.config.environment.value,
            'security_level': 'high' if self.is_production() else 'medium' if self.is_staging() else 'low',
            'secrets_valid': all(validation.values()),
            'rate_limiting_enabled': self.config.security.rate_limit_enabled,
            'cors_origins_count': len(self.config.security.cors_origins),
            'demo_mode': self.config.trading.demo_mode,
            'database_ssl': self.config.database.ssl_mode != 'disable',
            'redis_ssl': self.config.redis.ssl,
            'validation_details': validation
        }
    
    def get_safe_config_dict(self) -> Dict[str, Any]:
        """민감한 정보를 제거한 설정 딕셔너리"""
        config_dict = asdict(self.config)
        
        # 민감한 정보 마스킹
        security = config_dict['security']
        security['jwt_secret'] = '***' if security['jwt_secret'] else None
        security['encryption_key'] = '***' if security['encryption_key'] else None  
        security['webhook_secret'] = '***' if security['webhook_secret'] else None
        
        database = config_dict['database']
        database['password'] = '***' if database['password'] else None
        
        redis = config_dict['redis']
        redis['password'] = '***' if redis['password'] else None
        
        return config_dict

# 글로벌 환경 관리자 인스턴스
env_manager = EnvironmentManager()

def get_current_config() -> AppConfig:
    """현재 환경 설정 조회"""
    return env_manager.get_config()

# 테스트 함수
def test_environment_setup():
    """환경 설정 테스트"""
    print("🧪 Testing environment setup...")
    
    config = env_manager.get_config()
    print(f"📍 Environment: {config.environment.value}")
    print(f"🗄️ Database: {config.database.host}:{config.database.port}/{config.database.name}")
    print(f"🔥 Redis: {config.redis.host}:{config.redis.port}")
    print(f"🔒 Security Level: {'High' if env_manager.is_production() else 'Medium' if env_manager.is_staging() else 'Low'}")
    
    # 보안 검증
    validation = env_manager.validate_required_secrets()
    print(f"✅ Secrets validation: {validation}")
    
    # 안전한 설정 출력
    safe_config = env_manager.get_safe_config_dict()
    print(f"📋 Config preview: {safe_config['environment']}")

if __name__ == "__main__":
    test_environment_setup()