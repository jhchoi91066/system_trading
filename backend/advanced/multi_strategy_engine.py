"""
Multi-Strategy Engine
다중 전략 시스템 - 여러 전략을 동시에 실행하고 관리
"""

import asyncio
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import json
from concurrent.futures import ThreadPoolExecutor
import threading

from .advanced_indicators import AdvancedIndicators, CompositeSignal, SignalStrength

logger = logging.getLogger(__name__)

class StrategyStatus(Enum):
    """전략 상태"""
    INACTIVE = "inactive"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"

class PositionSide(Enum):
    """포지션 방향"""
    LONG = "long"
    SHORT = "short"
    NONE = "none"

@dataclass
class StrategyConfig:
    """전략 설정"""
    name: str
    description: str
    enabled: bool = True
    max_position_size: float = 0.1  # 최대 포지션 크기 (계좌 비중)
    risk_per_trade: float = 0.02  # 거래당 리스크 (2%)
    max_drawdown: float = 0.05  # 최대 손실 한도 (5%)
    cooldown_minutes: int = 30  # 재진입 대기시간
    indicators: List[str] = field(default_factory=list)  # 사용할 지표들
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StrategySignal:
    """전략 신호"""
    strategy_name: str
    action: str  # BUY, SELL, CLOSE
    confidence: float
    strength: SignalStrength
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    position_size: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class StrategyPosition:
    """전략별 포지션 정보"""
    strategy_name: str
    side: PositionSide
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.now)
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class StrategyPerformance:
    """전략 성과"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    last_trade_time: Optional[datetime] = None
    in_cooldown: bool = False
    cooldown_until: Optional[datetime] = None

class BaseStrategy:
    """기본 전략 클래스"""
    
    def __init__(self, config: StrategyConfig):
        self.config = config
        self.status = StrategyStatus.INACTIVE
        self.indicators_calc = AdvancedIndicators()
        self.last_signal_time = None
        self.error_count = 0
        self.max_errors = 5
        
        logger.info(f"📋 Strategy '{config.name}' initialized")
    
    async def analyze(self, market_data: pd.DataFrame) -> Optional[StrategySignal]:
        """시장 데이터 분석 및 신호 생성"""
        try:
            if self.status != StrategyStatus.ACTIVE:
                return None
            
            # 하위 클래스에서 구현
            return await self._generate_signal(market_data)
            
        except Exception as e:
            logger.error(f"🔴 Error in strategy '{self.config.name}' analysis: {e}")
            self.error_count += 1
            
            if self.error_count >= self.max_errors:
                self.status = StrategyStatus.ERROR
                logger.error(f"🚨 Strategy '{self.config.name}' disabled due to too many errors")
            
            return None
    
    async def _generate_signal(self, market_data: pd.DataFrame) -> Optional[StrategySignal]:
        """실제 신호 생성 로직 (하위 클래스에서 구현)"""
        raise NotImplementedError("Subclasses must implement _generate_signal method")
    
    def activate(self):
        """전략 활성화"""
        self.status = StrategyStatus.ACTIVE
        self.error_count = 0
        logger.info(f"✅ Strategy '{self.config.name}' activated")
    
    def deactivate(self):
        """전략 비활성화"""
        self.status = StrategyStatus.INACTIVE
        logger.info(f"⏸️ Strategy '{self.config.name}' deactivated")
    
    def pause(self):
        """전략 일시정지"""
        self.status = StrategyStatus.PAUSED
        logger.info(f"⏯️ Strategy '{self.config.name}' paused")

class CCIStrategy(BaseStrategy):
    """CCI 전략"""
    
    async def _generate_signal(self, market_data: pd.DataFrame) -> Optional[StrategySignal]:
        """CCI 신호 생성"""
        try:
            indicators = self.indicators_calc.calculate_all_indicators(market_data)
            
            if 'cci' not in indicators:
                return None
            
            cci_data = indicators['cci']
            current_price = market_data['close'].iloc[-1]
            
            # CCI 크로스오버 신호
            if cci_data.get('crossover_up'):  # -100 위로 돌파 (매수)
                return StrategySignal(
                    strategy_name=self.config.name,
                    action='BUY',
                    confidence=0.8,
                    strength=SignalStrength.STRONG,
                    entry_price=current_price,
                    stop_loss=current_price * 0.995,  # -0.5% 손절
                    take_profit=current_price * 1.015,  # +1.5% 익절
                    position_size=self.config.max_position_size,
                    metadata={'cci_value': cci_data['current'], 'signal_type': 'crossover_up'}
                )
            
            elif cci_data.get('crossover_down'):  # +100 아래로 돌파 (매도)
                return StrategySignal(
                    strategy_name=self.config.name,
                    action='SELL',
                    confidence=0.8,
                    strength=SignalStrength.STRONG,
                    entry_price=current_price,
                    stop_loss=current_price * 1.005,  # +0.5% 손절
                    take_profit=current_price * 0.985,  # -1.5% 익절
                    position_size=self.config.max_position_size,
                    metadata={'cci_value': cci_data['current'], 'signal_type': 'crossover_down'}
                )
            
            return None
            
        except Exception as e:
            logger.error(f"🔴 Error in CCI strategy signal generation: {e}")
            return None

class RSIMACDStrategy(BaseStrategy):
    """RSI + MACD 조합 전략"""
    
    async def _generate_signal(self, market_data: pd.DataFrame) -> Optional[StrategySignal]:
        """RSI + MACD 조합 신호 생성"""
        try:
            indicators = self.indicators_calc.calculate_all_indicators(market_data)
            
            if 'rsi' not in indicators or 'macd' not in indicators:
                return None
            
            rsi_data = indicators['rsi']
            macd_data = indicators['macd']
            current_price = market_data['close'].iloc[-1]
            
            # 매수 신호: RSI 과매도 + MACD 골든크로스
            if (rsi_data['current'] < 35 and 
                macd_data.get('bullish_crossover') and
                macd_data['current_macd'] < 0):
                
                confidence = min(0.9, 0.5 + (35 - rsi_data['current']) / 35 * 0.4)
                
                return StrategySignal(
                    strategy_name=self.config.name,
                    action='BUY',
                    confidence=confidence,
                    strength=SignalStrength.STRONG,
                    entry_price=current_price,
                    stop_loss=current_price * 0.98,  # -2% 손절
                    take_profit=current_price * 1.06,  # +6% 익절
                    position_size=self.config.max_position_size,
                    metadata={
                        'rsi_value': rsi_data['current'],
                        'macd_value': macd_data['current_macd'],
                        'signal_type': 'rsi_oversold_macd_bullish'
                    }
                )
            
            # 매도 신호: RSI 과매수 + MACD 데드크로스
            elif (rsi_data['current'] > 65 and 
                  macd_data.get('bearish_crossover') and
                  macd_data['current_macd'] > 0):
                
                confidence = min(0.9, 0.5 + (rsi_data['current'] - 65) / 35 * 0.4)
                
                return StrategySignal(
                    strategy_name=self.config.name,
                    action='SELL',
                    confidence=confidence,
                    strength=SignalStrength.STRONG,
                    entry_price=current_price,
                    stop_loss=current_price * 1.02,  # +2% 손절
                    take_profit=current_price * 0.94,  # -6% 익절
                    position_size=self.config.max_position_size,
                    metadata={
                        'rsi_value': rsi_data['current'],
                        'macd_value': macd_data['current_macd'],
                        'signal_type': 'rsi_overbought_macd_bearish'
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"🔴 Error in RSI+MACD strategy signal generation: {e}")
            return None

class BollingerBandStrategy(BaseStrategy):
    """볼린저 밴드 전략"""
    
    async def _generate_signal(self, market_data: pd.DataFrame) -> Optional[StrategySignal]:
        """볼린저 밴드 신호 생성"""
        try:
            indicators = self.indicators_calc.calculate_all_indicators(market_data)
            
            if 'bollinger' not in indicators or 'rsi' not in indicators:
                return None
            
            bb_data = indicators['bollinger']
            rsi_data = indicators['rsi']
            current_price = market_data['close'].iloc[-1]
            
            # 매수 신호: 볼린저 하단 접촉 + RSI 과매도
            if (bb_data.get('price_below_lower') and 
                rsi_data['current'] < 40 and
                bb_data['bb_position'] < 0.2):
                
                confidence = min(0.85, 0.6 + (40 - rsi_data['current']) / 40 * 0.25)
                
                return StrategySignal(
                    strategy_name=self.config.name,
                    action='BUY',
                    confidence=confidence,
                    strength=SignalStrength.MODERATE,
                    entry_price=current_price,
                    stop_loss=bb_data['current_lower'] * 0.995,  # 하단 밴드 아래 손절
                    take_profit=bb_data['current_middle'],  # 중간선까지 익절
                    position_size=self.config.max_position_size * 0.7,  # 보수적 크기
                    metadata={
                        'bb_position': bb_data['bb_position'],
                        'rsi_value': rsi_data['current'],
                        'signal_type': 'bollinger_bottom_rsi_oversold'
                    }
                )
            
            # 매도 신호: 볼린저 상단 접촉 + RSI 과매수
            elif (bb_data.get('price_above_upper') and 
                  rsi_data['current'] > 60 and
                  bb_data['bb_position'] > 0.8):
                
                confidence = min(0.85, 0.6 + (rsi_data['current'] - 60) / 40 * 0.25)
                
                return StrategySignal(
                    strategy_name=self.config.name,
                    action='SELL',
                    confidence=confidence,
                    strength=SignalStrength.MODERATE,
                    entry_price=current_price,
                    stop_loss=bb_data['current_upper'] * 1.005,  # 상단 밴드 위 손절
                    take_profit=bb_data['current_middle'],  # 중간선까지 익절
                    position_size=self.config.max_position_size * 0.7,  # 보수적 크기
                    metadata={
                        'bb_position': bb_data['bb_position'],
                        'rsi_value': rsi_data['current'],
                        'signal_type': 'bollinger_top_rsi_overbought'
                    }
                )
            
            return None
            
        except Exception as e:
            logger.error(f"🔴 Error in Bollinger Band strategy signal generation: {e}")
            return None

class MultiStrategyEngine:
    """다중 전략 엔진"""
    
    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}
        self.positions: Dict[str, StrategyPosition] = {}
        self.performance: Dict[str, StrategyPerformance] = {}
        self.signal_history: List[StrategySignal] = []
        self.max_history = 1000
        self.is_running = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 전략 조합 제한
        self.max_concurrent_positions = 3
        self.max_total_risk = 0.15  # 전체 리스크 한도 15%
        self.correlation_limit = 0.7  # 상관관계 한도
        
        logger.info("🚀 Multi-Strategy Engine initialized")
    
    def add_strategy(self, strategy: BaseStrategy):
        """전략 추가"""
        self.strategies[strategy.config.name] = strategy
        self.performance[strategy.config.name] = StrategyPerformance(strategy_name=strategy.config.name)
        logger.info(f"✅ Added strategy: {strategy.config.name}")
    
    def remove_strategy(self, strategy_name: str):
        """전략 제거"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].deactivate()
            del self.strategies[strategy_name]
            if strategy_name in self.performance:
                del self.performance[strategy_name]
            logger.info(f"🗑️ Removed strategy: {strategy_name}")
    
    def activate_strategy(self, strategy_name: str):
        """전략 활성화"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].activate()
            logger.info(f"🟢 Activated strategy: {strategy_name}")
    
    def deactivate_strategy(self, strategy_name: str):
        """전략 비활성화"""
        if strategy_name in self.strategies:
            self.strategies[strategy_name].deactivate()
            logger.info(f"🔴 Deactivated strategy: {strategy_name}")
    
    async def get_active_strategies(self) -> List[Dict[str, Any]]:
        """활성화된 전략 목록 반환"""
        active_strategies = []
        for strategy_name, strategy in self.strategies.items():
            if strategy.status == StrategyStatus.ACTIVE:
                performance = self.performance.get(strategy_name)
                active_strategies.append({
                    "name": strategy_name,
                    "enabled": True,
                    "type": strategy.config.strategy_type.value,
                    "description": strategy.config.description,
                    "pnl": performance.total_pnl if performance else 0.0,
                    "win_rate": performance.win_rate if performance else 0.0,
                    "total_trades": performance.total_trades if performance else 0
                })
        return active_strategies
    
    async def analyze_market(self, market_data: pd.DataFrame) -> List[StrategySignal]:
        """시장 분석 및 모든 전략의 신호 수집"""
        if market_data is None or len(market_data) < 50:
            logger.warning("⚠️ Insufficient market data for analysis")
            return []
        
        signals = []
        
        try:
            # 모든 활성화된 전략에서 신호 수집
            tasks = []
            for strategy_name, strategy in self.strategies.items():
                if strategy.status == StrategyStatus.ACTIVE:
                    tasks.append(self._analyze_strategy(strategy, market_data))
            
            # 병렬로 전략 분석 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"🔴 Strategy analysis error: {result}")
                elif result:
                    signals.append(result)
            
            # 신호 필터링 및 검증
            filtered_signals = await self._filter_signals(signals, market_data)
            
            # 히스토리에 추가
            for signal in filtered_signals:
                self.signal_history.append(signal)
            
            if len(self.signal_history) > self.max_history:
                self.signal_history = self.signal_history[-self.max_history:]
            
            logger.info(f"📊 Generated {len(filtered_signals)} filtered signals from {len(signals)} raw signals")
            
            return filtered_signals
            
        except Exception as e:
            logger.error(f"🔴 Error in market analysis: {e}")
            return []
    
    async def _analyze_strategy(self, strategy: BaseStrategy, market_data: pd.DataFrame) -> Optional[StrategySignal]:
        """개별 전략 분석"""
        try:
            # 쿨다운 확인
            if self._is_in_cooldown(strategy.config.name):
                return None
            
            # 리스크 한도 확인
            if not self._check_risk_limits(strategy.config.name):
                return None
            
            # 신호 생성
            signal = await strategy.analyze(market_data)
            
            if signal:
                logger.info(f"📈 Signal from {strategy.config.name}: {signal.action} (confidence: {signal.confidence:.2f})")
            
            return signal
            
        except Exception as e:
            logger.error(f"🔴 Error analyzing strategy {strategy.config.name}: {e}")
            return None
    
    async def _filter_signals(self, signals: List[StrategySignal], market_data: pd.DataFrame) -> List[StrategySignal]:
        """신호 필터링"""
        if not signals:
            return []
        
        filtered = []
        current_positions = len([p for p in self.positions.values() if p.side != PositionSide.NONE])
        
        # 1. 동시 포지션 수 제한
        if current_positions >= self.max_concurrent_positions:
            logger.warning(f"⚠️ Max concurrent positions reached ({current_positions})")
            # 현재 포지션 종료 신호만 허용
            filtered = [s for s in signals if s.action == 'CLOSE']
        else:
            # 2. 신호 품질 기반 필터링
            high_quality_signals = [
                s for s in signals 
                if s.confidence >= 0.6 and s.strength.value >= 3
            ]
            
            # 3. 상관관계 기반 필터링 (같은 방향 신호가 너무 많으면 제한)
            buy_signals = [s for s in high_quality_signals if s.action == 'BUY']
            sell_signals = [s for s in high_quality_signals if s.action == 'SELL']
            
            # 최고 품질 신호 우선 선택
            buy_signals.sort(key=lambda x: x.confidence * x.strength.value, reverse=True)
            sell_signals.sort(key=lambda x: x.confidence * x.strength.value, reverse=True)
            
            # 리스크 분산을 위해 최대 2개씩만 허용
            filtered.extend(buy_signals[:2])
            filtered.extend(sell_signals[:2])
        
        # 4. 최종 리스크 검증
        total_risk = sum(s.position_size * s.confidence for s in filtered if s.action in ['BUY', 'SELL'])
        if total_risk > self.max_total_risk:
            # 리스크가 높은 순서로 정렬하여 제한
            filtered.sort(key=lambda x: x.position_size * x.confidence, reverse=True)
            cumulative_risk = 0
            final_signals = []
            
            for signal in filtered:
                signal_risk = signal.position_size * signal.confidence
                if cumulative_risk + signal_risk <= self.max_total_risk:
                    final_signals.append(signal)
                    cumulative_risk += signal_risk
                else:
                    logger.warning(f"⚠️ Signal from {signal.strategy_name} rejected due to risk limit")
            
            filtered = final_signals
        
        logger.info(f"🔍 Filtered {len(signals)} signals → {len(filtered)} final signals")
        return filtered
    
    def _is_in_cooldown(self, strategy_name: str) -> bool:
        """쿨다운 상태 확인"""
        if strategy_name not in self.performance:
            return False
        
        perf = self.performance[strategy_name]
        if perf.in_cooldown and perf.cooldown_until:
            if datetime.now() < perf.cooldown_until:
                return True
            else:
                # 쿨다운 해제
                perf.in_cooldown = False
                perf.cooldown_until = None
        
        return False
    
    def _check_risk_limits(self, strategy_name: str) -> bool:
        """리스크 한도 확인"""
        if strategy_name not in self.performance:
            return True
        
        perf = self.performance[strategy_name]
        strategy_config = self.strategies[strategy_name].config
        
        # 최대 손실 한도 확인
        if abs(perf.total_pnl_pct) > strategy_config.max_drawdown:
            logger.warning(f"⚠️ Strategy {strategy_name} exceeded max drawdown limit")
            return False
        
        return True
    
    def start_cooldown(self, strategy_name: str):
        """쿨다운 시작"""
        if strategy_name in self.performance and strategy_name in self.strategies:
            cooldown_minutes = self.strategies[strategy_name].config.cooldown_minutes
            perf = self.performance[strategy_name]
            perf.in_cooldown = True
            perf.cooldown_until = datetime.now() + timedelta(minutes=cooldown_minutes)
            logger.info(f"⏳ Started cooldown for {strategy_name} ({cooldown_minutes} minutes)")
    
    def update_position(self, strategy_name: str, position: StrategyPosition):
        """포지션 업데이트"""
        self.positions[strategy_name] = position
        position.last_update = datetime.now()
        logger.info(f"📊 Updated position for {strategy_name}: {position.side.value} {position.size}")
    
    def close_position(self, strategy_name: str, exit_price: float):
        """포지션 종료 및 성과 업데이트"""
        if strategy_name not in self.positions:
            return
        
        position = self.positions[strategy_name]
        if position.side == PositionSide.NONE:
            return
        
        # 실현 손익 계산
        if position.side == PositionSide.LONG:
            pnl = (exit_price - position.entry_price) * position.size
        else:  # SHORT
            pnl = (position.entry_price - exit_price) * position.size
        
        pnl_pct = pnl / (position.entry_price * position.size) * 100
        
        # 성과 업데이트
        perf = self.performance[strategy_name]
        perf.total_trades += 1
        perf.total_pnl += pnl
        perf.total_pnl_pct += pnl_pct
        perf.last_trade_time = datetime.now()
        
        if pnl > 0:
            perf.winning_trades += 1
            perf.avg_win = (perf.avg_win * (perf.winning_trades - 1) + pnl) / perf.winning_trades
        else:
            perf.losing_trades += 1
            perf.avg_loss = (perf.avg_loss * (perf.losing_trades - 1) + abs(pnl)) / perf.losing_trades
        
        # 승률 계산
        perf.win_rate = perf.winning_trades / perf.total_trades * 100
        
        # Profit Factor 계산
        if perf.avg_loss > 0:
            perf.profit_factor = (perf.avg_win * perf.winning_trades) / (perf.avg_loss * perf.losing_trades)
        
        # 포지션 초기화
        position.side = PositionSide.NONE
        position.size = 0
        position.unrealized_pnl = 0
        position.unrealized_pnl_pct = 0
        
        logger.info(f"💰 Closed position for {strategy_name}: PnL {pnl:.2f} ({pnl_pct:.2f}%)")
        
        # 손실 거래 후 쿨다운
        if pnl < 0:
            self.start_cooldown(strategy_name)
    
    def get_system_status(self) -> Dict[str, Any]:
        """시스템 상태 조회"""
        active_strategies = sum(1 for s in self.strategies.values() if s.status == StrategyStatus.ACTIVE)
        total_positions = sum(1 for p in self.positions.values() if p.side != PositionSide.NONE)
        
        # 전체 성과 집계
        total_pnl = sum(perf.total_pnl for perf in self.performance.values())
        total_trades = sum(perf.total_trades for perf in self.performance.values())
        total_wins = sum(perf.winning_trades for perf in self.performance.values())
        
        overall_win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            'engine_status': 'running' if self.is_running else 'stopped',
            'strategies': {
                'total': len(self.strategies),
                'active': active_strategies,
                'inactive': len(self.strategies) - active_strategies
            },
            'positions': {
                'total': total_positions,
                'max_allowed': self.max_concurrent_positions
            },
            'performance': {
                'total_pnl': round(total_pnl, 2),
                'total_trades': total_trades,
                'overall_win_rate': round(overall_win_rate, 2),
                'signals_generated': len(self.signal_history)
            },
            'risk_management': {
                'max_total_risk': self.max_total_risk,
                'correlation_limit': self.correlation_limit,
                'current_risk_usage': sum(p.size for p in self.positions.values() if p.side != PositionSide.NONE)
            },
            'strategy_details': [
                {
                    'name': name,
                    'status': strategy.status.value,
                    'error_count': strategy.error_count,
                    'performance': {
                        'total_trades': self.performance[name].total_trades,
                        'win_rate': round(self.performance[name].win_rate, 2),
                        'total_pnl': round(self.performance[name].total_pnl, 2),
                        'in_cooldown': self.performance[name].in_cooldown
                    }
                }
                for name, strategy in self.strategies.items()
            ]
        }

# 전략 팩토리 함수들
def create_default_strategies() -> List[BaseStrategy]:
    """기본 전략들 생성"""
    strategies = []
    
    # 1. CCI 전략
    cci_config = StrategyConfig(
        name="CCI_Crossover",
        description="CCI -100/+100 크로스오버 전략",
        enabled=True,
        max_position_size=0.08,
        risk_per_trade=0.015,
        cooldown_minutes=30,
        indicators=['cci'],
        parameters={'cci_period': 20, 'overbought': 100, 'oversold': -100}
    )
    strategies.append(CCIStrategy(cci_config))
    
    # 2. RSI+MACD 조합 전략
    rsi_macd_config = StrategyConfig(
        name="RSI_MACD_Combo",
        description="RSI 과매수/과매도 + MACD 크로스오버 조합",
        enabled=True,
        max_position_size=0.10,
        risk_per_trade=0.02,
        cooldown_minutes=45,
        indicators=['rsi', 'macd'],
        parameters={'rsi_period': 14, 'rsi_oversold': 35, 'rsi_overbought': 65}
    )
    strategies.append(RSIMACDStrategy(rsi_macd_config))
    
    # 3. 볼린저 밴드 전략
    bb_config = StrategyConfig(
        name="Bollinger_Reversal",
        description="볼린저 밴드 반전 전략",
        enabled=True,
        max_position_size=0.07,
        risk_per_trade=0.015,
        cooldown_minutes=60,
        indicators=['bollinger', 'rsi'],
        parameters={'bb_period': 20, 'bb_std': 2, 'rsi_threshold': 40}
    )
    strategies.append(BollingerBandStrategy(bb_config))
    
    return strategies

# 테스트 함수
async def test_multi_strategy_engine():
    """Multi-Strategy Engine 테스트"""
    print("🧪 Testing Multi-Strategy Engine...")
    
    # 샘플 데이터 생성
    dates = pd.date_range('2025-01-01', periods=200, freq='5min')
    np.random.seed(42)
    
    price_base = 50000
    price_data = price_base + np.cumsum(np.random.randn(200) * 100)
    
    market_data = pd.DataFrame({
        'timestamp': dates,
        'open': price_data + np.random.randn(200) * 50,
        'high': price_data + np.abs(np.random.randn(200) * 100),
        'low': price_data - np.abs(np.random.randn(200) * 100),
        'close': price_data,
        'volume': np.random.randint(1000, 10000, 200)
    })
    
    # 다중 전략 엔진 생성
    engine = MultiStrategyEngine()
    
    # 기본 전략들 추가
    strategies = create_default_strategies()
    for strategy in strategies:
        engine.add_strategy(strategy)
        engine.activate_strategy(strategy.config.name)
    
    # 시스템 상태 확인
    status = engine.get_system_status()
    print(f"🚀 Engine Status: {status['engine_status']}")
    print(f"📊 Active Strategies: {status['strategies']['active']}/{status['strategies']['total']}")
    
    # 시장 분석 실행
    signals = await engine.analyze_market(market_data)
    print(f"🎯 Generated Signals: {len(signals)}")
    
    for signal in signals:
        print(f"  - {signal.strategy_name}: {signal.action}")
        print(f"    Confidence: {signal.confidence:.2f}, Strength: {signal.strength.name}")
        print(f"    Entry: ${signal.entry_price:.2f}, SL: ${signal.stop_loss:.2f}, TP: ${signal.take_profit:.2f}")
    
    # 최종 상태
    final_status = engine.get_system_status()
    print(f"📈 Total Signals Generated: {final_status['performance']['signals_generated']}")
    print(f"🎮 Strategy Details:")
    for strategy_detail in final_status['strategy_details']:
        print(f"  - {strategy_detail['name']}: {strategy_detail['status']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_multi_strategy_engine())