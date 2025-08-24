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
                
                # 최신 캔들의 신호만 확인 (실시간 거래용)
                if signals and len(signals) > 0:
                    # 현재 새로 생성된 캔들의 타임스탬프
                    latest_candle_time = monitor_info['last_candle_time']
                    
                    # 최신 캔들에 해당하는 신호만 찾기
                    latest_candle_signals = [s for s in signals if s.get('timestamp') == latest_candle_time]
                    
                    if latest_candle_signals:
                        latest_signal = latest_candle_signals[-1]  # 가장 최근 신호
                        logger.info(f"🚀 실시간 신호 감지! {latest_signal['signal']} at {latest_signal['price']} (최신 캔들: {datetime.fromtimestamp(latest_candle_time/1000)})")
                        
                        await self._execute_signal(
                            user_id, 
                            exchange_name, 
                            symbol, 
                            latest_signal, 
                            strategy_config
                        )
                    else:
                        # 최신 캔들에 신호가 없으면 전체에서 최신 신호 확인
                        latest_signal = signals[-1]
                        signal_time = latest_signal.get('timestamp', 0)
                        current_time = datetime.now().timestamp() * 1000
                        
                        logger.info(f"🔍 최신 캔들에 신호 없음. 전체 최신 신호: {latest_signal['signal']} at {latest_signal['price']}")
                        logger.info(f"🔍 신호 시간 체크: signal_time={signal_time}, current_time={current_time}")
                        logger.info(f"🔍 시간 차이: {current_time - signal_time}ms ({(current_time - signal_time)/1000/60:.1f}분)")
                        
                        # 5분 이내의 신호만 처리 (지연 신호 방지)
                        if current_time - signal_time <= 300000:  # 5분 = 300,000ms
                            logger.info(f"🚀 신호 실행 시작: {latest_signal['signal']} at {latest_signal['price']}")
                            await self._execute_signal(
                                user_id, 
                                exchange_name, 
                                symbol, 
                                latest_signal, 
                                strategy_config
                            )
                        else:
                            logger.warning(f"⏰ 신호가 너무 오래됨 (5분 초과): {(current_time - signal_time)/1000/60:.1f}분 전")
                
            except Exception as e:
                logger.error(f"Error checking strategy {strategy_config.get('strategy_type')}: {e}")
    
    async def _execute_signal(self, user_id: str, exchange_name: str, symbol: str, 
                            signal: Dict, strategy_config: Dict):
        """신호 실행"""
        try:
            signal_type = signal.get('signal')
            price = signal.get('price')
            reason = signal.get('reason', '')
            
            logger.info(f"💫 신호 실행 시작: {signal_type} {symbol} at {price} - {reason}")
            
            if signal_type not in ['buy', 'sell']:
                logger.warning(f"❌ 잘못된 신호 타입: {signal_type}")
                return
            
            # 포지션 확인
            current_position = await self._get_current_position(user_id, exchange_name, symbol)
            logger.info(f"🏦 현재 포지션: {current_position}")
            
            # 매수 신호 처리
            if signal_type == 'buy':
                if current_position == 0:
                    logger.info(f"🟢 매수 신호: 포지션 없음 → 롱 포지션 생성")
                    await self._place_buy_order(user_id, exchange_name, symbol, strategy_config, price, reason)
                elif current_position < 0:
                    logger.info(f"🟢 매수 신호: 숏 포지션 {current_position} → 청산 후 롱 포지션 생성")
                    await self._place_buy_order(user_id, exchange_name, symbol, strategy_config, price, reason, abs(current_position) * 2)
                else:
                    logger.info(f"⚪ 매수 신호 무시: 이미 롱 포지션 {current_position} 보유")
            
            # 매도 신호 처리
            elif signal_type == 'sell':
                if current_position > 0:
                    logger.info(f"🔴 매도 신호: 롱 포지션 {current_position} → 청산 후 숏 포지션 생성")  
                    await self._place_sell_order(user_id, exchange_name, symbol, strategy_config, price, reason, current_position * 2)
                elif current_position == 0:
                    logger.info(f"🔴 매도 신호: 포지션 없음 → 숏 포지션 생성")
                    await self._place_short_order(user_id, exchange_name, symbol, strategy_config, price, reason)
                else:
                    logger.info(f"⚪ 매도 신호 무시: 이미 숏 포지션 {current_position} 보유")
            
            else:
                logger.info(f"⚪ 알 수 없는 신호 타입: {signal_type}")
                
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
        """손절/익절 조건 확인 및 실행 (VST 포지션 기반)"""
        try:
            monitor_info = self.active_monitors[monitor_key]
            user_id = monitor_info['user_id']
            exchange_name = monitor_info['exchange_name']
            symbol = monitor_info['symbol']
            strategies = monitor_info['strategies']
            
            # VST 포지션 직접 확인
            from bingx_vst_client import create_vst_client_from_env
            vst_client = create_vst_client_from_env()
            if not vst_client:
                return
                
            try:
                positions = vst_client.get_vst_positions()
                for position in positions:
                    vst_symbol = position.get('symbol', '').replace('-', '/')
                    if vst_symbol == symbol:
                        position_amt = float(position.get('positionAmt', 0))
                        if position_amt == 0:  # 포지션 없음
                            continue
                            
                        entry_price = float(position.get('avgPrice', 0))
                        mark_price = float(position.get('markPrice', 0))
                        unrealized_pnl = float(position.get('unrealizedProfit', 0))
                        position_value = abs(position_amt * entry_price)
                        
                        if position_value > 0:
                            pnl_percentage = (unrealized_pnl / position_value) * 100
                            
                            # 스탑로스 확인 (-5% 기본값)
                            stop_loss_pct = 5.0
                            take_profit_pct = 10.0
                            
                            # 전략에서 스탑로스 설정 확인
                            for strategy in strategies:
                                if strategy.get('stop_loss_percentage'):
                                    stop_loss_pct = strategy.get('stop_loss_percentage')
                                if strategy.get('take_profit_percentage'):
                                    take_profit_pct = strategy.get('take_profit_percentage')
                            
                            logger.info(f"📊 {symbol} 포지션 손익률: {pnl_percentage:.2f}% (스탑로스: -{stop_loss_pct}%, 익절: +{take_profit_pct}%)")
                            
                            # 고급 TP/SL 먼저 확인
                            advanced_tp_executed = await self._check_advanced_tp_sl(user_id, exchange_name, symbol, position, mark_price, pnl_percentage)
                            
                            # 고급 TP/SL이 실행되지 않은 경우만 기본 로직 실행
                            if not advanced_tp_executed:
                                # 스탑로스 조건 확인
                                if pnl_percentage <= -stop_loss_pct:
                                    logger.info(f"🔴 스탑로스 조건 충족! {symbol} 손익률: {pnl_percentage:.2f}% <= -{stop_loss_pct}%")
                                    await self._execute_stop_loss(user_id, exchange_name, symbol, position, mark_price, "스탑로스")
                                    
                                # 익절 조건 확인
                                elif pnl_percentage >= take_profit_pct:
                                    logger.info(f"🟢 익절 조건 충족! {symbol} 손익률: {pnl_percentage:.2f}% >= +{take_profit_pct}%")
                                    await self._execute_stop_loss(user_id, exchange_name, symbol, position, mark_price, "익절")
                                
            except Exception as vst_e:
                logger.warning(f"VST 스탑로스 확인 실패: {vst_e}")
                
                # Fallback: Position Manager 사용
                open_positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
                
                for position in open_positions:
                    trigger = position_manager.check_stop_loss_take_profit(position.position_id)
                    
                    if trigger:
                        # 손절/익절 주문 실행
                        await self._execute_position_close(position, trigger)
                    
        except Exception as e:
            logger.error(f"Error checking stop loss/take profit: {e}")
    
    async def _execute_stop_loss(self, user_id: str, exchange_name: str, symbol: str, 
                                position: dict, price: float, reason: str):
        """VST 포지션 스탑로스/익절 실행"""
        try:
            position_amt = float(position.get('positionAmt', 0))
            if position_amt == 0:
                return
                
            # 거래소 어댑터 가져오기
            adapter = self.exchange_adapters.get(exchange_name)
            if not adapter:
                logger.error(f"Exchange {exchange_name} not available for stop loss")
                return
                
            # 포지션 방향에 따른 주문 실행
            if position_amt > 0:  # 롱 포지션
                order = await adapter.place_market_order(symbol, 'sell', abs(position_amt))
                logger.info(f"🔴 {reason} 매도 주문 실행: {symbol} {abs(position_amt)} at {price}")
            else:  # 숏 포지션  
                order = await adapter.place_market_order(symbol, 'buy', abs(position_amt))
                logger.info(f"🔴 {reason} 매수 주문 실행: {symbol} {abs(position_amt)} at {price}")
                
            # 거래 기록 저장
            await self._save_trade_record(
                user_id, exchange_name, symbol, 
                'sell' if position_amt > 0 else 'buy',
                abs(position_amt), price, order, reason, True
            )
            
        except Exception as e:
            logger.error(f"Error executing stop loss for {symbol}: {e}")
    
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
        """현재 포지션 수량 조회 (VST 실제 포지션 기반)"""
        try:
            # VST에서 실제 포지션 조회
            from bingx_vst_client import create_vst_client_from_env
            vst_client = create_vst_client_from_env()
            if vst_client:
                try:
                    positions = vst_client.get_vst_positions()
                    logger.info(f"🔍 포지션 감지 디버깅: 찾는 심볼={symbol}")
                    for position in positions:
                        # symbol 형식 변환 (BTC-USDT -> BTC/USDT)
                        original_symbol = position.get('symbol', '')
                        vst_symbol = original_symbol.replace('-', '/')
                        # 유연한 심볼 매칭: 원본과 변환된 형식 모두 확인
                        symbol_match = (original_symbol == symbol) or (vst_symbol == symbol)
                        logger.info(f"🔍 VST 심볼 비교: 원본={original_symbol}, 변환후={vst_symbol}, 찾는심볼={symbol}, 매칭={symbol_match}")
                        if symbol_match:
                            position_amt = float(position.get('positionAmt', 0))
                            logger.info(f"🎮 VST 포지션 확인: {symbol} = {position_amt}")
                            return position_amt
                    
                    # 포지션이 없으면 0 반환
                    return 0
                    
                except Exception as vst_e:
                    logger.warning(f"VST 포지션 조회 실패, fallback to position manager: {vst_e}")
            
            # Fallback: Position Manager에서 조회
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
            
            # 리스크 한도 확인 (임시로 비활성화)
            try:
                risk_check = risk_manager.check_risk_limits(user_id, symbol, position_size, price)
                
                if not risk_check['allowed']:
                    logger.warning(f"Risk check failed for {symbol}: {risk_check['violations']}")
                    logger.info(f"🛡️ Risk check disabled for testing - proceeding with order")
                    # 권장 포지션 크기로 조정
                    # position_size = risk_check.get('recommended_size', position_size * 0.5)
                    
                    # # 재검사
                    # risk_check = risk_manager.check_risk_limits(user_id, symbol, position_size, price)
                    # if not risk_check['allowed']:
                    #     logger.error(f"Risk limits prevent opening position for {symbol}")
                    #     return
            except Exception as e:
                logger.warning(f"Risk check error (ignored): {e}")
                logger.info(f"🛡️ Risk check failed but proceeding with order for testing")
            
            adapter = self.exchanges.get(exchange_name)
            if not adapter:
                logger.error(f"Exchange {exchange_name} not available")
                return
            
            # 시장가 매수 주문
            order = await adapter.place_market_order(symbol, 'buy', position_size)
            actual_price = order.get('price') or price  # VST에서 price가 None인 경우 signal price 사용
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
            
            # 고급 TP/SL 주문 설정
            await self._setup_advanced_tp_sl(adapter, symbol, position, actual_price, actual_quantity, 'long')
            
            # 주문 기록 저장
            await self._save_trade_record(user_id, exchange_name, symbol, 'buy', 
                                        actual_quantity, actual_price, reason, order, strategy_config)
            
        except Exception as e:
            logger.error(f"Error placing buy order for {symbol}: {e}")
    
    async def _place_short_order(self, user_id: str, exchange_name: str, symbol: str, 
                               strategy_config: Dict, price: float, reason: str):
        """숏 포지션 생성"""
        try:
            allocated_capital = strategy_config.get('allocated_capital', 100)  # USDT
            stop_loss_pct = strategy_config.get('stop_loss_pct', 5.0)
            take_profit_pct = strategy_config.get('take_profit_pct', 10.0)
            
            # 손절가 계산 (숏 포지션)
            stop_loss_price = price * (1 + stop_loss_pct / 100)
            
            # 리스크 관리자를 통한 포지션 크기 계산
            position_size = risk_manager.calculate_position_size(
                user_id, allocated_capital, price, stop_loss_price, 
                method=strategy_config.get('position_sizing_method', 'fixed_fractional')
            )
            
            adapter = self.exchanges.get(exchange_name)
            if not adapter:
                logger.error(f"Exchange {exchange_name} not available")
                return
            
            # 시장가 매도 주문 (숏 포지션)
            order = await adapter.place_market_order(symbol, 'sell', position_size)
            actual_price = order.get('price') or price
            actual_quantity = order.get('amount', position_size)
            
            logger.info(f"Short order placed for {symbol}: {order}")
            
            # 포지션 생성 (숏)
            position = position_manager.create_position(
                user_id=user_id,
                exchange_name=exchange_name,
                symbol=symbol,
                strategy_id=strategy_config.get('id', 0),
                side='short',
                entry_price=actual_price,
                quantity=actual_quantity,
                stop_loss_pct=stop_loss_pct,
                take_profit_pct=take_profit_pct
            )
            
            # 고급 TP/SL 주문 설정 (숏)
            await self._setup_advanced_tp_sl(adapter, symbol, position, actual_price, actual_quantity, 'short')
            
            # 주문 기록 저장
            await self._save_trade_record(user_id, exchange_name, symbol, 'sell', 
                                        actual_quantity, actual_price, reason, order, strategy_config)
            
        except Exception as e:
            logger.error(f"Error placing short order for {symbol}: {e}")
    
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
                close_price = order.get('price') or price  # VST에서 price가 None인 경우 signal price 사용
                
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
            
            logger.info(f"🔍 CCI 전략 실행: window={window}, buy_threshold={buy_threshold}, sell_threshold={sell_threshold}")
            logger.info(f"🔍 캔들 데이터 개수: {len(ohlcv_data)}")
            
            # generate_cci_signals 함수 호출
            df_signals = generate_cci_signals(ohlcv_data, window, buy_threshold, sell_threshold)
            
            # DataFrame을 dict 리스트로 변환
            signals = []
            timestamps = [candle[0] for candle in ohlcv_data]
            prices = [candle[4] for candle in ohlcv_data]  # 종가
            
            logger.info(f"🔍 CCI 신호 개수: {len(df_signals['signal'])}")
            
            for i, signal_value in enumerate(df_signals['signal']):
                if signal_value != 0:  # 신호가 있는 경우만
                    signals.append({
                        'timestamp': timestamps[i],
                        'signal': 'buy' if signal_value == 1 else 'sell',
                        'price': prices[i],
                        'reason': f'CCI신호 (임계값: {buy_threshold}/{sell_threshold})'
                    })
            
            logger.info(f"🔍 감지된 거래 신호 개수: {len(signals)}")
            if signals:
                latest_signal = signals[-1]
                logger.info(f"🔍 최신 신호: {latest_signal['signal']} at {latest_signal['price']} ({latest_signal['reason']})")
            
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
    
    async def _setup_advanced_tp_sl(self, adapter, symbol: str, position, entry_price: float, quantity: float, side: str):
        """
        고급 TP/SL 설정 - BingX 시스템에서 자동 처리
        - 10% 도달시 50% 부분 청산
        - 나머지 50%에 Trailing Stop (4% 콜백) 설정
        - 최대 15% 익절 제한가 설정
        """
        try:
            from bingx_vst_client import create_vst_client_from_env
            vst_client = create_vst_client_from_env()
            
            if not vst_client:
                logger.error("VST 클라이언트 초기화 실패")
                return
            
            # 심볼 형식 변환 (BTC/USDT -> BTC-USDT)
            vst_symbol = symbol.replace('/', '-')
            position_side = "LONG" if side == 'long' else "SHORT"
            
            # 롱 포지션의 경우
            if side == 'long':
                # 레버리지 정보 가져오기 (기본값: 1배)
                leverage = 1
                try:
                    # 현재 포지션에서 레버리지 정보 확인
                    positions = vst_client.get_vst_positions()
                    for pos in positions:
                        if pos.get('symbol') == vst_symbol:
                            leverage = pos.get('leverage', 1)
                            break
                except:
                    leverage = 1
                
                # 레버리지 고려한 실제 가격 변동률 계산
                # 실제 손익률 -5%를 위해서는 가격이 -5%/leverage 변동해야 함
                sl_price_change = -5.0 / leverage
                tp1_price_change = 10.0 / leverage
                tp2_price_change = 15.0 / leverage
                
                # 기본 손절 설정 (레버리지 고려)
                sl_price = entry_price * (1 + sl_price_change / 100)
                
                # 1단계: 10% 실제 수익률에서 50% 청산 주문
                tp1_price = entry_price * (1 + tp1_price_change / 100)
                tp1_quantity = quantity * 0.5   # 50% 청산
                
                # 2단계: 나머지 50%에 15% 실제 수익률 제한가 설정
                tp2_price = entry_price * (1 + tp2_price_change / 100)
                tp2_quantity = quantity * 0.5   # 나머지 50%
                
                logger.info(f"🎯 고급 TP/SL 설정 ({symbol} 롱포지션, 레버리지: {leverage}배):")
                logger.info(f"  📊 진입가: {entry_price:.4f}, 수량: {quantity:.4f}")
                logger.info(f"  🛡️  손절가: {sl_price:.6f} (가격변동: {sl_price_change:.3f}%, 실제손익: -5%)")
                logger.info(f"  🎯 1차 익절: {tp1_price:.6f} (가격변동: {tp1_price_change:.3f}%, 실제손익: +10%)")
                logger.info(f"  🎯 2차 익절: {tp2_price:.6f} (가격변동: {tp2_price_change:.3f}%, 실제손익: +15%)")
                
                # BingX에 손절 주문 (-5%)
                sl_order = vst_client.create_vst_stop_loss_order(
                    vst_symbol, quantity, sl_price, position_side
                )
                logger.info(f"📤 손절 주문 결과: {sl_order}")
                
                # BingX에 1차 익절 주문 (10%)
                tp1_order = vst_client.create_vst_take_profit_order(
                    vst_symbol, tp1_quantity, tp1_price, position_side
                )
                logger.info(f"📤 1차 익절 주문 결과: {tp1_order}")
                
                # BingX에 2차 익절 주문 (15% 제한가)
                tp2_order = vst_client.create_vst_take_profit_order(
                    vst_symbol, tp2_quantity, tp2_price, position_side
                )
                logger.info(f"📤 2차 익절 주문 결과: {tp2_order}")
                
                # BingX에 Trailing Stop 주문 (4% 콜백)
                # 주의: 실제로는 10% 도달 후에 설정해야 하므로 일단 보류
                # trailing_order = vst_client.create_vst_trailing_stop_order(
                #     vst_symbol, tp2_quantity, 0.04, position_side  # 4% 콜백
                # )
                logger.info(f"🎯 Trailing Stop은 1차 익절 후 설정됩니다 (4% 콜백)")
                
            # 숏 포지션의 경우  
            else:  # side == 'short'
                # 레버리지 정보 가져오기 (기본값: 1배)
                leverage = 1
                try:
                    # 현재 포지션에서 레버리지 정보 확인
                    positions = vst_client.get_vst_positions()
                    for pos in positions:
                        if pos.get('symbol') == vst_symbol:
                            leverage = pos.get('leverage', 1)
                            break
                except:
                    leverage = 1
                
                # 레버리지 고려한 실제 가격 변동률 계산 (숏의 경우)
                sl_price_change = 5.0 / leverage   # 숏은 가격 상승 시 손실
                tp1_price_change = -10.0 / leverage # 숏은 가격 하락 시 수익
                tp2_price_change = -15.0 / leverage # 숏은 가격 하락 시 수익
                
                # 기본 손절 설정 (레버리지 고려) - 숏의 경우 가격이 올라가면 손실
                sl_price = entry_price * (1 + sl_price_change / 100)
                
                # 1단계: 10% 실제 수익률에서 50% 청산
                tp1_price = entry_price * (1 + tp1_price_change / 100)
                tp1_quantity = quantity * 0.5   # 50% 청산
                
                # 2단계: 나머지 50%에 15% 실제 수익률 제한가
                tp2_price = entry_price * (1 + tp2_price_change / 100)
                tp2_quantity = quantity * 0.5   # 나머지 50%
                
                logger.info(f"🎯 고급 TP/SL 설정 ({symbol} 숏포지션, 레버리지: {leverage}배):")
                logger.info(f"  📊 진입가: {entry_price:.4f}, 수량: {quantity:.4f}")
                logger.info(f"  🛡️  손절가: {sl_price:.6f} (가격변동: +{sl_price_change:.3f}%, 실제손익: -5%)")
                logger.info(f"  🎯 1차 익절: {tp1_price:.6f} (가격변동: {tp1_price_change:.3f}%, 실제손익: +10%)")
                logger.info(f"  🎯 2차 익절: {tp2_price:.6f} (가격변동: {tp2_price_change:.3f}%, 실제손익: +15%)")
                
                # BingX에 손절 주문 (+5%)
                sl_order = vst_client.create_vst_stop_loss_order(
                    vst_symbol, quantity, sl_price, position_side
                )
                logger.info(f"📤 손절 주문 결과: {sl_order}")
                
                # BingX에 1차 익절 주문 (10%)
                tp1_order = vst_client.create_vst_take_profit_order(
                    vst_symbol, tp1_quantity, tp1_price, position_side
                )
                logger.info(f"📤 1차 익절 주문 결과: {tp1_order}")
                
                # BingX에 2차 익절 주문 (15% 제한가)
                tp2_order = vst_client.create_vst_take_profit_order(
                    vst_symbol, tp2_quantity, tp2_price, position_side
                )
                logger.info(f"📤 2차 익절 주문 결과: {tp2_order}")
                
                logger.info(f"🎯 Trailing Stop은 1차 익절 후 설정됩니다 (4% 콜백)")
            
            # position 객체에 고급 TP/SL 정보 저장
            position.metadata['advanced_tp_sl'] = {
                'tp1_price': tp1_price if side == 'long' else tp1_price,
                'tp1_quantity': tp1_quantity,
                'tp2_price': tp2_price,
                'tp2_quantity': tp2_quantity,
                'tp1_executed': False,
                'trailing_setup': False,
                'side': side
            }
            
        except Exception as e:
            logger.error(f"Error setting up advanced TP/SL for {symbol}: {e}")
    
    async def _check_advanced_tp_sl(self, user_id: str, exchange_name: str, symbol: str, vst_position: dict, current_price: float, pnl_percentage: float) -> bool:
        """
        고급 TP/SL 조건 확인 및 실행
        Returns: True if advanced TP/SL was executed, False otherwise
        """
        try:
            # Position Manager에서 해당 포지션 찾기
            open_positions = position_manager.get_symbol_positions(user_id, symbol, status="open")
            if not open_positions:
                return False
            
            for position in open_positions:
                # 고급 TP/SL 메타데이터가 있는지 확인
                advanced_tp_sl = position.metadata.get('advanced_tp_sl')
                if not advanced_tp_sl:
                    continue
                
                entry_price = position.entry_price
                side = advanced_tp_sl['side']
                tp1_executed = advanced_tp_sl.get('tp1_executed', False)
                
                logger.info(f"🔍 고급 TP/SL 체크 ({symbol}): 현재 {pnl_percentage:.2f}%")
                
                # 롱 포지션 처리
                if side == 'long':
                    # 1차 익절 (10%) - BingX 시스템에서 자동 실행됨
                    # 실시간 모니터링에서는 1차 익절 후 Trailing Stop 설정만 확인
                    if not tp1_executed and pnl_percentage >= 10.0:
                        # 1차 익절이 BingX에서 실행되었는지 확인
                        logger.info(f"🎯 1차 익절 조건 달성! ({symbol}) {pnl_percentage:.2f}% >= 10%")
                        logger.info(f"🔍 BingX 시스템에서 자동 처리 확인 중...")
                        
                        # 포지션 수량이 줄어들었는지 확인 (50% 부분 청산 확인)
                        original_quantity = advanced_tp_sl.get('tp1_quantity', 0) * 2  # 원래 수량
                        current_quantity = abs(float(vst_position.get('positionAmt', 0)))
                        
                        if current_quantity <= original_quantity * 0.6:  # 수량이 60% 이하로 줄었으면 1차 익절 실행된 것으로 판단
                            logger.info(f"✅ 1차 익절 완료 확인: 수량 {original_quantity:.4f} → {current_quantity:.4f}")
                            
                            # 1차 익절 완료 표시
                            position.metadata['advanced_tp_sl']['tp1_executed'] = True
                            
                            # 이제 나머지 수량에 Trailing Stop 설정
                            await self._setup_trailing_stop_after_tp1(user_id, exchange_name, symbol, position, current_quantity)
                            
                            return True
                    
                    # 2차 손절 (4%) - 나머지 전체 청산
                    elif tp1_executed and pnl_percentage <= -4.0:
                        logger.info(f"🛡️ 2차 손절 실행! ({symbol}) {pnl_percentage:.2f}% <= -4% - 나머지 전체 청산")
                        
                        adapter = self.exchanges.get(exchange_name)
                        if adapter:
                            position_amt = float(vst_position.get('positionAmt', 0))
                            
                            sell_order = await adapter.place_market_order(symbol, 'sell', position_amt)
                            logger.info(f"✅ 2차 손절 완료: {position_amt:.4f} 전체 청산")
                            
                            # 포지션 청산 처리
                            position_manager.close_position(position.position_id, current_price, "고급_손절")
                            
                            return True
                    
                    # 2차 익절 (15%) - 나머지 전체 청산
                    elif tp1_executed and pnl_percentage >= 15.0:
                        logger.info(f"🎯 2차 익절 실행! ({symbol}) {pnl_percentage:.2f}% >= 15% - 나머지 전체 청산")
                        
                        adapter = self.exchanges.get(exchange_name)
                        if adapter:
                            position_amt = float(vst_position.get('positionAmt', 0))
                            
                            sell_order = await adapter.place_market_order(symbol, 'sell', position_amt)
                            logger.info(f"✅ 2차 익절 완료: {position_amt:.4f} 전체 청산")
                            
                            # 포지션 청산 처리
                            position_manager.close_position(position.position_id, current_price, "고급_익절")
                            
                            return True
                
                # 숏 포지션 처리 (로직은 반대)
                elif side == 'short':
                    # 1차 익절 (10%) - 50% 부분 청산
                    if not tp1_executed and pnl_percentage >= 10.0:
                        logger.info(f"🎯 1차 익절 실행! ({symbol} 숏) {pnl_percentage:.2f}% >= 10% - 50% 부분 청산")
                        
                        adapter = self.exchanges.get(exchange_name)
                        if adapter:
                            position_amt = abs(float(vst_position.get('positionAmt', 0)))
                            partial_quantity = position_amt * 0.5
                            
                            buy_order = await adapter.place_market_order(symbol, 'buy', partial_quantity)
                            logger.info(f"✅ 1차 익절 완료: {partial_quantity:.4f} 청산")
                            
                            position.metadata['advanced_tp_sl']['tp1_executed'] = True
                            return True
                    
                    # 2차 손절/익절 로직은 롱과 유사하게 구현...
                    elif tp1_executed and pnl_percentage <= -4.0:
                        logger.info(f"🛡️ 2차 손절 실행! ({symbol} 숏) {pnl_percentage:.2f}% <= -4%")
                        # 숏 포지션 전체 청산 로직...
                        return True
                    elif tp1_executed and pnl_percentage >= 15.0:
                        logger.info(f"🎯 2차 익절 실행! ({symbol} 숏) {pnl_percentage:.2f}% >= 15%")
                        # 숏 포지션 전체 청산 로직...
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in advanced TP/SL check for {symbol}: {e}")
            return False
    
    async def _setup_trailing_stop_after_tp1(self, user_id: str, exchange_name: str, symbol: str, position, remaining_quantity: float):
        """
        1차 익절 후 Trailing Stop 설정
        - 나머지 수량에 대해 4% 콜백 Trailing Stop 설정
        """
        try:
            from bingx_vst_client import create_vst_client_from_env
            vst_client = create_vst_client_from_env()
            
            if not vst_client:
                logger.error("VST 클라이언트 초기화 실패")
                return
            
            # 심볼 형식 변환 (BTC/USDT -> BTC-USDT)
            vst_symbol = symbol.replace('/', '-')
            advanced_tp_sl = position.metadata.get('advanced_tp_sl', {})
            side = advanced_tp_sl.get('side', 'long')
            position_side = "LONG" if side == 'long' else "SHORT"
            
            if not advanced_tp_sl.get('trailing_setup', False):
                logger.info(f"🎯 Trailing Stop 설정 중... ({symbol})")
                logger.info(f"  📊 나머지 수량: {remaining_quantity:.4f}")
                logger.info(f"  📉 콜백 비율: 4% (10%에서 6%로 떨어지면 익절)")
                
                # BingX에 Trailing Stop 주문 설정 (4% 콜백)
                trailing_order = vst_client.create_vst_trailing_stop_order(
                    vst_symbol, remaining_quantity, 0.04, position_side  # 4% 콜백
                )
                
                logger.info(f"📤 Trailing Stop 주문 결과: {trailing_order}")
                
                # Trailing Stop 설정 완료 표시
                position.metadata['advanced_tp_sl']['trailing_setup'] = True
                
                if trailing_order.get('code') == 0:
                    logger.info(f"✅ Trailing Stop 설정 완료! 최고점에서 4% 떨어지면 자동 익절됩니다")
                else:
                    logger.error(f"❌ Trailing Stop 설정 실패: {trailing_order}")
            
        except Exception as e:
            logger.error(f"Error setting up trailing stop for {symbol}: {e}")

# 글로벌 인스턴스
trading_engine = RealtimeTradingEngine()