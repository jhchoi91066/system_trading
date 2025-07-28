import ccxt.async_support as ccxt
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from db import supabase
import asyncio
from strategy import backtest_strategy

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000", # Next.js frontend
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Strategy(BaseModel):
    name: str
    script: str

@app.post("/strategies")
async def create_strategy(strategy: Strategy):
    response = supabase.table("strategies").insert({"name": strategy.name, "script": strategy.script}).execute()
    if response.data:
        return response.data
    raise HTTPException(status_code=400, detail="Strategy could not be created.")

@app.get("/strategies")
async def get_strategies():
    response = supabase.table("strategies").select("*").execute()
    return response.data

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/users")
async def get_users():
    response = supabase.table("users").select("*").execute()
    return response.data

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

