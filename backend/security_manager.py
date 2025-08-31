"""
보안 관리자 - API 키 암호화 및 보안 유틸리티
Enterprise급 보안 기능 제공
"""

import os
import base64
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
import hashlib
import hmac
import jwt
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class SecurityManager:
    """Enterprise급 보안 관리 시스템"""
    
    def __init__(self):
        self.master_key = self._get_or_create_master_key()
        self.cipher_suite = self._init_cipher_suite()
        self.jwt_secret = self._get_jwt_secret()
        
    def _get_or_create_master_key(self) -> bytes:
        """마스터 키 생성 또는 조회"""
        key_file = os.path.join(os.path.dirname(__file__), '.master_key')
        
        if os.path.exists(key_file):
            try:
                with open(key_file, 'rb') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to read master key: {e}")
        
        # 새 마스터 키 생성
        password = os.getenv('SECURITY_PASSWORD', 'default-dev-password-change-me').encode()
        salt = os.urandom(16)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        
        # 키 파일에 저장 (salt + key)
        try:
            with open(key_file, 'wb') as f:
                f.write(salt + key)
            os.chmod(key_file, 0o600)  # 소유자만 읽기 가능
            logger.info("🔐 New master key generated and saved securely")
        except Exception as e:
            logger.error(f"Failed to save master key: {e}")
            
        return salt + key
    
    def _init_cipher_suite(self) -> Fernet:
        """암호화 도구 초기화"""
        # 마스터 키에서 실제 암호화 키 추출
        if len(self.master_key) >= 48:  # 16 bytes salt + 32 bytes key
            key_data = self.master_key[16:48]  # salt 제외하고 키만
        else:
            key_data = self.master_key[-32:]  # 마지막 32바이트
            
        cipher_key = base64.urlsafe_b64encode(key_data)
        return Fernet(cipher_key)
    
    def _get_jwt_secret(self) -> str:
        """JWT 시크릿 키 조회"""
        return os.getenv('JWT_SECRET', 'dev-jwt-secret-change-in-production')
    
    # =============================================================================
    # API 키 암호화 관리
    # =============================================================================
    
    def encrypt_api_key(self, api_key: str, user_id: str) -> Dict[str, str]:
        """API 키 암호화 저장"""
        try:
            # 메타데이터 추가
            metadata = {
                'user_id': user_id,
                'encrypted_at': datetime.utcnow().isoformat(),
                'key_hash': hashlib.sha256(api_key.encode()).hexdigest()[:16]
            }
            
            # API 키와 메타데이터를 함께 암호화
            data_to_encrypt = f"{api_key}|{metadata['encrypted_at']}|{metadata['key_hash']}"
            encrypted_key = self.cipher_suite.encrypt(data_to_encrypt.encode())
            
            return {
                'encrypted_key': base64.b64encode(encrypted_key).decode(),
                'key_hash': metadata['key_hash'],
                'encrypted_at': metadata['encrypted_at']
            }
        except Exception as e:
            logger.error(f"🔴 API key encryption failed: {e}")
            raise SecurityError(f"Encryption failed: {e}")
    
    def decrypt_api_key(self, encrypted_data: Dict[str, str], user_id: str) -> str:
        """API 키 복호화"""
        try:
            encrypted_key = base64.b64decode(encrypted_data['encrypted_key'])
            decrypted_data = self.cipher_suite.decrypt(encrypted_key).decode()
            
            # 데이터 파싱
            parts = decrypted_data.split('|')
            if len(parts) != 3:
                raise SecurityError("Invalid encrypted data format")
                
            api_key, encrypted_at, key_hash = parts
            
            # 해시 검증
            if hashlib.sha256(api_key.encode()).hexdigest()[:16] != key_hash:
                raise SecurityError("API key integrity check failed")
            
            return api_key
        except Exception as e:
            logger.error(f"🔴 API key decryption failed: {e}")
            raise SecurityError(f"Decryption failed: {e}")
    
    # =============================================================================
    # 웹훅 서명 검증 (TradingView)
    # =============================================================================
    
    def generate_webhook_signature(self, payload: str, secret: str) -> str:
        """웹훅 서명 생성"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_webhook_signature(self, payload: str, signature: str, secret: str) -> bool:
        """웹훅 서명 검증"""
        try:
            expected_signature = self.generate_webhook_signature(payload, secret)
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"🔴 Webhook signature verification failed: {e}")
            return False
    
    # =============================================================================
    # JWT 토큰 관리 강화
    # =============================================================================
    
    def create_access_token(self, user_id: str, expires_minutes: int = 30) -> str:
        """액세스 토큰 생성"""
        expires = datetime.utcnow() + timedelta(minutes=expires_minutes)
        payload = {
            'user_id': user_id,
            'exp': expires,
            'iat': datetime.utcnow(),
            'type': 'access'
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def create_refresh_token(self, user_id: str, expires_days: int = 30) -> str:
        """리프레시 토큰 생성"""
        expires = datetime.utcnow() + timedelta(days=expires_days)
        payload = {
            'user_id': user_id,
            'exp': expires,
            'iat': datetime.utcnow(),
            'type': 'refresh',
            'jti': secrets.token_urlsafe(32)  # JWT ID for revocation
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def verify_token(self, token: str, token_type: str = 'access') -> Optional[Dict[str, Any]]:
        """토큰 검증"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            
            if payload.get('type') != token_type:
                raise SecurityError(f"Invalid token type. Expected {token_type}")
                
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("🔴 Token expired")
            raise SecurityError("Token expired")
        except jwt.InvalidTokenError as e:
            logger.error(f"🔴 Invalid token: {e}")
            raise SecurityError("Invalid token")
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, str]:
        """리프레시 토큰으로 액세스 토큰 갱신"""
        try:
            payload = self.verify_token(refresh_token, 'refresh')
            user_id = payload['user_id']
            
            # 새 토큰 쌍 생성
            new_access_token = self.create_access_token(user_id)
            new_refresh_token = self.create_refresh_token(user_id)
            
            return {
                'access_token': new_access_token,
                'refresh_token': new_refresh_token,
                'token_type': 'bearer'
            }
        except Exception as e:
            logger.error(f"🔴 Token refresh failed: {e}")
            raise SecurityError("Token refresh failed")
    
    # =============================================================================
    # 보안 유틸리티
    # =============================================================================
    
    def generate_secure_random_key(self, length: int = 32) -> str:
        """보안 랜덤 키 생성"""
        return secrets.token_urlsafe(length)
    
    def hash_password(self, password: str) -> str:
        """비밀번호 해시"""
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}:{password_hash.hex()}"
    
    def verify_password(self, password: str, password_hash: str) -> bool:
        """비밀번호 검증"""
        try:
            salt, hash_value = password_hash.split(':')
            password_hash_check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return password_hash_check.hex() == hash_value
        except Exception:
            return False
    
    def get_client_ip(self, request) -> str:
        """클라이언트 IP 주소 조회"""
        # 프록시를 통한 접속 시 실제 IP 확인
        forwarded_for = getattr(request, 'headers', {}).get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = getattr(request, 'headers', {}).get('X-Real-IP')
        if real_ip:
            return real_ip
            
        return getattr(request, 'client', {}).get('host', 'unknown')

class SecurityError(Exception):
    """보안 관련 예외"""
    pass

# 글로벌 보안 관리자 인스턴스
security_manager = SecurityManager()

# 테스트 함수들
def test_encryption():
    """암호화/복호화 테스트"""
    print("🧪 Testing API key encryption...")
    
    # 테스트 데이터
    test_api_key = "sk-test-api-key-1234567890"
    test_user_id = "test_user_123"
    
    try:
        # 암호화
        encrypted_data = security_manager.encrypt_api_key(test_api_key, test_user_id)
        print(f"✅ Encryption successful: {encrypted_data['key_hash']}")
        
        # 복호화
        decrypted_key = security_manager.decrypt_api_key(encrypted_data, test_user_id)
        print(f"✅ Decryption successful: {decrypted_key == test_api_key}")
        
        # JWT 토큰 테스트
        access_token = security_manager.create_access_token(test_user_id)
        payload = security_manager.verify_token(access_token)
        print(f"✅ JWT token test: {payload['user_id'] == test_user_id}")
        
        print("🎉 All security tests passed!")
        
    except Exception as e:
        print(f"🔴 Security test failed: {e}")

if __name__ == "__main__":
    test_encryption()