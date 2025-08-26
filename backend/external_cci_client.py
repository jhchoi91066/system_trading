#!/usr/bin/env python3
"""
External CCI Indicator Client using TAAPI.IO
"""

import requests
import os
import asyncio
import aiohttp
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class ExternalCCIClient:
    """TAAPI.IO를 통한 외부 CCI 지표 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None):
        # TAAPI.IO API 키 (환경변수에서 가져오거나 직접 설정)
        self.api_key = api_key or os.getenv('TAAPI_KEY')
        self.base_url = "https://api.taapi.io"
        
    def get_cci_sync(self, symbol: str, exchange: str = "bingx", 
                     interval: str = "5m", period: int = 20) -> Optional[float]:
        """동기적으로 CCI 값 가져오기"""
        try:
            url = f"{self.base_url}/cci"
            params = {
                "secret": self.api_key,
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval,
                "period": period
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            if isinstance(data, dict) and 'value' in data:
                return float(data['value'])
            elif isinstance(data, (int, float)):
                return float(data)
            else:
                logger.error(f"Unexpected CCI response format: {data}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to get CCI from TAAPI.IO: {e}")
            return None
    
    async def get_cci_async(self, symbol: str, exchange: str = "bingx", 
                           interval: str = "5m", period: int = 20) -> Optional[float]:
        """비동기적으로 CCI 값 가져오기"""
        try:
            url = f"{self.base_url}/cci"
            params = {
                "secret": self.api_key,
                "exchange": exchange,
                "symbol": symbol,
                "interval": interval,
                "period": period
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    response.raise_for_status()
                    data = await response.json()
                    
                    if isinstance(data, dict) and 'value' in data:
                        return float(data['value'])
                    elif isinstance(data, (int, float)):
                        return float(data)
                    else:
                        logger.error(f"Unexpected CCI response format: {data}")
                        return None
                        
        except Exception as e:
            logger.error(f"Failed to get CCI from TAAPI.IO: {e}")
            return None
    
    def get_multiple_cci_values(self, symbols: list, exchange: str = "bingx", 
                               interval: str = "5m", period: int = 20) -> Dict[str, Optional[float]]:
        """여러 심볼의 CCI 값을 한 번에 가져오기"""
        results = {}
        for symbol in symbols:
            cci_value = self.get_cci_sync(symbol, exchange, interval, period)
            results[symbol] = cci_value
        return results

# 백업용 내부 CCI 계산 함수 (TAAPI.IO 실패 시 사용)
def calculate_internal_cci(high, low, close, period=20):
    """내부 CCI 계산 (백업용)"""
    try:
        import pandas as pd
        import numpy as np
        
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(window=period).mean()
        mad_tp = tp.rolling(window=period).apply(
            lambda x: np.mean(np.abs(x - np.mean(x))), raw=True
        )
        cci = (tp - sma_tp) / (0.015 * mad_tp)
        return cci.iloc[-1] if not pd.isna(cci.iloc[-1]) else None
        
    except Exception as e:
        logger.error(f"Internal CCI calculation failed: {e}")
        return None

# 하이브리드 CCI 클라이언트 (외부 + 내부 백업)
class HybridCCIClient:
    """외부 CCI를 우선 사용하고, 실패 시 내부 계산으로 백업하는 클라이언트"""
    
    def __init__(self, api_key: Optional[str] = None, use_internal_backup: bool = True):
        self.external_client = ExternalCCIClient(api_key)
        self.use_internal_backup = use_internal_backup
        
    async def get_cci_value(self, symbol: str, ohlcv_data: list = None, 
                           exchange: str = "bingx", interval: str = "5m", 
                           period: int = 20) -> Optional[float]:
        """CCI 값 가져오기 (외부 우선, 실패 시 내부 계산)"""
        
        # 1. 외부 CCI 시도
        cci_value = await self.external_client.get_cci_async(
            symbol, exchange, interval, period
        )
        
        if cci_value is not None:
            logger.info(f"External CCI for {symbol}: {cci_value:.2f}")
            return cci_value
        
        # 2. 외부 실패 시 내부 계산 사용
        if self.use_internal_backup and ohlcv_data and len(ohlcv_data) >= period:
            logger.warning(f"External CCI failed for {symbol}, using internal calculation")
            
            import pandas as pd
            df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            internal_cci = calculate_internal_cci(
                df['high'], df['low'], df['close'], period
            )
            
            if internal_cci is not None:
                logger.info(f"Internal CCI for {symbol}: {internal_cci:.2f}")
                return internal_cci
        
        logger.error(f"Both external and internal CCI failed for {symbol}")
        return None

# 테스트 함수
async def test_external_cci():
    """외부 CCI 클라이언트 테스트"""
    print("🧪 External CCI Client 테스트 시작")
    
    # TAAPI.IO API 키가 필요합니다
    api_key = os.getenv('TAAPI_KEY')
    if not api_key:
        print("❌ TAAPI_KEY 환경변수가 설정되지 않았습니다")
        print("📝 무료 API 키는 https://taapi.io 에서 받을 수 있습니다 (5,000 calls/day)")
        print("🔄 데모 모드로 내부 CCI 계산을 테스트합니다...")
        
        # Demo mode: 내부 CCI 계산 테스트
        import pandas as pd
        import numpy as np
        from datetime import datetime
        
        # 가상의 OHLCV 데이터 생성 (테스트용)
        test_data = []
        base_price = 95000
        
        for i in range(50):
            high = base_price + np.random.randint(-1000, 1000)
            low = base_price + np.random.randint(-1000, 1000)
            close = base_price + np.random.randint(-1000, 1000)
            
            if high < low:
                high, low = low, high
            if close < low:
                close = low
            if close > high:
                close = high
                
            test_data.append([
                int(datetime.now().timestamp() * 1000) + i * 300000,  # 5분 간격
                base_price,  # open
                high,
                low, 
                close,
                1000  # volume
            ])
            
            base_price = close  # 다음 캔들의 시작가
        
        # 내부 CCI 계산 테스트
        df = pd.DataFrame(test_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        cci_value = calculate_internal_cci(df['high'], df['low'], df['close'], 20)
        
        if cci_value is not None:
            print(f"✅ Demo CCI 계산 성공: {cci_value:.2f}")
            if cci_value < -100:
                print(f"📈 과매도 신호 (CCI: {cci_value:.2f})")
            elif cci_value > 100:
                print(f"📉 과매수 신호 (CCI: {cci_value:.2f})")
            else:
                print(f"⚖️ 중립 범위 (CCI: {cci_value:.2f})")
        else:
            print("❌ Demo CCI 계산 실패")
        return
    
    client = ExternalCCIClient(api_key)
    
    # BTC/USDT CCI 테스트
    print("📊 BTC/USDT CCI 값 가져오는 중...")
    btc_cci = await client.get_cci_async("BTC/USDT", "binance", "5m", 20)
    
    if btc_cci is not None:
        print(f"✅ BTC/USDT CCI: {btc_cci:.2f}")
        
        # CCI 신호 해석
        if btc_cci < -100:
            print(f"📈 과매도 신호 (CCI: {btc_cci:.2f})")
        elif btc_cci > 100:
            print(f"📉 과매수 신호 (CCI: {btc_cci:.2f})")
        else:
            print(f"⚖️ 중립 범위 (CCI: {btc_cci:.2f})")
    else:
        print("❌ BTC/USDT CCI 가져오기 실패")
    
    # ETH/USDT CCI 테스트
    print("📊 ETH/USDT CCI 값 가져오는 중...")
    eth_cci = await client.get_cci_async("ETH/USDT", "binance", "5m", 20)
    
    if eth_cci is not None:
        print(f"✅ ETH/USDT CCI: {eth_cci:.2f}")
        
        # CCI 신호 해석
        if eth_cci < -100:
            print(f"📈 과매도 신호 (CCI: {eth_cci:.2f})")
        elif eth_cci > 100:
            print(f"📉 과매수 신호 (CCI: {eth_cci:.2f})")
        else:
            print(f"⚖️ 중립 범위 (CCI: {eth_cci:.2f})")
    else:
        print("❌ ETH/USDT CCI 가져오기 실패")

if __name__ == "__main__":
    asyncio.run(test_external_cci())