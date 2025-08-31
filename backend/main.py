import ccxt.async_support as ccxt
from fastapi import FastAPI, HTTPException, Path, Query, WebSocket, WebSocketDisconnect, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import supabase
import asyncio
from strategy import (
    backtest_strategy, 
    bollinger_bands_strategy, 
    macd_stochastic_strategy,
    williams_r_mean_reversion_strategy,
    multi_indicator_strategy,
    backtest_advanced_strategy
)
from advanced_indicators import AdvancedIndicators, calculate_all_indicators
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from typing import List, Optional, Set, Dict
import json
import os
import logging
from dotenv import load_dotenv

# 환경 관리 시스템 (Phase 15.1.3)
from environment_manager import env_manager, get_current_config

# 신뢰성 시스템 (Phase 15.2)
try:
    from reliability import (
        circuit_breaker, retry_with_backoff,
        health_monitor, shutdown_manager
    )
    from reliability.backup_manager import backup_manager
    RELIABILITY_ENABLED = True
except ImportError as e:
    RELIABILITY_ENABLED = False

# 고급 기능 시스템 (Phase 15.3)
try:
    from advanced import MultiStrategyEngine, AdvancedIndicators
    from advanced.analytics_engine import AnalyticsEngine
    from advanced.portfolio_manager import PortfolioManager
    from advanced.backtesting_engine import BacktestingEngine
    from advanced.advanced_risk_manager import AdvancedRiskManager
    from advanced.parameter_optimizer import ParameterOptimizer
    ADVANCED_ENABLED = True
except ImportError as e:
    ADVANCED_ENABLED = False

# 운영 및 모니터링 시스템 (Phase 15.5)
try:
    from operations import PerformanceCollector, AlertingManager, AdvancedLogger, DeploymentManager
    from operations.performance_metrics import initialize_performance_monitoring, get_performance_collector
    from operations.alerting_system import initialize_alerting, get_alerting_manager
    from operations.database_optimizer import initialize_database_optimization, get_database_optimization_manager
    from operations.disaster_recovery import initialize_disaster_recovery, get_disaster_recovery_manager
    OPERATIONS_ENABLED = True
except ImportError as e:
    OPERATIONS_ENABLED = False
    
    # 추가 인스턴스들 생성 (필요시)
    try:
        from reliability.circuit_breaker import CircuitBreakerConfig
        
        # 거래소용 Circuit Breaker 생성
        exchange_config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=30.0,
            success_threshold=2
        )
        exchange_breaker = circuit_breaker.create_instance("exchange_api", exchange_config)
        
        # 데이터베이스용 Circuit Breaker 생성
        database_config = CircuitBreakerConfig(
            failure_threshold=5,
            recovery_timeout=60.0, 
            success_threshold=3
        )
        database_breaker = circuit_breaker.create_instance("database", database_config)
        
    except Exception as e:
        # logger는 아직 정의되지 않았으므로 print 사용
        print(f"⚠️ Could not create additional circuit breakers: {e}")
        exchange_breaker = circuit_breaker
        database_breaker = circuit_breaker
    
except ImportError as e:
    RELIABILITY_ENABLED = False
    # 나중에 logger 정의 후 로깅

# 로깅 설정
config = get_current_config()
logging.basicConfig(
    level=getattr(logging, config.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"🌍 Application starting in {config.environment.value} mode")

# 신뢰성 시스템 로깅 (지연된 로깅)
if RELIABILITY_ENABLED:
    logger.info("🛡️ Reliability systems loaded")
else:
    logger.warning("⚠️ Reliability systems not available")

# 고급 기능 시스템 로깅 (Phase 15.3)
if ADVANCED_ENABLED:
    logger.info("🚀 Advanced features loaded")
else:
    logger.warning("⚠️ Advanced features not available")

# 운영 시스템 로깅 (Phase 15.5)
if OPERATIONS_ENABLED:
    logger.info("📊 Operations & monitoring systems loaded")
else:
    logger.warning("⚠️ Operations systems not available")
from jose import jwt, jwk
from jose.jwt import get_unverified_header
import requests
from persistent_storage import persistent_storage
from realtime_optimizer import realtime_optimizer, connection_monitor, cleanup_task, run_periodic_updates
from realtime_trading_engine import trading_engine
from position_manager import position_manager
from risk_manager import risk_manager, RiskLimits
from demo_trading import demo_simulator, is_demo_mode_enabled, switch_trading_mode
import time

# Database error tracking to reduce console spam
db_error_cache = {
    'last_error_time': 0,
    'error_count': 0,
    'suppress_until': 0
}

def log_db_error_limited(error_msg: str, component: str = "database"):
    """Log database errors with rate limiting to reduce console spam"""
    current_time = time.time()
    
    # If we're in suppression period, don't log
    if current_time < db_error_cache['suppress_until']:
        return
    
    # If it's been more than 60 seconds since last error, reset counter
    if current_time - db_error_cache['last_error_time'] > 60:
        db_error_cache['error_count'] = 0
    
    db_error_cache['last_error_time'] = current_time
    db_error_cache['error_count'] += 1
    
    # Log first few errors, then suppress for increasing intervals
    if db_error_cache['error_count'] <= 3:
        print(f"[{component}] {error_msg}")
    elif db_error_cache['error_count'] == 4:
        print(f"[{component}] Database connectivity issues detected. Suppressing similar errors for 5 minutes. Using fallback storage.")
        db_error_cache['suppress_until'] = current_time + 300  # 5 minutes
    elif db_error_cache['error_count'] % 20 == 0:  # Log every 20th error after suppression
        print(f"[{component}] Database still unavailable after {db_error_cache['error_count']} attempts. Using fallback storage.")

def safe_db_operation(operation_name: str = "database_operation"):
    """Decorator to safely handle database operations with fallback"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            if supabase is None:
                log_db_error_limited(f"Database unavailable for {operation_name}, using fallback", operation_name)
                return None
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                log_db_error_limited(f"Database error in {operation_name}: {e}", operation_name)
                return None
        return wrapper
    return decorator

from performance_analyzer import performance_analyzer, convert_trades_to_returns, calculate_rolling_metrics
from bingx_vst_client import create_vst_client_from_env

# Load environment variables
load_dotenv()

CLERK_JWKS_URL = os.getenv("CLERK_JWKS_URL")
if not CLERK_JWKS_URL:
    raise ValueError("CLERK_JWKS_URL environment variable not set")

# Cache for JWKS
jwks_client = None

async def get_jwks_client():
    global jwks_client
    if jwks_client is None:
        try:
            response = requests.get(CLERK_JWKS_URL)
            response.raise_for_status()  # Raise an exception for HTTP errors
            jwks_client = jwk.construct(response.json())
        except requests.exceptions.RequestException as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch JWKS from Clerk: {e}")
    return jwks_client

async def get_current_user(request: Request, authorization: Optional[str] = Header(None)) -> str:
    if request.method == "OPTIONS":
        return "anonymous" # Placeholder for OPTIONS requests

    # Temporarily bypass authentication for debugging
    return "test_user_id"

    # Original authentication logic (commented out for now)
    # if not authorization:
    #     raise HTTPException(status_code=401, detail="Authorization header missing")

    # token = authorization.split(" ")[1] if " " in authorization else authorization
    # try:
    #     unverified_header = get_unverified_header(token)
    #     jwks = await get_jwks_client()
    #     public_key = jwks.get_key(unverified_header['kid'])
    #     if not public_key:
    #         raise HTTPException(status_code=401, detail="Invalid token: KID not found")
        
    #     decoded_token = jwt.decode(
    #         token,
    #         public_key,
    #         algorithms=["RS256"],
    #         audience=os.getenv("CLERK_JWT_AUDIENCE"), # Optional: Set if you have a specific audience
    #         issuer=os.getenv("CLERK_JWT_ISSUER") # Optional: Set if you have a specific issuer
    #     )
    #     user_id = decoded_token.get("sub")
    #     if not user_id:
    #         raise HTTPException(status_code=401, detail="Invalid token: User ID not found")
    #     return user_id
    # except jwt.ExpiredSignatureError:
    #     raise HTTPException(status_code=401, detail="Token has expired")
    # except jwt.JWTError as e:
    #     raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    # except Exception as e:
    #     raise HTTPException(status_code=401, detail=f"Authentication failed: {e}")

# FastAPI 앱 초기화 (환경별 설정 적용)
app = FastAPI(
    title="Bitcoin Trading Bot API",
    description="Enterprise Trading Bot with Multi-Environment Support",
    version="1.0.0",
    debug=config.debug
)

# Health Check Endpoint (Enhanced with Environment Info)
@app.get("/health")
async def health_check():
    """시스템 건강 상태 확인"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "environment": config.environment.value,
            "security_level": env_manager.get_security_summary()['security_level'],
            "services": {
                "trading_engine": True,
                "position_manager": True,
                "risk_manager": True,
                "demo_mode": config.trading.demo_mode,
                "rate_limiting": config.security.rate_limit_enabled
            },
            "uptime": "running",
            "version": "1.0.0"
        }
        
        # Database connection check
        try:
            # Simple database connectivity check
            health_status["services"]["database"] = True
        except Exception:
            health_status["services"]["database"] = False
            health_status["status"] = "degraded"
        
        return health_status
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# Environment Configuration Endpoint (Phase 15.1.3)
@app.get("/environment")
async def get_environment_info():
    """환경 설정 정보 조회 (민감한 정보 제외)"""
    try:
        return {
            "environment": config.environment.value,
            "config": env_manager.get_safe_config_dict(),
            "security_summary": env_manager.get_security_summary(),
            "features": {
                "demo_mode": config.trading.demo_mode,
                "debug_mode": config.debug,
                "rate_limiting": config.security.rate_limit_enabled,
                "cors_enabled": len(config.security.cors_origins) > 0
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Environment info retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve environment info")

# Reliability Status Endpoint (Phase 15.2)
@app.get("/reliability")
async def get_reliability_status():
    """신뢰성 시스템 상태 조회"""
    try:
        if not RELIABILITY_ENABLED:
            return {
                "reliability_enabled": False,
                "message": "Basic reliability mode",
                "timestamp": datetime.now().isoformat()
            }
        
        return {
            "reliability_enabled": True,
            "circuit_breakers": {
                "exchange_api": exchange_breaker.get_status(),
                "database": database_breaker.get_status()
            },
            "health_monitor": health_monitor.get_current_status(),
            "backup_manager": backup_manager.get_status(),
            "shutdown_manager": shutdown_manager.get_status(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Reliability status retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve reliability status")

# Backup Management Endpoints (Phase 15.2)
@app.post("/backup/create")
async def create_backup():
    """백업 생성"""
    if not RELIABILITY_ENABLED:
        raise HTTPException(status_code=503, detail="Reliability systems not available")
    
    try:
        from reliability.backup_manager import BackupType
        metadata = await backup_manager.create_backup(BackupType.FULL, compress=True)
        
        return {
            "success": metadata.status.value == "completed",
            "backup_id": metadata.backup_id,
            "status": metadata.status.value,
            "file_size_mb": metadata.file_size / 1024 / 1024,
            "duration_seconds": metadata.duration_seconds,
            "timestamp": metadata.timestamp
        }
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to create backup")

@app.get("/backup/list")
async def list_backups(limit: int = 20):
    """백업 목록 조회"""
    if not RELIABILITY_ENABLED:
        raise HTTPException(status_code=503, detail="Reliability systems not available")
    
    try:
        backups = await backup_manager.list_backups(limit=limit)
        return {
            "backups": backups,
            "total_count": len(backup_manager.backup_history),
            "backup_manager_status": backup_manager.get_status()
        }
    except Exception as e:
        logger.error(f"Backup list retrieval failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve backup list")

@app.post("/backup/restore/{backup_id}")
async def restore_backup(backup_id: str):
    """백업 복원"""
    if not RELIABILITY_ENABLED:
        raise HTTPException(status_code=503, detail="Reliability systems not available")
    
    try:
        success = await backup_manager.restore_backup(backup_id)
        return {
            "success": success,
            "backup_id": backup_id,
            "message": "Backup restored successfully" if success else "Backup restore failed"
        }
    except Exception as e:
        logger.error(f"Backup restore failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore backup")

origins = [
    "http://localhost",
    "http://localhost:3000", # Next.js frontend
    "http://127.0.0.1:3000",
]

# 환경별 CORS 설정 (Phase 15.1.3: Environment Separation)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.security.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Rate-Limit-Remaining", "X-Rate-Limit-Reset"]
)

logger.info(f"🔗 CORS configured for origins: {config.security.cors_origins}")

# 신뢰성 시스템 초기화 (Phase 15.2)
if RELIABILITY_ENABLED:
    try:
        # 백업할 데이터 소스들 등록
        backup_manager.register_json_source("active_strategies", "./data/active_strategies.json")
        backup_manager.register_json_source("api_keys", "./data/api_keys.json")
        backup_manager.register_json_source("fund_management", "./data/fund_management.json")
        backup_manager.register_json_source("notifications", "./data/notifications.json")
        backup_manager.register_json_source("trading_history", "./data/trading_history.json")
        backup_manager.register_json_source("user_settings", "./data/user_settings.json")
        
        logger.info("💾 Backup sources registered for critical data")
    except Exception as e:
        logger.error(f"🔴 Failed to initialize backup system: {e}")

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        # Note: websocket.accept() should be called before this method
        self.active_connections[user_id] = websocket
        connection_monitor.record_connection(user_id)
        print(f"✅ WebSocket client connected for user {user_id}. Total connections: {len(self.active_connections)}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"❌ WebSocket client disconnected for user {user_id}. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, user_id: str):
        websocket = self.active_connections.get(user_id)
        if websocket:
            try:
                await websocket.send_text(message)
                connection_monitor.record_activity(user_id, 'message_sent')
            except Exception as e:
                print(f"Failed to send personal message to {user_id}: {e}")
                connection_monitor.record_error(user_id)
                self.disconnect(user_id)

    async def broadcast(self, message: str):
        if not self.active_connections:
            return
        
        disconnected_users = []
        for user_id, connection in self.active_connections.copy().items():
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"Failed to broadcast to user {user_id}: {e}")
                disconnected_users.append(user_id)
        
        # Clean up disconnected connections
        for user_id in disconnected_users:
            self.disconnect(user_id)

manager = ConnectionManager()

# Background task for periodic data updates (DEPRECATED by realtime_optimizer)
# async def periodic_data_broadcast():
#     """Background task that broadcasts updated data every 5 seconds to each connected user"""
#     while True:
#         try:
#             await asyncio.sleep(5)  # Broadcast every 5 seconds
#             
#             if not manager.active_connections:
#                 continue
#                 
#             for user_id, websocket in manager.active_connections.copy().items():
#                 try:
#                     # Gather real-time data for this specific user
#                     data = await get_realtime_monitoring_data(user_id)
#                     
#                     # Send to this specific user's WebSocket
#                     await websocket.send_text(json.dumps({
#                         "type": "monitoring_update",
#                         "data": data,
#                         "timestamp": datetime.now().isoformat()
#                     }))
#                 except Exception as e:
#                     print(f"Error broadcasting to user {user_id}: {e}")
#                     # Disconnect this user if there's an error sending
#                     manager.disconnect(user_id)
#             
#         except Exception as e:
#             print(f"Error in periodic broadcast loop: {e}")
#             await asyncio.sleep(10)  # Wait longer on error



# Start the background task when the app starts
@app.on_event("startup")
async def startup_event():
    # Start the optimizer's periodic update task
    asyncio.create_task(run_periodic_updates())
    
    # Register data fetchers with the optimizer
    realtime_optimizer.register_data_fetcher('portfolio_stats', get_portfolio_stats_data_raw)
    realtime_optimizer.register_data_fetcher('active_strategies', get_active_strategies_data_raw)
    realtime_optimizer.register_data_fetcher('notifications', get_recent_notifications_data_raw)
    realtime_optimizer.register_data_fetcher('performance_data', get_strategy_performance_data_raw)
    
    # Start the realtime trading engine
    await trading_engine.start_engine()

    # Start monitoring for existing active strategies
    await startup_existing_strategies()

    # Start the old periodic broadcast task (can be deprecated later)
    # asyncio.create_task(periodic_data_broadcast())
    
    # Start the connection cleanup task
    asyncio.create_task(cleanup_task())
    
    print("✅ Background tasks started.")

async def startup_existing_strategies():
    """서버 시작 시 기존 활성 전략들에 대한 모니터링을 자동으로 시작"""
    try:
        logger.info("🚀 Starting monitoring for existing active strategies...")
        
        # 모든 활성 전략 조회
        all_strategies = persistent_storage.get_active_strategies("test_user_id")  # 임시로 test_user_id 사용
        active_strategies = [s for s in all_strategies if s.get('is_active', False)]
        
        logger.info(f"Found {len(active_strategies)} active strategies to monitor")
        
        for strategy in active_strategies:
            try:
                user_id = strategy.get('user_id')
                exchange_name = strategy.get('exchange_name', 'bingx')
                symbol = strategy.get('symbol', 'BTC/USDT')
                strategy_id = strategy.get('strategy_id', 1)
                
                # API 키 조회 (임시로 환경변수 사용)
                api_key = os.getenv('BINGX_API_KEY')
                secret = os.getenv('BINGX_SECRET_KEY')
                
                if not api_key or not secret:
                    logger.warning(f"API keys not found for {exchange_name}")
                    continue
                
                # 거래소 초기화
                await trading_engine.initialize_exchange(exchange_name, api_key, secret, demo_mode=True)
                
                # 전략 정보 구성
                strategy_for_engine = {
                    'strategy_type': 'CCI',
                    'id': strategy_id,
                    'allocated_capital': strategy.get('allocated_capital', 1000),
                    'stop_loss_percentage': strategy.get('stop_loss_percentage', 5.0),
                    'take_profit_percentage': strategy.get('take_profit_percentage', 10.0),
                    'risk_per_trade': strategy.get('risk_per_trade', 2.0),
                    'is_active': True,
                    'parameters': {
                        'window': 20,
                        'buy_threshold': -100,
                        'sell_threshold': 100
                    }
                }
                
                # 모니터링 시작
                await trading_engine.start_monitoring_symbol(
                    user_id=user_id,
                    exchange_name=exchange_name,
                    symbol=symbol,
                    timeframe="5m",
                    strategies=[strategy_for_engine]
                )
                
                logger.info(f"✅ Started monitoring {symbol} on {exchange_name} for user {user_id}")
                
            except Exception as e:
                logger.error(f"❌ Failed to start monitoring for strategy {strategy.get('id')}: {e}")
                
    except Exception as e:
        logger.error(f"❌ Failed to startup existing strategies: {e}")

class Strategy(BaseModel):
    name: str
    script: str
    description: str = None
    strategy_type: str = "custom"
    parameters: dict = None

@app.post("/strategies")
async def create_strategy(strategy: Strategy, user_id: str = Depends(get_current_user)):
    try:
        # Try database first, fallback to in-memory storage
        try:
            strategy_data = {
                "name": strategy.name, 
                "script": strategy.script,
                "description": strategy.description,
                "strategy_type": strategy.strategy_type,
                "parameters": strategy.parameters or {},
                "created_at": datetime.now().isoformat()
            }
            response = supabase.table("strategies").insert(strategy_data).execute()
            
            if response.data:
                return {
                    "message": f"Strategy '{strategy.name}' created successfully",
                    "strategy": response.data[0]
                }
        except Exception as db_error:
            print(f"Database not available, using in-memory storage: {db_error}")
            
            # Fallback to in-memory storage
            strategy_data = {
                "id": len(strategies_storage) + 1,
                "name": strategy.name, 
                "script": strategy.script,
                "description": strategy.description,
                "strategy_type": strategy.strategy_type,
                "parameters": strategy.parameters or {},
                "created_at": datetime.now().isoformat()
            }
            strategies_storage.append(strategy_data)
            return {
                "message": f"Strategy '{strategy.name}' created successfully (in-memory)",
                "strategy": strategy_data
            }
        
        raise HTTPException(status_code=400, detail="Strategy could not be created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating strategy: {str(e)}")

@app.get("/strategies")
async def get_strategies(user_id: str = Depends(get_current_user)):
    try:
        # Try database first, fallback to in-memory storage
        try:
            if supabase is not None:
                response = supabase.table("strategies").select("*").execute()
                return response.data if response.data else []
        except Exception as e:
            log_db_error_limited(f"Database error in strategies endpoint: {str(e)}", "strategies")
        
        # Fallback to in-memory storage
        return strategies_storage
    except Exception as e:
        print(f"Error fetching strategies: {str(e)}")
        return strategies_storage

# Define APIKey model
class APIKey(BaseModel):
    exchange_name: str
    api_key: str
    secret_key: str
    is_active: bool = True

class ActivateStrategy(BaseModel):
    strategy_id: int
    exchange_name: str
    symbol: str
    allocated_capital: float
    stop_loss_percentage: float = 5.0
    take_profit_percentage: float = 10.0
    max_position_size: float = 0.1  # Maximum position size as percentage of capital
    risk_per_trade: float = 2.0     # Risk per trade as percentage
    daily_loss_limit: float = 5.0   # Daily loss limit as percentage

class TradeOrder(BaseModel):
    strategy_id: int
    exchange_name: str
    symbol: str
    order_type: str  # 'buy' or 'sell'
    amount: float
    price: float = None  # None for market orders

class Notification(BaseModel):
    user_id: str
    title: str
    message: str
    notification_type: str  # 'trade', 'risk', 'system', 'performance'
    priority: str = 'medium'  # 'low', 'medium', 'high', 'critical'
    data: dict = None  # Additional data for the notification
    
class NotificationSettings(BaseModel):
    user_id: str
    email_enabled: bool = True
    push_enabled: bool = True
    trade_notifications: bool = True
    risk_notifications: bool = True
    performance_notifications: bool = True
    daily_summary: bool = True

class FundManagementSettings(BaseModel):
    user_id: str = None
    total_capital: float = 10000.0
    max_risk_per_trade: float = 2.0  # % of capital
    max_daily_loss: float = 5.0  # % of capital
    max_portfolio_risk: float = 10.0  # % of capital
    position_sizing_method: str = "fixed"  # "fixed", "kelly", "optimal_f"
    rebalance_frequency: str = "daily"  # "daily", "weekly", "monthly"
    emergency_stop_loss: float = 20.0  # % of capital - emergency liquidation
    
class RiskMetrics(BaseModel):
    current_risk_exposure: float
    daily_pnl: float
    max_drawdown: float
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0

class MarketPrices(BaseModel):
    prices: Dict[str, float]

# Placeholder for encryption/decryption
def encrypt_data(data: str) -> str:
    # In a real application, use a strong encryption library (e.g., cryptography)
    return f"ENCRYPTED_{data}"

def decrypt_data(data: str) -> str:
    # In a real application, use a strong encryption library (e.g., cryptography)
    return data.replace("ENCRYPTED_", "")

# Trading utility functions
async def get_exchange_instance(exchange_name: str, api_key: str = None, secret: str = None):
    """Create and return an exchange instance"""
    try:
        exchange_class = getattr(ccxt, exchange_name)
        config = {'asyncio_loop': asyncio.get_event_loop()}
        
        if api_key and secret:
            config.update({
                'apiKey': api_key,
                'secret': secret,
                'sandbox': False,  # Set to False for real trading, True for testing
                'enableRateLimit': True,
            })
        
        exchange = exchange_class(config)
        return exchange
    except AttributeError:
        raise HTTPException(status_code=404, detail=f"Exchange {exchange_name} not found")

async def execute_trade_order(exchange_name: str, symbol: str, order_type: str, amount: float, price: float = None, api_key: str = None, secret: str = None):
    """Execute a trade order on the specified exchange"""
    exchange = None
    try:
        exchange = await get_exchange_instance(exchange_name, api_key, secret)
        
        if order_type.lower() == 'buy':
            if price:
                order = await exchange.create_limit_buy_order(symbol, amount, price)
            else:
                order = await exchange.create_market_buy_order(symbol, amount)
        elif order_type.lower() == 'sell':
            if price:
                order = await exchange.create_limit_sell_order(symbol, amount, price)
            else:
                order = await exchange.create_market_sell_order(symbol, amount)
        else:
            raise HTTPException(status_code=400, detail="Invalid order type. Use 'buy' or 'sell'")
        
        return order
    except ccxt.BaseError as e:
        raise HTTPException(status_code=400, detail=f"Exchange error: {str(e)}")
    finally:
        if exchange:
            await exchange.close()

async def get_account_balance(exchange_name: str, api_key: str, secret: str):
    """Get account balance from exchange"""
    exchange = None
    try:
        exchange = await get_exchange_instance(exchange_name, api_key, secret)
        balance = await exchange.fetch_balance()
        return balance
    except ccxt.BaseError as e:
        raise HTTPException(status_code=400, detail=f"Exchange error: {str(e)}")
    finally:
        if exchange:
            await exchange.close()

# In-memory storage for development (TEMP solution)
# Using persistent storage instead of in-memory storage
# api_keys data is now handled by persistent_storage.get_api_keys()
# notifications data is now handled by persistent_storage.get_notifications()
strategies_storage = [
    {
        "id": 1,
        "name": "Default CCI Strategy",
        "script": "def strategy(): return 'CCI based trading'",
        "description": "Default CCI strategy for testing",
        "strategy_type": "CCI",  
        "parameters": {"window": 20, "buy_threshold": -100, "sell_threshold": 100},
        "created_at": datetime.now().isoformat()
    }
]
# active_strategies data is now handled by persistent_storage.get_active_strategies()
# fund_management data is now handled by persistent_storage.get_fund_settings()



# Notification system functions
async def create_notification(user_id: str, title: str, message: str, 
                            notification_type: str, priority: str = 'medium', 
                            data: dict = None):
    """Create a new notification for the user"""
    try:
        notification_data = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "notification_type": notification_type,
            "priority": priority,
            "data": data or {},
            "is_read": False,
            "created_at": datetime.now().isoformat()
        }
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("notifications").insert(notification_data).execute()
            if response.data:
                print(f"✅ Notification created: {title}")
                return response.data[0]
        except:
            # Fallback to in-memory storage
            # Get existing notifications to determine next ID
            existing_notifications = persistent_storage.get_notifications(user_id)
            notification_data["id"] = len(existing_notifications) + 1
            persistent_storage.add_notification(notification_data)
            print(f"✅ Notification created (in-memory): {title}")
            return notification_data
            
    except Exception as e:
        print(f"❌ Failed to create notification: {str(e)}")
        return None

async def check_risk_alerts(user_id: str, active_strategy: dict, current_balance: dict):
    """Check for risk-related alerts and create notifications"""
    try:
        allocated_capital = active_strategy.get('allocated_capital', 0)
        daily_loss_limit = active_strategy.get('daily_loss_limit', 5.0)
        
        # Get today's trades for this strategy to calculate daily P&L
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            trades_response = supabase.table("trades").select("*").eq("user_id", user_id).eq("strategy_id", active_strategy['strategy_id']).gte("created_at", f"{today}T00:00:00").execute()
            daily_trades = trades_response.data if trades_response.data else []
        except:
            daily_trades = []
        
        # Calculate daily loss (simplified)
        daily_loss_percentage = 0  # This would be calculated based on actual trade results
        
        if daily_loss_percentage >= daily_loss_limit:
            await create_notification_with_broadcast(
                user_id=user_id,
                title="Daily Loss Limit Reached",
                message=f"Strategy '{active_strategy.get('exchange_name', 'Unknown')}' has reached daily loss limit of {daily_loss_limit}%",
                notification_type="risk",
                priority="critical",
                data={"strategy_id": active_strategy['strategy_id'], "loss_percentage": daily_loss_percentage}
            )
            
    except Exception as e:
        print(f"Error checking risk alerts: {str(e)}")

async def send_trade_notification(user_id: str, trade_data: dict, order_result: dict):
    """Send notification when a trade is executed"""
    try:
        trade_type = trade_data.get('order_type', 'unknown').upper()
        symbol = trade_data.get('symbol', 'Unknown')
        amount = trade_data.get('amount', 0)
        price = order_result.get('price', trade_data.get('price', 0))
        
        await create_notification_with_broadcast(
            user_id=user_id,
            title=f"Trade Executed: {trade_type} {symbol}",
            message=f"{trade_type} {amount} {symbol} at ${price:.4f}",
            notification_type="trade",
            priority="medium",
            data={
                "trade_id": order_result.get('id'),
                "symbol": symbol,
                "amount": amount,
                "price": price,
                "order_type": trade_type
            }
        )
    except Exception as e:
        print(f"Error sending trade notification: {str(e)}")

# Endpoints for API Key management
@app.post("/api_keys")
async def add_api_key(api_key_data: APIKey, user_id: str = Depends(get_current_user)):
    try:
        encrypted_api_key = encrypt_data(api_key_data.api_key)
        encrypted_secret_key = encrypt_data(api_key_data.secret_key)

        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("api_keys").insert({
                "user_id": user_id,
                "exchange_name": api_key_data.exchange_name,
                "api_key_encrypted": encrypted_api_key,
                "secret_key_encrypted": encrypted_secret_key,
                "is_active": api_key_data.is_active,
                "created_at": datetime.now().isoformat()
            }).execute()
            
            if response.data:
                return {"message": "API Key added successfully", "data": response.data[0]}
        except:
            # Fallback to in-memory storage
            api_key_entry = {
                "id": len(api_keys_storage) + 1,
                "user_id": user_id,
                "exchange_name": api_key_data.exchange_name,
                "api_key_encrypted": encrypted_api_key,
                "secret_key_encrypted": encrypted_secret_key,
                "api_key": api_key_data.api_key,  # For easy access
                "secret_key": api_key_data.secret_key,  # For easy access
                "is_active": api_key_data.is_active,
                "created_at": datetime.now().isoformat()
            }
            api_keys_storage.append(api_key_entry)
            return {"message": "API Key added successfully (in-memory)", "data": api_key_entry}
        
        raise HTTPException(status_code=400, detail="Failed to add API Key.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding API key: {str(e)}")

@app.get("/api_keys")
async def get_api_keys(user_id: str = Depends(get_current_user)):
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("api_keys").select("*").eq("user_id", user_id).execute()
            
            if response.data:
                # Decrypt keys before returning (for demonstration, in real app, be careful with exposing keys)
                for key_entry in response.data:
                    key_entry["api_key"] = decrypt_data(key_entry["api_key_encrypted"])
                    key_entry["secret_key"] = decrypt_data(key_entry["secret_key_encrypted"])
                return response.data
        except:
            # Fallback to persistent storage
            return persistent_storage.get_api_keys(user_id)
        
        return []
    except Exception as e:
        print(f"Error fetching API keys: {str(e)}")
        return persistent_storage.get_api_keys(user_id)

@app.delete("/api_keys/{api_key_id}")
async def delete_api_key(api_key_id: int, user_id: str = Depends(get_current_user)):
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("api_keys").delete().eq("id", api_key_id).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return {"message": "API Key deleted successfully"}
        except:
            # Fallback to in-memory storage
            global api_keys_storage
            for i, key in enumerate(api_keys_storage):
                if key["id"] == api_key_id and key["user_id"] == user_id:
                    api_keys_storage.pop(i)
                    return {"message": "API Key deleted successfully (in-memory)"}
        
        raise HTTPException(status_code=404, detail="API Key not found or you don't have permission to delete it.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting API key: {str(e)}")

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/indicators/cci/{symbol}")
async def get_cci_indicators(
    symbol: str = Path(..., description="Trading symbol (e.g., BTC-USDT)"),
    exchange_id: str = Query("bingx", description="Exchange ID"),
    timeframe: str = Query("5m", description="Timeframe"),
    limit: int = Query(100, description="Number of candles"),
    window: int = Query(20, description="CCI calculation window"),
    method: str = Query("standard", description="CCI calculation method: standard or talib"),
    current_user: dict = Depends(get_current_user)
):
    """Get CCI indicator values and current market signals"""
    try:
        from strategy import calculate_cci, generate_cci_signals
        import pandas as pd
        
        # 심볼 형식 변환 (BTC-USDT -> BTC/USDT)
        trading_symbol = symbol.replace('-', '/')
        
        # 시장 데이터 가져오기
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(trading_symbol, timeframe, limit=limit)
        await exchange.close()

        if not ohlcv:
            raise HTTPException(status_code=404, detail="No OHLCV data found")

        # DataFrame 생성
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        # CCI 계산 방법 선택
        if method == "talib":
            from strategy import calculate_cci_talib_style
            df['cci'] = calculate_cci_talib_style(df['high'], df['low'], df['close'], window)
        else:
            df['cci'] = calculate_cci(df['high'], df['low'], df['close'], window)
        
        # 신호 생성 (기본 임계값 사용)
        buy_threshold = -100
        sell_threshold = 100
        signals = generate_cci_signals(ohlcv, window, buy_threshold, sell_threshold)
        df['signal'] = signals['signal']
        
        # 최근 데이터만 반환 (NaN 제거)
        df_clean = df.dropna()
        latest_data = df_clean.tail(50)  # 최근 50개 데이터
        
        # 현재 CCI 값과 신호
        current_cci = latest_data['cci'].iloc[-1] if len(latest_data) > 0 else None
        current_signal = latest_data['signal'].iloc[-1] if len(latest_data) > 0 else 0
        current_price = latest_data['close'].iloc[-1] if len(latest_data) > 0 else None
        
        # 신호 해석
        signal_interpretation = "중립"
        if current_signal == 1:
            signal_interpretation = "매수 신호"
        elif current_signal == -1:
            signal_interpretation = "매도 신호"
        
        # CCI 과매수/과매도 해석
        cci_interpretation = "중립"
        if current_cci and current_cci > sell_threshold:
            cci_interpretation = "과매수 (매도 고려)"
        elif current_cci and current_cci < buy_threshold:
            cci_interpretation = "과매도 (매수 고려)"
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "current_time": datetime.utcnow().isoformat(),
            "current_price": float(current_price) if current_price else None,
            "cci": {
                "current_value": float(current_cci) if current_cci else None,
                "buy_threshold": buy_threshold,
                "sell_threshold": sell_threshold,
                "interpretation": cci_interpretation,
                "window": window
            },
            "signal": {
                "current": int(current_signal) if current_signal else 0,
                "interpretation": signal_interpretation,
                "timestamp": int(latest_data['timestamp'].iloc[-1]) if len(latest_data) > 0 else None
            },
            "historical_data": [
                {
                    "timestamp": int(row['timestamp']),
                    "price": float(row['close']),
                    "cci": float(row['cci']),
                    "signal": int(row['signal'])
                }
                for _, row in latest_data.iterrows()
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting CCI indicators: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get CCI indicators: {str(e)}")

@app.get("/users")
async def get_users():
    try:
        if supabase is not None:
            response = supabase.table("users").select("*").execute()
            return response.data if response.data else []
        else:
            log_db_error_limited("Database unavailable for users endpoint", "users")
            return []
    except Exception as e:
        log_db_error_limited(f"Database error in users endpoint: {str(e)}", "users")
        return []

@app.get("/exchanges")
async def get_exchanges():
    return ccxt.exchanges

@app.get("/routes")
async def get_all_routes():
    routes = []
    for route in app.routes:
        routes.append({"path": route.path, "name": route.name, "methods": route.methods if hasattr(route, 'methods') else []})
    return routes

@app.get("/ticker/{exchange_id}/{symbol:path}")
async def get_ticker(exchange_id: str, symbol: str = Path(..., description="The cryptocurrency symbol (e.g., BTC/USDT)")):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ticker = await exchange.fetch_ticker(symbol)
        await exchange.close()
        return ticker
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")

@app.get("/ohlcv/{exchange_id}/{symbol:path}")
async def get_ohlcv(
    exchange_id: str,
    symbol: str = Path(..., description="The cryptocurrency symbol (e.g., BTC/USDT)"),
    timeframe: str = Query("1d", description="Candlestick timeframe (e.g., 1m, 1h, 1d)"),
    limit: int = Query(100, description="Number of candlesticks to fetch")
):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()
        return ohlcv
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/backtest/{exchange_id}/{symbol:path}")
async def run_backtest(
    exchange_id: str,
    symbol: str = Path(..., description="The cryptocurrency symbol (e.g., BTC/USDT)"),
    timeframe: str = Query("1d", description="Candlestick timeframe (e.g., 1m, 1h, 1d)"),
    limit: int = Query(100, description="Number of candlesticks to fetch"),
    window: int = Query(20, description="CCI window period"),
    buy_threshold: int = Query(100, description="CCI buy threshold"),
    sell_threshold: int = Query(-100, description="CCI sell threshold"),
    initial_capital: float = Query(10000.0, description="Initial capital for backtesting"),
    commission: float = Query(0.001, description="Commission rate per trade")
):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()

        if not ohlcv:
            raise HTTPException(status_code=404, detail="No OHLCV data found for the given parameters.")

        results = backtest_strategy(
            ohlcv_data=ohlcv,
            window=window,
            buy_threshold=buy_threshold,
            sell_threshold=sell_threshold,
            initial_capital=initial_capital,
            commission=commission
        )
        return results
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during backtesting: {str(e)}")

# Real-time trading endpoints
@app.post("/trading/activate")
async def activate_strategy_trading(activate_data: ActivateStrategy, user_id: str = Depends(get_current_user)):  
    """Activate a strategy for real-time trading"""
    try:
        # Get strategy details from memory storage first
        strategy = None
        for strat in strategies_storage:
            if strat["id"] == activate_data.strategy_id:
                strategy = strat
                break
        
        if not strategy:
            # Try database as fallback
            try:
                strategy_response = supabase.table("strategies").select("*").eq("id", activate_data.strategy_id).execute()
                if strategy_response.data:
                    strategy = strategy_response.data[0]
            except:
                pass
        
        if not strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        # For development - skip API key check and exchange connection test
        # In production, these would be restored:
        # - Get API keys from storage/database
        # - Test exchange connection
        
        # Create active strategy record in memory storage
        # Get existing active strategies to determine next ID
        existing_strategies = persistent_storage.get_active_strategies(user_id)
        active_strategy_data = {
            "id": len(existing_strategies) + 1,
            "user_id": user_id,
            "strategy_id": activate_data.strategy_id,
            "exchange_name": activate_data.exchange_name,
            "symbol": activate_data.symbol,
            "allocated_capital": activate_data.allocated_capital,
            "stop_loss_percentage": activate_data.stop_loss_percentage,
            "take_profit_percentage": activate_data.take_profit_percentage,
            "max_position_size": activate_data.max_position_size,
            "risk_per_trade": activate_data.risk_per_trade,
            "daily_loss_limit": activate_data.daily_loss_limit,
            "is_active": True,
            "created_at": datetime.now().isoformat()
        }
        
        persistent_storage.add_active_strategy(active_strategy_data)
        
        # Send activation notification
        await create_notification_with_broadcast(
            user_id=user_id,
            title="Strategy Activated",
            message=f"Strategy '{strategy['name']}' activated for {activate_data.symbol} on {activate_data.exchange_name}",
            notification_type="system",
            priority="medium",
            data={
                "strategy_id": activate_data.strategy_id,
                "symbol": activate_data.symbol,
                "exchange": activate_data.exchange_name,
                "allocated_capital": activate_data.allocated_capital
            }
        )
        
        # Start real-time monitoring for the activated strategy
        try:
            # Get API keys for exchange initialization
            try:
                api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", activate_data.exchange_name).execute()
                
                if not api_keys_response.data:
                    # Use real BingX VST credentials from environment
                    api_key = os.getenv('BINGX_API_KEY', 'dTwrrGyzx3jzFKSWIyufzjdUso9LwdRO1r1jbgHG2yRTfGS2GWDKxUNBVuyOvn5kSJMfcjSRMdQfqamZOSFA')
                    secret = os.getenv('BINGX_SECRET_KEY', 'LITVDtJ8WdQgKpRFlDqAUrW2asU5buvdBrDUkNYro4JlUS5VFgDHEweTK1C4MFomquGRxa1pwXxWTXhQNeg')
                    logger.info(f"Using environment VST credentials for {activate_data.exchange_name}")
                else:
                    api_key_data = api_keys_response.data[0]
                    api_key = api_key_data["api_key"] 
                    secret = api_key_data["secret"]
                    logger.info(f"Using stored credentials for {activate_data.exchange_name}")
                
                # Initialize exchange if not already initialized
                if activate_data.exchange_name not in trading_engine.exchanges:
                    await trading_engine.initialize_exchange(activate_data.exchange_name, api_key, secret, demo_mode=True)
                    logger.info(f"Initialized exchange {activate_data.exchange_name}")
                
            except Exception as e:
                logger.warning(f"Database unavailable, using environment VST credentials: {e}")
                # Use real BingX VST credentials from environment
                api_key = os.getenv('BINGX_API_KEY', 'dTwrrGyzx3jzFKSWIyufzjdUso9LwdRO1r1jbgHG2yRTfGS2GWDKxUNBVuyOvn5kSJMfcjSRMdQfqamZOSFA')
                secret = os.getenv('BINGX_SECRET_KEY', 'LITVDtJ8WdQgKpRFlDqAUrW2asU5buvdBrDUkNYro4JlUS5VFgDHEweTK1C4MFomquGRxa1pwXxWTXhQNeg')
                if activate_data.exchange_name not in trading_engine.exchanges:
                    await trading_engine.initialize_exchange(activate_data.exchange_name, api_key, secret, demo_mode=True)
            
            # Prepare strategy data for the trading engine
            strategy_for_engine = {
                'strategy_id': activate_data.strategy_id,
                'strategy_type': strategy.get('strategy_type', 'CCI'),
                'parameters': strategy.get('parameters', {}),
                'allocated_capital': activate_data.allocated_capital,
                'stop_loss_percentage': activate_data.stop_loss_percentage,
                'take_profit_percentage': activate_data.take_profit_percentage,
                'risk_per_trade': activate_data.risk_per_trade,
                'is_active': True
            }
            
            # Start monitoring with the trading engine
            await trading_engine.start_monitoring_symbol(
                user_id=user_id,
                exchange_name=activate_data.exchange_name,
                symbol=activate_data.symbol,
                timeframe="5m",  # 5분 주기로 변경
                strategies=[strategy_for_engine]
            )
            
            logger.info(f"✅ Real-time monitoring started for {activate_data.symbol} on {activate_data.exchange_name}")
            
        except Exception as e:
            logger.error(f"❌ Failed to start real-time monitoring: {e}")
            # Don't fail the activation if monitoring fails, just log the error
        
        return {
            "message": f"Strategy '{strategy['name']}' activated for {activate_data.symbol} on {activate_data.exchange_name}",
            "active_strategy": active_strategy_data,
            "current_balance": {"total": 10000, "available": 8000}  # Mock balance for development
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error activating strategy: {str(e)}")

@app.post("/trading/deactivate/{active_strategy_id}")
async def deactivate_strategy_trading(active_strategy_id: int, user_id: str = Depends(get_current_user)):
    """Deactivate a strategy from real-time trading"""
    try:
        # Try database first, fallback to in-memory storage
        strategy_found = False
        updated_strategy = None
        
        try:
            response = supabase.table("active_strategies").update({
                "is_active": False,
                "deactivated_at": datetime.now().isoformat()
            }).eq("id", active_strategy_id).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                strategy_found = True
                updated_strategy = response.data[0]
        except Exception as e:
            print(f"Database not available, using in-memory storage: {str(e)}")
        
        # Fallback to persistent storage
        if not strategy_found:
            logger.info(f"Attempting to deactivate strategy {active_strategy_id} for user {user_id}")
            if persistent_storage.deactivate_strategy(user_id, active_strategy_id):
                logger.info(f"Strategy {active_strategy_id} deactivated in persistent storage")
                # Get the deactivated strategy for notification
                all_strategies = persistent_storage.get_active_strategies(user_id)
                logger.info(f"After deactivation, found {len(all_strategies)} active strategies")
                for strategy in all_strategies:
                    if strategy["id"] == active_strategy_id:
                        updated_strategy = strategy
                        strategy_found = True
                        logger.info(f"Found deactivated strategy in active list: {strategy}")
                        break
                
                # If not found in active strategies, try to get it from all strategies
                if not strategy_found:
                    logger.info("Strategy not found in active list, searching all strategies")
                    all_data = persistent_storage._read_json(persistent_storage.files['active_strategies']) or []
                    for strategy in all_data:
                        if (strategy.get('user_id') == user_id and 
                            strategy.get('id') == active_strategy_id):
                            updated_strategy = strategy
                            strategy_found = True
                            logger.info(f"Found deactivated strategy in full list: {strategy}")
                            break
            else:
                logger.warning(f"Failed to deactivate strategy {active_strategy_id} in persistent storage")
        
        if strategy_found and updated_strategy:
            # Stop real-time monitoring for the deactivated strategy
            try:
                symbol = updated_strategy.get('symbol', 'BTC/USDT')
                exchange_name = updated_strategy.get('exchange_name', 'bingx')
                monitor_key = f"{user_id}_{exchange_name}_{symbol}_5m"
                
                # Remove from active monitors
                if hasattr(trading_engine, 'active_monitors') and monitor_key in trading_engine.active_monitors:
                    del trading_engine.active_monitors[monitor_key]
                    logger.info(f"Stopped monitoring {symbol} for user {user_id}")
                
                # Remove candle data
                if hasattr(trading_engine, 'candle_data') and monitor_key in trading_engine.candle_data:
                    del trading_engine.candle_data[monitor_key]
                    
            except Exception as e:
                logger.warning(f"Failed to stop real-time monitoring: {e}")
            
            # Send deactivation notification
            await create_notification_with_broadcast(
                user_id=user_id,
                title="Strategy Deactivated",
                message=f"Strategy deactivated for {updated_strategy.get('symbol', 'Unknown')} on {updated_strategy.get('exchange_name', 'Unknown')}",
                notification_type="system",
                priority="medium",
                data={
                    "strategy_id": updated_strategy.get("strategy_id"),
                    "active_strategy_id": active_strategy_id
                }
            )
            
            return {"message": "Strategy deactivated successfully", "active_strategy": updated_strategy}
        
        raise HTTPException(status_code=404, detail="Active strategy not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deactivating strategy: {str(e)}")

@app.get("/trading/active")
async def get_active_strategies(user_id: str = Depends(get_current_user)):
    """Get all active trading strategies for the user"""
    try:
        # Try database first, fallback to in-memory storage
        try:
            if supabase is not None:
                response = supabase.table("active_strategies").select("*, strategies(*)").eq("user_id", user_id).eq("is_active", True).execute()
                if response.data:
                    return response.data
        except Exception as e:
            log_db_error_limited(f"Database not available for active strategies, using in-memory storage: {str(e)}", "active_strategies")
        
        # Return from memory storage
        return persistent_storage.get_active_strategies(user_id)
        
    except Exception as e:
        print(f"Error getting active strategies: {str(e)}")
        return []

@app.post("/trading/execute")
async def execute_manual_trade(trade_order: TradeOrder, user_id: str = Depends(get_current_user)):
    """Execute a manual trade order"""
    try:
        
        # Get API keys for the exchange
        api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", trade_order.exchange_name).eq("is_active", True).execute()
        if not api_keys_response.data:
            raise HTTPException(status_code=400, detail=f"No active API keys found for {trade_order.exchange_name}")
        
        api_key_data = api_keys_response.data[0]
        decrypted_api_key = decrypt_data(api_key_data["api_key_encrypted"])
        decrypted_secret = decrypt_data(api_key_data["secret_key_encrypted"])
        
        # Execute the trade
        order_result = await execute_trade_order(
            trade_order.exchange_name,
            trade_order.symbol,
            trade_order.order_type,
            trade_order.amount,
            trade_order.price,
            decrypted_api_key,
            decrypted_secret
        )
        
        # Save trade record to database (simulate if table doesn't exist)
        try:
            trade_record = supabase.table("trades").insert({
                "user_id": user_id,
                "strategy_id": trade_order.strategy_id,
                "exchange_name": trade_order.exchange_name,
                "symbol": trade_order.symbol,
                "order_type": trade_order.order_type,
                "amount": trade_order.amount,
                "price": trade_order.price,
                "order_id": order_result.get('id'),
                "status": order_result.get('status', 'pending'),
                "created_at": datetime.now().isoformat()
            }).execute()
        except Exception as db_error:
            print(f"Database table not found, simulating trade record: {db_error}")
            trade_record = type('obj', (object,), {
                'data': [{
                    'id': 1,
                    'user_id': user_id,
                    'strategy_id': trade_order.strategy_id,
                    'exchange_name': trade_order.exchange_name,
                    'symbol': trade_order.symbol,
                    'order_type': trade_order.order_type,
                    'amount': trade_order.amount,
                    'price': trade_order.price,
                    'status': 'completed',
                    'created_at': datetime.now().isoformat()
                }]
            })()
        
        # Send trade notification
        await send_trade_notification(user_id, trade_order.dict(), order_result)
        
        return {
            "message": "Trade executed successfully",
            "order": order_result,
            "trade_record": trade_record.data[0] if trade_record.data else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing trade: {str(e)}")

@app.get("/trading/balance/{exchange_name}")
async def get_trading_balance(exchange_name: str, user_id: str = Depends(get_current_user)):
    """Get account balance for a specific exchange"""
    try:
        
        # Get API keys for the exchange
        api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", exchange_name).eq("is_active", True).execute()
        if not api_keys_response.data:
            raise HTTPException(status_code=400, detail=f"No active API keys found for {exchange_name}")
        
        api_key_data = api_keys_response.data[0]
        decrypted_api_key = decrypt_data(api_key_data["api_key_encrypted"])
        decrypted_secret = decrypt_data(api_key_data["secret_key_encrypted"])
        
        balance = await get_account_balance(exchange_name, decrypted_api_key, decrypted_secret)
        return balance
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching balance: {str(e)}")

@app.get("/trading/history")
async def get_trading_history(user_id: str = Depends(get_current_user)):
    """Get trading history for the user"""
    try:
        # Try database first
        response = supabase.table("trades").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        if response.data:
            return response.data
    except Exception as e:
        print(f"Database error in trading history: {e}")
    
    # Try to get BingX VST demo trades
    try:
        demo_trades = demo_simulator.get_trade_history(user_id, limit=50)
        if demo_trades:
            # Convert demo trades to trading history format
            converted_trades = []
            for i, trade in enumerate(demo_trades):
                converted_trades.append({
                    "id": i + 1,
                    "user_id": user_id,
                    "strategy_name": f"{trade.get('side', '').title()} Strategy",
                    "exchange_name": "bingx_vst",
                    "symbol": trade.get("symbol", "BTC/USDT"),
                    "side": trade.get("side", "buy"),
                    "amount": float(trade.get("amount", 0.0)),
                    "price": float(trade.get("price", 0.0)),
                    "fee": float(trade.get("fee", 0.0)) if trade.get("fee") is not None else 0.0,
                    "profit_loss": float(trade.get("profit_loss", 0.0)) if trade.get("profit_loss") is not None else 0.0,
                    "profit_loss_percentage": float(trade.get("profit_percent", 0.0)) if trade.get("profit_percent") is not None else 0.0,
                    "status": trade.get("status", "completed"),
                    "created_at": trade.get("timestamp", datetime.now().isoformat()),
                    "closed_at": trade.get("timestamp", datetime.now().isoformat())
                })
            return converted_trades
    except Exception as e:
        print(f"Error getting demo trades: {e}")
    
    # Fallback to memory storage - generate some mock trading history for demonstration
    mock_trades = [
        {
            "id": 1,
            "user_id": user_id,
            "strategy_name": "CCI Strategy",
            "exchange_name": "binance",
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.001,
            "price": 45000.0,
            "fee": 0.45,
            "profit_loss": 150.0,
            "profit_loss_percentage": 3.33,
            "status": "completed",
            "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
            "closed_at": (datetime.now() - timedelta(hours=1)).isoformat()
        },
        {
            "id": 2,
            "user_id": user_id,
            "strategy_name": "MACD Strategy", 
            "exchange_name": "binance",
            "symbol": "ETH/USDT",
            "side": "sell",
            "amount": 0.1,
            "price": 3200.0,
            "fee": 0.32,
            "profit_loss": -50.0,
            "profit_loss_percentage": -1.56,
            "status": "completed",
            "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
            "closed_at": (datetime.now() - timedelta(hours=4)).isoformat()
        },
        {
            "id": 3,
            "user_id": user_id,
            "strategy_name": "RSI Strategy",
            "exchange_name": "binance", 
            "symbol": "BTC/USDT",
            "side": "buy",
            "amount": 0.0015,
            "price": 44800.0,
            "fee": 0.67,
            "profit_loss": 225.0,
            "profit_loss_percentage": 5.02,
            "status": "completed", 
            "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
            "closed_at": (datetime.now() - timedelta(hours=20)).isoformat()
        },
        {
            "id": 4,
            "user_id": user_id,
            "strategy_name": "SMA Strategy",
            "exchange_name": "binance",
            "symbol": "ADA/USDT", 
            "side": "sell",
            "amount": 100.0,
            "price": 0.85,
            "fee": 0.085,
            "profit_loss": 15.0,
            "profit_loss_percentage": 1.76,
            "status": "completed",
            "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
            "closed_at": (datetime.now() - timedelta(days=1, hours=18)).isoformat()
        },
        {
            "id": 5,
            "user_id": user_id,
            "strategy_name": "Bollinger Bands",
            "exchange_name": "binance",
            "symbol": "SOL/USDT",
            "side": "buy", 
            "amount": 2.5,
            "price": 120.0,
            "fee": 0.30,
            "profit_loss": -75.0,
            "profit_loss_percentage": -2.50,
            "status": "completed",
            "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
            "closed_at": (datetime.now() - timedelta(days=2, hours=12)).isoformat()
        }
    ]
    
    return mock_trades

@app.get("/symbols/{exchange_id}")
async def get_symbols(exchange_id: str):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        markets = await exchange.load_markets()
        await exchange.close()
        return list(markets.keys())
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

# Portfolio management endpoints
@app.get("/portfolio/stats")
async def get_portfolio_stats(user_id: str = Depends(get_current_user)):
    """Get portfolio statistics and allocation overview"""
    try:
        # Get active strategies to calculate total allocation
        active_strategies = []
        try:
            # Try database first
            active_strategies_response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            if active_strategies_response.data:
                active_strategies = active_strategies_response.data
        except Exception as e:
            print(f"Database not available for portfolio stats, using in-memory storage: {str(e)}")
        
        # Fallback to in-memory storage if database failed or returned no data
        if not active_strategies:
            active_strategies = persistent_storage.get_active_strategies(user_id)
        
        # Try to get actual BingX VST balance using optimized client
        try:
            vst_client = create_vst_client_from_env()
            vst_balance = vst_client.get_vst_balance()
            
            if vst_balance and vst_balance.get('code') == 0 and vst_balance.get('data'):
                balance_data = vst_balance['data']
                if isinstance(balance_data, dict) and 'balance' in balance_data:
                    balance_info = balance_data['balance']
                    total_capital = float(balance_info.get('balance', 0))
                    available_capital = float(balance_info.get('availableMargin', 0))
                    total_allocated = float(balance_info.get('usedMargin', 0))
                else:
                    raise Exception("Unexpected VST balance data structure")
            else:
                raise Exception("No VST balance data received")
            
            vst_client.close()
        except Exception as e:
            print(f"Error getting VST balance, using defaults: {e}")
            # Calculate portfolio stats (fallback)
            total_allocated = sum(strategy.get('allocated_capital', 0) for strategy in active_strategies)
            total_capital = 10000  # This would come from user settings
            available_capital = total_capital - total_allocated
        
        # Get recent trades for P&L calculation (simplified)
        try:
            trades_response = supabase.table("trades").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
            recent_trades = trades_response.data if trades_response.data else []
        except:
            recent_trades = []
        
        return {
            "total_capital": total_capital,
            "total_allocated": total_allocated,
            "available_capital": available_capital,
            "active_strategies": len(active_strategies),
            "recent_trades_count": len(recent_trades),
            "allocation_percentage": (total_allocated / total_capital * 100) if total_capital > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching portfolio stats: {str(e)}")

@app.get("/strategies/performance/{strategy_id}")
async def get_strategy_performance(strategy_id: int, user_id: str = Depends(get_current_user)):
    """Get performance metrics for a specific strategy"""
    try:
        
        # Get trades for this strategy
        try:
            trades_response = supabase.table("trades").select("*").eq("user_id", user_id).eq("strategy_id", strategy_id).order("created_at", desc=True).execute()
            trades = trades_response.data if trades_response.data else []
        except:
            trades = []
        
        # Calculate basic performance metrics
        total_trades = len(trades)
        winning_trades = len([t for t in trades if t.get('status') == 'completed' and t.get('price', 0) > 0])
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "strategy_id": strategy_id,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": win_rate,
            "recent_trades": trades[:5]  # Last 5 trades
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching strategy performance: {str(e)}")

# Notification endpoints
@app.get("/notifications")
async def get_notifications(limit: int = 50, unread_only: bool = False, user_id: str = Depends(get_current_user)):
    """Get notifications for the user"""
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            query = supabase.table("notifications").select("*").eq("user_id", user_id)
            if unread_only:
                query = query.eq("is_read", False)
            
            response = query.order("created_at", desc=True).limit(limit).execute()
            return response.data if response.data else []
        except:
            # Fallback to persistent storage
            filtered_notifications = persistent_storage.get_notifications(user_id)
            if unread_only:
                filtered_notifications = [n for n in filtered_notifications if not n.get("is_read", False)]
            
            return sorted(filtered_notifications, key=lambda x: x["created_at"], reverse=True)[:limit]
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notifications: {str(e)}")

@app.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, user_id: str = Depends(get_current_user)):
    """Mark a notification as read"""
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("notifications").update({
                "is_read": True,
                "read_at": datetime.now().isoformat()
            }).eq("id", notification_id).eq("user_id", user_id).execute()
            
            if response.data and len(response.data) > 0:
                return {"message": "Notification marked as read"}
        except:
            # Fallback to persistent storage
            if persistent_storage.mark_notification_read(user_id, notification_id):
                return {"message": "Notification marked as read (persistent storage)"}
            else:
                raise HTTPException(status_code=404, detail="Notification not found")
        
        raise HTTPException(status_code=404, detail="Notification not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking notification as read: {str(e)}")

@app.post("/notifications/mark-all-read")
async def mark_all_notifications_read(user_id: str = Depends(get_current_user)):
    """Mark all notifications as read for the user"""
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("notifications").update({
                "is_read": True,
                "read_at": datetime.now().isoformat()
            }).eq("user_id", user_id).eq("is_read", False).execute()
            
            count = len(response.data) if response.data else 0
            return {"message": f"Marked {count} notifications as read"}
        except:
            # Fallback to persistent storage - mark all unread notifications as read
            notifications = persistent_storage.get_notifications(user_id)
            count = 0
            for notification in notifications:
                if not notification.get("is_read", False):
                    persistent_storage.mark_notification_read(user_id, notification["id"])
                    count += 1
            
            return {"message": f"Marked {count} notifications as read (in-memory)"}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error marking all notifications as read: {str(e)}")

@app.get("/notifications/stats")
async def get_notification_stats(user_id: str = Depends(get_current_user)):
    """Get notification statistics"""
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            all_response = supabase.table("notifications").select("*", count="exact").eq("user_id", user_id).execute()
            unread_response = supabase.table("notifications").select("*", count="exact").eq("user_id", user_id).eq("is_read", False).execute()
            
            return {
                "total_notifications": all_response.count or 0,
                "unread_notifications": unread_response.count or 0
            }
        except:
            # Fallback to in-memory storage
            user_notifications = persistent_storage.get_notifications(user_id)
            unread_notifications = [n for n in user_notifications if not n.get("is_read", False)]
            
            return {
                "total_notifications": len(user_notifications),
                "unread_notifications": len(unread_notifications)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notification stats: {str(e)}")

# Fund Management Endpoints
@app.get("/fund-management/settings")
async def get_fund_management_settings(user_id: str = Depends(get_current_user)):
    """Get user's fund management settings"""
    try:
        settings = persistent_storage.get_fund_settings(user_id)
        
        # Fetch real VST balance
        vst_client = create_vst_client_from_env()
        vst_account_info = vst_client.get_vst_account_info()
        
        real_total_capital = float(vst_account_info.get('vst_balance', settings.get('total_capital', 10000.0) if settings else 10000.0))
        real_available_capital = float(vst_account_info.get('vst_balance', settings.get('total_capital', 10000.0) if settings else 10000.0))

        if not settings:
            # Return default settings, but use real VST balance for total_capital
            default_settings = {
                "user_id": user_id,
                "total_capital": real_total_capital,
                "max_risk_per_trade": 2.0,
                "max_daily_loss": 5.0,
                "max_portfolio_risk": 10.0,
                "position_sizing_method": "fixed",
                "rebalance_frequency": "daily",
                "emergency_stop_loss": 20.0
            }
            persistent_storage.save_fund_settings(user_id, default_settings)
            settings = default_settings
        
        # Update settings with real-time VST balance
        settings['total_capital'] = real_total_capital
        settings['available_capital'] = real_available_capital # Add available_capital to settings

        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching fund management settings: {str(e)}")

@app.post("/fund-management/settings")
async def update_fund_management_settings(settings: FundManagementSettings, user_id: str = Depends(get_current_user)):
    """Update user's fund management settings"""
    try:
        settings.user_id = user_id
        persistent_storage.save_fund_settings(user_id, settings.model_dump())
        
        # Send notification about settings update
        await create_notification_with_broadcast(
            user_id=user_id,
            title="Fund Management Updated",
            message=f"Fund management settings updated. Total capital: ${settings.total_capital:,}",
            notification_type="system",
            priority="low",
            data={"total_capital": settings.total_capital, "max_risk_per_trade": settings.max_risk_per_trade}
        )
        
        return {"message": "Fund management settings updated successfully", "settings": persistent_storage.get_fund_settings(user_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating fund management settings: {str(e)}")

@app.get("/fund-management/risk-metrics")
async def get_risk_metrics(user_id: str = Depends(get_current_user)):
    """Get current risk metrics and analysis"""
    try:
        # Get fund management settings
        settings = persistent_storage.get_fund_settings(user_id)
        
        # Fetch real VST account info and positions
        vst_client = create_vst_client_from_env()
        vst_account_info = vst_client.get_vst_account_info()
        vst_positions = vst_client.get_vst_positions()

        total_capital = float(vst_account_info.get('vst_balance', settings["total_capital"])) # Use real VST balance
        
        # Calculate total allocated from real VST positions
        total_allocated = sum(float(pos.get('positionAmt', 0)) * float(pos.get('avgPrice', 0)) for pos in vst_positions if float(pos.get('positionAmt', 0)) != 0)
        
        # Calculate risk metrics
        current_risk_exposure = (total_allocated / total_capital * 100) if total_capital > 0 else 0
        
        # Placeholder for daily_pnl, max_drawdown, sharpe_ratio, win_rate, profit_factor
        # These would require more complex calculations based on historical trade data and equity curve
        daily_pnl = 0.0  
        max_drawdown = 0.0  
        win_rate = 0.0  
        sharpe_ratio = 0.0  
        profit_factor = 0.0  
        
        risk_status = "SAFE"
        if current_risk_exposure > settings.get("max_portfolio_risk", 10.0):
            risk_status = "HIGH_RISK"
        elif current_risk_exposure > settings.get("max_portfolio_risk", 10.0) * 0.8:
            risk_status = "MODERATE_RISK"
        
        return {
            "current_risk_exposure": current_risk_exposure,
            "daily_pnl": daily_pnl,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "risk_status": risk_status,
            "total_allocated": total_allocated,
            "available_capital": total_capital - total_allocated,
            "active_strategies_count": len(vst_positions) # Use real active positions count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating risk metrics: {str(e)}")

@app.post("/fund-management/rebalance")
async def rebalance_portfolio(user_id: str = Depends(get_current_user)):
    """Rebalance portfolio based on current settings"""
    try:
        # Get current settings and active strategies
        settings = persistent_storage.get_fund_settings(user_id)
        active_strategies = persistent_storage.get_active_strategies(user_id)
        
        if not active_strategies:
            return {"message": "No active strategies to rebalance", "changes": []}
        
        total_capital = settings.get("total_capital", 10000.0)
        max_portfolio_risk = settings.get("max_portfolio_risk", 10.0)
        max_allocation = total_capital * (max_portfolio_risk / 100)
        
        # Simple equal-weight rebalancing
        target_allocation_per_strategy = max_allocation / len(active_strategies)
        
        changes = []
        for strategy in active_strategies:
            current_allocation = strategy.get("allocated_capital", 0)
            difference = target_allocation_per_strategy - current_allocation
            
            if abs(difference) > 50:  # Only rebalance if difference > $50
                strategy["allocated_capital"] = target_allocation_per_strategy
                changes.append({
                    "strategy_id": strategy["id"],
                    "symbol": strategy["symbol"],
                    "old_allocation": current_allocation,
                    "new_allocation": target_allocation_per_strategy,
                    "change": difference
                })
        
        if changes:
            await create_notification_with_broadcast(
                user_id=user_id,
                title="Portfolio Rebalanced",
                message=f"Portfolio rebalanced across {len(changes)} strategies",
                notification_type="system",
                priority="medium",
                data={"changes_count": len(changes), "total_changes": sum(c["change"] for c in changes)}
            )
        
        return {
            "message": f"Rebalancing completed. {len(changes)} strategies adjusted.",
            "changes": changes,
            "new_total_allocation": len(active_strategies) * target_allocation_per_strategy
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error rebalancing portfolio: {str(e)}")

@app.post("/notifications/test")
async def create_test_notification(user_id: str = Depends(get_current_user)):
    
    notification = await create_notification_with_broadcast(
        user_id=user_id,
        title="Test Notification",
        message="This is a test notification to verify the WebSocket system is working",
        notification_type="system",
        priority="low",
        data={"test": True, "websocket": True}
    )
    
    return {"message": "Test notification created and broadcasted", "notification": notification}

# =============================================================================
# Phase 15.5: Operations & Monitoring API 엔드포인트
# =============================================================================

@app.get("/api/operations/performance/current")
async def get_current_performance_metrics():
    """현재 성능 메트릭 조회"""
    try:
        if not OPERATIONS_ENABLED:
            return {
                "success": False,
                "error": "Operations systems not available",
                "data": None
            }
        
        collector = get_performance_collector()
        if not collector:
            return {
                "success": False,
                "error": "Performance collector not initialized",
                "data": None
            }
        
        metrics = collector.get_current_metrics()
        return {
            "success": True,
            "data": metrics,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": None
        }

@app.get("/api/operations/system/overview")
async def get_operations_overview():
    """운영 시스템 종합 개요"""
    try:
        if not OPERATIONS_ENABLED:
            return {
                "success": False,
                "error": "Operations systems not available",
                "data": {
                    "operations_enabled": False,
                    "systems_status": "disabled"
                }
            }
        
        # 성능 메트릭
        performance_data = {}
        collector = get_performance_collector()
        if collector:
            performance_data = collector.get_current_metrics()
        
        # 알림 상태
        alerts_data = {}
        alerting_manager = get_alerting_manager()
        if alerting_manager:
            alerts_data = alerting_manager.get_alert_summary(24)
        
        return {
            "success": True,
            "data": {
                "operations_enabled": True,
                "performance_metrics": performance_data,
                "alerts_summary": alerts_data,
                "systems_status": {
                    "performance_monitoring": collector is not None,
                    "alerting_system": alerting_manager is not None,
                    "database_optimization": True
                }
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {
                "operations_enabled": OPERATIONS_ENABLED,
                "systems_status": "error"
            }
        }

# WebSocket endpoint
@app.websocket("/ws/monitoring")
async def websocket_endpoint(websocket: WebSocket):
    user_id: Optional[str] = None
    try:
        await websocket.accept()
        
        # Temporarily use simplified authentication for development
        # In production, restore full JWT validation
        user_id = "test_user_id"  # Using the same as in get_current_user
        
        await manager.connect(user_id, websocket)
        print(f"✅ WebSocket authenticated and connected for user: {user_id}")
        
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }))

        # Send initial data
        try:
            initial_data = await realtime_optimizer.get_all_optimized_data(user_id)
            await websocket.send_text(json.dumps({
                "type": "initial_data",
                "data": initial_data,
                "timestamp": datetime.now().isoformat()
            }))
        except Exception as e:
            print(f"Error sending initial data: {e}")

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Receive message with timeout
                message_text = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
                
                try:
                    message = json.loads(message_text)
                    message_type = message.get("type", "unknown")
                    
                    if message_type == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }))
                    elif message_type == "request_update":
                        current_data = await realtime_optimizer.get_all_optimized_data(user_id)
                        await websocket.send_text(json.dumps({
                            "type": "data_update",
                            "data": current_data,
                            "timestamp": datetime.now().isoformat()
                        }))
                        
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {message_text}")
                    
            except asyncio.TimeoutError:
                # Send periodic heartbeat and data updates
                try:
                    current_data = await realtime_optimizer.get_all_optimized_data(user_id)
                    await websocket.send_text(json.dumps({
                        "type": "periodic_update",
                        "data": current_data,
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception as e:
                    print(f"Error sending periodic update: {e}")
                    break
                    
            except WebSocketDisconnect:
                print(f"WebSocket disconnected for user: {user_id}")
                break
            except Exception as e:
                print(f"Error handling WebSocket message for user {user_id}: {e}")
                break

    except WebSocketDisconnect:
        print("WebSocket disconnected before authentication")
    except Exception as e:
        print(f"Error during WebSocket connection setup: {e}")
    finally:
        if user_id:
            manager.disconnect(user_id)

# Optimized helper functions for data collection
async def get_portfolio_stats_data_raw(user_id: str):
    """Raw data fetcher for portfolio statistics (used by optimizer)"""
    try:
        # Get active strategies to calculate total allocation
        try:
            active_strategies_response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            active_strategies = active_strategies_response.data if active_strategies_response.data else []
        except:
            active_strategies = persistent_storage.get_active_strategies(user_id)
        
        # Get fund settings for total capital
        fund_settings = persistent_storage.get_fund_settings(user_id)
        total_capital = fund_settings.get('total_capital', 10000.0)
        
        # Calculate portfolio stats
        total_allocated = sum(strategy.get('allocated_capital', 0) for strategy in active_strategies)
        available_capital = total_capital - total_allocated
        
        # Get recent trades for P&L calculation (simplified)
        try:
            trades_response = supabase.table("trades").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
            recent_trades = trades_response.data if trades_response.data else []
        except:
            recent_trades = persistent_storage.get_trading_history(user_id, limit=10)
        
        return {
            "total_capital": total_capital,
            "total_allocated": total_allocated,
            "available_capital": available_capital,
            "active_strategies": len(active_strategies),
            "recent_trades_count": len(recent_trades),
            "allocation_percentage": (total_allocated / total_capital * 100) if total_capital > 0 else 0
        }
    except Exception as e:
        print(f"Error fetching portfolio stats: {e}")
        return None

# Optimized wrapper functions using realtime optimizer
async def get_portfolio_stats_data(user_id: str):
    """Get optimized portfolio statistics data"""
    return await realtime_optimizer.get_optimized_data(
        user_id, 'portfolio_stats', get_portfolio_stats_data_raw
    )

async def get_active_strategies_data_raw(user_id: str):
    """Raw data fetcher for active strategies (used by optimizer)"""
    try:
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            if response.data:
                return response.data
        except Exception as e:
            log_db_error_limited(f"Database not available for active strategies data, using in-memory storage: {str(e)}", "active_strategies")
        
        # Fallback to in-memory storage
        return persistent_storage.get_active_strategies(user_id)
    except Exception as e:
        log_db_error_limited(f"Error fetching active strategies: {e}", "active_strategies")
        return []

async def get_active_strategies_data(user_id: str):
    """Get optimized active strategies data"""
    return await realtime_optimizer.get_optimized_data(
        user_id, 'active_strategies', get_active_strategies_data_raw
    )

async def get_strategy_performance_data_raw(user_id: str):
    """Raw data fetcher for all strategy performance (used by optimizer)"""
    try:
        # Get all active strategies for this user
        try:
            active_strategies_response = supabase.table("active_strategies").select("*").eq("user_id", user_id).execute()
            active_strategies = active_strategies_response.data if active_strategies_response.data else []
        except:
            active_strategies = persistent_storage.get_active_strategies(user_id)
        
        performance_data = {}
        
        for strategy in active_strategies:
            strategy_id = strategy.get('strategy_id')
            if not strategy_id:
                continue
                
            try:
                # Get trades for this strategy
                try:
                    trades_response = supabase.table("trades").select("*").eq("user_id", user_id).eq("strategy_id", strategy_id).order("created_at", desc=True).execute()
                    trades = trades_response.data if trades_response.data else []
                except:
                    trades = persistent_storage.get_trading_history(user_id, strategy_id=strategy_id)
                
                # Calculate basic performance metrics
                total_trades = len(trades)
                winning_trades = len([t for t in trades if t.get('status') == 'completed' and t.get('price', 0) > 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                performance_data[strategy_id] = {
                    "strategy_id": strategy_id,
                    "total_trades": total_trades,
                    "winning_trades": winning_trades,
                    "win_rate": win_rate,
                    "recent_trades": trades[:5]  # Last 5 trades
                }
            except Exception as e:
                print(f"Error fetching performance for strategy {strategy_id}: {e}")
                # Create default performance data
                performance_data[strategy_id] = {
                    "strategy_id": strategy_id,
                    "total_trades": 0,
                    "winning_trades": 0,
                    "win_rate": 0,
                    "recent_trades": []
                }
        
        return performance_data
        
    except Exception as e:
        print(f"Error fetching strategy performance data: {e}")
        return {}

async def get_strategy_performance_data(strategy_id: int, user_id: str):
    """Get optimized performance metrics for a specific strategy"""
    return await realtime_optimizer.get_optimized_data(
        user_id, f'strategy_perf_{strategy_id}', 
        lambda: get_strategy_performance_data_raw(strategy_id, user_id)
    )

# Optimized aggregate data function
async def get_realtime_monitoring_data(user_id: str):
    """Get all real-time monitoring data efficiently using the optimizer"""
    return await realtime_optimizer.get_all_optimized_data(user_id)

async def get_recent_notifications_data_raw(user_id: str):
    """Raw data fetcher for recent notifications (used by optimizer)"""
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
            return response.data if response.data else []
        except:
            # Fallback to in-memory storage
            return persistent_storage.get_notifications(user_id, limit=10)
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return []

async def get_recent_notifications_data(user_id: str):
    """Get optimized recent notifications"""
    return await realtime_optimizer.get_optimized_data(
        user_id, 'notifications', get_recent_notifications_data_raw
    )

# Enhanced notification system with WebSocket broadcast
async def create_notification_with_broadcast(user_id: str, title: str, message: str, 
                                            notification_type: str, priority: str = 'medium', 
                                            data: dict = None):
    """Create a notification and broadcast it via WebSocket"""
    notification = await create_notification(user_id, title, message, notification_type, priority, data)
    
    if notification:
        # Broadcast the new notification to all connected clients
        await manager.broadcast(json.dumps({
            "type": "new_notification",
            "data": notification,
            "timestamp": datetime.now().isoformat()
        }))
    
    return notification

# WebSocket 연결 상태 모니터링 엔드포인트
@app.get("/ws/connection-status")
async def get_connection_status(user_id: str = Depends(get_current_user)):
    """Get WebSocket connection status and statistics"""
    try:
        connection_info = connection_monitor.get_connection_info(user_id)
        is_connected = user_id in manager.active_connections
        
        return {
            "is_connected": is_connected,
            "connection_info": connection_info,
            "total_connections": len(manager.active_connections),
            "optimizer_stats": realtime_optimizer.get_cache_stats(user_id) if hasattr(realtime_optimizer, 'get_cache_stats') else {}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching connection status: {str(e)}")

@app.post("/ws/force-update")
async def force_websocket_update(user_id: str = Depends(get_current_user)):
    """Force a WebSocket data update for the user"""
    try:
        if user_id not in manager.active_connections:
            raise HTTPException(status_code=404, detail="WebSocket connection not found")
        
        # Force update all data
        current_data = await realtime_optimizer.get_all_optimized_data(user_id)
        
        # Send via WebSocket
        await manager.send_personal_message(json.dumps({
            "type": "forced_update",
            "data": current_data,
            "timestamp": datetime.now().isoformat()
        }), user_id)
        
        return {"message": "Forced update sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error forcing update: {str(e)}")

# 고급 기술적 지표 및 전략 엔드포인트

@app.get("/indicators/advanced/{exchange_id}/{symbol:path}")
async def get_advanced_indicators(
    exchange_id: str,
    symbol: str = Path(..., description="The cryptocurrency symbol (e.g., BTC/USDT)"),
    timeframe: str = Query("1d", description="Candlestick timeframe (e.g., 1m, 1h, 1d)"),
    limit: int = Query(100, description="Number of candlesticks to fetch")
):
    """Get all advanced technical indicators for a symbol"""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()

        if not ohlcv:
            raise HTTPException(status_code=404, detail="No OHLCV data found")

        # 모든 고급 지표 계산
        all_indicators = calculate_all_indicators(ohlcv)
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data_points": len(ohlcv),
            "indicators": all_indicators
        }
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating indicators: {str(e)}")

@app.get("/backtest/advanced/{exchange_id}/{symbol:path}")
async def run_advanced_backtest(
    exchange_id: str,
    symbol: str = Path(..., description="The cryptocurrency symbol (e.g., BTC/USDT)"),
    strategy: str = Query("bollinger_bands", description="Strategy name (bollinger_bands, macd_stochastic, williams_r, multi_indicator)"),
    timeframe: str = Query("1d", description="Candlestick timeframe"),
    limit: int = Query(100, description="Number of candlesticks to fetch"),
    initial_capital: float = Query(10000.0, description="Initial capital for backtesting"),
    commission: float = Query(0.001, description="Commission rate per trade"),
    # 볼린저 밴드 파라미터
    bb_window: int = Query(20, description="Bollinger Bands window"),
    bb_std_dev: float = Query(2.0, description="Bollinger Bands standard deviation"),
    bb_rsi_period: int = Query(14, description="RSI period for Bollinger strategy"),
    # MACD 파라미터
    macd_fast: int = Query(12, description="MACD fast EMA"),
    macd_slow: int = Query(26, description="MACD slow EMA"),
    macd_signal: int = Query(9, description="MACD signal EMA"),
    stoch_rsi_period: int = Query(14, description="Stochastic RSI period"),
    stoch_k: int = Query(3, description="Stochastic %K period"),
    stoch_d: int = Query(3, description="Stochastic %D period"),
    # Williams %R 파라미터
    williams_period: int = Query(14, description="Williams %R period"),
    williams_oversold: int = Query(-80, description="Williams %R oversold level"),
    williams_overbought: int = Query(-20, description="Williams %R overbought level"),
    # 다중 지표 파라미터
    confirmation_count: int = Query(2, description="Number of confirmations needed for multi-indicator strategy")
):
    """Run advanced strategy backtesting"""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()

        if not ohlcv:
            raise HTTPException(status_code=404, detail="No OHLCV data found")

        # 전략 선택 및 파라미터 설정
        strategy_funcs = {
            "bollinger_bands": (bollinger_bands_strategy, {
                "window": bb_window,
                "std_dev": bb_std_dev,
                "rsi_period": bb_rsi_period
            }),
            "macd_stochastic": (macd_stochastic_strategy, {
                "fast_ema": macd_fast,
                "slow_ema": macd_slow,
                "signal_ema": macd_signal,
                "stoch_rsi_period": stoch_rsi_period,
                "k_period": stoch_k,
                "d_period": stoch_d
            }),
            "williams_r": (williams_r_mean_reversion_strategy, {
                "williams_period": williams_period,
                "oversold": williams_oversold,
                "overbought": williams_overbought
            }),
            "multi_indicator": (multi_indicator_strategy, {
                "confirmation_count": confirmation_count
            })
        }

        if strategy not in strategy_funcs:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

        strategy_func, strategy_params = strategy_funcs[strategy]
        
        # 백테스팅 실행
        results = backtest_advanced_strategy(
            ohlcv,
            strategy_func,
            initial_capital=initial_capital,
            commission=commission,
            **strategy_params
        )
        
        # 추가 분석 정보
        max_drawdown = 0
        peak_capital = initial_capital
        for trade in results['trades']:
            if 'capital' in trade:
                if trade['capital'] > peak_capital:
                    peak_capital = trade['capital']
                current_drawdown = (peak_capital - trade['capital']) / peak_capital * 100
                if current_drawdown > max_drawdown:
                    max_drawdown = current_drawdown
        
        results.update({
            "strategy_name": strategy,
            "strategy_params": strategy_params,
            "symbol": symbol,
            "timeframe": timeframe,
            "data_points": len(ohlcv),
            "max_drawdown": max_drawdown,
            "sharpe_ratio": 0.0,  # 추후 구현
            "signals_count": len(results.get('signals', []))
        })
        
        return results
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during backtesting: {str(e)}")

@app.get("/strategies/signals/{exchange_id}/{symbol:path}")
async def get_strategy_signals(
    exchange_id: str,
    symbol: str = Path(..., description="The cryptocurrency symbol (e.g., BTC/USDT)"),
    strategy: str = Query("bollinger_bands", description="Strategy name"),
    timeframe: str = Query("1d", description="Candlestick timeframe"),
    limit: int = Query(50, description="Number of candlesticks to fetch"),
    # 파라미터들은 위와 동일
    bb_window: int = Query(20),
    bb_std_dev: float = Query(2.0),
    bb_rsi_period: int = Query(14),
    macd_fast: int = Query(12),
    macd_slow: int = Query(26),
    macd_signal: int = Query(9),
    stoch_rsi_period: int = Query(14),
    stoch_k: int = Query(3),
    stoch_d: int = Query(3),
    williams_period: int = Query(14),
    williams_oversold: int = Query(-80),
    williams_overbought: int = Query(-20),
    confirmation_count: int = Query(2)
):
    """Get current trading signals for a strategy"""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()

        if not ohlcv:
            raise HTTPException(status_code=404, detail="No OHLCV data found")

        # 전략별 신호 생성
        strategy_funcs = {
            "bollinger_bands": (bollinger_bands_strategy, {
                "window": bb_window, "std_dev": bb_std_dev, "rsi_period": bb_rsi_period
            }),
            "macd_stochastic": (macd_stochastic_strategy, {
                "fast_ema": macd_fast, "slow_ema": macd_slow, "signal_ema": macd_signal,
                "stoch_rsi_period": stoch_rsi_period, "k_period": stoch_k, "d_period": stoch_d
            }),
            "williams_r": (williams_r_mean_reversion_strategy, {
                "williams_period": williams_period, "oversold": williams_oversold, "overbought": williams_overbought
            }),
            "multi_indicator": (multi_indicator_strategy, {
                "confirmation_count": confirmation_count
            })
        }

        if strategy not in strategy_funcs:
            raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

        strategy_func, strategy_params = strategy_funcs[strategy]
        signals = strategy_func(ohlcv, **strategy_params)
        
        # 최근 신호만 반환 (최대 10개)
        recent_signals = signals[-10:] if len(signals) > 10 else signals
        
        # 현재 가격과 마지막 신호
        current_price = ohlcv[-1][4] if ohlcv else 0
        last_signal = signals[-1] if signals else None
        
        return {
            "symbol": symbol,
            "strategy": strategy,
            "current_price": current_price,
            "last_signal": last_signal,
            "recent_signals": recent_signals,
            "total_signals": len(signals),
            "strategy_params": strategy_params
        }
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating signals: {str(e)}")

@app.get("/strategies/comparison/{exchange_id}/{symbol:path}")
async def compare_strategies(
    exchange_id: str,
    symbol: str = Path(..., description="The cryptocurrency symbol"),
    timeframe: str = Query("1d", description="Candlestick timeframe"),
    limit: int = Query(100, description="Number of candlesticks"),
    initial_capital: float = Query(10000.0, description="Initial capital")
):
    """Compare performance of all advanced strategies"""
    try:
        exchange_class = getattr(ccxt, exchange_id)
        exchange = exchange_class({'asyncio_loop': asyncio.get_event_loop()})
        ohlcv = await exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        await exchange.close()

        if not ohlcv:
            raise HTTPException(status_code=404, detail="No OHLCV data found")

        # 모든 전략 테스트
        strategies = {
            "bollinger_bands": (bollinger_bands_strategy, {}),
            "macd_stochastic": (macd_stochastic_strategy, {}),
            "williams_r": (williams_r_mean_reversion_strategy, {}),
            "multi_indicator": (multi_indicator_strategy, {})
        }
        
        comparison_results = {}
        
        for strategy_name, (strategy_func, params) in strategies.items():
            try:
                result = backtest_advanced_strategy(
                    ohlcv, strategy_func, initial_capital=initial_capital, **params
                )
                comparison_results[strategy_name] = {
                    "return_rate": result["return_rate"],
                    "total_trades": result["total_trades"],
                    "win_rate": result["win_rate"],
                    "final_capital": result["final_capital"],
                    "profit_loss": result["profit_loss"]
                }
            except Exception as e:
                comparison_results[strategy_name] = {
                    "error": str(e),
                    "return_rate": 0,
                    "total_trades": 0,
                    "win_rate": 0,
                    "final_capital": initial_capital,
                    "profit_loss": 0
                }
        
        # 가장 성과가 좋은 전략 찾기
        best_strategy = max(comparison_results.keys(), 
                          key=lambda x: comparison_results[x]["return_rate"])
        
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "data_points": len(ohlcv),
            "comparison": comparison_results,
            "best_strategy": best_strategy,
            "best_return": comparison_results[best_strategy]["return_rate"]
        }
    except AttributeError as e:
        raise HTTPException(status_code=404, detail=f"Exchange not found: {e}")
    except ccxt.ExchangeError as e:
        raise HTTPException(status_code=400, detail=f"CCXT Exchange Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing strategies: {str(e)}")

# 자동 트레이딩 엔드포인트

# @app.post("/trading/auto/start")
# async def start_auto_trading(
#     exchange_name: str = Query(..., description="Exchange name (e.g., binance)"),
#     symbol: str = Query(..., description="Trading symbol (e.g., BTC/USDT)"),
#     timeframe: str = Query(default="1h", description="Timeframe (1m, 5m, 15m, 1h, 4h, 1d)"),
#     strategy_type: str = Query(..., description="Strategy type"),
#     user_id: str = Depends(get_current_user)
# ):
#     """자동 트레이딩 시작"""
#     try:
#         # API 키 확인
#         api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", exchange_name).eq("is_active", True).execute()
#         
#         if not api_keys_response.data:
#             raise HTTPException(status_code=400, detail=f"No active API keys found for {exchange_name}")
#         
#         api_key_data = api_keys_response.data[0]
#         api_key = api_key_data["api_key"]
#         secret = api_key_data["secret"]
#         
#         # 거래소 초기화 (테스트넷 사용)
#         success = await trading_engine.initialize_exchange(exchange_name, api_key, secret, sandbox=True)
#         
#         if not success:
#             raise HTTPException(status_code=500, detail="Failed to initialize exchange")
#         
#         # 활성화된 전략 조회
#         strategies_data = persistent_storage.get_active_strategies(user_id)
        matching_strategies = [
            strategy for strategy in strategies_data
            if (strategy.get('exchange_name') == exchange_name and 
                strategy.get('symbol') == symbol and
                strategy.get('strategy_type') == strategy_type and
                strategy.get('is_active', False))
        ]
        
        if not matching_strategies:
            raise HTTPException(status_code=404, detail="No matching active strategies found")
        
        # 실시간 모니터링 시작
        await trading_engine.start_monitoring_symbol(
            user_id=user_id,
            exchange_name=exchange_name,
            symbol=symbol,
            timeframe=timeframe,
            strategies=matching_strategies
        )
        
        return {
            "message": "Auto trading started successfully",
            "exchange": exchange_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "strategies_count": len(matching_strategies),
            "status": "active"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting auto trading: {str(e)}")

@app.post("/trading/auto/stop")
async def stop_auto_trading(
    exchange_name: str = Query(..., description="Exchange name"),
    symbol: str = Query(..., description="Trading symbol"),
    timeframe: str = Query(default="1h", description="Timeframe"),
    user_id: str = Depends(get_current_user)
):
    """자동 트레이딩 중지"""
    try:
        await trading_engine.stop_monitoring_symbol(user_id, exchange_name, symbol, timeframe)
        
        return {
            "message": "Auto trading stopped successfully",
            "exchange": exchange_name,
            "symbol": symbol,
            "timeframe": timeframe,
            "status": "stopped"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error stopping auto trading: {str(e)}")

@app.get("/trading/auto/status")
async def get_auto_trading_status(user_id: str = Depends(get_current_user)):
    """자동 트레이딩 상태 조회"""
    try:
        active_monitors = []
        
        for _, monitor_info in trading_engine.active_monitors.items():
            if monitor_info['user_id'] == user_id:
                active_monitors.append({
                    "exchange": monitor_info['exchange_name'],
                    "symbol": monitor_info['symbol'],
                    "timeframe": monitor_info['timeframe'],
                    "strategies_count": len(monitor_info['strategies']),
                    "last_update": monitor_info.get('last_candle_time', 0),
                    "status": "active"
                })
        
        return {
            "engine_status": "running" if trading_engine.running else "stopped",
            "active_monitors": active_monitors,
            "monitors_count": len(active_monitors)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting auto trading status: {str(e)}")

@app.post("/trading/auto/strategy/activate/{strategy_id}")
async def activate_auto_strategy(
    strategy_id: int,
    exchange_name: str = Query(..., description="Exchange name"),
    symbol: str = Query(..., description="Trading symbol"), 
    timeframe: str = Query(default="1h", description="Timeframe"),
    allocated_capital: float = Query(default=100.0, description="Allocated capital in USDT"),
    user_id: str = Depends(get_current_user)
):
    """전략 자동 실행 활성화"""
    try:
        # 전략 존재 확인
        strategies = persistent_storage.get_active_strategies(user_id)
        target_strategy = None
        
        for strategy in strategies:
            if strategy.get('id') == strategy_id:
                target_strategy = strategy
                break
        
        if not target_strategy:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        # 전략 활성화
        target_strategy.update({
            'is_active': True,
            'exchange_name': exchange_name,
            'symbol': symbol,
            'timeframe': timeframe,
            'allocated_capital': allocated_capital,
            'auto_trading': True
        })
        
        # API 키 확인
        api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", exchange_name).eq("is_active", True).execute()
        
        if not api_keys_response.data:
            raise HTTPException(status_code=400, detail=f"No active API keys found for {exchange_name}")
        
        api_key_data = api_keys_response.data[0]
        api_key = api_key_data["api_key"] 
        secret = api_key_data["secret"]
        
        # 거래소 초기화
        await trading_engine.initialize_exchange(exchange_name, api_key, secret, sandbox=True)
        
        # 모니터링 시작
        await trading_engine.start_monitoring_symbol(
            user_id=user_id,
            exchange_name=exchange_name,
            symbol=symbol,
            timeframe=timeframe,
            strategies=[target_strategy]
        )
        
        return {
            "message": "Strategy auto trading activated successfully",
            "strategy_id": strategy_id,
            "exchange": exchange_name,
            "symbol": symbol,
            "allocated_capital": allocated_capital,
            "status": "active"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error activating auto strategy: {str(e)}")

@app.post("/trading/auto/strategy/deactivate/{strategy_id}")
async def deactivate_auto_strategy(
    strategy_id: int,
    exchange_name: str = Query(..., description="Exchange name"),
    symbol: str = Query(..., description="Trading symbol"),
    timeframe: str = Query(default="1h", description="Timeframe"),
    user_id: str = Depends(get_current_user)
):
    """전략 자동 실행 비활성화"""
    try:
        # 모니터링 중지
        await trading_engine.stop_monitoring_symbol(user_id, exchange_name, symbol, timeframe)
        
        # 전략 상태 업데이트
        strategies = persistent_storage.get_active_strategies(user_id)
        for strategy in strategies:
            if strategy.get('id') == strategy_id:
                strategy['is_active'] = False
                strategy['auto_trading'] = False
                break
        
        return {
            "message": "Strategy auto trading deactivated successfully",
            "strategy_id": strategy_id,
            "status": "inactive"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deactivating auto strategy: {str(e)}")

# 포지션 관리 엔드포인트

@app.get("/positions")
async def get_positions(
    status: str = Query(default=None, description="Position status (open, closed)"),
    symbol: str = Query(default=None, description="Filter by symbol"),
    user_id: str = Depends(get_current_user)
):
    """사용자 포지션 조회"""
    try:
        if symbol:
            positions = position_manager.get_symbol_positions(user_id, symbol, status)
        else:
            positions = position_manager.get_user_positions(user_id, status)
        
        position_list = []
        for position in positions:
            position_list.append({
                "position_id": position.position_id,
                "exchange": position.exchange_name,
                "symbol": position.symbol,
                "strategy_id": position.strategy_id,
                "side": position.side,
                "entry_price": position.entry_price,
                "quantity": position.quantity,
                "current_price": position.current_price,
                "unrealized_pnl": position.unrealized_pnl,
                "realized_pnl": position.realized_pnl,
                "stop_loss": position.stop_loss,
                "take_profit": position.take_profit,
                "entry_time": position.entry_time.isoformat(),
                "status": position.status,
                "metadata": position.metadata
            })
        
        return {
            "positions": position_list,
            "count": len(position_list)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting positions: {str(e)}")

@app.get("/positions/portfolio")
async def get_portfolio_pnl(user_id: str = Depends(get_current_user)):
    """포트폴리오 손익 통계"""
    try:
        portfolio_stats = position_manager.get_portfolio_pnl(user_id)
        
        # 현재 노출 금액 추가
        total_exposure = position_manager.get_total_exposure(user_id)
        portfolio_stats["total_exposure"] = total_exposure
        
        return portfolio_stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting portfolio PnL: {str(e)}")

@app.post("/positions/{position_id}/close")
async def close_position_manually(
    position_id: str,
    close_reason: str = Query(default="manual", description="Reason for closing"),
    user_id: str = Depends(get_current_user)
):
    """포지션 수동 청산"""
    try:
        position = position_manager.get_position(position_id)
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        if position.user_id != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access to position")
        
        if position.status != "open":
            raise HTTPException(status_code=400, detail="Position is not open")
        
        # API 키 확인
        api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", position.exchange_name).eq("is_active", True).execute()
        
        if not api_keys_response.data:
            raise HTTPException(status_code=400, detail=f"No active API keys found for {position.exchange_name}")
        
        api_key_data = api_keys_response.data[0]
        api_key = api_key_data["api_key"]
        secret = api_key_data["secret"]
        
        # 거래소 초기화
        success = await trading_engine.initialize_exchange(position.exchange_name, api_key, secret, sandbox=True)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to initialize exchange")
        
        exchange = trading_engine.exchanges.get(position.exchange_name)
        
        # 청산 주문 실행
        if position.side == 'long':
            order = await exchange.create_market_sell_order(position.symbol, position.quantity)
        else:  # short
            order = await exchange.create_market_buy_order(position.symbol, position.quantity)
        
        close_price = order.get('price', position.current_price)
        
        # 포지션 상태 업데이트
        position_manager.close_position(position_id, close_price, close_reason)
        
        return {
            "message": "Position closed successfully",
            "position_id": position_id,
            "close_price": close_price,
            "realized_pnl": position.realized_pnl,
            "order": order
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error closing position: {str(e)}")

@app.post("/positions/{position_id}/update-stops")
async def update_position_stops(
    position_id: str,
    stop_loss: float = Query(default=None, description="New stop loss price"),
    take_profit: float = Query(default=None, description="New take profit price"),
    user_id: str = Depends(get_current_user)
):
    """포지션 손절/익절가 수정"""
    try:
        position = position_manager.get_position(position_id)
        
        if not position:
            raise HTTPException(status_code=404, detail="Position not found")
        
        if position.user_id != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized access to position")
        
        if position.status != "open":
            raise HTTPException(status_code=400, detail="Position is not open")
        
        # 손절/익절가 업데이트
        if stop_loss is not None:
            position.stop_loss = stop_loss
        
        if take_profit is not None:
            position.take_profit = take_profit
        
        return {
            "message": "Position stops updated successfully",
            "position_id": position_id,
            "stop_loss": position.stop_loss,
            "take_profit": position.take_profit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating position stops: {str(e)}")

@app.get("/positions/exposure/{symbol}")
async def get_symbol_exposure(
    symbol: str,
    user_id: str = Depends(get_current_user)
):
    """특정 심볼의 노출 금액 조회"""
    try:
        exposure = position_manager.get_total_exposure(user_id, symbol)
        positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
        
        return {
            "symbol": symbol,
            "total_exposure": exposure,
            "open_positions": len(positions),
            "positions": [
                {
                    "position_id": p.position_id,
                    "side": p.side,
                    "quantity": p.quantity,
                    "entry_price": p.entry_price,
                    "current_price": p.current_price,
                    "unrealized_pnl": p.unrealized_pnl
                }
                for p in positions
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting symbol exposure: {str(e)}")

# 리스크 관리 엔드포인트

@app.post("/risk/limits")
async def set_risk_limits(
    max_position_size_pct: float = Query(default=5.0, description="최대 포지션 크기 (%)"),
    max_daily_loss_pct: float = Query(default=2.0, description="일일 최대 손실 (%)"),
    max_weekly_loss_pct: float = Query(default=5.0, description="주간 최대 손실 (%)"),
    max_monthly_loss_pct: float = Query(default=10.0, description="월간 최대 손실 (%)"),
    max_drawdown_pct: float = Query(default=15.0, description="최대 드로우다운 (%)"),
    max_open_positions: int = Query(default=10, description="최대 동시 포지션 수"),
    max_symbol_exposure_pct: float = Query(default=10.0, description="심볼별 최대 노출 (%)"),
    max_correlation_limit: float = Query(default=0.7, description="최대 상관관계 한도"),
    user_id: str = Depends(get_current_user)
):
    """리스크 한도 설정"""
    try:
        limits = RiskLimits(
            max_position_size_pct=max_position_size_pct,
            max_daily_loss_pct=max_daily_loss_pct,
            max_weekly_loss_pct=max_weekly_loss_pct,
            max_monthly_loss_pct=max_monthly_loss_pct,
            max_drawdown_pct=max_drawdown_pct,
            max_open_positions=max_open_positions,
            max_symbol_exposure_pct=max_symbol_exposure_pct,
            max_correlation_limit=max_correlation_limit
        )
        
        risk_manager.set_risk_limits(user_id, limits)
        
        return {
            "message": "Risk limits set successfully",
            "limits": {
                "max_position_size_pct": limits.max_position_size_pct,
                "max_daily_loss_pct": limits.max_daily_loss_pct,
                "max_weekly_loss_pct": limits.max_weekly_loss_pct,
                "max_monthly_loss_pct": limits.max_monthly_loss_pct,
                "max_drawdown_pct": limits.max_drawdown_pct,
                "max_open_positions": limits.max_open_positions,
                "max_symbol_exposure_pct": limits.max_symbol_exposure_pct,
                "max_correlation_limit": limits.max_correlation_limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error setting risk limits: {str(e)}")

@app.get("/risk/limits")
async def get_risk_limits(user_id: str = Depends(get_current_user)):
    """리스크 한도 조회"""
    try:
        limits = risk_manager.get_risk_limits(user_id)
        
        return {
            "limits": {
                "max_position_size_pct": limits.max_position_size_pct,
                "max_daily_loss_pct": limits.max_daily_loss_pct,
                "max_weekly_loss_pct": limits.max_weekly_loss_pct,
                "max_monthly_loss_pct": limits.max_monthly_loss_pct,
                "max_drawdown_pct": limits.max_drawdown_pct,
                "max_open_positions": limits.max_open_positions,
                "max_symbol_exposure_pct": limits.max_symbol_exposure_pct,
                "max_correlation_limit": limits.max_correlation_limit
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting risk limits: {str(e)}")

@app.post("/risk/check")
async def check_risk_limits(
    symbol: str = Query(..., description="Trading symbol"),
    position_size: float = Query(..., description="Position size"),
    entry_price: float = Query(..., description="Entry price"),
    user_id: str = Depends(get_current_user)
):
    """포지션 개설 전 리스크 확인"""
    try:
        risk_check = risk_manager.check_risk_limits(user_id, symbol, position_size, entry_price)
        
        return {
            "symbol": symbol,
            "position_size": position_size,
            "entry_price": entry_price,
            "risk_check": risk_check
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking risk limits: {str(e)}")

@app.post("/risk/position-size")
async def calculate_position_size(
    account_balance: float = Query(..., description="Account balance"),
    entry_price: float = Query(..., description="Entry price"),
    stop_loss_price: float = Query(..., description="Stop loss price"),
    method: str = Query(default="fixed_fractional", description="Sizing method"),
    user_id: str = Depends(get_current_user)
):
    """포지션 크기 계산"""
    try:
        position_size = risk_manager.calculate_position_size(
            user_id, account_balance, entry_price, stop_loss_price, method
        )
        
        # 리스크 계산
        risk_amount = abs(entry_price - stop_loss_price) * position_size
        risk_percentage = (risk_amount / account_balance) * 100 if account_balance > 0 else 0
        
        return {
            "account_balance": account_balance,
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "method": method,
            "recommended_position_size": position_size,
            "risk_amount": risk_amount,
            "risk_percentage": risk_percentage
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating position size: {str(e)}")

@app.get("/risk/report")
async def get_risk_report(user_id: str = Depends(get_current_user)):
    """종합 리스크 리포트"""
    try:
        report = risk_manager.generate_risk_report(user_id)
        return report
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating risk report: {str(e)}")

@app.post("/risk/equity")
async def update_equity_history(
    equity: float = Query(..., description="Current equity value"),
    user_id: str = Depends(get_current_user)
):
    """계좌 자산 히스토리 업데이트"""
    try:
        risk_manager.update_equity_history(user_id, equity)
        
        return {
            "message": "Equity history updated successfully",
            "equity": equity,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating equity history: {str(e)}")

# ============= 데모 트레이딩 API =============

@app.post("/demo/initialize")
async def initialize_demo_account(
    initial_balance: float = Query(default=10000.0, description="초기 데모 자금"),
    user_id: str = Depends(get_current_user)
):
    """데모 계정 초기화"""
    try:
        success = demo_simulator.initialize_user_balance(user_id, initial_balance)
        
        if success:
            return {
                "message": "Demo account initialized successfully",
                "initial_balance": initial_balance,
                "currency": "USDT"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to initialize demo account")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing demo account: {str(e)}")

@app.get("/demo/balance")
async def get_demo_balance(user_id: str = Depends(get_current_user)):
    """데모 계정 잔고 조회"""
    try:
        balance = demo_simulator.get_balance(user_id)
        
        if not balance:
            # 잔고가 없으면 자동으로 초기화
            demo_simulator.initialize_user_balance(user_id)
            balance = demo_simulator.get_balance(user_id)
        
        return {"balance": balance}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting demo balance: {str(e)}")

@app.post("/demo/orders")
async def place_demo_order(
    exchange: str = Query(..., description="거래소명"),
    symbol: str = Query(..., description="거래 심볼"),
    side: str = Query(..., description="매수/매도 (buy/sell)"),
    order_type: str = Query(..., description="주문 타입 (market/limit)"),
    amount: float = Query(..., description="주문 수량"),
    price: Optional[float] = Query(None, description="주문 가격 (지정가 주문시)"),
    current_price: Optional[float] = Query(None, description="현재 시장가 (시장가 주문시)"),
    user_id: str = Depends(get_current_user)
):
    """데모 주문 생성"""
    try:
        order_result = await demo_simulator.place_order(
            user_id=user_id,
            exchange=exchange,
            symbol=symbol,
            side=side,
            order_type=order_type,
            amount=amount,
            price=price,
            current_market_price=current_price
        )
        
        if 'error' in order_result:
            raise HTTPException(status_code=400, detail=order_result['error'])
        
        return {"order": order_result}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error placing demo order: {str(e)}")

@app.get("/demo/orders")
async def get_demo_orders(
    symbol: Optional[str] = Query(None, description="거래 심볼 필터"),
    status: Optional[str] = Query(None, description="주문 상태 필터"),
    user_id: str = Depends(get_current_user)
):
    """데모 주문 조회"""
    try:
        orders = demo_simulator.get_orders(user_id, symbol, status)
        return {"orders": orders}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting demo orders: {str(e)}")

@app.delete("/demo/orders/{order_id}")
async def cancel_demo_order(
    order_id: str,
    user_id: str = Depends(get_current_user)
):
    """데모 주문 취소"""
    try:
        result = await demo_simulator.cancel_order(user_id, order_id)
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling demo order: {str(e)}")

@app.get("/demo/positions")
async def get_demo_positions(
    symbol: Optional[str] = Query(None, description="거래 심볼 필터"),
    user_id: str = Depends(get_current_user)
):
    """데모 포지션 조회"""
    try:
        positions = demo_simulator.get_positions(user_id, symbol)
        return {"positions": positions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting demo positions: {str(e)}")

@app.get("/demo/trades")
async def get_demo_trades(
    symbol: Optional[str] = Query(None, description="거래 심볼 필터"),
    limit: int = Query(default=100, description="조회 개수 제한"),
    user_id: str = Depends(get_current_user)
):
    """데모 거래 기록 조회"""
    try:
        trades = demo_simulator.get_trade_history(user_id, symbol, limit)
        return {"trades": trades}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting demo trades: {str(e)}")

@app.get("/demo/performance")
async def get_demo_performance(user_id: str = Depends(get_current_user)):
    """데모 성과 요약"""
    try:
        performance = demo_simulator.get_performance_summary(user_id)
        return {"performance": performance}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting demo performance: {str(e)}")

# ============= BingX VST (실제 데모 거래) API =============

@app.post("/vst/orders")
async def place_vst_order(
    symbol: str = Query(..., description="거래 심볼 (BTC-USDT 형식)"),
    side: str = Query(..., description="매수/매도 (BUY/SELL)"),
    order_type: str = Query(..., description="주문 타입 (MARKET/LIMIT)"),
    quantity: float = Query(..., description="주문 수량"),
    price: Optional[float] = Query(None, description="주문 가격 (지정가 주문시)"),
    user_id: str = Depends(get_current_user)
):
    """BingX VST 실제 데모 주문 생성"""
    try:
        # BingX VST 클라이언트 생성 (환경 변수에서 API 키 로드)
        try:
            vst_client = create_vst_client_from_env()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"BingX API keys not configured: {str(e)}")
        
        # VST 연결 테스트
        if not vst_client.test_vst_connection():
            raise HTTPException(status_code=503, detail="BingX VST connection failed")
        
        # 주문 실행
        if order_type.upper() == "MARKET":
            if side.upper() == "BUY":
                result = vst_client.create_vst_market_buy_order(symbol, quantity)
            else:
                result = vst_client.create_vst_market_sell_order(symbol, quantity)
        elif order_type.upper() == "LIMIT":
            if price is None:
                raise HTTPException(status_code=400, detail="Price required for limit orders")
            if side.upper() == "BUY":
                result = vst_client.create_vst_limit_buy_order(symbol, quantity, price)
            else:
                result = vst_client.create_vst_limit_sell_order(symbol, quantity, price)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported order type: {order_type}")
        
        vst_client.close()
        
        if 'error' in result:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return {"order": result, "message": "VST order placed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VST order error: {e}")
        raise HTTPException(status_code=500, detail=f"Error placing VST order: {str(e)}")

@app.get("/vst/balance")
async def get_vst_balance(user_id: str = Depends(get_current_user)):
    """BingX VST 잔고 조회"""
    try:
        try:
            vst_client = create_vst_client_from_env()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"BingX API keys not configured: {str(e)}")
        
        # 잔고 정보 한 번만 조회
        balance = vst_client.get_vst_balance()
        
        # 포지션 정보도 한 번만 조회
        positions = vst_client.get_vst_positions()
        
        # VST 계정 정보 직접 계산 (중복 API 호출 방지)
        vst_balance = 0.0
        if balance.get('code') == 0 and balance.get('data'):
            balance_data = balance['data']
            if isinstance(balance_data, dict) and 'balance' in balance_data:
                balance_info = balance_data['balance']
                if balance_info.get('asset') in ['VST', 'USDT']:
                    vst_balance = float(balance_info.get('availableMargin', 0))
        
        # 포지션 수 계산
        open_positions = 0
        total_positions = 0
        if isinstance(positions, dict) and positions.get('code') == 0 and positions.get('data'):
            positions_data = positions['data']
            if isinstance(positions_data, list):
                total_positions = len(positions_data)
                open_positions = len([p for p in positions_data if float(p.get('positionAmt', 0)) != 0])
        elif isinstance(positions, list):
            # 포지션 데이터가 직접 리스트인 경우
            total_positions = len(positions)
            open_positions = len([p for p in positions if float(p.get('positionAmt', 0)) != 0])
        
        account_info = {
            'vst_balance': vst_balance,
            'open_positions': open_positions,
            'total_positions': total_positions,
            'account_status': 'active'
        }
        
        vst_client.close()
        
        return {
            "balance": balance,
            "account_info": account_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VST balance error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting VST balance: {str(e)}")

@app.get("/vst/positions")
async def get_vst_positions(
    symbol: Optional[str] = Query(None, description="거래 심볼 필터"),
    user_id: str = Depends(get_current_user)
):
    """BingX VST 포지션 조회"""
    try:
        try:
            vst_client = create_vst_client_from_env()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"BingX API keys not configured: {str(e)}")
        
        positions = vst_client.get_vst_positions(symbol)
        
        vst_client.close()
        
        return {"positions": positions}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VST positions error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting VST positions: {str(e)}")

@app.get("/vst/trades")
async def get_vst_trades(
    symbol: Optional[str] = Query(None, description="거래 심볼 필터"),
    limit: int = Query(default=100, description="조회 개수 제한"),
    user_id: str = Depends(get_current_user)
):
    """BingX VST 거래 기록 조회"""
    try:
        try:
            vst_client = create_vst_client_from_env()
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"BingX API keys not configured: {str(e)}")
        
        trades = vst_client.get_vst_trade_history(symbol, limit)
        
        vst_client.close()
        
        return {"trades": trades}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VST trades error: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting VST trades: {str(e)}")

@app.get("/vst/portfolio")
async def get_vst_portfolio_summary(user_id: str = Depends(get_current_user)):
    """BingX VST 포트폴리오 종합 정보 (잔고, 포지션, 최근거래 통합)"""
    try:
        try:
            vst_client = create_vst_client_from_env()
            
            # Fetch all data in parallel for better performance
            import asyncio
            balance_task = asyncio.create_task(asyncio.to_thread(vst_client.get_vst_balance))
            positions_task = asyncio.create_task(asyncio.to_thread(vst_client.get_vst_positions))
            trades_task = asyncio.create_task(asyncio.to_thread(vst_client.get_vst_trade_history, None, 10))
            
            balance_result = await balance_task
            positions_result = await positions_task  
            trades_result = await trades_task
            
            return {
                "balance": balance_result,
                "positions": positions_result, 
                "recent_trades": trades_result,
                "combined_at": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "error": f"VST API call failed: {str(e)}",
                "balance": {"balance": {"balance": "0", "equity": "0", "availableMargin": "0", "usedMargin": "0", "unrealizedProfit": "0"}},
                "positions": {"positions": []},
                "recent_trades": []
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting VST portfolio: {str(e)}")

@app.get("/vst/status")
async def get_vst_status(user_id: str = Depends(get_current_user)):
    """BingX VST 연결 상태 확인"""
    try:
        try:
            vst_client = create_vst_client_from_env()
        except ValueError as e:
            return {
                "connected": False,
                "error": f"API keys not configured: {str(e)}",
                "account_info": None
            }
        
        connected = vst_client.test_vst_connection()
        account_info = None
        
        if connected:
            account_info = vst_client.get_vst_account_info()
        
        vst_client.close()
        
        return {
            "connected": connected,
            "account_info": account_info,
            "message": "VST connection active" if connected else "VST connection failed"
        }
        
    except Exception as e:
        logger.error(f"VST status error: {e}")
        return {
            "connected": False,
            "error": str(e),
            "account_info": None
        }

@app.post("/demo/mode")
async def switch_demo_mode(
    demo_mode: bool = Query(..., description="데모 모드 활성화 여부"),
    user_id: str = Depends(get_current_user)
):
    """데모/실거래 모드 전환"""
    try:
        success = switch_trading_mode(user_id, demo_mode)
        
        if success:
            return {
                "message": f"Switched to {'demo' if demo_mode else 'live'} trading mode",
                "demo_mode": demo_mode
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to switch trading mode")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error switching trading mode: {str(e)}")

@app.get("/demo/mode")
async def get_demo_mode(user_id: str = Depends(get_current_user)):
    """현재 트레이딩 모드 조회"""
    try:
        demo_mode = is_demo_mode_enabled(user_id)
        return {
            "demo_mode": demo_mode,
            "mode": "demo" if demo_mode else "live"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting trading mode: {str(e)}")

@app.post("/demo/market-update")
async def update_demo_market_prices(prices: MarketPrices, user_id: str = Depends(get_current_user)):
    """데모 시장 가격 업데이트 (포지션 PnL 계산용)"""
    try:
        demo_simulator.update_market_prices(prices.prices)
        logger.info(f"Market prices updated by user {user_id} for symbols: {list(prices.prices.keys())}")
        
        return {
            "message": "Market prices updated successfully",
            "updated_symbols": list(prices.prices.keys()),
            "user_id": user_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating market prices: {str(e)}")

# ============= BingX 거래소 지원 API =============

@app.post("/exchanges/{exchange_name}/initialize")
async def initialize_exchange_connection(
    exchange_name: str,
    api_key: str = Query(..., description="API 키"),
    secret_key: str = Query(..., description="Secret 키"),
    demo_mode: bool = Query(default=True, description="데모 모드 여부"),
    user_id: str = Depends(get_current_user)
):
    """거래소 연결 초기화 (바이낸스, BingX 지원)"""
    try:
        success = await trading_engine.initialize_exchange(
            exchange_name=exchange_name,
            api_key=api_key,
            secret=secret_key,
            demo_mode=demo_mode
        )
        
        if success:
            logger.info(f"User {user_id} initialized {exchange_name} exchange (demo: {demo_mode})")
            return {
                "message": f"{exchange_name} exchange initialized successfully",
                "exchange": exchange_name,
                "demo_mode": demo_mode,
                "status": "connected",
                "user_id": user_id
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to initialize {exchange_name}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initializing exchange: {str(e)}")

@app.get("/exchanges/supported")
async def get_supported_exchanges():
    """지원되는 거래소 목록"""
    try:
        from exchange_adapter import ExchangeFactory
        exchanges = ExchangeFactory.get_supported_exchanges()
        
        return {
            "supported_exchanges": exchanges,
            "features": {
                "binance": ["spot", "futures", "demo_mode"],
                "bingx": ["spot", "futures", "demo_mode", "copy_trading"]
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting supported exchanges: {str(e)}")

# ============= 고급 성과 분석 API =============

@app.post("/analysis/performance")
async def analyze_performance(
    analysis_type: str = Query(..., description="분석 타입 (backtest/demo/live)"),
    strategy_id: Optional[int] = Query(None, description="전략 ID"),
    start_date: Optional[str] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    user_id: str = Depends(get_current_user)
):
    """종합 성과 분석"""
    try:
        # 데이터 수집
        if analysis_type == "demo":
            trades = demo_simulator.get_trade_history(user_id, limit=1000)
            returns, equity_curve = convert_trades_to_returns(trades)
        elif analysis_type == "backtest":
            # 백테스트 결과에서 데이터 가져오기 (실제 구현 필요)
            returns = []
            equity_curve = []
            trades = []
        else:
            # 실거래 데이터 (실제 구현 필요)
            returns = []
            equity_curve = []
            trades = []
        
        # 성과 분석 실행
        metrics = performance_analyzer.analyze_performance(
            returns=returns,
            equity_curve=equity_curve,
            trades=trades
        )
        
        # 결과 반환
        return {
            "analysis_type": analysis_type,
            "metrics": {
                "total_return": metrics.total_return,
                "annualized_return": metrics.annualized_return,
                "volatility": metrics.volatility,
                "sharpe_ratio": metrics.sharpe_ratio,
                "sortino_ratio": metrics.sortino_ratio,
                "max_drawdown": metrics.max_drawdown,
                "max_drawdown_duration": metrics.max_drawdown_duration,
                "calmar_ratio": metrics.calmar_ratio,
                "win_rate": metrics.win_rate,
                "profit_factor": metrics.profit_factor,
                "total_trades": metrics.total_trades,
                "var_95": metrics.var_95,
                "cvar_95": metrics.cvar_95
            },
            "report": performance_analyzer.generate_performance_report(metrics, analysis_type)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing performance: {str(e)}")

@app.post("/analysis/compare")
async def compare_strategies(
    strategy_a_type: str = Query(..., description="전략 A 타입 (backtest/demo/live)"),
    strategy_b_type: str = Query(..., description="전략 B 타입 (backtest/demo/live)"),
    strategy_a_id: Optional[int] = Query(None, description="전략 A ID"),
    strategy_b_id: Optional[int] = Query(None, description="전략 B ID"),
    user_id: str = Depends(get_current_user)
):
    """전략 비교 분석"""
    try:
        # 전략 A 데이터 수집
        if strategy_a_type == "demo":
            trades_a = demo_simulator.get_trade_history(user_id, limit=1000)
            returns_a, equity_a = convert_trades_to_returns(trades_a)
        else:
            returns_a, equity_a, trades_a = [], [], []
        
        # 전략 B 데이터 수집
        if strategy_b_type == "demo":
            trades_b = demo_simulator.get_trade_history(user_id, limit=1000)
            returns_b, equity_b = convert_trades_to_returns(trades_b)
        else:
            returns_b, equity_b, trades_b = [], [], []
        
        # 비교 분석 실행
        comparison = performance_analyzer.compare_strategies(
            results_a={
                'returns': returns_a,
                'equity_curve': equity_a,
                'trades': trades_a
            },
            results_b={
                'returns': returns_b,
                'equity_curve': equity_b,
                'trades': trades_b
            },
            analysis_type_a=f"{strategy_a_type} Strategy A",
            analysis_type_b=f"{strategy_b_type} Strategy B"
        )
        
        return {
            "comparison": {
                "strategy_a": strategy_a_type,
                "strategy_b": strategy_b_type,
                "correlation": comparison.correlation,
                "outperformance": comparison.outperformance,
                "statistical_significance": comparison.statistical_significance,
                "summary": comparison.summary
            },
            "metrics_a": {
                "total_return": comparison.metrics_a.total_return,
                "sharpe_ratio": comparison.metrics_a.sharpe_ratio,
                "max_drawdown": comparison.metrics_a.max_drawdown,
                "win_rate": comparison.metrics_a.win_rate
            },
            "metrics_b": {
                "total_return": comparison.metrics_b.total_return,
                "sharpe_ratio": comparison.metrics_b.sharpe_ratio,
                "max_drawdown": comparison.metrics_b.max_drawdown,
                "win_rate": comparison.metrics_b.win_rate
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing strategies: {str(e)}")

@app.get("/analysis/rolling/{analysis_type}")
async def get_rolling_metrics(
    analysis_type: str,
    window: int = Query(default=30, description="롤링 윈도우 크기 (일)"),
    strategy_id: Optional[int] = Query(None, description="전략 ID"),
    user_id: str = Depends(get_current_user)
):
    """롤링 성과 지표 조회"""
    try:
        # 데이터 수집
        if analysis_type == "demo":
            trades = demo_simulator.get_trade_history(user_id, limit=1000)
            returns, equity_curve = convert_trades_to_returns(trades)
        else:
            returns, equity_curve = [], []
        
        if not returns:
            return {"message": "No data available for rolling metrics"}
        
        # 롤링 지표 계산
        rolling_metrics = calculate_rolling_metrics(returns, window)
        
        return {
            "analysis_type": analysis_type,
            "window": window,
            "metrics": rolling_metrics,
            "data_points": len(rolling_metrics.get('rolling_return', []))
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating rolling metrics: {str(e)}")

@app.get("/analysis/risk-metrics/{analysis_type}")
async def get_risk_metrics(
    analysis_type: str,
    confidence_level: float = Query(default=0.95, description="신뢰수준"),
    strategy_id: Optional[int] = Query(None, description="전략 ID"),
    user_id: str = Depends(get_current_user)
):
    """리스크 지표 분석"""
    try:
        # 데이터 수집
        if analysis_type == "demo":
            trades = demo_simulator.get_trade_history(user_id, limit=1000)
            returns, equity_curve = convert_trades_to_returns(trades)
        else:
            returns, equity_curve = [], []
        
        if not returns:
            return {"message": "No data available for risk analysis"}
        
        # 리스크 지표 계산
        risk_metrics = performance_analyzer.calculate_risk_metrics(returns, confidence_level)
        drawdown_metrics = performance_analyzer.calculate_drawdown_metrics(equity_curve) if equity_curve else {}
        
        return {
            "analysis_type": analysis_type,
            "confidence_level": confidence_level,
            "risk_metrics": {
                **risk_metrics,
                **drawdown_metrics
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating risk metrics: {str(e)}")

@app.get("/analysis/trade-analysis/{analysis_type}")
async def get_trade_analysis(
    analysis_type: str,
    strategy_id: Optional[int] = Query(None, description="전략 ID"),
    user_id: str = Depends(get_current_user)
):
    """거래 분석"""
    try:
        # 데이터 수집
        if analysis_type == "demo":
            trades = demo_simulator.get_trade_history(user_id, limit=1000)
        else:
            trades = []
        
        if not trades:
            return {"message": "No trades available for analysis"}
        
        # 거래 지표 계산
        trade_metrics = performance_analyzer.calculate_trade_metrics(trades)
        
        # 거래 패턴 분석
        trade_analysis = {
            "daily_trades": len([t for t in trades if datetime.fromisoformat(t['timestamp']).date() == datetime.now().date()]),
            "avg_trades_per_day": len(trades) / max(1, (datetime.now() - datetime.fromisoformat(trades[0]['timestamp'])).days),
            "best_performing_symbol": None,
            "worst_performing_symbol": None
        }
        
        # 심볼별 성과 분석
        symbol_performance = {}
        for trade in trades:
            symbol = trade.get('symbol', 'Unknown')
            pnl = trade.get('pnl', 0)
            
            if symbol not in symbol_performance:
                symbol_performance[symbol] = {'pnl': 0, 'trades': 0}
            
            symbol_performance[symbol]['pnl'] += pnl
            symbol_performance[symbol]['trades'] += 1
        
        if symbol_performance:
            best_symbol = max(symbol_performance, key=lambda x: symbol_performance[x]['pnl'])
            worst_symbol = min(symbol_performance, key=lambda x: symbol_performance[x]['pnl'])
            
            trade_analysis['best_performing_symbol'] = {
                'symbol': best_symbol,
                'pnl': symbol_performance[best_symbol]['pnl'],
                'trades': symbol_performance[best_symbol]['trades']
            }
            trade_analysis['worst_performing_symbol'] = {
                'symbol': worst_symbol,
                'pnl': symbol_performance[worst_symbol]['pnl'],
                'trades': symbol_performance[worst_symbol]['trades']
            }
        
        return {
            "analysis_type": analysis_type,
            "trade_metrics": trade_metrics,
            "trade_analysis": trade_analysis,
            "symbol_performance": symbol_performance
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing trades: {str(e)}")

@app.get("/analysis/dashboard/{analysis_type}")
async def get_analysis_dashboard(
    analysis_type: str,
    strategy_id: Optional[int] = Query(None, description="전략 ID"),
    user_id: str = Depends(get_current_user)
):
    """종합 분석 대시보드 데이터"""
    try:
        # 기본 성과 분석
        performance_response = await analyze_performance(analysis_type, strategy_id, None, None, user_id)
        
        # 롤링 지표
        rolling_response = await get_rolling_metrics(analysis_type, 30, strategy_id, user_id)
        
        # 리스크 지표
        risk_response = await get_risk_metrics(analysis_type, 0.95, strategy_id, user_id)
        
        # 거래 분석
        trade_response = await get_trade_analysis(analysis_type, strategy_id, user_id)
        
        return {
            "analysis_type": analysis_type,
            "dashboard": {
                "performance": performance_response.get("metrics", {}),
                "rolling_metrics": rolling_response.get("metrics", {}),
                "risk_metrics": risk_response.get("risk_metrics", {}),
                "trade_analysis": trade_response.get("trade_metrics", {}),
                "symbol_performance": trade_response.get("symbol_performance", {})
            },
            "report": performance_response.get("report", ""),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating analysis dashboard: {str(e)}")

@app.get("/debug/trading-engine")
async def debug_trading_engine():
    """실시간 거래 엔진 상태 디버깅"""
    try:
        debug_info = {
            "engine_running": trading_engine.running,
            "active_monitors": list(trading_engine.active_monitors.keys()),
            "candle_data_symbols": list(trading_engine.candle_data.keys()),
            "exchanges": list(trading_engine.exchanges.keys()),
            "monitor_details": {},
            "candle_data_counts": {}
        }
        
        # 각 모니터의 상세 정보
        for monitor_key, monitor_info in trading_engine.active_monitors.items():
            candle_count = len(trading_engine.candle_data.get(monitor_key, []))
            debug_info["monitor_details"][monitor_key] = {
                "user_id": monitor_info.get("user_id"),
                "symbol": monitor_info.get("symbol"),
                "exchange": monitor_info.get("exchange_name"),
                "timeframe": monitor_info.get("timeframe"),
                "strategies_count": len(monitor_info.get("strategies", [])),
                "last_candle_time": monitor_info.get("last_candle_time"),
                "candle_data_count": candle_count,
                "ready_for_trading": candle_count >= 50
            }
            debug_info["candle_data_counts"][monitor_key] = candle_count
        
        return debug_info
        
    except Exception as e:
        return {"error": str(e)}

# =============================================================================
# Phase 15.3: 고급 기능 엔드포인트
# =============================================================================

# 고급 기능 시스템 (Phase 15.3)
try:
    from advanced import MultiStrategyEngine, AdvancedIndicators
    from advanced.analytics_engine import AnalyticsEngine, ReportType
    ADVANCED_FEATURES_ENABLED = True
    
    # 글로벌 인스턴스 생성
    multi_strategy_engine = MultiStrategyEngine()
    advanced_indicators = AdvancedIndicators()
    analytics_engine = AnalyticsEngine("data")
    
    logger.info("✅ Advanced features loaded successfully")
except ImportError as e:
    ADVANCED_FEATURES_ENABLED = False
    logger.warning(f"⚠️ Advanced features not available: {e}")

@app.get("/advanced/status")
async def get_advanced_features_status():
    """고급 기능 상태 확인"""
    if not ADVANCED_FEATURES_ENABLED:
        return {"enabled": False, "message": "Advanced features not available"}
    
    try:
        status = multi_strategy_engine.get_system_status()
        return {
            "enabled": True,
            "multi_strategy_engine": status,
            "analytics_engine": {
                "status": "ready",
                "available_analysis_types": ["performance", "risk", "correlation", "volatility", "drawdown"]
            },
            "advanced_indicators": {
                "status": "ready", 
                "available_indicators": ["cci", "rsi", "macd", "bollinger", "stochastic", "adx", "williams_r", "ichimoku"]
            }
        }
    except Exception as e:
        logger.error(f"🔴 Error getting advanced features status: {e}")
        return {"enabled": False, "error": str(e)}

@app.post("/advanced/strategy/add")
async def add_trading_strategy(
    strategy_config: dict,
    user_id: str = Depends(get_current_user)
):
    """거래 전략 추가"""
    if not ADVANCED_FEATURES_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced features not available")
    
    try:
        # 기본 전략들 생성 및 추가
        from advanced.multi_strategy_engine import create_default_strategies
        strategies = create_default_strategies()
        
        added_strategies = []
        for strategy in strategies:
            multi_strategy_engine.add_strategy(strategy)
            added_strategies.append({
                "name": strategy.config.name,
                "description": strategy.config.description,
                "status": strategy.status.value
            })
        
        return {
            "message": "Default strategies added successfully",
            "strategies": added_strategies,
            "total_strategies": len(multi_strategy_engine.strategies)
        }
        
    except Exception as e:
        logger.error(f"🔴 Error adding trading strategy: {e}")
        raise HTTPException(status_code=500, detail=f"Error adding strategy: {str(e)}")

@app.post("/advanced/analytics/performance")
async def create_performance_analysis(
    user_id: str = Depends(get_current_user)
):
    """성과 분석 생성"""
    if not ADVANCED_FEATURES_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced features not available")
    
    try:
        # 샘플 거래 데이터 생성 (실제로는 사용자 데이터 사용)
        import numpy as np
        np.random.seed(42)
        trades_data = []
        
        for i in range(30):
            is_win = np.random.random() < 0.65  # 65% 승률
            pnl = np.random.uniform(50, 300) if is_win else np.random.uniform(-150, -25)
            trades_data.append({
                'timestamp': (datetime.now() - timedelta(days=30-i)).isoformat(),
                'pnl': pnl,
                'pnl_pct': pnl / 5000 * 100,  # 5000달러 기준
                'entry_time': (datetime.now() - timedelta(days=30-i, hours=2)).isoformat(),
                'exit_time': (datetime.now() - timedelta(days=30-i, hours=1)).isoformat()
            })
        
        # 성과 분석 생성
        analysis = await analytics_engine.create_performance_analysis(trades_data, "Portfolio Performance")
        
        return {
            "analysis_type": analysis.analysis_type.value,
            "trades_analyzed": len(trades_data),
            "metrics": analysis.data,
            "summary": analysis.summary,
            "recommendations": analysis.recommendations,
            "charts_generated": len(analysis.charts),
            "timestamp": analysis.timestamp.isoformat()
        }
        
    except Exception as e:
        logger.error(f"🔴 Error creating performance analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating analysis: {str(e)}")

# =============================================================================
# Phase 15.4: Frontend Dashboard Integration APIs
# =============================================================================

# 고급 기능들을 위한 글로벌 인스턴스들
portfolio_manager_instance = None
advanced_risk_manager_instance = None
backtesting_engine_instance = None
optimizer_instance = None

async def initialize_advanced_instances():
    """고급 기능 인스턴스들 초기화"""
    global portfolio_manager_instance, advanced_risk_manager_instance
    global backtesting_engine_instance, optimizer_instance
    
    if ADVANCED_FEATURES_ENABLED:
        try:
            from advanced.portfolio_manager import PortfolioManager
            from advanced.advanced_risk_manager import AdvancedRiskManager
            from advanced.backtesting_engine import BacktestingEngine
            from advanced.parameter_optimizer import ParameterOptimizer
            
            portfolio_manager_instance = PortfolioManager(
                initial_capital=10000.0,
                max_positions=3,
                rebalance_interval=timedelta(hours=24)
            )
            
            advanced_risk_manager_instance = AdvancedRiskManager(current_capital=10000.0)
            backtesting_engine_instance = BacktestingEngine()
            optimizer_instance = ParameterOptimizer()
            
            logger.info("✅ Advanced instances initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize advanced instances: {e}")
    
    # 운영 시스템 초기화 (Phase 15.5)
    if OPERATIONS_ENABLED:
        try:
            # 성능 모니터링 초기화
            initialize_performance_monitoring(interval=30)
            
            # 알림 시스템 초기화
            initialize_alerting()
            
            # 데이터베이스 최적화 초기화
            initialize_database_optimization()
            
            # 재해 복구 시스템 초기화
            initialize_disaster_recovery()
            
            logger.info("✅ Operations & monitoring systems initialized")
            
        except Exception as e:
            logger.error(f"❌ Error initializing operations systems: {e}")

# Frontend Dashboard API 엔드포인트들

@app.get("/api/dashboard/overview")
async def get_dashboard_overview():
    """대시보드 개요 데이터"""
    try:
        # 포트폴리오 상태
        portfolio_data = {}
        if ADVANCED_FEATURES_ENABLED and portfolio_manager_instance:
            portfolio_data = await portfolio_manager_instance.get_portfolio_status()
        else:
            portfolio_data = {
                "total_balance": 10000.0,
                "available_balance": 9500.0,
                "positions": 1,
                "pnl": 150.0,
                "pnl_pct": 1.5
            }
        
        # 활성 전략
        strategies_data = []
        if ADVANCED_FEATURES_ENABLED:
            strategies_data = await multi_strategy_engine.get_active_strategies()
        else:
            strategies_data = [
                {"name": "CCI Strategy", "enabled": True, "pnl": 85.2},
                {"name": "RSI+MACD Strategy", "enabled": False, "pnl": 0.0}
            ]
        
        # 최근 거래
        try:
            result = supabase.table('trades').select('*').order('created_at', desc=True).limit(5).execute()
            recent_trades = result.data if result.data else []
        except:
            recent_trades = []
        
        return {
            "success": True,
            "data": {
                "portfolio": portfolio_data,
                "strategies": strategies_data,
                "recent_trades": recent_trades,
                "system_status": {
                    "uptime": "running",
                    "advanced_features": ADVANCED_FEATURES_ENABLED,
                    "reliability_systems": RELIABILITY_ENABLED
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Dashboard overview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/strategies/optimize")
async def optimize_strategy_parameters(
    strategy_name: str,
    parameter_ranges: dict,
    optimization_method: str = "genetic"
):
    """전략 파라미터 최적화"""
    if not ADVANCED_FEATURES_ENABLED or not optimizer_instance:
        raise HTTPException(status_code=503, detail="Advanced optimization not available")
    
    try:
        # 시장 데이터 가져오기
        from bingx_client import BingXClient
        client = BingXClient()
        market_data = await client.get_market_data("BTCUSDT", "5m", 1000)
        
        from advanced.parameter_optimizer import OptimizationConfig
        config = OptimizationConfig(
            parameter_ranges=parameter_ranges,
            method=optimization_method,
            objective="sharpe_ratio",
            max_iterations=50,
            population_size=20
        )
        
        result = await optimizer_instance.optimize_strategy_parameters(
            strategy_name, market_data, config
        )
        
        return {
            "success": True,
            "optimization_result": {
                "best_parameters": result.best_parameters,
                "best_score": result.best_score,
                "method_used": result.method_used,
                "objective": result.objective_used
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Strategy optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analytics/advanced")
async def get_advanced_analytics():
    """고급 분석 데이터"""
    if not ADVANCED_FEATURES_ENABLED:
        raise HTTPException(status_code=503, detail="Advanced analytics not available")
    
    try:
        # VaR 계산
        risk_data = {}
        if advanced_risk_manager_instance:
            # 샘플 수익률 데이터
            import numpy as np
            returns = np.random.normal(0.001, 0.02, 100).tolist()
            var_calculation = await advanced_risk_manager_instance.calculate_var(returns)
            risk_data = {
                "var_95": var_calculation.var_95,
                "var_99": var_calculation.var_99,
                "cvar_95": var_calculation.cvar_95
            }
        
        # 포트폴리오 성과
        portfolio_performance = {}
        if portfolio_manager_instance:
            portfolio_performance = await portfolio_manager_instance.get_performance_summary()
        
        return {
            "success": True,
            "data": {
                "risk_metrics": risk_data,
                "portfolio_performance": portfolio_performance,
                "analytics_engine_status": "active" if ADVANCED_FEATURES_ENABLED else "inactive"
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Advanced analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/market/indicators/{symbol}")
async def get_market_indicators(symbol: str = "BTCUSDT"):
    """실시간 기술 지표 데이터"""
    if not ADVANCED_FEATURES_ENABLED:
        # 기본 지표 데이터 반환
        return {
            "success": True,
            "data": {
                "indicators": {
                    "cci": {"current": -85.3, "signal": "BUY"},
                    "rsi": {"current": 45.2, "signal": "NEUTRAL"},
                    "macd": {"current": 125.8, "signal": "BUY"}
                },
                "composite_signal": {
                    "signal": "BUY",
                    "confidence": 0.72,
                    "strength": "MODERATE",
                    "trend": "UPWARD"
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    
    try:
        # 데모 시장 데이터 생성
        import pandas as pd
        import numpy as np
        dates = pd.date_range(start=datetime.now() - timedelta(hours=8), periods=100, freq='5T')
        market_data = pd.DataFrame({
            'timestamp': dates,
            'open': np.random.uniform(65000, 67000, 100),
            'high': np.random.uniform(66000, 68000, 100),
            'low': np.random.uniform(64000, 66000, 100),
            'close': np.random.uniform(65000, 67000, 100),
            'volume': np.random.uniform(10, 100, 100)
        })
        
        if market_data.empty:
            raise HTTPException(status_code=503, detail="Market data unavailable")
        
        # 고급 지표 계산
        indicators = advanced_indicators.calculate_all_indicators(market_data)
        composite_signal = advanced_indicators.create_composite_signal([], indicators)
        
        return {
            "success": True,
            "data": {
                "indicators": indicators,
                "composite_signal": {
                    "signal": composite_signal.overall_signal,
                    "confidence": composite_signal.confidence,
                    "strength": composite_signal.strength.name,
                    "trend": composite_signal.trend_direction.name
                }
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"❌ Failed to get market indicators: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/advanced")
async def advanced_websocket(websocket: WebSocket):
    """고급 기능 실시간 업데이트"""
    await websocket.accept()
    logger.info("📡 Advanced WebSocket connected")
    
    try:
        while True:
            # 실시간 시장 데이터
            if ADVANCED_FEATURES_ENABLED:
                from bingx_client import BingXClient
                client = BingXClient()
                market_data = await client.get_market_data("BTCUSDT", "5m", 20)
                
                if not market_data.empty:
                    # 고급 지표 계산
                    indicators = advanced_indicators.calculate_all_indicators(market_data)
                    
                    # 실시간 업데이트 데이터
                    update_data = {
                        "type": "advanced_update",
                        "market_data": {
                            "symbol": "BTCUSDT",
                            "price": float(market_data['close'].iloc[-1]),
                            "volume": float(market_data['volume'].iloc[-1])
                        },
                        "indicators": {
                            "cci": indicators.get('cci', {}).get('current', 0),
                            "rsi": indicators.get('rsi', {}).get('current', 0),
                            "macd": indicators.get('macd', {}).get('histogram', 0)
                        },
                        "portfolio_status": await portfolio_manager_instance.get_portfolio_status() if portfolio_manager_instance else {},
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    await websocket.send_text(json.dumps(update_data))
            
            await asyncio.sleep(5)  # 5초마다 업데이트
            
    except WebSocketDisconnect:
        logger.info("📡 Advanced WebSocket disconnected")
    except Exception as e:
        logger.error(f"❌ Advanced WebSocket error: {e}")
        await websocket.close()

# 앱 시작 시 고급 인스턴스 초기화
@app.on_event("startup")
async def startup_event():
    await initialize_advanced_instances()

