import ccxt.async_support as ccxt
from fastapi import FastAPI, HTTPException, Path, Query, WebSocket, WebSocketDisconnect, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import supabase
import asyncio
from strategy import backtest_strategy
from uuid import UUID, uuid4
from datetime import datetime
from typing import List, Optional, Set
import json
import os
from dotenv import load_dotenv
from jose import jwt, jwk
from jose.jwt import get_unverified_header
import requests

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

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000", # Next.js frontend
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket
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
            except Exception as e:
                print(f"Failed to send personal message to {user_id}: {e}")
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

# Background task for periodic data updates
async def periodic_data_broadcast():
    """Background task that broadcasts updated data every 5 seconds to each connected user"""
    while True:
        try:
            await asyncio.sleep(5)  # Broadcast every 5 seconds
            
            if not manager.active_connections:
                continue
                
            for user_id, websocket in manager.active_connections.copy().items():
                try:
                    # Gather real-time data for this specific user
                    data = await get_realtime_monitoring_data(user_id)
                    
                    # Send to this specific user's WebSocket
                    await websocket.send_text(json.dumps({
                        "type": "monitoring_update",
                        "data": data,
                        "timestamp": datetime.now().isoformat()
                    }))
                except Exception as e:
                    print(f"Error broadcasting to user {user_id}: {e}")
                    # Disconnect this user if there's an error sending
                    manager.disconnect(user_id)
            
        except Exception as e:
            print(f"Error in periodic broadcast loop: {e}")
            await asyncio.sleep(10)  # Wait longer on error

async def get_realtime_monitoring_data(user_id: str):
    """Gather all monitoring data in one call"""
    try:
        # Get portfolio stats
        portfolio_stats = await get_portfolio_stats_data(user_id)
        
        # Get active strategies
        active_strategies = await get_active_strategies_data(user_id)
        
        # Get performance data for active strategies
        performance_data = {}
        for strategy in active_strategies:
            try:
                perf = await get_strategy_performance_data(strategy['strategy_id'], user_id)
                performance_data[strategy['strategy_id']] = perf
            except:
                pass
        
        # Get recent notifications
        recent_notifications = await get_recent_notifications_data(user_id)
        
        return {
            "portfolio_stats": portfolio_stats,
            "active_strategies": active_strategies,
            "performance_data": performance_data,
            "notifications": recent_notifications
        }
    except Exception as e:
        print(f"Error gathering realtime data: {e}")
        return {
            "portfolio_stats": None,
            "active_strategies": [],
            "performance_data": {},
            "notifications": []
        }

# Start the background task when the app starts
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(periodic_data_broadcast())

class Strategy(BaseModel):
    name: str
    script: str
    description: str = None
    strategy_type: str = "custom"
    parameters: dict = None

@app.post("/strategies")
async def create_strategy(strategy: Strategy, user_id: str = Depends(get_current_user)):
    try:
        # Try with enhanced fields first, fallback to basic fields if columns don't exist
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
        except Exception as db_error:
            # Fallback to basic strategy creation if enhanced columns don't exist
            print(f"Enhanced columns not available, using basic strategy creation: {db_error}")
            strategy_data = {
                "name": strategy.name, 
                "script": strategy.script,
                "created_at": datetime.now().isoformat()
            }
            response = supabase.table("strategies").insert(strategy_data).execute()
        
        if response.data:
            return {
                "message": f"Strategy '{strategy.name}' created successfully",
                "strategy": response.data[0]
            }
        raise HTTPException(status_code=400, detail="Strategy could not be created.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/strategies")
async def get_strategies(user_id: str = Depends(get_current_user)):
    try:
        response = supabase.table("strategies").select("*").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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

# In-memory API key storage for development (TEMP solution)
api_keys_storage = []

# In-memory notification storage for development
notifications_storage = []



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
            notification_data["id"] = len(notifications_storage) + 1
            notifications_storage.append(notification_data)
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
            # Fallback to in-memory storage
            return [key for key in api_keys_storage if key["user_id"] == user_id]
        
        return []
    except Exception as e:
        print(f"Error fetching API keys: {str(e)}")
        return api_keys_storage

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

@app.get("/users")
async def get_users():
    try:
        response = supabase.table("users").select("*").execute()
        return response.data if response.data else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

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
        
        # Get strategy details
        strategy_response = supabase.table("strategies").select("*").eq("id", activate_data.strategy_id).execute()
        if not strategy_response.data:
            raise HTTPException(status_code=404, detail="Strategy not found")
        
        strategy = strategy_response.data[0]
        
        # Get API keys for the exchange
        api_keys_response = supabase.table("api_keys").select("*").eq("user_id", user_id).eq("exchange_name", activate_data.exchange_name).eq("is_active", True).execute()
        if not api_keys_response.data:
            raise HTTPException(status_code=400, detail=f"No active API keys found for {activate_data.exchange_name}")
        
        api_key_data = api_keys_response.data[0]
        decrypted_api_key = decrypt_data(api_key_data["api_key_encrypted"])
        decrypted_secret = decrypt_data(api_key_data["secret_key_encrypted"])
        
        # Test exchange connection
        try:
            balance = await get_account_balance(activate_data.exchange_name, decrypted_api_key, decrypted_secret)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to connect to {activate_data.exchange_name}: {str(e)}")
        
        # Create active strategy record (simulate if table doesn't exist)
        try:
            active_strategy_response = supabase.table("active_strategies").insert({
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
            }).execute()
        except Exception as db_error:
            # Simulate successful activation if database table doesn't exist
            print(f"Database table not found, simulating activation: {db_error}")
            active_strategy_response = type('obj', (object,), {
                'data': [{
                    'id': 1,
                    'user_id': user_id,
                    'strategy_id': activate_data.strategy_id,
                    'exchange_name': activate_data.exchange_name,
                    'symbol': activate_data.symbol,
                    'allocated_capital': activate_data.allocated_capital,
                    'is_active': True,
                    'created_at': datetime.now().isoformat()
                }]
            })()
        
        if active_strategy_response.data:
            # Send strategy activation notification
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
            
            # Check for risk alerts
            await check_risk_alerts(user_id, active_strategy_response.data[0], balance)
            
            return {
                "message": f"Strategy '{strategy['name']}' activated for {activate_data.symbol} on {activate_data.exchange_name}",
                "active_strategy": active_strategy_response.data[0],
                "current_balance": balance.get('total', {})
            }
        
        raise HTTPException(status_code=400, detail="Failed to activate strategy")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error activating strategy: {str(e)}")

@app.post("/trading/deactivate/{active_strategy_id}")
async def deactivate_strategy_trading(active_strategy_id: int, user_id: str = Depends(get_current_user)):
    """Deactivate a strategy from real-time trading"""
    try:
        
        response = supabase.table("active_strategies").update({
            "is_active": False,
            "deactivated_at": datetime.now().isoformat()
        }).eq("id", active_strategy_id).eq("user_id", user_id).execute()
        
        if response.data and len(response.data) > 0:
            return {"message": "Strategy deactivated successfully", "active_strategy": response.data[0]}
        
        raise HTTPException(status_code=404, detail="Active strategy not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deactivating strategy: {str(e)}")

@app.get("/trading/active")
async def get_active_strategies(user_id: str = Depends(get_current_user)):
    """Get all active trading strategies for the user"""
    try:
        
        response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        return response.data if response.data else []
    except Exception as e:
        # Return empty list if table doesn't exist yet
        print(f"Active strategies table not found: {str(e)}")
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
        
        response = supabase.table("trades").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trading history: {str(e)}")

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
        try:
            active_strategies_response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            active_strategies = active_strategies_response.data if active_strategies_response.data else []
        except:
            active_strategies = []
        
        # Calculate portfolio stats
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
            # Fallback to in-memory storage
            filtered_notifications = [n for n in notifications_storage if n["user_id"] == user_id]
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
            # Fallback to in-memory storage
            for notification in notifications_storage:
                if notification["id"] == notification_id and notification["user_id"] == user_id:
                    notification["is_read"] = True
                    notification["read_at"] = datetime.now().isoformat()
                    return {"message": "Notification marked as read (in-memory)"}
        
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
            # Fallback to in-memory storage
            count = 0
            for notification in notifications_storage:
                if notification["user_id"] == user_id and not notification.get("is_read", False):
                    notification["is_read"] = True
                    notification["read_at"] = datetime.now().isoformat()
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
            user_notifications = [n for n in notifications_storage if n["user_id"] == user_id]
            unread_notifications = [n for n in user_notifications if not n.get("is_read", False)]
            
            return {
                "total_notifications": len(user_notifications),
                "unread_notifications": len(unread_notifications)
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching notification stats: {str(e)}")

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

# WebSocket endpoint
@app.websocket("/ws/monitoring")
async def websocket_endpoint(websocket: WebSocket):
    user_id: Optional[str] = None
    try:
        await websocket.accept()
        # First message should be the authentication token
        auth_message = await websocket.receive_text()
        auth_data = json.loads(auth_message)
        token = auth_data.get("token")

        if not token:
            await websocket.close(code=1008, reason="Authentication token missing")
            return

        try:
            # Use the same logic as get_current_user to validate the token
            unverified_header = get_unverified_header(token)
            jwks = await get_jwks_client()
            public_key = jwks.get_key(unverified_header['kid'])
            if not public_key:
                await websocket.close(code=1008, reason="Invalid token: KID not found")
                return
            
            decoded_token = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=os.getenv("CLERK_JWT_AUDIENCE"),
                issuer=os.getenv("CLERK_JWT_ISSUER")
            )
            user_id = decoded_token.get("sub")
            if not user_id:
                await websocket.close(code=1008, reason="Invalid token: User ID not found")
                return

            await manager.connect(user_id, websocket)
            print(f"✅ WebSocket authenticated and connected for user: {user_id}")

            # Send initial data immediately upon connection
            initial_data = await get_realtime_monitoring_data(user_id)
            await websocket.send_text(json.dumps({
                "type": "initial_data",
                "data": initial_data,
                "timestamp": datetime.now().isoformat()
            }))

            # Keep connection alive and handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    message = json.loads(data)
                    
                    if message.get("type") == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "timestamp": datetime.now().isoformat()
                        }))
                    elif message.get("type") == "request_update":
                        current_data = await get_realtime_monitoring_data(user_id)
                        await websocket.send_text(json.dumps({
                            "type": "monitoring_update",
                            "data": current_data,
                            "timestamp": datetime.now().isoformat()
                        }))

                except WebSocketDisconnect:
                    print(f"WebSocket disconnected for user: {user_id}")
                    break
                except Exception as e:
                    print(f"Error handling WebSocket message for user {user_id}: {e}")
                    break

        except jwt.ExpiredSignatureError:
            await websocket.close(code=1008, reason="Token has expired")
        except jwt.JWTError as e:
            await websocket.close(code=1008, reason=f"Invalid token: {e}")
        except Exception as e:
            await websocket.close(code=1008, reason=f"Authentication failed: {e}")

    except WebSocketDisconnect:
        print("WebSocket disconnected before authentication")
    except Exception as e:
        print(f"Error during WebSocket connection setup: {e}")
    finally:
        if user_id:
            manager.disconnect(user_id)

# Helper functions for data collection
async def get_portfolio_stats_data(user_id: str):
    """Get portfolio statistics data"""
    try:
        
        # Get active strategies to calculate total allocation
        try:
            active_strategies_response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
            active_strategies = active_strategies_response.data if active_strategies_response.data else []
        except:
            active_strategies = []
        
        # Calculate portfolio stats
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
        print(f"Error fetching portfolio stats: {e}")
        return None

async def get_active_strategies_data(user_id: str):
    """Get active strategies data"""
    try:
        response = supabase.table("active_strategies").select("*").eq("user_id", user_id).eq("is_active", True).execute()
        return response.data if response.data else []
    except Exception as e:
        print(f"Error fetching active strategies: {e}")
        return []

async def get_strategy_performance_data(strategy_id: int, user_id: str):
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
        print(f"Error fetching strategy performance: {e}")
        return None

async def get_recent_notifications_data(user_id: str):
    """Get recent notifications"""
    try:
        
        # Try database first, fallback to in-memory storage
        try:
            response = supabase.table("notifications").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(10).execute()
            return response.data if response.data else []
        except:
            # Fallback to in-memory storage
            filtered_notifications = [n for n in notifications_storage if n["user_id"] == user_id]
            return sorted(filtered_notifications, key=lambda x: x["created_at"], reverse=True)[:10]
    except Exception as e:
        print(f"Error fetching notifications: {e}")
        return []

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