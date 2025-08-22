"""
실시간 트레이딩 엔진
- 다중 거래소(바이낸스, BingX) 지원
- 실시간 OHLCV 데이터 수집
- 새로운 캔들 생성 시마다 지표 계산 및 신호 감지
- 자동 주문 실행
- 데모 트레이딩 및 실거래 모드 지원
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import json
from persistent_storage import persistent_storage
from advanced_indicators import AdvancedIndicators
from position_manager import position_manager, Position
from risk_manager import risk_manager, RiskLimits
from exchange_adapter import ExchangeFactory, ExchangeAdapter
from strategy import (
    bollinger_bands_strategy,
    macd_stochastic_strategy,
    williams_r_mean_reversion_strategy,
    multi_indicator_strategy,
    generate_cci_signals
)

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealtimeTradingEngine:
    def __init__(self):
        self.exchanges = {}
        self.active_monitors = {}  # symbol별 모니터링 상태
        self.candle_data = {}  # symbol별 캔들 데이터 저장
        self.indicators = AdvancedIndicators()
        self.strategy_functions = {
            'CCI': self._cci_strategy_wrapper,
            'MACD': macd_stochastic_strategy,
            'RSI': self._rsi_strategy_wrapper,
            'SMA': self._sma_strategy_wrapper,
            'Bollinger': bollinger_bands_strategy,
            'bollinger_bands': bollinger_bands_strategy,
            'macd_stochastic': macd_stochastic_strategy,
            'williams_r_mean_reversion': williams_r_mean_reversion_strategy,
            'multi_indicator': multi_indicator_strategy
        }
        self.running = False
        
    async def initialize_exchange(self, exchange_name: str, api_key: str, secret: str, demo_mode: bool = True):
        """거래소 초기화 (다중 거래소 지원)"""
        try:
            # ExchangeAdapter를 사용하여 거래소 생성
            adapter = ExchangeFactory.create_adapter(exchange_name.lower(), demo_mode=demo_mode)
            
            # 자격 증명으로 초기화
            credentials = {
                'api_key': api_key,
                'secret': secret
            }
            
            success = await adapter.initialize(credentials)
            
            if success:
                self.exchanges[exchange_name] = adapter
                logger.info(f"Exchange {exchange_name} initialized successfully (demo: {demo_mode})")
                return True
            else:
                logger.error(f"Failed to initialize exchange {exchange_name}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to initialize exchange {exchange_name}: {e}")
            return False
    
    async def get_recent_candles(self, exchange_name: str, symbol: str, timeframe: str, limit: int = 100):
        """최근 캔들 데이터 가져오기"""
        try:
            adapter = self.exchanges.get(exchange_name)
            if not adapter:
                raise ValueError(f"Exchange {exchange_name} not initialized")
                
            ohlcv = await adapter.get_ohlcv(symbol, timeframe, limit)
            return ohlcv
            
        except Exception as e:
            logger.error(f"Failed to fetch candles for {symbol}: {e}")
            return []
    
    async def start_monitoring_symbol(self, user_id: str, exchange_name: str, symbol: str, timeframe: str, strategies: List[Dict]):
        """특정 심볼에 대한 실시간 모니터링 시작"""
        monitor_key = f"{user_id}_{exchange_name}_{symbol}_{timeframe}"
        
        if monitor_key in self.active_monitors:
            logger.warning(f"Already monitoring {monitor_key}")
            return
        
        # 거래소가 초기화되어 있는지 확인
        if exchange_name not in self.exchanges:
            logger.error(f"Exchange {exchange_name} not initialized. Please initialize exchange first.")
            return
        
        # 초기 캔들 데이터 로드
        initial_candles = await self.get_recent_candles(exchange_name, symbol, timeframe, 200)
        if not initial_candles:
            logger.error(f"Failed to load initial candles for {symbol}")
            return
            
        self.candle_data[monitor_key] = initial_candles
        self.active_monitors[monitor_key] = {
            'user_id': user_id,
            'exchange_name': exchange_name,
            'symbol': symbol,
            'timeframe': timeframe,
            'strategies': strategies,
            'last_candle_time': initial_candles[-1][0] if initial_candles else 0
        }
        
        logger.info(f"Started monitoring {symbol} for user {user_id}")
        
        # 모니터링 태스크 시작
        asyncio.create_task(self._monitor_symbol(monitor_key))
    
    async def _monitor_symbol(self, monitor_key: str):
        """심볼 모니터링 메인 루프"""
        monitor_info = self.active_monitors[monitor_key]
        exchange_name = monitor_info['exchange_name']
        symbol = monitor_info['symbol']
        timeframe = monitor_info['timeframe']
        
        # 타임프레임별 대기 시간 설정 (초) - 빠른 신호 감지를 위해 더 자주 체크
        timeframe_seconds = {
            '1m': 30,     # 1분 봉은 30초마다 체크
            '5m': 30,     # 5분 봉은 30초마다 체크 (빠른 감지)
            '15m': 60,    # 15분 봉은 1분마다 체크
            '1h': 300,    # 1시간 봉은 5분마다 체크
            '4h': 900,    # 4시간 봉은 15분마다 체크
            '1d': 3600    # 일봉은 1시간마다 체크
        }
        
        wait_seconds = timeframe_seconds.get(timeframe, 30)
        
        while monitor_key in self.active_monitors and self.running:
            try:
                # 새로운 캔들 확인
                latest_candles = await self.get_recent_candles(exchange_name, symbol, timeframe, 5)
                
                if latest_candles and len(latest_candles) > 0:
                    latest_candle = latest_candles[-1]
                    latest_time = latest_candle[0]
                    
                    # 새로운 캔들이 완성되었는지 확인
                    if latest_time > monitor_info['last_candle_time']:
                        # 캔들 데이터 업데이트
                        self.candle_data[monitor_key].append(latest_candle)
                        
                        # 오래된 데이터 제거 (최근 200개만 유지)
                        if len(self.candle_data[monitor_key]) > 200:
                            self.candle_data[monitor_key] = self.candle_data[monitor_key][-200:]
                        
                        monitor_info['last_candle_time'] = latest_time
                        
                        logger.info(f"New candle detected for {symbol}: {datetime.fromtimestamp(latest_time/1000)}")
                        
                        # 포지션 현재가 업데이트
                        await self._update_positions_price(monitor_key, latest_candle[4])  # 종가 사용
                        
                        # 손절/익절 확인
                        await self._check_stop_loss_take_profit(monitor_key)
                        
                        # 전략 신호 확인 및 실행
                        await self._check_and_execute_strategies(monitor_key)
                
                # 대기
                await asyncio.sleep(wait_seconds)
                
            except Exception as e:
                logger.error(f"Error monitoring {symbol}: {e}")
                await asyncio.sleep(30)  # 에러 발생시 30초 대기
    
    async def _check_and_execute_strategies(self, monitor_key: str):
        """전략 신호 확인 및 실행"""
        monitor_info = self.active_monitors[monitor_key]
        user_id = monitor_info['user_id']
        exchange_name = monitor_info['exchange_name']
        symbol = monitor_info['symbol']
        strategies = monitor_info['strategies']
        candle_data = self.candle_data[monitor_key]
        
        if len(candle_data) < 50:  # 최소 데이터 요구사항
            logger.warning(f"Insufficient data for {symbol} strategies")
            return
        
        for strategy_config in strategies:
            try:
                if not strategy_config.get('is_active', False):
                    continue
                    
                strategy_name = strategy_config.get('strategy_type')
                strategy_params = strategy_config.get('parameters', {})
                
                # 전략 함수 실행
                strategy_func = self.strategy_functions.get(strategy_name)
                if not strategy_func:
                    logger.warning(f"Unknown strategy: {strategy_name}")
                    continue
                
                signals = strategy_func(candle_data, **strategy_params)
                
                # 최신 신호 확인
                if signals and len(signals) > 0:
                    latest_signal = signals[-1]
                    signal_time = latest_signal.get('timestamp', 0)
                    current_time = datetime.now().timestamp() * 1000
                    
                    # 5분 이내의 신호만 처리 (지연 신호 방지)
                    if current_time - signal_time <= 300000:  # 5분 = 300,000ms
                        await self._execute_signal(
                            user_id, 
                            exchange_name, 
                            symbol, 
                            latest_signal, 
                            strategy_config
                        )
                
            except Exception as e:
                logger.error(f"Error checking strategy {strategy_config.get('strategy_type')}: {e}")
    
    async def _execute_signal(self, user_id: str, exchange_name: str, symbol: str, 
                            signal: Dict, strategy_config: Dict):
        """신호 실행"""
        try:
            signal_type = signal.get('signal')
            price = signal.get('price')
            reason = signal.get('reason', '')
            
            if signal_type not in ['buy', 'sell']:
                return
            
            # 포지션 확인
            current_position = await self._get_current_position(user_id, exchange_name, symbol)
            
            # 매수 신호이고 포지션이 없는 경우
            if signal_type == 'buy' and current_position == 0:
                await self._place_buy_order(user_id, exchange_name, symbol, strategy_config, price, reason)
            
            # 매도 신호이고 롱 포지션이 있는 경우
            elif signal_type == 'sell' and current_position > 0:
                await self._place_sell_order(user_id, exchange_name, symbol, strategy_config, price, reason, current_position)
                
        except Exception as e:
            logger.error(f"Error executing signal for {symbol}: {e}")
    
    async def _update_positions_price(self, monitor_key: str, current_price: float):
        """모니터링 중인 심볼의 모든 포지션 현재가 업데이트"""
        try:
            monitor_info = self.active_monitors[monitor_key]
            user_id = monitor_info['user_id']
            symbol = monitor_info['symbol']
            
            # 해당 심볼의 열린 포지션들 조회 및 업데이트
            open_positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
            
            for position in open_positions:
                position_manager.update_position_price(position.position_id, current_price)
                
        except Exception as e:
            logger.error(f"Error updating positions price: {e}")
    
    async def _check_stop_loss_take_profit(self, monitor_key: str):
        """손절/익절 조건 확인 및 실행"""
        try:
            monitor_info = self.active_monitors[monitor_key]
            user_id = monitor_info['user_id']
            exchange_name = monitor_info['exchange_name']
            symbol = monitor_info['symbol']
            
            # 해당 심볼의 열린 포지션들 확인
            open_positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
            
            for position in open_positions:
                trigger = position_manager.check_stop_loss_take_profit(position.position_id)
                
                if trigger:
                    # 손절/익절 주문 실행
                    await self._execute_position_close(position, trigger)
                    
        except Exception as e:
            logger.error(f"Error checking stop loss/take profit: {e}")
    
    async def _execute_position_close(self, position: Position, reason: str):
        """포지션 청산 실행"""
        try:
            adapter = self.exchanges.get(position.exchange_name)
            if not adapter:
                logger.error(f"Exchange {position.exchange_name} not available")
                return
            
            # 청산 주문 실행
            if position.side == 'long':
                order = await adapter.place_market_order(position.symbol, 'sell', position.quantity)
            else:  # short
                order = await adapter.place_market_order(position.symbol, 'buy', position.quantity)
            
            close_price = order.get('price', position.current_price)
            
            # 포지션 상태 업데이트
            position_manager.close_position(position.position_id, close_price, reason)
            
            logger.info(f"Position closed: {position.position_id}, Reason: {reason}, PnL: {position.realized_pnl}")
            
            # 거래 기록 저장
            await self._save_trade_record(
                position.user_id, position.exchange_name, position.symbol,
                'sell' if position.side == 'long' else 'buy',
                position.quantity, close_price, f"Auto {reason}", order,
                {'strategy_id': position.strategy_id}
            )
            
        except Exception as e:
            logger.error(f"Error executing position close: {e}")
    
    async def _get_current_position(self, user_id: str, exchange_name: str, symbol: str) -> float:
        """현재 포지션 수량 조회 (모든 열린 포지션의 총 수량)"""
        try:
            open_positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
            total_quantity = sum(
                position.quantity if position.side == 'long' else -position.quantity 
                for position in open_positions
            )
            return total_quantity
        except Exception as e:
            logger.error(f"Error getting position for {symbol}: {e}")
            return 0
    
    async def _place_buy_order(self, user_id: str, exchange_name: str, symbol: str, 
                             strategy_config: Dict, price: float, reason: str):
        """매수 주문 실행"""
        try:
            allocated_capital = strategy_config.get('allocated_capital', 100)  # USDT
            stop_loss_pct = strategy_config.get('stop_loss_pct', 5.0)
            take_profit_pct = strategy_config.get('take_profit_pct', 10.0)
            
            # 손절가 계산
            stop_loss_price = price * (1 - stop_loss_pct / 100)
            
            # 리스크 관리자를 통한 포지션 크기 계산
            position_size = risk_manager.calculate_position_size(
                user_id, allocated_capital, price, stop_loss_price, 
                method=strategy_config.get('position_sizing_method', 'fixed_fractional')
            )
            
            # 리스크 한도 확인
            risk_check = risk_manager.check_risk_limits(user_id, symbol, position_size, price)
            
            if not risk_check['allowed']:
                logger.warning(f"Risk check failed for {symbol}: {risk_check['violations']}")
                # 권장 포지션 크기로 조정
                position_size = risk_check.get('recommended_size', position_size * 0.5)
                
                # 재검사
                risk_check = risk_manager.check_risk_limits(user_id, symbol, position_size, price)
                if not risk_check['allowed']:
                    logger.error(f"Risk limits prevent opening position for {symbol}")
                    return
            
            adapter = self.exchanges.get(exchange_name)
            if not adapter:
                logger.error(f"Exchange {exchange_name} not available")
                return
            
            # 시장가 매수 주문
            order = await adapter.place_market_order(symbol, 'buy', position_size)
            actual_price = order.get('price', price)
            actual_quantity = order.get('amount', position_size)
            
            logger.info(f"Buy order placed for {symbol}: {order}")
            
            # 포지션 생성
            position = position_manager.create_position(
                user_id=user_id,
                exchange_name=exchange_name,
                symbol=symbol,
                strategy_id=strategy_config.get('id', 0),
                side='long',
                entry_price=actual_price,
                quantity=actual_quantity,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct
            )
            
            # 주문 기록 저장
            await self._save_trade_record(user_id, exchange_name, symbol, 'buy', 
                                        actual_quantity, actual_price, reason, order, strategy_config)
            
        except Exception as e:
            logger.error(f"Error placing buy order for {symbol}: {e}")
    
    async def _place_sell_order(self, user_id: str, exchange_name: str, symbol: str,
                              strategy_config: Dict, price: float, reason: str, amount: float):
        """매도 주문 실행 (전략 신호에 의한 포지션 청산)"""
        try:
            # 청산할 포지션 찾기 (FIFO 방식)
            open_positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
            long_positions = [p for p in open_positions if p.side == 'long']
            
            if not long_positions:
                logger.warning(f"No long positions found for {symbol} to sell")
                return
            
            adapter = self.exchanges.get(exchange_name)
            if not adapter:
                logger.error(f"Exchange {exchange_name} not available")
                return
            
            # 가장 오래된 포지션부터 청산
            for position in sorted(long_positions, key=lambda x: x.entry_time):
                if amount <= 0:
                    break
                    
                sell_quantity = min(amount, position.quantity)
                
                # 시장가 매도 주문
                order = await adapter.place_market_order(symbol, 'sell', sell_quantity)
                close_price = order.get('price', price)
                
                # 포지션 청산 (부분 청산 처리)
                if sell_quantity == position.quantity:
                    # 전체 청산
                    position_manager.close_position(position.position_id, close_price, f"Strategy: {reason}")
                else:
                    # 부분 청산 - 새로운 포지션으로 분할
                    remaining_quantity = position.quantity - sell_quantity
                    
                    # 기존 포지션 청산
                    position_manager.close_position(position.position_id, close_price, f"Partial Strategy: {reason}")
                    
                    # 남은 수량으로 새 포지션 생성
                    new_position = position_manager.create_position(
                        user_id=user_id,
                        exchange_name=exchange_name,
                        symbol=symbol,
                        strategy_id=position.strategy_id,
                        side='long',
                        entry_price=position.entry_price,
                        quantity=remaining_quantity,
                        stop_loss_pct=0,  # 기존 손절가 유지
                        take_profit_pct=0  # 기존 익절가 유지
                    )
                    new_position.stop_loss = position.stop_loss
                    new_position.take_profit = position.take_profit
                
                logger.info(f"Sell order placed for {symbol}: {order}")
                
                # 주문 기록 저장
                await self._save_trade_record(user_id, exchange_name, symbol, 'sell',
                                            sell_quantity, close_price, reason, order, strategy_config)
                
                amount -= sell_quantity
            
        except Exception as e:
            logger.error(f"Error placing sell order for {symbol}: {e}")
    
    async def _save_trade_record(self, user_id: str, exchange_name: str, symbol: str,
                               order_type: str, amount: float, price: float, reason: str,
                               order: Dict, strategy_config: Dict):
        """거래 기록 저장"""
        try:
            trade_record = {
                'user_id': user_id,
                'strategy_id': strategy_config.get('id'),
                'exchange_name': exchange_name,
                'symbol': symbol,
                'order_type': order_type,
                'amount': amount,
                'price': price,
                'order_id': order.get('id'),
                'status': order.get('status', 'pending'),
                'fee': order.get('fee', {}),
                'timestamp': datetime.now(),
                'reason': reason,
                'auto_executed': True
            }
            
            # 데이터베이스에 저장 (추후 구현)
            logger.info(f"Trade record saved: {trade_record}")
            
        except Exception as e:
            logger.error(f"Error saving trade record: {e}")
    
    async def stop_monitoring_symbol(self, user_id: str, exchange_name: str, symbol: str, timeframe: str):
        """심볼 모니터링 중지"""
        monitor_key = f"{user_id}_{exchange_name}_{symbol}_{timeframe}"
        
        if monitor_key in self.active_monitors:
            del self.active_monitors[monitor_key]
            if monitor_key in self.candle_data:
                del self.candle_data[monitor_key]
            logger.info(f"Stopped monitoring {symbol} for user {user_id}")
    
    async def start_engine(self):
        """트레이딩 엔진 시작"""
        self.running = True
        logger.info("Realtime Trading Engine started")
    
    async def stop_engine(self):
        """트레이딩 엔진 중지"""
        self.running = False
        self.active_monitors.clear()
        self.candle_data.clear()
        
        # 모든 거래소 연결 종료
        for exchange in self.exchanges.values():
            await exchange.close()
        
        self.exchanges.clear()
        logger.info("Realtime Trading Engine stopped")
    
    def _cci_strategy_wrapper(self, ohlcv_data, **params):
        """CCI 전략 래퍼"""
        try:
            window = params.get('window', 20)
            buy_threshold = params.get('buy_threshold', -100)
            sell_threshold = params.get('sell_threshold', 100)
            
            # generate_cci_signals 함수 호출
            df_signals = generate_cci_signals(ohlcv_data, window, buy_threshold, sell_threshold)
            
            # DataFrame을 dict 리스트로 변환
            signals = []
            timestamps = [candle[0] for candle in ohlcv_data]
            prices = [candle[4] for candle in ohlcv_data]  # 종가
            
            for i, signal_value in enumerate(df_signals['signal']):
                if signal_value != 0:  # 신호가 있는 경우만
                    signals.append({
                        'timestamp': timestamps[i],
                        'signal': 'buy' if signal_value == 1 else 'sell',
                        'price': prices[i],
                        'reason': f'CCI신호 (임계값: {buy_threshold}/{sell_threshold})'
                    })
            
            return signals
            
        except Exception as e:
            logger.error(f"Error in CCI strategy: {e}")
            return []
    
    def _rsi_strategy_wrapper(self, ohlcv_data, **params):
        """RSI 전략 래퍼"""
        try:
            window = params.get('window', 14)
            buy_threshold = params.get('buy_threshold', 30)
            sell_threshold = params.get('sell_threshold', 70)
            
            if len(ohlcv_data) < window + 10:
                return []
            
            closes = [candle[4] for candle in ohlcv_data]
            timestamps = [candle[0] for candle in ohlcv_data]
            
            # RSI 계산
            rsi_values = self.indicators.rsi(closes, window)
            
            signals = []
            for i in range(1, len(rsi_values)):
                if rsi_values[i] is None or rsi_values[i-1] is None:
                    continue
                
                # 과매도에서 상승 → 매수
                if rsi_values[i-1] <= buy_threshold and rsi_values[i] > buy_threshold:
                    signals.append({
                        'timestamp': timestamps[i],
                        'signal': 'buy',
                        'price': closes[i],
                        'reason': f'RSI과매도반등 (RSI:{rsi_values[i]:.1f})'
                    })
                
                # 과매수에서 하락 → 매도
                elif rsi_values[i-1] >= sell_threshold and rsi_values[i] < sell_threshold:
                    signals.append({
                        'timestamp': timestamps[i],
                        'signal': 'sell',
                        'price': closes[i],
                        'reason': f'RSI과매수하락 (RSI:{rsi_values[i]:.1f})'
                    })
            
            return signals
            
        except Exception as e:
            logger.error(f"Error in RSI strategy: {e}")
            return []
    
    def _sma_strategy_wrapper(self, ohlcv_data, **params):
        """SMA 전략 래퍼 (이동평균선 교차)"""
        try:
            short_window = params.get('short_window', 10)
            long_window = params.get('long_window', 50)
            
            if len(ohlcv_data) < long_window + 10:
                return []
            
            closes = [candle[4] for candle in ohlcv_data]
            timestamps = [candle[0] for candle in ohlcv_data]
            
            # SMA 계산
            short_sma = self.indicators.sma(closes, short_window)
            long_sma = self.indicators.sma(closes, long_window)
            
            signals = []
            for i in range(1, len(closes)):
                if (short_sma[i] is None or short_sma[i-1] is None or 
                    long_sma[i] is None or long_sma[i-1] is None):
                    continue
                
                # 골든크로스 → 매수
                if short_sma[i-1] <= long_sma[i-1] and short_sma[i] > long_sma[i]:
                    signals.append({
                        'timestamp': timestamps[i],
                        'signal': 'buy',
                        'price': closes[i],
                        'reason': f'SMA골든크로스 ({short_window}/{long_window})'
                    })
                
                # 데드크로스 → 매도
                elif short_sma[i-1] >= long_sma[i-1] and short_sma[i] < long_sma[i]:
                    signals.append({
                        'timestamp': timestamps[i],
                        'signal': 'sell',
                        'price': closes[i],
                        'reason': f'SMA데드크로스 ({short_window}/{long_window})'
                    })
            
            return signals
            
        except Exception as e:
            logger.error(f"Error in SMA strategy: {e}")
            return []

# 글로벌 인스턴스
trading_engine = RealtimeTradingEngine()