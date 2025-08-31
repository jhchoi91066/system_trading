#!/usr/bin/env python3
"""
TradingView Webhook 서버
TradingView Pine Script 신호를 받아 자동 거래를 실행하는 Flask 서버
"""

import os
import logging
import asyncio
from datetime import datetime
from flask import Flask, request, jsonify
import json
import hashlib
import hmac
from threading import Thread
import time
from realtime_trading_engine import RealtimeTradingEngine
from hybrid_trading_config import hybrid_signal_manager, SignalSource

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 보안 모듈 import (새로 추가)
try:
    from security_manager import security_manager
    from rate_limiter import webhook_rate_limit, check_blacklist, ip_blacklist
    SECURITY_ENABLED = True
    logger.info("🔐 Enhanced security modules loaded")
except ImportError as e:
    logger.warning(f"⚠️ Security modules not available: {e}")
    SECURITY_ENABLED = False
    # 폴백 데코레이터 정의
    def webhook_rate_limit(func):
        return func
    def check_blacklist(func):
        return func

# Flask 호환 보안 데코레이터
def flask_rate_limit(max_requests=60, window_seconds=60):
    """Flask용 레이트 리미팅 데코레이터"""
    def decorator(func):
        from functools import wraps
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not SECURITY_ENABLED:
                return func(*args, **kwargs)
            
            try:
                from flask import request as flask_request
                # Mock request for rate limiter
                class MockRequest:
                    def __init__(self):
                        self.client = type('client', (), {
                            'host': flask_request.environ.get('REMOTE_ADDR', 'unknown')
                        })()
                        self.headers = dict(flask_request.headers)
                
                mock_request = MockRequest()
                result = rate_limiter.check_rate_limit(mock_request, max_requests, window_seconds)
                
                if not result['allowed']:
                    from flask import jsonify
                    logger.warning(f"🔴 Rate limit exceeded for {mock_request.client.host}")
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'retry_after': result.get('retry_after', 60)
                    }), 429
                    
            except Exception as e:
                logger.error(f"Rate limit check error: {e}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

def flask_blacklist_check(func):
    """Flask용 IP 블랙리스트 체크 데코레이터"""
    from functools import wraps
    @wraps(func) 
    def wrapper(*args, **kwargs):
        if not SECURITY_ENABLED:
            return func(*args, **kwargs)
            
        try:
            from flask import request as flask_request, jsonify
            client_ip = flask_request.environ.get('REMOTE_ADDR', 'unknown')
            
            if ip_blacklist.is_blacklisted(client_ip):
                logger.warning(f"🚫 Blocked request from blacklisted IP: {client_ip}")
                return jsonify({'error': 'IP address is blacklisted'}), 403
                
        except Exception as e:
            logger.error(f"Blacklist check error: {e}")
            
        return func(*args, **kwargs)
    return wrapper

class TradingViewWebhook:
    def __init__(self):
        self.app = Flask(__name__)
        self.engine = None
        self.setup_routes()
        
        # 보안 설정
        self.webhook_secret = os.getenv('TRADINGVIEW_WEBHOOK_SECRET', 'default_secret_change_me')
        # Pine Script 호환: 다양한 심볼 포맷 지원 (Perpetual 계약 포함)
        self.allowed_symbols = [
            'BTC/USDT', 'ETH/USDT', 'BTC-USDT', 'ETH-USDT',
            'BTCUSDT', 'ETHUSDT', 'BTCUSD', 'ETHUSD',
            'BTCUSDT.P', 'ETHUSDT.P', 'BTCUSD.P', 'ETHUSD.P'  # Perpetual 계약
        ]
        
        # 중복 방지를 위한 최근 신호 추적
        self.recent_signals = {}
        self.signal_cooldown = 300  # 5분간 동일 신호 무시
        
    def setup_routes(self):
        """Flask 라우트 설정"""
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """헬스 체크 엔드포인트"""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'service': 'TradingView Webhook Server',
                'security': 'enabled' if SECURITY_ENABLED else 'basic'
            })
        
        @self.app.route('/webhook', methods=['POST'])
        @flask_rate_limit(max_requests=60, window_seconds=60)
        @flask_blacklist_check
        def webhook_handler():
            """TradingView Webhook 메인 핸들러 - 보안 강화"""
            try:
                # 보안 검증 (서명 확인)
                if SECURITY_ENABLED and not self.verify_webhook_signature(request):
                    logger.warning("❌ Webhook signature verification failed")
                    return jsonify({'error': 'Signature verification failed'}), 401
                # 1. 요청 검증
                if not self.verify_request(request):
                    logger.warning("Unauthorized webhook request")
                    return jsonify({'error': 'Unauthorized'}), 401
                
                # 2. 데이터 파싱 (JSON 또는 TradingView 텍스트 형식)
                raw_data = request.get_data(as_text=True)
                logger.info(f"Raw webhook data: {raw_data}")
                logger.info(f"Content-Type: {request.content_type}")
                
                data = None
                
                # Content-Type에 따라 파싱 방법 결정
                if request.content_type and 'application/json' in request.content_type:
                    try:
                        data = request.get_json(force=True)
                    except Exception as e:
                        logger.warning(f"JSON parsing failed: {e}")
                
                # JSON 파싱 실패 또는 text/plain인 경우 텍스트 파싱 시도
                if not data and raw_data:
                    # TradingView alert() 함수에서 오는 텍스트 형식 파싱
                    data = self.parse_tradingview_text(raw_data)
                    
                    # 텍스트 파싱도 실패하면 JSON으로 마지막 시도
                    if not data:
                        try:
                            import json
                            data = json.loads(raw_data)
                        except Exception as json_e:
                            logger.error(f"All parsing methods failed. JSON error: {json_e}")
                
                if not data:
                    logger.error("No valid data found in webhook request")
                    return jsonify({'error': 'Invalid data format'}), 400
                
                # 3. 신호 검증
                if not self.validate_signal(data):
                    return jsonify({'error': 'Invalid signal format'}), 400
                
                # 4. 하이브리드 신호 관리 체크
                signal_data = self.convert_tradingview_signal(data)
                if not signal_data:
                    return jsonify({'error': 'Signal conversion failed'}), 400
                
                if not hybrid_signal_manager.should_process_signal(signal_data, SignalSource.TRADINGVIEW):
                    logger.info(f"Signal rejected by hybrid manager: {data}")
                    return jsonify({'status': 'ignored', 'reason': 'hybrid_filter'})
                
                # 5. 신호 처리 (비동기)
                Thread(target=self.process_signal_sync, args=(data,)).start()
                
                logger.info(f"✅ TradingView signal received: {data}")
                return jsonify({'status': 'received', 'timestamp': datetime.now().isoformat()})
                
            except Exception as e:
                logger.error(f"Webhook handler error: {e}")
                return jsonify({'error': 'Internal server error'}), 500
        
        @self.app.route('/signals', methods=['GET'])
        @flask_blacklist_check
        def get_recent_signals():
            """최근 신호 조회 엔드포인트 - IP 블랙리스트 확인"""
            return jsonify({
                'recent_signals': self.recent_signals,
                'signal_count': len(self.recent_signals)
            })
        
        @self.app.route('/hybrid/status', methods=['GET'])
        def get_hybrid_status():
            """하이브리드 시스템 상태 조회"""
            return jsonify({
                'config': {
                    'internal_cci_enabled': hybrid_signal_manager.config.enable_internal_cci,
                    'tradingview_enabled': hybrid_signal_manager.config.enable_tradingview,
                    'external_cci_enabled': hybrid_signal_manager.config.enable_external_cci,
                    'signal_cooldown': hybrid_signal_manager.config.signal_cooldown,
                    'conflict_resolution': hybrid_signal_manager.config.conflict_resolution,
                    'allowed_symbols': hybrid_signal_manager.config.allowed_symbols
                },
                'stats': hybrid_signal_manager.get_signal_stats(),
                'timestamp': datetime.now().isoformat()
            })
        
        @self.app.route('/security/status', methods=['GET'])
        @flask_blacklist_check
        def get_security_status():
            """보안 시스템 상태 조회"""
            try:
                if not SECURITY_ENABLED:
                    return jsonify({
                        'security_enabled': False,
                        'message': 'Basic security mode',
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Simple rate status without Mock Request (to avoid Flask async issues)  
                rate_status = {
                    'requests_made': 0,
                    'window_seconds': 3600,
                    'last_request': 0
                }
                
                return jsonify({
                    'security_enabled': True,
                    'rate_limiting': {
                        'requests_made': rate_status.get('requests_made', 0),
                        'window_seconds': rate_status.get('window_seconds', 3600), 
                        'last_request': rate_status.get('last_request', 0)
                    },
                    'webhook_secret_set': bool(self.webhook_secret and self.webhook_secret != 'default_secret_change_me'),
                    'allowed_symbols': len(self.allowed_symbols),
                    'signal_cooldown': self.signal_cooldown,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Security status error: {e}")
                return jsonify({
                    'error': 'Failed to get security status',
                    'timestamp': datetime.now().isoformat()
                }), 500
    
    def verify_request(self, request):
        """Webhook 요청 검증 (기본)"""
        try:
            # 1. User-Agent 체크 (선택사항)
            user_agent = request.headers.get('User-Agent', '')
            if 'TradingView' not in user_agent and os.getenv('SKIP_UA_CHECK') != 'true':
                logger.warning(f"Suspicious User-Agent: {user_agent}")
                # return False  # 개발중에는 비활성화
            
            # 2. 보안 토큰 체크 (선택사항)
            auth_header = request.headers.get('Authorization')
            if auth_header:
                if auth_header != f"Bearer {self.webhook_secret}":
                    return False
            elif os.getenv('REQUIRE_AUTH', 'false').lower() == 'true':
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Request verification error: {e}")
            return False
    
    def verify_webhook_signature(self, request):
        """웹훅 서명 검증 (고급 보안)"""
        try:
            if not SECURITY_ENABLED:
                return True  # 보안 모듈 없으면 통과
            
            # 1. 서명 헤더 확인
            signature_header = request.headers.get('X-TradingView-Signature')
            if not signature_header:
                # TradingView에서 서명을 보내지 않는 경우 기본 검증 사용
                return self.verify_request(request)
            
            # 2. 페이로드 가져오기
            payload = request.get_data(as_text=True)
            if not payload:
                logger.error("Empty payload for signature verification")
                return False
            
            # 3. 서명 검증
            is_valid = security_manager.verify_webhook_signature(
                payload=payload,
                signature=signature_header,
                secret=self.webhook_secret
            )
            
            if is_valid:
                logger.info("✅ Webhook signature verified")
                return True
            else:
                logger.warning("🔴 Webhook signature verification failed")
                return False
                
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False
    
    def parse_tradingview_text(self, text_data):
        """TradingView alert() 함수에서 오는 텍스트 형식 파싱"""
        try:
            import re
            
            # 예시: "CCI Crossover Strategy (14, hlc3): 오더 buy @ 20.314617 필드 온 BTCUSDT.P. 뉴 스트래티지 포지션은 10.155799"
            logger.info(f"Parsing TradingView text: {text_data}")
            
            # 액션 패턴 매칭 (buy, sell, long, short 등)
            action_pattern = r'오더\s+(buy|sell|long|short|매수|매도)'
            action_match = re.search(action_pattern, text_data, re.IGNORECASE)
            
            # 심볼 패턴 매칭 (BTCUSDT.P, ETHUSDT 등)
            symbol_pattern = r'(BTC|ETH|XRP|ADA|DOT|LINK|UNI|AVAX|SOL|MATIC)(USDT?\.?P?)'
            symbol_match = re.search(symbol_pattern, text_data)
            
            # 가격 패턴 매칭
            price_pattern = r'@\s*([\d.]+)'
            price_match = re.search(price_pattern, text_data)
            
            if action_match and symbol_match:
                action = action_match.group(1).lower()
                symbol_base = symbol_match.group(1)
                symbol_quote = symbol_match.group(2)
                
                # 액션 정규화
                if action in ['buy', '매수']:
                    action = 'BUY'
                elif action in ['sell', '매도']:
                    action = 'SELL'
                elif action in ['long']:
                    action = 'BUY'
                elif action in ['short']:
                    action = 'SELL'
                
                # 심볼 구성
                if symbol_quote.endswith('.P'):
                    symbol = f"{symbol_base}USDT.P"
                else:
                    symbol = f"{symbol_base}USDT"
                
                # 가격 추출
                price = float(price_match.group(1)) if price_match else 0
                
                parsed_data = {
                    'action': action,
                    'symbol': symbol,
                    'price': price,
                    'source': 'tradingview_text',
                    'raw_message': text_data
                }
                
                logger.info(f"✅ Parsed TradingView text data: {parsed_data}")
                return parsed_data
            
            else:
                logger.warning(f"Failed to parse TradingView text - no action/symbol match: {text_data}")
                return None
                
        except Exception as e:
            logger.error(f"TradingView text parsing error: {e}")
            return None
    
    def validate_signal(self, data):
        """신호 데이터 유효성 검증"""
        try:
            required_fields = ['action', 'symbol']
            
            # 필수 필드 체크
            for field in required_fields:
                if field not in data:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            # 액션 유효성 체크
            valid_actions = ['BUY', 'SELL', 'LONG', 'SHORT', 'CLOSE']
            if data['action'].upper() not in valid_actions:
                logger.error(f"Invalid action: {data['action']}")
                return False
            
            # 심볼 유효성 체크
            symbol = data['symbol'].upper()
            if symbol not in [s.upper() for s in self.allowed_symbols]:
                logger.error(f"Symbol not allowed: {symbol}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Signal validation error: {e}")
            return False
    
    def is_duplicate_signal(self, data):
        """중복 신호 체크"""
        try:
            signal_key = f"{data['symbol']}_{data['action']}"
            current_time = time.time()
            
            if signal_key in self.recent_signals:
                last_signal_time = self.recent_signals[signal_key]['timestamp']
                if current_time - last_signal_time < self.signal_cooldown:
                    return True
            
            # 신호 기록
            self.recent_signals[signal_key] = {
                'timestamp': current_time,
                'data': data,
                'processed_at': datetime.now().isoformat()
            }
            
            return False
            
        except Exception as e:
            logger.error(f"Duplicate check error: {e}")
            return False
    
    def process_signal_sync(self, data):
        """동기 래퍼로 비동기 신호 처리"""
        try:
            # 새 이벤트 루프에서 비동기 함수 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.process_signal(data))
            loop.close()
        except Exception as e:
            logger.error(f"Signal processing sync wrapper error: {e}")
    
    async def process_signal(self, data):
        """TradingView 신호 처리"""
        try:
            logger.info(f"🎯 Processing TradingView signal: {data}")
            
            # 거래 엔진이 초기화되지 않은 경우 초기화
            if not self.engine:
                await self.initialize_engine()
            
            if not self.engine:
                logger.error("Trading engine not available")
                return
            
            # 신호 데이터 변환
            signal_data = self.convert_tradingview_signal(data)
            
            if signal_data:
                # 기존 거래 엔진의 신호 실행 로직 사용
                await self.execute_tradingview_signal(signal_data)
            else:
                logger.error(f"Failed to convert TradingView signal: {data}")
                
        except Exception as e:
            logger.error(f"Signal processing error: {e}")
            import traceback
            traceback.print_exc()
    
    def convert_tradingview_signal(self, data):
        """TradingView 신호를 내부 포맷으로 변환"""
        try:
            action = data['action'].upper()
            symbol = data['symbol'].upper()
            
            # 심볼 포맷 정규화 (다양한 형태 지원, Perpetual 포함)
            if symbol in ['BTCUSDT', 'BTCUSD']:
                symbol = 'BTC-USDT'
            elif symbol in ['ETHUSDT', 'ETHUSD']:
                symbol = 'ETH-USDT'
            elif symbol in ['BTCUSDT.P', 'BTCUSD.P']:
                symbol = 'BTC-USDT'  # Perpetual도 일반 거래로 처리
            elif symbol in ['ETHUSDT.P', 'ETHUSD.P']:
                symbol = 'ETH-USDT'  # Perpetual도 일반 거래로 처리
            elif '/' in symbol:
                symbol = symbol.replace('/', '-')
            # .P 접미사가 있는 Perpetual 계약 처리
            elif symbol.endswith('.P'):
                base_symbol = symbol[:-2]  # .P 제거
                if len(base_symbol) >= 6 and base_symbol.endswith('USDT'):
                    base = base_symbol[:-4]  # USDT 제거
                    symbol = f'{base}-USDT'
            # BTCUSDT 형태 자동 변환
            elif len(symbol) >= 6 and symbol.endswith('USDT'):
                base = symbol[:-4]  # USDT 제거
                symbol = f'{base}-USDT'
            
            # 액션 매핑 (소문자도 지원)
            if action in ['BUY', 'LONG', 'B']:
                signal_type = 'buy'
            elif action in ['SELL', 'SHORT', 'CLOSE', 'S']:
                signal_type = 'sell'
            else:
                return None
            
            # 가격 정보 (있는 경우)
            price = data.get('price', 0)
            if not price:
                price = data.get('close', 0)
            
            return {
                'timestamp': int(datetime.now().timestamp() * 1000),
                'signal': signal_type,
                'price': float(price) if price else 0,
                'symbol': symbol,
                'reason': f'TradingView {action} 신호',
                'source': 'TradingView',
                'raw_data': data
            }
            
        except Exception as e:
            logger.error(f"Signal conversion error: {e}")
            return None
    
    async def execute_tradingview_signal(self, signal_data):
        """변환된 신호 실행"""
        try:
            symbol = signal_data['symbol']
            signal_type = signal_data['signal']
            
            logger.info(f"🚀 Executing TradingView signal: {signal_type} {symbol}")
            
            # 기존 거래 엔진의 신호 실행 메서드 호출
            await self.engine._execute_signal(
                user_id='tradingview_user',
                exchange_name='bingx',
                symbol=symbol.replace('-', '/'),  # BTC/USDT 포맷으로 변환
                signal=signal_data,
                strategy_config={
                    'strategy_type': 'TradingView',
                    'parameters': {},
                    'is_active': True,
                    # 고정 마진 200 USDT 설정
                    'allocated_capital': 200,        # 고정 거래 마진: 200 USDT
                    # 레버리지 기반 TP/SL 설정
                    'take_profit_pct': 10.0,         # 10% 수익률
                    'stop_loss_pct': 5.0,           # 5% 손실률
                    'position_sizing_method': 'fixed_amount'  # 고정 금액 방식
                }
            )
            
            logger.info(f"✅ TradingView signal executed successfully")
            
        except Exception as e:
            logger.error(f"Signal execution error: {e}")
            import traceback
            traceback.print_exc()
    
    async def initialize_engine(self):
        """거래 엔진 초기화"""
        try:
            logger.info("Initializing trading engine for TradingView webhook...")
            
            self.engine = RealtimeTradingEngine()
            
            # BingX 거래소 초기화
            success = await self.engine.initialize_exchange(
                exchange_name='bingx',
                api_key=os.getenv('BINGX_API_KEY', ''),
                secret=os.getenv('BINGX_SECRET_KEY', ''),
                demo_mode=os.getenv('DEMO_MODE', 'true').lower() == 'true'
            )
            
            if success:
                # 엔진 시작
                await self.engine.start_engine()
                logger.info("✅ Trading engine initialized for TradingView webhook")
            else:
                logger.error("❌ Failed to initialize trading engine")
                self.engine = None
                
        except Exception as e:
            logger.error(f"Engine initialization error: {e}")
            self.engine = None
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Flask 서버 실행"""
        logger.info(f"🌐 Starting TradingView Webhook Server on {host}:{port}")
        logger.info(f"🔒 Webhook Secret: {'*' * len(self.webhook_secret)}")
        logger.info(f"📊 Allowed Symbols: {self.allowed_symbols}")
        
        self.app.run(host=host, port=port, debug=debug, threaded=True)

# 메인 실행
if __name__ == '__main__':
    webhook_server = TradingViewWebhook()
    
    # 환경변수에서 설정 읽기
    host = os.getenv('WEBHOOK_HOST', '0.0.0.0')
    port = int(os.getenv('WEBHOOK_PORT', 5001))  # 기본 FastAPI와 구분
    debug = os.getenv('DEBUG', 'false').lower() == 'true'
    
    webhook_server.run(host=host, port=port, debug=debug)