"""
Backtesting Engine - 고속 백테스팅 & 페이퍼 트레이딩
전략 검증, 최적화, A/B 테스트
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import time
from copy import deepcopy

logger = logging.getLogger(__name__)

class BacktestMode(Enum):
    """백테스트 모드"""
    HISTORICAL = "historical"  # 과거 데이터
    PAPER_TRADING = "paper_trading"  # 실시간 페이퍼 트레이딩
    WALK_FORWARD = "walk_forward"  # 워크 포워드 분석

class OrderType(Enum):
    """주문 타입"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"

class ExecutionMode(Enum):
    """실행 모드"""
    OPTIMISTIC = "optimistic"  # 모든 주문 즉시 체결
    REALISTIC = "realistic"  # 슬리피지 및 지연 고려
    CONSERVATIVE = "conservative"  # 높은 슬리피지 및 거부 확률

@dataclass
class BacktestTrade:
    """백테스트 거래"""
    entry_time: datetime
    exit_time: datetime
    symbol: str
    side: str  # BUY, SELL
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    pnl_pct: float
    fees: float
    slippage: float
    strategy_name: str
    signal_confidence: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BacktestConfig:
    """백테스트 설정"""
    start_date: datetime
    end_date: datetime
    initial_capital: float
    commission_rate: float = 0.001  # 0.1%
    slippage_rate: float = 0.0005  # 0.05%
    max_positions: int = 5
    max_position_size: float = 0.2  # 20%
    execution_mode: ExecutionMode = ExecutionMode.REALISTIC
    enable_stop_loss: bool = True
    enable_take_profit: bool = True
    benchmark_symbol: str = "BTC/USDT"

@dataclass
class BacktestResult:
    """백테스트 결과"""
    config: BacktestConfig
    trades: List[BacktestTrade]
    equity_curve: List[Tuple[datetime, float]]
    drawdown_curve: List[Tuple[datetime, float]]
    
    # 성과 메트릭
    total_return: float
    total_return_pct: float
    annualized_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    calmar_ratio: float
    
    # 거래 통계
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_return: float
    avg_win: float
    avg_loss: float
    
    # 시간 통계
    avg_holding_period: float  # 시간
    max_holding_period: float
    min_holding_period: float
    
    # 기타
    execution_time: float  # 백테스트 실행 시간
    data_points: int
    start_time: datetime
    end_time: datetime

class BacktestingEngine:
    """백테스팅 엔진"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=8)
        self.paper_trading_active = False
        self.paper_positions: Dict[str, Dict] = {}
        self.paper_capital = 10000.0
        self.paper_trades: List[BacktestTrade] = []
        
        logger.info("🏗️ Backtesting Engine initialized")
    
    async def run_backtest(
        self, 
        strategy_func: Callable,
        market_data: pd.DataFrame,
        config: BacktestConfig
    ) -> BacktestResult:
        """백테스트 실행"""
        start_time = time.time()
        
        try:
            if market_data.empty or len(market_data) < 100:
                raise ValueError("Insufficient market data for backtesting")
            
            # 데이터 필터링
            filtered_data = self._filter_data_by_date(market_data, config.start_date, config.end_date)
            
            if filtered_data.empty:
                raise ValueError("No data available for the specified date range")
            
            logger.info(f"🎯 Starting backtest: {len(filtered_data)} data points from {config.start_date} to {config.end_date}")
            
            # 백테스트 실행
            trades, equity_curve, drawdown_curve = await self._execute_backtest(
                strategy_func, filtered_data, config
            )
            
            # 결과 분석
            result = self._analyze_backtest_results(
                trades, equity_curve, drawdown_curve, config, start_time
            )
            
            execution_time = time.time() - start_time
            result.execution_time = execution_time
            
            logger.info(f"✅ Backtest completed in {execution_time:.2f}s: {result.total_trades} trades, {result.total_return_pct:.2f}% return")
            
            return result
            
        except Exception as e:
            logger.error(f"🔴 Error in backtest execution: {e}")
            raise
    
    def _filter_data_by_date(self, data: pd.DataFrame, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """날짜별 데이터 필터링"""
        try:
            # timestamp 컬럼을 datetime으로 변환
            if 'timestamp' in data.columns:
                data['timestamp'] = pd.to_datetime(data['timestamp'])
                return data[(data['timestamp'] >= start_date) & (data['timestamp'] <= end_date)]
            else:
                # index가 datetime인 경우
                data.index = pd.to_datetime(data.index)
                return data[(data.index >= start_date) & (data.index <= end_date)]
                
        except Exception as e:
            logger.error(f"🔴 Error filtering data by date: {e}")
            return data
    
    async def _execute_backtest(
        self, 
        strategy_func: Callable,
        data: pd.DataFrame,
        config: BacktestConfig
    ) -> Tuple[List[BacktestTrade], List[Tuple[datetime, float]], List[Tuple[datetime, float]]]:
        """백테스트 실행"""
        trades = []
        equity_curve = []
        drawdown_curve = []
        
        current_capital = config.initial_capital
        peak_capital = config.initial_capital
        open_positions = {}
        
        try:
            for i in range(50, len(data)):  # 충분한 지표 계산을 위해 50부터 시작
                current_data = data.iloc[:i+1]
                current_time = current_data.iloc[-1]['timestamp'] if 'timestamp' in current_data.columns else datetime.now()
                current_price = current_data.iloc[-1]['close']
                
                # 전략 신호 생성
                try:
                    signals = await strategy_func(current_data)
                    if not isinstance(signals, list):
                        signals = [signals] if signals else []
                except Exception as e:
                    logger.error(f"🔴 Strategy function error at step {i}: {e}")
                    continue
                
                # 신호 처리
                for signal in signals:
                    if signal and hasattr(signal, 'action'):
                        trade = await self._process_signal(
                            signal, current_time, current_price, 
                            open_positions, current_capital, config
                        )
                        
                        if trade:
                            trades.append(trade)
                            current_capital += trade.pnl
                
                # 기존 포지션 관리 (스톱로스, 테이크프로핏)
                closed_trades = await self._manage_open_positions(
                    open_positions, current_time, current_price, config
                )
                
                for trade in closed_trades:
                    trades.append(trade)
                    current_capital += trade.pnl
                
                # 자본 곡선 업데이트
                equity_curve.append((current_time, current_capital))
                
                # 낙폭 곡선 업데이트
                if current_capital > peak_capital:
                    peak_capital = current_capital
                
                drawdown = (current_capital - peak_capital) / peak_capital * 100
                drawdown_curve.append((current_time, drawdown))
                
                # 진행 상황 로깅 (10%마다)
                if i % (len(data) // 10) == 0:
                    progress = i / len(data) * 100
                    logger.info(f"⏳ Backtest progress: {progress:.1f}% - Capital: ${current_capital:,.2f}")
            
            logger.info(f"🏁 Backtest execution completed: {len(trades)} trades, Final capital: ${current_capital:,.2f}")
            
        except Exception as e:
            logger.error(f"🔴 Error during backtest execution: {e}")
        
        return trades, equity_curve, drawdown_curve
    
    async def _process_signal(
        self, 
        signal, 
        current_time: datetime, 
        current_price: float,
        open_positions: Dict,
        current_capital: float,
        config: BacktestConfig
    ) -> Optional[BacktestTrade]:
        """신호 처리"""
        try:
            if signal.action not in ['BUY', 'SELL']:
                return None
            
            # 포지션 크기 계산
            position_value = min(
                signal.position_size * current_capital if hasattr(signal, 'position_size') else config.max_position_size * current_capital,
                config.max_position_size * current_capital
            )
            
            # 자본 확인
            if position_value > current_capital * 0.95:  # 95% 이상 사용 방지
                return None
            
            # 슬리피지 및 수수료 계산
            slippage = self._calculate_slippage(current_price, position_value, config)
            execution_price = current_price * (1 + slippage) if signal.action == 'BUY' else current_price * (1 - slippage)
            
            quantity = position_value / execution_price
            fees = position_value * config.commission_rate
            
            # 포지션 기록
            position_id = f"{signal.strategy_name}_{current_time.timestamp()}"
            open_positions[position_id] = {
                'strategy_name': signal.strategy_name,
                'entry_time': current_time,
                'entry_price': execution_price,
                'quantity': quantity,
                'side': signal.action,
                'stop_loss': getattr(signal, 'stop_loss', None),
                'take_profit': getattr(signal, 'take_profit', None),
                'signal_confidence': getattr(signal, 'confidence', 0.5)
            }
            
            logger.debug(f"📈 Opened position: {signal.action} {quantity:.4f} @ ${execution_price:.2f}")
            
            return None  # 포지션 오픈은 거래 완료가 아님
            
        except Exception as e:
            logger.error(f"🔴 Error processing signal: {e}")
            return None
    
    async def _manage_open_positions(
        self,
        open_positions: Dict,
        current_time: datetime,
        current_price: float,
        config: BacktestConfig
    ) -> List[BacktestTrade]:
        """오픈 포지션 관리"""
        closed_trades = []
        positions_to_close = []
        
        try:
            for position_id, position in open_positions.items():
                # 스톱로스 확인
                if (config.enable_stop_loss and position.get('stop_loss') and
                    ((position['side'] == 'BUY' and current_price <= position['stop_loss']) or
                     (position['side'] == 'SELL' and current_price >= position['stop_loss']))):
                    
                    trade = self._close_position(position, current_time, current_price, "STOP_LOSS", config)
                    if trade:
                        closed_trades.append(trade)
                        positions_to_close.append(position_id)
                        continue
                
                # 테이크프로핏 확인
                if (config.enable_take_profit and position.get('take_profit') and
                    ((position['side'] == 'BUY' and current_price >= position['take_profit']) or
                     (position['side'] == 'SELL' and current_price <= position['take_profit']))):
                    
                    trade = self._close_position(position, current_time, current_price, "TAKE_PROFIT", config)
                    if trade:
                        closed_trades.append(trade)
                        positions_to_close.append(position_id)
                        continue
                
                # 시간 기반 종료 (24시간 후 자동 종료)
                holding_period = (current_time - position['entry_time']).total_seconds() / 3600
                if holding_period > 24:  # 24시간 초과
                    trade = self._close_position(position, current_time, current_price, "TIME_EXIT", config)
                    if trade:
                        closed_trades.append(trade)
                        positions_to_close.append(position_id)
            
            # 종료된 포지션 제거
            for position_id in positions_to_close:
                del open_positions[position_id]
            
        except Exception as e:
            logger.error(f"🔴 Error managing open positions: {e}")
        
        return closed_trades
    
    def _close_position(
        self, 
        position: Dict, 
        exit_time: datetime, 
        exit_price: float, 
        exit_reason: str,
        config: BacktestConfig
    ) -> Optional[BacktestTrade]:
        """포지션 종료"""
        try:
            # 슬리피지 계산
            position_value = position['quantity'] * exit_price
            slippage = self._calculate_slippage(exit_price, position_value, config)
            
            # 실제 종료 가격 (슬리피지 적용)
            actual_exit_price = exit_price * (1 - slippage) if position['side'] == 'BUY' else exit_price * (1 + slippage)
            
            # 손익 계산
            if position['side'] == 'BUY':
                pnl = (actual_exit_price - position['entry_price']) * position['quantity']
            else:  # SELL (short)
                pnl = (position['entry_price'] - actual_exit_price) * position['quantity']
            
            # 수수료 차감
            fees = position_value * config.commission_rate * 2  # 진입 + 종료
            pnl -= fees
            
            # 퍼센트 수익률
            initial_value = position['entry_price'] * position['quantity']
            pnl_pct = (pnl / initial_value) * 100 if initial_value > 0 else 0
            
            # 보유 기간
            holding_period = (exit_time - position['entry_time']).total_seconds() / 3600
            
            trade = BacktestTrade(
                entry_time=position['entry_time'],
                exit_time=exit_time,
                symbol="BTC/USDT",  # 기본값
                side=position['side'],
                entry_price=position['entry_price'],
                exit_price=actual_exit_price,
                quantity=position['quantity'],
                pnl=pnl,
                pnl_pct=pnl_pct,
                fees=fees,
                slippage=slippage,
                strategy_name=position['strategy_name'],
                signal_confidence=position['signal_confidence'],
                metadata={
                    'exit_reason': exit_reason,
                    'holding_period_hours': holding_period,
                    'original_exit_price': exit_price
                }
            )
            
            logger.debug(f"💰 Closed position: {position['side']} ${pnl:.2f} ({pnl_pct:.2f}%) - {exit_reason}")
            
            return trade
            
        except Exception as e:
            logger.error(f"🔴 Error closing position: {e}")
            return None
    
    def _calculate_slippage(self, price: float, position_value: float, config: BacktestConfig) -> float:
        """슬리피지 계산"""
        try:
            base_slippage = config.slippage_rate
            
            # 실행 모드에 따른 슬리피지 조정
            if config.execution_mode == ExecutionMode.OPTIMISTIC:
                return base_slippage * 0.5
            elif config.execution_mode == ExecutionMode.CONSERVATIVE:
                return base_slippage * 2.0
            else:  # REALISTIC
                # 포지션 크기가 클수록 슬리피지 증가
                size_impact = min(0.0005, position_value / 100000 * 0.0001)
                return base_slippage + size_impact
                
        except Exception as e:
            logger.error(f"🔴 Error calculating slippage: {e}")
            return config.slippage_rate
    
    def _analyze_backtest_results(
        self,
        trades: List[BacktestTrade],
        equity_curve: List[Tuple[datetime, float]],
        drawdown_curve: List[Tuple[datetime, float]],
        config: BacktestConfig,
        start_time: float
    ) -> BacktestResult:
        """백테스트 결과 분석"""
        try:
            if not trades:
                return BacktestResult(
                    config=config,
                    trades=[],
                    equity_curve=equity_curve,
                    drawdown_curve=drawdown_curve,
                    total_return=0, total_return_pct=0, annualized_return=0,
                    volatility=0, sharpe_ratio=0, sortino_ratio=0,
                    max_drawdown=0, max_drawdown_pct=0, calmar_ratio=0,
                    total_trades=0, winning_trades=0, losing_trades=0,
                    win_rate=0, profit_factor=0, avg_trade_return=0,
                    avg_win=0, avg_loss=0,
                    avg_holding_period=0, max_holding_period=0, min_holding_period=0,
                    execution_time=time.time() - start_time,
                    data_points=len(equity_curve),
                    start_time=config.start_date,
                    end_time=config.end_date
                )
            
            # 기본 통계
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.pnl > 0])
            losing_trades = len([t for t in trades if t.pnl < 0])
            
            total_return = sum(t.pnl for t in trades)
            total_return_pct = (total_return / config.initial_capital) * 100
            
            # 승률 및 평균
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            wins = [t.pnl for t in trades if t.pnl > 0]
            losses = [abs(t.pnl) for t in trades if t.pnl < 0]
            
            avg_win = np.mean(wins) if wins else 0
            avg_loss = np.mean(losses) if losses else 0
            avg_trade_return = total_return / total_trades if total_trades > 0 else 0
            
            # Profit Factor
            gross_profit = sum(wins)
            gross_loss = sum(losses)
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
            
            # 시간 통계
            holding_periods = [
                (t.exit_time - t.entry_time).total_seconds() / 3600 
                for t in trades
            ]
            avg_holding_period = np.mean(holding_periods) if holding_periods else 0
            max_holding_period = np.max(holding_periods) if holding_periods else 0
            min_holding_period = np.min(holding_periods) if holding_periods else 0
            
            # 수익률 시계열
            daily_returns = []
            if len(equity_curve) > 1:
                for i in range(1, len(equity_curve)):
                    prev_capital = equity_curve[i-1][1]
                    curr_capital = equity_curve[i][1]
                    daily_return = (curr_capital - prev_capital) / prev_capital
                    daily_returns.append(daily_return)
            
            # 리스크 조정 수익률
            volatility = np.std(daily_returns) * np.sqrt(252) if len(daily_returns) > 1 else 0
            
            # Sharpe Ratio
            risk_free_rate = 0.02 / 252  # 일간 무위험 수익률 2%
            excess_returns = np.array(daily_returns) - risk_free_rate
            sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if len(excess_returns) > 1 and np.std(excess_returns) > 0 else 0
            
            # Sortino Ratio
            downside_returns = [r for r in daily_returns if r < 0]
            downside_vol = np.std(downside_returns) if len(downside_returns) > 1 else np.std(daily_returns)
            sortino_ratio = np.mean(excess_returns) / downside_vol * np.sqrt(252) if downside_vol > 0 else 0
            
            # 최대 낙폭
            max_drawdown = min([dd[1] for dd in drawdown_curve]) if drawdown_curve else 0
            max_drawdown_pct = abs(max_drawdown)
            
            # Calmar Ratio
            trading_days = (config.end_date - config.start_date).days
            annualized_return = total_return_pct * (252 / trading_days) if trading_days > 0 else 0
            calmar_ratio = annualized_return / max_drawdown_pct if max_drawdown_pct > 0 else 0
            
            result = BacktestResult(
                config=config,
                trades=trades,
                equity_curve=equity_curve,
                drawdown_curve=drawdown_curve,
                total_return=total_return,
                total_return_pct=total_return_pct,
                annualized_return=annualized_return,
                volatility=volatility * 100,
                sharpe_ratio=sharpe_ratio,
                sortino_ratio=sortino_ratio,
                max_drawdown=abs(max_drawdown) * config.initial_capital / 100,
                max_drawdown_pct=max_drawdown_pct,
                calmar_ratio=calmar_ratio,
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_trade_return=avg_trade_return,
                avg_win=avg_win,
                avg_loss=avg_loss,
                avg_holding_period=avg_holding_period,
                max_holding_period=max_holding_period,
                min_holding_period=min_holding_period,
                execution_time=0,  # 나중에 설정
                data_points=len(equity_curve),
                start_time=config.start_date,
                end_time=config.end_date
            )
            
            return result
            
        except Exception as e:
            logger.error(f"🔴 Error analyzing backtest results: {e}")
            raise
    
    async def _manage_open_positions(
        self,
        open_positions: Dict,
        current_time: datetime,
        current_price: float,
        config: BacktestConfig
    ) -> List[BacktestTrade]:
        """오픈 포지션 관리 (스톱로스, 테이크프로핏)"""
        closed_trades = []
        positions_to_close = []
        
        try:
            for position_id, position in open_positions.items():
                should_close = False
                exit_reason = ""
                
                # 스톱로스 확인
                if config.enable_stop_loss and position.get('stop_loss'):
                    if ((position['side'] == 'BUY' and current_price <= position['stop_loss']) or
                        (position['side'] == 'SELL' and current_price >= position['stop_loss'])):
                        should_close = True
                        exit_reason = "STOP_LOSS"
                
                # 테이크프로핏 확인
                elif config.enable_take_profit and position.get('take_profit'):
                    if ((position['side'] == 'BUY' and current_price >= position['take_profit']) or
                        (position['side'] == 'SELL' and current_price <= position['take_profit'])):
                        should_close = True
                        exit_reason = "TAKE_PROFIT"
                
                # 최대 보유 시간 확인 (24시간)
                elif (current_time - position['entry_time']).total_seconds() > 86400:  # 24시간
                    should_close = True
                    exit_reason = "TIME_LIMIT"
                
                if should_close:
                    trade = self._close_position(position, current_time, current_price, exit_reason, config)
                    if trade:
                        closed_trades.append(trade)
                        positions_to_close.append(position_id)
            
            # 종료된 포지션 제거
            for position_id in positions_to_close:
                del open_positions[position_id]
                
        except Exception as e:
            logger.error(f"🔴 Error managing open positions: {e}")
        
        return closed_trades
    
    async def run_parameter_optimization(
        self,
        strategy_func: Callable,
        market_data: pd.DataFrame,
        parameter_ranges: Dict[str, List],
        config: BacktestConfig,
        max_workers: int = 4
    ) -> Dict[str, Any]:
        """매개변수 최적화"""
        try:
            logger.info(f"🔧 Starting parameter optimization with {len(parameter_ranges)} parameters")
            
            # 매개변수 조합 생성
            param_combinations = self._generate_parameter_combinations(parameter_ranges)
            logger.info(f"🎯 Testing {len(param_combinations)} parameter combinations")
            
            # 병렬 백테스트 실행
            tasks = []
            for i, params in enumerate(param_combinations[:50]):  # 최대 50개 조합
                task = self._run_single_optimization_test(
                    strategy_func, market_data, params, config, i
                )
                tasks.append(task)
            
            # 결과 수집
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 성공한 결과만 필터링
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"🔴 Optimization test {i} failed: {result}")
                elif result:
                    valid_results.append(result)
            
            if not valid_results:
                return {"error": "No valid optimization results"}
            
            # 최적 매개변수 찾기
            best_result = max(valid_results, key=lambda x: x['sharpe_ratio'])
            
            # 결과 정리
            optimization_result = {
                'best_parameters': best_result['parameters'],
                'best_performance': {
                    'total_return_pct': best_result['total_return_pct'],
                    'sharpe_ratio': best_result['sharpe_ratio'],
                    'max_drawdown_pct': best_result['max_drawdown_pct'],
                    'win_rate': best_result['win_rate'],
                    'profit_factor': best_result['profit_factor']
                },
                'optimization_summary': {
                    'total_combinations': len(param_combinations),
                    'tested_combinations': len(valid_results),
                    'success_rate': len(valid_results) / len(param_combinations) * 100,
                    'best_sharpe': best_result['sharpe_ratio'],
                    'parameter_ranges': parameter_ranges
                },
                'top_10_results': sorted(valid_results, key=lambda x: x['sharpe_ratio'], reverse=True)[:10]
            }
            
            logger.info(f"✅ Parameter optimization completed: Best Sharpe {best_result['sharpe_ratio']:.2f}")
            
            return optimization_result
            
        except Exception as e:
            logger.error(f"🔴 Error in parameter optimization: {e}")
            return {"error": str(e)}
    
    def _generate_parameter_combinations(self, parameter_ranges: Dict[str, List]) -> List[Dict]:
        """매개변수 조합 생성"""
        try:
            import itertools
            
            keys = list(parameter_ranges.keys())
            values = list(parameter_ranges.values())
            
            combinations = []
            for combination in itertools.product(*values):
                param_dict = dict(zip(keys, combination))
                combinations.append(param_dict)
            
            return combinations
            
        except Exception as e:
            logger.error(f"🔴 Error generating parameter combinations: {e}")
            return []
    
    async def _run_single_optimization_test(
        self,
        strategy_func: Callable,
        market_data: pd.DataFrame,
        parameters: Dict,
        config: BacktestConfig,
        test_id: int
    ) -> Optional[Dict]:
        """단일 최적화 테스트"""
        try:
            # 매개변수가 적용된 전략 함수 생성
            async def parameterized_strategy(data):
                # 여기서 매개변수를 strategy_func에 적용
                # 실제 구현에서는 전략 함수에 매개변수를 전달하는 방식 구현
                return await strategy_func(data)
            
            # 백테스트 실행
            test_config = deepcopy(config)
            trades, equity_curve, drawdown_curve = await self._execute_backtest(
                parameterized_strategy, market_data, test_config
            )
            
            if not trades:
                return None
            
            # 간단한 성과 메트릭 계산
            total_pnl = sum(t.pnl for t in trades)
            total_return_pct = (total_pnl / config.initial_capital) * 100
            
            returns = []
            if len(equity_curve) > 1:
                for i in range(1, len(equity_curve)):
                    prev_value = equity_curve[i-1][1]
                    curr_value = equity_curve[i][1]
                    daily_return = (curr_value - prev_value) / prev_value
                    returns.append(daily_return)
            
            # Sharpe Ratio
            sharpe_ratio = 0
            if len(returns) > 1:
                mean_return = np.mean(returns)
                std_return = np.std(returns)
                sharpe_ratio = mean_return / std_return * np.sqrt(252) if std_return > 0 else 0
            
            # 최대 낙폭
            max_drawdown_pct = abs(min([dd[1] for dd in drawdown_curve])) if drawdown_curve else 0
            
            # 승률
            win_rate = len([t for t in trades if t.pnl > 0]) / len(trades) * 100
            
            # Profit Factor
            gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
            gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
            
            return {
                'test_id': test_id,
                'parameters': parameters,
                'total_return_pct': total_return_pct,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown_pct': max_drawdown_pct,
                'win_rate': win_rate,
                'profit_factor': profit_factor,
                'total_trades': len(trades)
            }
            
        except Exception as e:
            logger.error(f"🔴 Error in optimization test {test_id}: {e}")
            return None
    
    def start_paper_trading(self, initial_capital: float = 10000.0):
        """페이퍼 트레이딩 시작"""
        self.paper_trading_active = True
        self.paper_capital = initial_capital
        self.paper_positions = {}
        self.paper_trades = []
        
        logger.info(f"📝 Paper trading started with ${initial_capital:,.2f}")
    
    def stop_paper_trading(self):
        """페이퍼 트레이딩 중지"""
        self.paper_trading_active = False
        logger.info("📝 Paper trading stopped")
    
    async def execute_paper_trade(self, signal, current_price: float) -> Dict[str, Any]:
        """페이퍼 트레이딩 주문 실행"""
        if not self.paper_trading_active:
            return {"error": "Paper trading not active"}
        
        try:
            position_value = signal.position_size * self.paper_capital if hasattr(signal, 'position_size') else self.paper_capital * 0.1
            quantity = position_value / current_price
            
            # 수수료 시뮬레이션
            fees = position_value * 0.001  # 0.1%
            
            # 페이퍼 포지션 기록
            position_id = f"paper_{len(self.paper_trades)}"
            paper_position = {
                'id': position_id,
                'strategy_name': signal.strategy_name,
                'entry_time': datetime.now(),
                'entry_price': current_price,
                'quantity': quantity,
                'side': signal.action,
                'stop_loss': getattr(signal, 'stop_loss', None),
                'take_profit': getattr(signal, 'take_profit', None)
            }
            
            self.paper_positions[position_id] = paper_position
            
            return {
                "message": "Paper trade executed",
                "position_id": position_id,
                "action": signal.action,
                "quantity": quantity,
                "price": current_price,
                "fees": fees,
                "paper_capital_remaining": self.paper_capital - position_value
            }
            
        except Exception as e:
            logger.error(f"🔴 Error executing paper trade: {e}")
            return {"error": str(e)}

# 테스트 함수
async def test_backtesting_engine():
    """Backtesting Engine 테스트"""
    print("🧪 Testing Backtesting Engine...")
    
    # 샘플 시장 데이터 생성
    start_date = datetime(2025, 1, 1)
    end_date = datetime(2025, 1, 31)
    dates = pd.date_range(start_date, end_date, freq='5min')
    
    np.random.seed(42)
    price_base = 50000
    price_data = price_base + np.cumsum(np.random.randn(len(dates)) * 50)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': price_data + np.random.randn(len(dates)) * 25,
        'high': price_data + np.abs(np.random.randn(len(dates)) * 50),
        'low': price_data - np.abs(np.random.randn(len(dates)) * 50),
        'close': price_data,
        'volume': np.random.randint(1000, 10000, len(dates))
    })
    
    # 백테스팅 엔진 생성
    engine = BacktestingEngine()
    
    # 간단한 전략 함수 (CCI 기반)
    async def simple_cci_strategy(data):
        from advanced.multi_strategy_engine import CCIStrategy, StrategyConfig
        
        config = StrategyConfig(
            name="Test_CCI",
            description="Test CCI Strategy",
            max_position_size=0.1
        )
        strategy = CCIStrategy(config)
        
        return await strategy.analyze(data)
    
    # 백테스트 설정
    config = BacktestConfig(
        start_date=start_date,
        end_date=end_date,
        initial_capital=10000.0,
        commission_rate=0.001,
        slippage_rate=0.0005,
        max_positions=3,
        max_position_size=0.2
    )
    
    # 백테스트 실행
    print(f"🎯 Running backtest from {start_date.date()} to {end_date.date()}")
    result = await engine.run_backtest(simple_cci_strategy, market_data, config)
    
    # 결과 출력
    print(f"\\n📊 Backtest Results:")
    print(f"  - Total Trades: {result.total_trades}")
    print(f"  - Win Rate: {result.win_rate:.1f}%")
    print(f"  - Total Return: {result.total_return_pct:.2f}%")
    print(f"  - Sharpe Ratio: {result.sharpe_ratio:.2f}")
    print(f"  - Max Drawdown: {result.max_drawdown_pct:.2f}%")
    print(f"  - Profit Factor: {result.profit_factor:.2f}")
    print(f"  - Avg Holding Period: {result.avg_holding_period:.1f} hours")
    print(f"  - Execution Time: {result.execution_time:.2f} seconds")
    
    # 매개변수 최적화 테스트
    print(f"\\n🔧 Testing Parameter Optimization...")
    param_ranges = {
        'cci_period': [14, 20, 26],
        'overbought': [80, 100, 120],
        'oversold': [-120, -100, -80]
    }
    
    # 작은 데이터셋으로 최적화 테스트
    small_data = market_data.iloc[:500]  # 500개 데이터포인트
    opt_config = BacktestConfig(
        start_date=small_data.iloc[0]['timestamp'],
        end_date=small_data.iloc[-1]['timestamp'],
        initial_capital=5000.0
    )
    
    try:
        opt_result = await engine.run_parameter_optimization(
            simple_cci_strategy, small_data, param_ranges, opt_config
        )
        
        if 'error' not in opt_result:
            print(f"  - Best Parameters: {opt_result['best_parameters']}")
            print(f"  - Best Sharpe: {opt_result['best_performance']['sharpe_ratio']:.2f}")
            print(f"  - Success Rate: {opt_result['optimization_summary']['success_rate']:.1f}%")
        else:
            print(f"  - Optimization Error: {opt_result['error']}")
            
    except Exception as e:
        print(f"  - Optimization failed: {e}")
    
    # 페이퍼 트레이딩 테스트
    print(f"\\n📝 Testing Paper Trading...")
    engine.start_paper_trading(5000.0)
    
    # 가상 신호로 테스트
    from advanced.multi_strategy_engine import StrategySignal, SignalStrength
    
    test_signal = StrategySignal(
        strategy_name="Test_Strategy",
        action="BUY",
        confidence=0.8,
        strength=SignalStrength.STRONG,
        position_size=0.1
    )
    
    paper_result = await engine.execute_paper_trade(test_signal, 50000.0)
    print(f"  - Paper Trade Result: {paper_result}")
    
    engine.stop_paper_trading()

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_backtesting_engine())