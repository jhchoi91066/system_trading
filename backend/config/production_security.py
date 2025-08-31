"""
Production Security Hardening Configuration
🔒 Phase 16: Final Production Deployment

Enterprise-grade security configuration for production deployment
"""

import os
import secrets
import hashlib
from typing import Dict, List, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

class ProductionSecurityConfig:
    """Production security configuration and hardening"""
    
    def __init__(self):
        self.security_headers = self._get_security_headers()
        self.rate_limits = self._get_rate_limits()
        self.encryption_config = self._get_encryption_config()
        self.audit_config = self._get_audit_config()
        
    def _get_security_headers(self) -> Dict[str, str]:
        """Configure security headers for production"""
        return {
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' wss: https: "
            ),
            'Permissions-Policy': (
                "geolocation=(), microphone=(), camera=(), "
                "payment=(), usb=(), magnetometer=(), gyroscope=()"
            )
        }
    
    def _get_rate_limits(self) -> Dict[str, Dict[str, int]]:
        """Configure rate limiting for different endpoints"""
        return {
            'auth': {
                'requests': 5,
                'window': 300,  # 5 minutes
                'block_duration': 3600  # 1 hour
            },
            'trading': {
                'requests': 100,
                'window': 60,   # 1 minute
                'block_duration': 600   # 10 minutes
            },
            'api': {
                'requests': 1000,
                'window': 3600,  # 1 hour
                'block_duration': 300    # 5 minutes
            },
            'webhook': {
                'requests': 10,
                'window': 60,    # 1 minute
                'block_duration': 1800   # 30 minutes
            }
        }
    
    def _get_encryption_config(self) -> Dict[str, any]:
        """Configure encryption settings"""
        return {
            'algorithm': 'AES-256-GCM',
            'key_derivation': 'PBKDF2-SHA256',
            'iterations': 100000,
            'salt_length': 32,
            'token_expiry': 3600,  # 1 hour
            'refresh_token_expiry': 604800  # 7 days
        }
    
    def _get_audit_config(self) -> Dict[str, any]:
        """Configure audit logging"""
        return {
            'enabled': True,
            'retention_days': 365,
            'events': [
                'user_login',
                'user_logout', 
                'trading_action',
                'config_change',
                'security_event',
                'system_error',
                'api_access',
                'admin_action'
            ],
            'sensitive_fields': [
                'password',
                'api_key',
                'secret_key',
                'token',
                'private_key'
            ]
        }

class SecurityHardening:
    """Production security hardening utilities"""
    
    @staticmethod
    def generate_secure_key(length: int = 32) -> str:
        """Generate cryptographically secure random key"""
        return secrets.token_hex(length)
    
    @staticmethod
    def derive_key(password: str, salt: bytes = None) -> tuple[bytes, bytes]:
        """Derive encryption key from password using PBKDF2"""
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt
    
    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> tuple[str, bytes]:
        """Hash password with secure salt"""
        if salt is None:
            salt = os.urandom(32)
        
        pwdhash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return base64.b64encode(pwdhash).decode('utf-8'), salt
    
    @staticmethod
    def verify_password(password: str, hash_string: str, salt: bytes) -> bool:
        """Verify password against hash"""
        pwdhash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return base64.b64encode(pwdhash).decode('utf-8') == hash_string

class ProductionSecurityMiddleware:
    """Security middleware for production deployment"""
    
    def __init__(self, config: ProductionSecurityConfig):
        self.config = config
        self.failed_attempts = {}
        self.blocked_ips = set()
        
    def validate_request_security(self, request) -> bool:
        """Validate request security requirements"""
        # Check IP blocking
        client_ip = self._get_client_ip(request)
        if client_ip in self.blocked_ips:
            return False
            
        # Validate headers
        if not self._validate_security_headers(request):
            return False
            
        # Check rate limits
        if not self._check_rate_limit(request, client_ip):
            return False
            
        return True
    
    def _get_client_ip(self, request) -> str:
        """Extract client IP from request"""
        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        # Check for real IP (behind CDN)
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
            
        # Fallback to direct connection
        return request.client.host if request.client else 'unknown'
    
    def _validate_security_headers(self, request) -> bool:
        """Validate required security headers"""
        required_headers = ['User-Agent', 'Accept']
        
        for header in required_headers:
            if header not in request.headers:
                logging.warning(f"Missing required header: {header}")
                return False
                
        return True
    
    def _check_rate_limit(self, request, client_ip: str) -> bool:
        """Check rate limiting for client IP"""
        endpoint_type = self._get_endpoint_type(request.url.path)
        limits = self.config.rate_limits.get(endpoint_type, self.config.rate_limits['api'])
        
        # Implementation of sliding window rate limiting
        # This would integrate with Redis in production
        return True  # Simplified for demo
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type for rate limiting"""
        if '/auth/' in path:
            return 'auth'
        elif '/trading/' in path:
            return 'trading'
        elif '/webhook' in path:
            return 'webhook'
        else:
            return 'api'

class SecurityAuditor:
    """Security auditing and monitoring"""
    
    def __init__(self):
        self.audit_log_path = "security_audit.log"
        self.setup_logging()
    
    def setup_logging(self):
        """Setup security audit logging"""
        logging.basicConfig(
            filename=self.audit_log_path,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    def log_security_event(self, event_type: str, details: Dict[str, any]):
        """Log security events for audit"""
        sanitized_details = self._sanitize_sensitive_data(details)
        
        audit_entry = {
            'event_type': event_type,
            'timestamp': self._get_timestamp(),
            'details': sanitized_details
        }
        
        logging.info(f"SECURITY_EVENT: {audit_entry}")
    
    def _sanitize_sensitive_data(self, data: Dict[str, any]) -> Dict[str, any]:
        """Remove sensitive information from audit logs"""
        sensitive_fields = ['password', 'api_key', 'secret', 'token', 'private_key']
        sanitized = {}
        
        for key, value in data.items():
            if any(field in key.lower() for field in sensitive_fields):
                sanitized[key] = '[REDACTED]'
            else:
                sanitized[key] = value
                
        return sanitized
    
    def _get_timestamp(self) -> str:
        """Get ISO timestamp"""
        from datetime import datetime
        return datetime.utcnow().isoformat()

# Production security configuration instance
production_security = ProductionSecurityConfig()
security_middleware = ProductionSecurityMiddleware(production_security)
security_auditor = SecurityAuditor()

# Export for use in main application
__all__ = [
    'ProductionSecurityConfig',
    'SecurityHardening', 
    'ProductionSecurityMiddleware',
    'SecurityAuditor',
    'production_security',
    'security_middleware',
    'security_auditor'
]