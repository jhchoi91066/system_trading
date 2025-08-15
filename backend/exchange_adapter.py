"""
거래소 추상화 계층
- 다양한 거래소(바이낸스, BingX)에 대한 통일된 인터페이스 제공
- 어댑터 패턴을 사용하여 거래소별 API 차이점 추상화
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import ccxt.async_support as ccxt
from bingx_client import BingXClient, convert_ccxt_to_bingx_symbol, convert_bingx_to_ccxt_symbol, normalize_timeframe
from bingx_vst_client import BingXVSTClient
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ExchangeAdapter(ABC):
    """거래소 어댑터 추상 클래스"""
    
    def __init__(self, name: str, demo_mode: bool = True):
        self.name = name
        self.demo_mode = demo_mode
        self.connected = False
    
    @abstractmethod
    async def initialize(self, credentials: Dict[str, str]) -> bool:
        """거래소 초기화"""
        pass
    
    @abstractmethod
    async def close(self):
        """연결 종료"""
        pass
    
    @abstractmethod
    async def get_balance(self) -> Dict[str, float]:
        """잔고 조회"""
        pass
    
    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """티커 정보 조회"""
        pass
    
    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List]:
        """OHLCV 데이터 조회"""
        pass
    
    @abstractmethod
    async def place_market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        """시장가 주문"""
        pass
    
    @abstractmethod
    async def place_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict[str, Any]:
        """지정가 주문"""
        pass
    
    @abstractmethod
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        pass
    
    @abstractmethod
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        pass
    
    @abstractmethod
    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """포지션 조회"""
        pass

class BinanceAdapter(ExchangeAdapter):
    """바이낸스 어댑터 (CCXT 기반)"""
    
    def __init__(self, demo_mode: bool = True):
        super().__init__("binance", demo_mode)
        self.exchange = None
    
    async def initialize(self, credentials: Dict[str, str]) -> bool:
        """바이낸스 초기화"""
        try:
            self.exchange = ccxt.binance({
                'apiKey': credentials.get('api_key'),
                'secret': credentials.get('secret'),
                'sandbox': self.demo_mode,  # 테스트넷 사용
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'future'  # 선물 거래
                }
            })
            
            await self.exchange.load_markets()
            self.connected = True
            logger.info(f"Binance adapter initialized (demo: {self.demo_mode})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Binance adapter: {e}")
            self.connected = False
            return False
    
    async def close(self):
        """연결 종료"""
        if self.exchange:
            await self.exchange.close()
            self.connected = False
    
    async def get_balance(self) -> Dict[str, float]:
        """잔고 조회"""
        try:
            balance = await self.exchange.fetch_balance()
            return {
                'USDT': balance.get('USDT', {}).get('free', 0.0),
                'total': balance.get('USDT', {}).get('total', 0.0)
            }
        except Exception as e:
            logger.error(f"Failed to get Binance balance: {e}")
            return {}
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """티커 정보 조회"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return {
                'symbol': symbol,
                'last': ticker.get('last'),
                'bid': ticker.get('bid'),
                'ask': ticker.get('ask'),
                'volume': ticker.get('baseVolume'),
                'change': ticker.get('change'),
                'percentage': ticker.get('percentage'),
                'timestamp': ticker.get('timestamp')
            }
        except Exception as e:
            logger.error(f"Failed to get Binance ticker for {symbol}: {e}")
            return {}
    
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List]:
        """OHLCV 데이터 조회"""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            logger.error(f"Failed to get Binance OHLCV for {symbol}: {e}")
            return []
    
    async def place_market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        """시장가 주문"""
        try:
            order = await self.exchange.create_market_order(symbol, side.lower(), amount)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Failed to place Binance market order: {e}")
            return {'error': str(e)}
    
    async def place_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict[str, Any]:
        """지정가 주문"""
        try:
            order = await self.exchange.create_limit_order(symbol, side.lower(), amount, price)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Failed to place Binance limit order: {e}")
            return {'error': str(e)}
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            result = await self.exchange.cancel_order(order_id, symbol)
            return result
        except Exception as e:
            logger.error(f"Failed to cancel Binance order: {e}")
            return {'error': str(e)}
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        try:
            order = await self.exchange.fetch_order(order_id, symbol)
            return self._normalize_order(order)
        except Exception as e:
            logger.error(f"Failed to get Binance order status: {e}")
            return {'error': str(e)}
    
    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """포지션 조회"""
        try:
            positions = await self.exchange.fetch_positions()
            if symbol:
                positions = [p for p in positions if p['symbol'] == symbol]
            
            return [self._normalize_position(p) for p in positions if p['contracts'] > 0]
        except Exception as e:
            logger.error(f"Failed to get Binance positions: {e}")
            return []
    
    def _normalize_order(self, order: Dict) -> Dict[str, Any]:
        """주문 정보 정규화"""
        return {
            'id': order.get('id'),
            'symbol': order.get('symbol'),
            'side': order.get('side'),
            'amount': order.get('amount'),
            'price': order.get('price'),
            'status': order.get('status'),
            'type': order.get('type'),
            'timestamp': order.get('timestamp'),
            'filled': order.get('filled', 0),
            'remaining': order.get('remaining', 0),
            'fee': order.get('fee', {})
        }
    
    def _normalize_position(self, position: Dict) -> Dict[str, Any]:
        """포지션 정보 정규화"""
        return {
            'symbol': position.get('symbol'),
            'side': position.get('side'),
            'size': position.get('contracts', 0),
            'entry_price': position.get('entryPrice'),
            'mark_price': position.get('markPrice'),
            'pnl': position.get('unrealizedPnl', 0),
            'percentage': position.get('percentage', 0)
        }

class BingXAdapter(ExchangeAdapter):
    """BingX 어댑터"""
    
    def __init__(self, demo_mode: bool = True):
        super().__init__("bingx", demo_mode)
        self.client = None
    
    async def initialize(self, credentials: Dict[str, str]) -> bool:
        """BingX 초기화"""
        try:
            if self.demo_mode:
                # 데모 모드일 때는 VST 클라이언트 사용
                self.client = BingXVSTClient(
                    credentials.get('api_key', 'demo_key'),
                    credentials.get('secret', 'demo_secret')
                )
            else:
                # 실제 거래는 일반 BingX 클라이언트 사용
                self.client = BingXClient(
                    credentials.get('api_key'),
                    credentials.get('secret'),
                    demo_mode=self.demo_mode
                )
            
            # 연결 테스트 (VST는 항상 성공으로 가정)
            self.connected = True if self.demo_mode else self.client.test_connection()
            
            if self.connected:
                logger.info(f"BingX adapter initialized (demo: {self.demo_mode})")
            else:
                logger.error("BingX connection test failed")
            
            return self.connected
            
        except Exception as e:
            logger.error(f"Failed to initialize BingX adapter: {e}")
            self.connected = False
            return False
    
    async def close(self):
        """연결 종료"""
        if self.client:
            self.client.close()
            self.connected = False
    
    async def get_balance(self) -> Dict[str, float]:
        """잔고 조회"""
        try:
            balance_data = self.client.get_account_balance()
            
            if 'data' in balance_data:
                balance = balance_data['data']
                usdt_balance = 0.0
                
                if isinstance(balance, list):
                    for item in balance:
                        if item.get('asset') == 'USDT':
                            usdt_balance = float(item.get('availableMargin', 0))
                            break
                
                return {
                    'USDT': usdt_balance,
                    'total': usdt_balance
                }
            
            return {'USDT': 0.0, 'total': 0.0}
            
        except Exception as e:
            logger.error(f"Failed to get BingX balance: {e}")
            return {}
    
    async def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """티커 정보 조회"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol)
            
            # 가격 정보
            price_data = self.client.get_ticker_price(bingx_symbol)
            
            # 24시간 통계
            ticker_data = self.client.get_24hr_ticker(bingx_symbol)
            
            return {
                'symbol': symbol,
                'last': float(price_data.get('price', 0)) if price_data.get('price') else None,
                'bid': float(ticker_data.get('bidPrice', 0)) if ticker_data.get('bidPrice') else None,
                'ask': float(ticker_data.get('askPrice', 0)) if ticker_data.get('askPrice') else None,
                'volume': float(ticker_data.get('volume', 0)) if ticker_data.get('volume') else None,
                'change': float(ticker_data.get('priceChangePercent', 0)) if ticker_data.get('priceChangePercent') else None,
                'percentage': float(ticker_data.get('priceChangePercent', 0)) if ticker_data.get('priceChangePercent') else None,
                'timestamp': int(datetime.now().timestamp() * 1000)
            }
            
        except Exception as e:
            logger.error(f"Failed to get BingX ticker for {symbol}: {e}")
            return {}
    
    async def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> List[List]:
        """OHLCV 데이터 조회"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol)
            bingx_timeframe = normalize_timeframe(timeframe)
            
            # VST 클라이언트와 일반 클라이언트에 따라 다른 메서드 사용
            if isinstance(self.client, BingXVSTClient):
                # VST에서는 소문자 h 사용
                vst_timeframe = bingx_timeframe.replace('H', 'h')
                klines = self.client.get_kline_data(bingx_symbol, vst_timeframe, limit)
            else:
                klines = self.client.get_klines(bingx_symbol, bingx_timeframe, limit)
            
            # BingX 형식을 CCXT 형식으로 변환
            ohlcv = []
            for kline in klines:
                # VST 클라이언트는 딕셔너리 형태, 일반 클라이언트는 리스트 형태
                if isinstance(kline, dict):
                    # VST 클라이언트 형식
                    ohlcv.append([
                        int(kline.get('time', 0)),        # timestamp
                        float(kline.get('open', 0)),      # open
                        float(kline.get('high', 0)),      # high
                        float(kline.get('low', 0)),       # low
                        float(kline.get('close', 0)),     # close
                        float(kline.get('volume', 0))     # volume
                    ])
                elif len(kline) >= 6:
                    # 일반 클라이언트 형식
                    ohlcv.append([
                        int(kline[0]),      # timestamp
                        float(kline[1]),    # open
                        float(kline[2]),    # high
                        float(kline[3]),    # low
                        float(kline[4]),    # close
                        float(kline[5])     # volume
                    ])
            
            return ohlcv
            
        except Exception as e:
            logger.error(f"Failed to get BingX OHLCV for {symbol}: {e}")
            return []
    
    async def place_market_order(self, symbol: str, side: str, amount: float) -> Dict[str, Any]:
        """시장가 주문"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol)
            result = self.client.place_order(
                symbol=bingx_symbol,
                side=side.upper(),
                order_type="MARKET",
                quantity=amount
            )
            
            return self._normalize_order_result(result, symbol, side, amount)
            
        except Exception as e:
            logger.error(f"Failed to place BingX market order: {e}")
            return {'error': str(e)}
    
    async def place_limit_order(self, symbol: str, side: str, amount: float, price: float) -> Dict[str, Any]:
        """지정가 주문"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol)
            result = self.client.place_order(
                symbol=bingx_symbol,
                side=side.upper(),
                order_type="LIMIT",
                quantity=amount,
                price=price
            )
            
            return self._normalize_order_result(result, symbol, side, amount, price)
            
        except Exception as e:
            logger.error(f"Failed to place BingX limit order: {e}")
            return {'error': str(e)}
    
    async def cancel_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 취소"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol)
            return self.client.cancel_order(bingx_symbol, order_id)
        except Exception as e:
            logger.error(f"Failed to cancel BingX order: {e}")
            return {'error': str(e)}
    
    async def get_order_status(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """주문 상태 조회"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol)
            result = self.client.get_order_status(bingx_symbol, order_id)
            
            if 'data' in result:
                order_data = result['data']
                return {
                    'id': order_data.get('orderId'),
                    'symbol': symbol,
                    'side': order_data.get('side', '').lower(),
                    'amount': float(order_data.get('origQty', 0)),
                    'price': float(order_data.get('price', 0)),
                    'status': order_data.get('status', '').lower(),
                    'type': order_data.get('type', '').lower(),
                    'timestamp': int(order_data.get('time', 0)),
                    'filled': float(order_data.get('executedQty', 0)),
                    'remaining': float(order_data.get('origQty', 0)) - float(order_data.get('executedQty', 0))
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get BingX order status: {e}")
            return {'error': str(e)}
    
    async def get_positions(self, symbol: str = None) -> List[Dict[str, Any]]:
        """포지션 조회"""
        try:
            bingx_symbol = convert_ccxt_to_bingx_symbol(symbol) if symbol else None
            positions_data = self.client.get_positions(bingx_symbol)
            
            positions = []
            for pos in positions_data:
                if float(pos.get('positionAmt', 0)) != 0:  # 포지션이 있는 경우만
                    positions.append({
                        'symbol': convert_bingx_to_ccxt_symbol(pos.get('symbol', '')),
                        'side': 'long' if float(pos.get('positionAmt', 0)) > 0 else 'short',
                        'size': abs(float(pos.get('positionAmt', 0))),
                        'entry_price': float(pos.get('entryPrice', 0)),
                        'mark_price': float(pos.get('markPrice', 0)),
                        'pnl': float(pos.get('unRealizedProfit', 0)),
                        'percentage': float(pos.get('percentage', 0))
                    })
            
            return positions
            
        except Exception as e:
            logger.error(f"Failed to get BingX positions: {e}")
            return []
    
    def _normalize_order_result(self, result: Dict, symbol: str, side: str, amount: float, price: float = None) -> Dict[str, Any]:
        """주문 결과 정규화"""
        if 'error' in result:
            return result
        
        if 'data' in result:
            order_data = result['data']
            return {
                'id': order_data.get('orderId'),
                'symbol': symbol,
                'side': side.lower(),
                'amount': amount,
                'price': price,
                'status': 'open',
                'type': 'market' if not price else 'limit',
                'timestamp': int(datetime.now().timestamp() * 1000),
                'filled': 0,
                'remaining': amount
            }
        
        return result

class ExchangeFactory:
    """거래소 어댑터 팩토리"""
    
    @staticmethod
    def create_adapter(exchange_name: str, demo_mode: bool = True) -> ExchangeAdapter:
        """거래소 어댑터 생성"""
        exchange_name = exchange_name.lower()
        
        if exchange_name == 'binance':
            return BinanceAdapter(demo_mode)
        elif exchange_name == 'bingx':
            return BingXAdapter(demo_mode)
        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")
    
    @staticmethod
    def get_supported_exchanges() -> List[str]:
        """지원되는 거래소 목록"""
        return ['binance', 'bingx']

# ============= 유틸리티 함수 =============

async def test_exchange_adapter(adapter: ExchangeAdapter, credentials: Dict[str, str]):
    """거래소 어댑터 테스트"""
    print(f"\n=== Testing {adapter.name} adapter ===")
    
    # 초기화
    success = await adapter.initialize(credentials)
    print(f"Initialization: {'✓' if success else '✗'}")
    
    if not success:
        return
    
    try:
        # 잔고 조회
        balance = await adapter.get_balance()
        print(f"Balance: {balance}")
        
        # 티커 조회
        ticker = await adapter.get_ticker('BTC/USDT')
        print(f"BTC/USDT ticker: {ticker.get('last', 'N/A')}")
        
        # OHLCV 조회
        ohlcv = await adapter.get_ohlcv('BTC/USDT', '1h', 5)
        print(f"OHLCV data points: {len(ohlcv)}")
        
        # 포지션 조회
        positions = await adapter.get_positions()
        print(f"Open positions: {len(positions)}")
        
    except Exception as e:
        print(f"Test error: {e}")
    
    finally:
        await adapter.close()

if __name__ == "__main__":
    import os
    import asyncio
    
    # 환경 변수에서 자격 증명 읽기
    binance_creds = {
        'api_key': os.getenv('BINANCE_API_KEY', ''),
        'secret': os.getenv('BINANCE_SECRET', '')
    }
    
    bingx_creds = {
        'api_key': os.getenv('BINGX_API_KEY', ''),
        'secret': os.getenv('BINGX_SECRET_KEY', '')
    }
    
    async def main():
        # BingX 어댑터 테스트
        if bingx_creds['api_key']:
            bingx_adapter = ExchangeFactory.create_adapter('bingx', demo_mode=True)
            await test_exchange_adapter(bingx_adapter, bingx_creds)
        
        # 바이낸스 어댑터 테스트
        if binance_creds['api_key']:
            binance_adapter = ExchangeFactory.create_adapter('binance', demo_mode=True)
            await test_exchange_adapter(binance_adapter, binance_creds)
    
    asyncio.run(main())