"""
Portfolio Manager - 포트폴리오 관리 & 다중 전략 지원
Kelly Criterion, Risk Parity, 자동 리밸런싱
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class PositionSizingMethod(Enum):
    """포지션 사이징 방법"""
    FIXED = "fixed"
    KELLY = "kelly"
    RISK_PARITY = "risk_parity"
    VOLATILITY_TARGET = "volatility_target"
    OPTIMAL_F = "optimal_f"

class RebalanceFrequency(Enum):
    """리밸런싱 주기"""
    NEVER = "never"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

@dataclass
class AssetAllocation:
    """자산 배분"""
    symbol: str
    target_weight: float  # 목표 비중 (0-1)
    current_weight: float  # 현재 비중 (0-1)
    current_value: float  # 현재 가치
    target_value: float  # 목표 가치
    deviation: float  # 편차 (target - current)
    last_rebalance: Optional[datetime] = None

@dataclass
class StrategyAllocation:
    """전략 배분"""
    strategy_name: str
    target_allocation: float  # 목표 배분 (0-1)
    current_allocation: float  # 현재 배분 (0-1)
    performance_score: float  # 성과 점수 (0-1)
    risk_score: float  # 리스크 점수 (0-1)
    correlation_to_portfolio: float  # 포트폴리오 상관관계
    kelly_optimal: float  # Kelly Criterion 최적 배분
    is_active: bool = True
    last_update: datetime = field(default_factory=datetime.now)

@dataclass
class PortfolioMetrics:
    """포트폴리오 메트릭"""
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    daily_pnl: float
    daily_pnl_pct: float
    weekly_pnl: float
    weekly_pnl_pct: float
    monthly_pnl: float
    monthly_pnl_pct: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    max_drawdown_pct: float
    var_95: float
    beta: float
    correlation_to_market: float
    diversification_ratio: float
    concentration_risk: float  # HHI Index
    last_updated: datetime = field(default_factory=datetime.now)

@dataclass
class RebalanceRecommendation:
    """리밸런싱 권장사항"""
    action: str  # BUY, SELL, HOLD
    symbol: str
    strategy_name: str
    current_weight: float
    target_weight: float
    weight_difference: float
    recommended_amount: float
    urgency: str  # LOW, MEDIUM, HIGH, CRITICAL
    reason: str
    expected_impact: Dict[str, float]

class PortfolioManager:
    """포트폴리오 관리자"""
    
    def __init__(self, total_capital: float = 10000.0):
        self.total_capital = total_capital
        self.available_capital = total_capital
        self.positions: Dict[str, AssetAllocation] = {}
        self.strategy_allocations: Dict[str, StrategyAllocation] = {}
        self.transaction_history: List[Dict] = []
        self.rebalance_history: List[Dict] = []
        
        # 설정
        self.position_sizing_method = PositionSizingMethod.KELLY
        self.rebalance_frequency = RebalanceFrequency.DAILY
        self.rebalance_threshold = 0.05  # 5% 편차시 리밸런싱
        self.max_position_size = 0.25  # 단일 포지션 최대 25%
        self.max_correlation = 0.7  # 최대 상관관계
        self.target_volatility = 0.15  # 목표 변동성 15%
        
        # 리스크 관리
        self.max_drawdown_limit = 0.20  # 20% 최대 낙폭 한도
        self.stop_loss_threshold = 0.10  # 10% 손실시 전체 포지션 정리
        
        logger.info(f"💼 Portfolio Manager initialized with ${total_capital:,.2f}")
    
    def add_strategy(self, strategy_name: str, target_allocation: float, performance_data: List[Dict] = None):
        """전략 추가"""
        try:
            # 성과 데이터 분석
            performance_score = 0.5  # 기본값
            risk_score = 0.5
            
            if performance_data:
                returns = [trade.get('pnl_pct', 0) / 100 for trade in performance_data]
                
                if returns:
                    # 성과 점수 계산 (Sharpe ratio 기반)
                    mean_return = np.mean(returns)
                    std_return = np.std(returns)
                    sharpe = mean_return / std_return if std_return > 0 else 0
                    performance_score = min(1.0, max(0.0, (sharpe + 2) / 4))  # -2~2 범위를 0~1로 변환
                    
                    # 리스크 점수 계산 (변동성 기반)
                    annual_vol = std_return * np.sqrt(252)
                    risk_score = min(1.0, max(0.0, 1 - annual_vol / 0.5))  # 50% 변동성을 기준으로 정규화
            
            # Kelly Criterion 계산
            kelly_optimal = self._calculate_kelly_optimal(performance_data) if performance_data else target_allocation
            
            self.strategy_allocations[strategy_name] = StrategyAllocation(
                strategy_name=strategy_name,
                target_allocation=target_allocation,
                current_allocation=0.0,
                performance_score=performance_score,
                risk_score=risk_score,
                correlation_to_portfolio=0.0,
                kelly_optimal=kelly_optimal
            )
            
            logger.info(f"✅ Added strategy '{strategy_name}' with {target_allocation:.1%} allocation")
            
        except Exception as e:
            logger.error(f"🔴 Error adding strategy {strategy_name}: {e}")
    
    def _calculate_kelly_optimal(self, performance_data: List[Dict]) -> float:
        """Kelly Criterion 계산"""
        try:
            if not performance_data:
                return 0.1  # 기본값 10%
            
            returns = [trade.get('pnl_pct', 0) / 100 for trade in performance_data]
            
            if len(returns) < 10:  # 최소 10개 거래 필요
                return 0.1
            
            wins = [r for r in returns if r > 0]
            losses = [r for r in returns if r < 0]
            
            if not wins or not losses:
                return 0.1
            
            # Kelly Formula: f* = (bp - q) / b
            # b = 평균 수익률 / 평균 손실률
            # p = 승률
            # q = 패률 = 1 - p
            
            avg_win = np.mean(wins)
            avg_loss = abs(np.mean(losses))
            win_prob = len(wins) / len(returns)
            loss_prob = 1 - win_prob
            
            if avg_loss == 0:
                return 0.1
            
            b = avg_win / avg_loss
            kelly_fraction = (b * win_prob - loss_prob) / b
            
            # Kelly 값 제한 (0~25%)
            kelly_fraction = max(0, min(0.25, kelly_fraction))
            
            return kelly_fraction
            
        except Exception as e:
            logger.error(f"🔴 Error calculating Kelly optimal: {e}")
            return 0.1
    
    def calculate_risk_parity_weights(self, returns_data: Dict[str, List[float]]) -> Dict[str, float]:
        """Risk Parity 가중치 계산"""
        try:
            if not returns_data:
                return {}
            
            strategies = list(returns_data.keys())
            n_strategies = len(strategies)
            
            if n_strategies == 1:
                return {strategies[0]: 1.0}
            
            # 각 전략의 변동성 계산
            volatilities = {}
            for strategy, returns in returns_data.items():
                if returns:
                    vol = np.std(returns) * np.sqrt(252)  # 연간 변동성
                    volatilities[strategy] = max(vol, 0.01)  # 최소 1% 변동성
                else:
                    volatilities[strategy] = 0.2  # 기본 20% 변동성
            
            # 역변동성 가중치 (Risk Parity)
            inv_vol_sum = sum(1/vol for vol in volatilities.values())
            weights = {
                strategy: (1/vol) / inv_vol_sum 
                for strategy, vol in volatilities.items()
            }
            
            logger.info(f"📊 Risk Parity weights calculated for {n_strategies} strategies")
            return weights
            
        except Exception as e:
            logger.error(f"🔴 Error calculating risk parity weights: {e}")
            return {}
    
    def calculate_optimal_position_sizes(self, current_prices: Dict[str, float]) -> Dict[str, float]:
        """최적 포지션 크기 계산"""
        try:
            if not self.strategy_allocations:
                return {}
            
            position_sizes = {}
            total_allocation = 0.0
            
            for strategy_name, allocation in self.strategy_allocations.items():
                if not allocation.is_active:
                    continue
                
                # 포지션 사이징 방법에 따라 계산
                if self.position_sizing_method == PositionSizingMethod.KELLY:
                    size = allocation.kelly_optimal
                elif self.position_sizing_method == PositionSizingMethod.FIXED:
                    size = allocation.target_allocation
                elif self.position_sizing_method == PositionSizingMethod.RISK_PARITY:
                    # 전체 리스크 패리티에서 이 전략의 비중
                    size = allocation.target_allocation / allocation.risk_score if allocation.risk_score > 0 else 0.1
                else:
                    size = allocation.target_allocation
                
                # 최대 포지션 크기 제한
                size = min(size, self.max_position_size)
                
                # 가용 자본 기준으로 실제 금액 계산
                position_value = size * self.total_capital
                position_sizes[strategy_name] = position_value
                total_allocation += size
            
            # 총 배분이 100%를 초과하면 비례 축소
            if total_allocation > 1.0:
                scale_factor = 1.0 / total_allocation
                position_sizes = {k: v * scale_factor for k, v in position_sizes.items()}
                logger.warning(f"⚠️ Total allocation exceeded 100%, scaled down by {scale_factor:.2f}")
            
            logger.info(f"💰 Calculated position sizes for {len(position_sizes)} strategies")
            return position_sizes
            
        except Exception as e:
            logger.error(f"🔴 Error calculating optimal position sizes: {e}")
            return {}
    
    def check_rebalance_needed(self) -> List[RebalanceRecommendation]:
        """리밸런싱 필요성 확인"""
        recommendations = []
        
        try:
            for strategy_name, allocation in self.strategy_allocations.items():
                if not allocation.is_active:
                    continue
                
                weight_diff = allocation.target_allocation - allocation.current_allocation
                abs_diff = abs(weight_diff)
                
                # 리밸런싱 임계값 확인
                if abs_diff > self.rebalance_threshold:
                    
                    # 긴급도 결정
                    if abs_diff > 0.15:  # 15% 이상 편차
                        urgency = "CRITICAL"
                    elif abs_diff > 0.10:  # 10% 이상 편차
                        urgency = "HIGH"
                    elif abs_diff > 0.07:  # 7% 이상 편차
                        urgency = "MEDIUM"
                    else:
                        urgency = "LOW"
                    
                    # 액션 결정
                    action = "BUY" if weight_diff > 0 else "SELL"
                    recommended_amount = abs(weight_diff) * self.total_capital
                    
                    # 예상 효과
                    expected_impact = {
                        'risk_reduction': abs_diff * 0.1,  # 편차 감소에 따른 리스크 감소
                        'return_improvement': abs_diff * allocation.performance_score * 0.05,
                        'diversification_improvement': abs_diff * 0.03
                    }
                    
                    recommendation = RebalanceRecommendation(
                        action=action,
                        symbol=f"{strategy_name}_ALLOCATION",
                        strategy_name=strategy_name,
                        current_weight=allocation.current_allocation,
                        target_weight=allocation.target_allocation,
                        weight_difference=weight_diff,
                        recommended_amount=recommended_amount,
                        urgency=urgency,
                        reason=f"Weight deviation {abs_diff:.1%} exceeds threshold {self.rebalance_threshold:.1%}",
                        expected_impact=expected_impact
                    )
                    
                    recommendations.append(recommendation)
            
            if recommendations:
                logger.info(f"🔄 Found {len(recommendations)} rebalance recommendations")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"🔴 Error checking rebalance needs: {e}")
            return []
    
    def calculate_portfolio_metrics(self, price_history: Dict[str, List[float]], returns_history: List[float]) -> PortfolioMetrics:
        """포트폴리오 메트릭 계산"""
        try:
            if not returns_history:
                return PortfolioMetrics(
                    total_value=self.total_capital,
                    total_pnl=0, total_pnl_pct=0,
                    daily_pnl=0, daily_pnl_pct=0,
                    weekly_pnl=0, weekly_pnl_pct=0,
                    monthly_pnl=0, monthly_pnl_pct=0,
                    volatility=0, sharpe_ratio=0,
                    max_drawdown=0, max_drawdown_pct=0,
                    var_95=0, beta=0,
                    correlation_to_market=0,
                    diversification_ratio=1.0,
                    concentration_risk=1.0
                )
            
            returns = np.array(returns_history)
            
            # 기본 수익률 통계
            total_return = np.sum(returns)
            total_return_pct = total_return / self.total_capital * 100
            
            # 기간별 수익률
            daily_return = returns[-1] if len(returns) > 0 else 0
            weekly_return = np.sum(returns[-7:]) if len(returns) >= 7 else total_return
            monthly_return = np.sum(returns[-30:]) if len(returns) >= 30 else total_return
            
            # 리스크 메트릭
            volatility = np.std(returns) * np.sqrt(252) if len(returns) > 1 else 0
            
            # Sharpe Ratio (연간 무위험 수익률 2% 가정)
            risk_free_rate = 0.02 / 252  # 일간 무위험 수익률
            excess_returns = returns - risk_free_rate
            sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
            
            # VaR 95%
            var_95 = np.percentile(returns, 5) if len(returns) > 20 else 0
            
            # 최대 낙폭
            cumulative_returns = np.cumsum(returns)
            peak = np.maximum.accumulate(cumulative_returns)
            drawdown = cumulative_returns - peak
            max_drawdown = np.min(drawdown)
            max_drawdown_pct = max_drawdown / self.total_capital * 100 if self.total_capital > 0 else 0
            
            # 다양성 비율 (Diversification Ratio)
            diversification_ratio = self._calculate_diversification_ratio()
            
            # 집중도 리스크 (HHI)
            concentration_risk = self._calculate_concentration_risk()
            
            metrics = PortfolioMetrics(
                total_value=self.total_capital + total_return,
                total_pnl=total_return,
                total_pnl_pct=total_return_pct,
                daily_pnl=daily_return,
                daily_pnl_pct=daily_return / self.total_capital * 100,
                weekly_pnl=weekly_return,
                weekly_pnl_pct=weekly_return / self.total_capital * 100,
                monthly_pnl=monthly_return,
                monthly_pnl_pct=monthly_return / self.total_capital * 100,
                volatility=volatility * 100,
                sharpe_ratio=sharpe_ratio,
                max_drawdown=max_drawdown,
                max_drawdown_pct=max_drawdown_pct,
                var_95=var_95 * 100,
                beta=0.0,  # 벤치마크 데이터 필요
                correlation_to_market=0.0,  # 시장 데이터 필요
                diversification_ratio=diversification_ratio,
                concentration_risk=concentration_risk
            )
            
            logger.info(f"📊 Portfolio metrics calculated: Total PnL {total_return_pct:.2f}%, Sharpe {sharpe_ratio:.2f}")
            return metrics
            
        except Exception as e:
            logger.error(f"🔴 Error calculating portfolio metrics: {e}")
            return PortfolioMetrics(total_value=self.total_capital, total_pnl=0, total_pnl_pct=0,
                                  daily_pnl=0, daily_pnl_pct=0, weekly_pnl=0, weekly_pnl_pct=0,
                                  monthly_pnl=0, monthly_pnl_pct=0, volatility=0, sharpe_ratio=0,
                                  max_drawdown=0, max_drawdown_pct=0, var_95=0, beta=0,
                                  correlation_to_market=0, diversification_ratio=1.0, concentration_risk=1.0)
    
    def _calculate_diversification_ratio(self) -> float:
        """다양성 비율 계산"""
        try:
            if len(self.strategy_allocations) <= 1:
                return 1.0
            
            # 가중 평균 변동성 / 포트폴리오 변동성
            # 단순화된 계산 (실제로는 공분산 행렬 필요)
            weights = [alloc.current_allocation for alloc in self.strategy_allocations.values()]
            diversification = 1 / np.sqrt(np.sum(np.array(weights) ** 2))
            
            return min(diversification, len(self.strategy_allocations))
            
        except Exception as e:
            logger.error(f"🔴 Error calculating diversification ratio: {e}")
            return 1.0
    
    def _calculate_concentration_risk(self) -> float:
        """집중도 리스크 계산 (HHI Index)"""
        try:
            if not self.strategy_allocations:
                return 1.0
            
            weights = [alloc.current_allocation for alloc in self.strategy_allocations.values()]
            hhi = sum(w**2 for w in weights)
            
            return hhi
            
        except Exception as e:
            logger.error(f"🔴 Error calculating concentration risk: {e}")
            return 1.0
    
    def update_positions(self, current_positions: Dict[str, Dict]):
        """현재 포지션 업데이트"""
        try:
            total_value = 0
            
            for strategy_name, position_data in current_positions.items():
                current_value = position_data.get('value', 0)
                total_value += current_value
                
                # 전략 배분 업데이트
                if strategy_name in self.strategy_allocations:
                    self.strategy_allocations[strategy_name].current_allocation = current_value / self.total_capital
                    self.strategy_allocations[strategy_name].last_update = datetime.now()
            
            # 가용 자본 업데이트
            self.available_capital = max(0, self.total_capital - total_value)
            
            logger.info(f"💼 Updated positions: Total value ${total_value:,.2f}, Available ${self.available_capital:,.2f}")
            
        except Exception as e:
            logger.error(f"🔴 Error updating positions: {e}")
    
    def execute_rebalancing(self, recommendations: List[RebalanceRecommendation]) -> Dict[str, Any]:
        """리밸런싱 실행"""
        try:
            executed_actions = []
            total_trades = 0
            total_amount = 0
            
            # 긴급도 순으로 정렬
            urgency_order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
            recommendations.sort(key=lambda x: urgency_order.get(x.urgency, 0), reverse=True)
            
            for rec in recommendations:
                try:
                    # 실제 거래 실행 (시뮬레이션)
                    executed_actions.append({
                        'strategy': rec.strategy_name,
                        'action': rec.action,
                        'amount': rec.recommended_amount,
                        'urgency': rec.urgency,
                        'reason': rec.reason,
                        'executed_at': datetime.now().isoformat()
                    })
                    
                    total_trades += 1
                    total_amount += rec.recommended_amount
                    
                    # 리밸런싱 히스토리에 기록
                    self.rebalance_history.append({
                        'timestamp': datetime.now(),
                        'strategy': rec.strategy_name,
                        'action': rec.action,
                        'amount': rec.recommended_amount,
                        'weight_before': rec.current_weight,
                        'weight_after': rec.target_weight,
                        'urgency': rec.urgency
                    })
                    
                    logger.info(f"🔄 Executed rebalance: {rec.strategy_name} {rec.action} ${rec.recommended_amount:.2f}")
                    
                except Exception as e:
                    logger.error(f"🔴 Error executing rebalance for {rec.strategy_name}: {e}")
            
            # 최대 100개 히스토리 유지
            if len(self.rebalance_history) > 100:
                self.rebalance_history = self.rebalance_history[-100:]
            
            result = {
                'executed_actions': executed_actions,
                'total_trades': total_trades,
                'total_amount': total_amount,
                'execution_time': datetime.now().isoformat(),
                'next_rebalance_check': (datetime.now() + timedelta(hours=24)).isoformat()
            }
            
            logger.info(f"✅ Rebalancing completed: {total_trades} trades, ${total_amount:,.2f} total")
            return result
            
        except Exception as e:
            logger.error(f"🔴 Error executing rebalancing: {e}")
            return {'error': str(e)}
    
    def get_portfolio_status(self) -> Dict[str, Any]:
        """포트폴리오 상태 조회"""
        try:
            total_allocated = sum(alloc.current_allocation for alloc in self.strategy_allocations.values())
            available_pct = (self.available_capital / self.total_capital) * 100
            
            # 전략별 상세 정보
            strategy_details = []
            for name, allocation in self.strategy_allocations.items():
                strategy_details.append({
                    'name': name,
                    'target_allocation': round(allocation.target_allocation * 100, 2),
                    'current_allocation': round(allocation.current_allocation * 100, 2),
                    'performance_score': round(allocation.performance_score, 3),
                    'risk_score': round(allocation.risk_score, 3),
                    'kelly_optimal': round(allocation.kelly_optimal * 100, 2),
                    'is_active': allocation.is_active,
                    'deviation': round((allocation.target_allocation - allocation.current_allocation) * 100, 2)
                })
            
            # 리밸런싱 권장사항
            rebalance_recs = self.check_rebalance_needed()
            
            return {
                'capital_management': {
                    'total_capital': self.total_capital,
                    'available_capital': self.available_capital,
                    'allocated_capital': self.total_capital - self.available_capital,
                    'available_percentage': round(available_pct, 2),
                    'allocated_percentage': round(total_allocated * 100, 2)
                },
                'strategies': {
                    'total_strategies': len(self.strategy_allocations),
                    'active_strategies': sum(1 for alloc in self.strategy_allocations.values() if alloc.is_active),
                    'strategy_details': strategy_details
                },
                'risk_management': {
                    'position_sizing_method': self.position_sizing_method.value,
                    'max_position_size': round(self.max_position_size * 100, 2),
                    'max_correlation': self.max_correlation,
                    'target_volatility': round(self.target_volatility * 100, 2),
                    'concentration_risk': round(self._calculate_concentration_risk(), 3),
                    'diversification_ratio': round(self._calculate_diversification_ratio(), 2)
                },
                'rebalancing': {
                    'frequency': self.rebalance_frequency.value,
                    'threshold': round(self.rebalance_threshold * 100, 2),
                    'recommendations_count': len(rebalance_recs),
                    'recommendations': [
                        {
                            'strategy': rec.strategy_name,
                            'action': rec.action,
                            'amount': round(rec.recommended_amount, 2),
                            'urgency': rec.urgency,
                            'deviation': round(rec.weight_difference * 100, 2)
                        }
                        for rec in rebalance_recs[:5]  # 상위 5개만
                    ],
                    'last_rebalance': self.rebalance_history[-1]['timestamp'].isoformat() if self.rebalance_history else None
                },
                'transaction_summary': {
                    'total_transactions': len(self.transaction_history),
                    'rebalance_count': len(self.rebalance_history),
                    'last_transaction': self.transaction_history[-1] if self.transaction_history else None
                }
            }
            
        except Exception as e:
            logger.error(f"🔴 Error getting portfolio status: {e}")
            return {'error': str(e)}
    
    def optimize_allocation(self, performance_data: Dict[str, List[Dict]], method: str = "risk_parity") -> Dict[str, float]:
        """배분 최적화"""
        try:
            if not performance_data:
                return {}
            
            if method == "risk_parity":
                # 각 전략의 수익률 데이터 추출
                returns_data = {}
                for strategy, trades in performance_data.items():
                    returns = [trade.get('pnl_pct', 0) / 100 for trade in trades]
                    if returns:
                        returns_data[strategy] = returns
                
                return self.calculate_risk_parity_weights(returns_data)
            
            elif method == "kelly":
                # Kelly Criterion 기반 최적화
                kelly_weights = {}
                total_kelly = 0
                
                for strategy, trades in performance_data.items():
                    kelly_frac = self._calculate_kelly_optimal(trades)
                    kelly_weights[strategy] = kelly_frac
                    total_kelly += kelly_frac
                
                # 정규화
                if total_kelly > 0:
                    kelly_weights = {k: v/total_kelly for k, v in kelly_weights.items()}
                
                return kelly_weights
            
            elif method == "max_sharpe":
                # 최대 샤프 비율 포트폴리오 (단순화된 버전)
                sharpe_scores = {}
                
                for strategy, trades in performance_data.items():
                    returns = [trade.get('pnl_pct', 0) / 100 for trade in trades]
                    if len(returns) > 5:
                        mean_ret = np.mean(returns)
                        std_ret = np.std(returns)
                        sharpe = mean_ret / std_ret if std_ret > 0 else 0
                        sharpe_scores[strategy] = max(0, sharpe)
                
                # 점수 기반 가중치
                total_score = sum(sharpe_scores.values())
                if total_score > 0:
                    return {k: v/total_score for k, v in sharpe_scores.items()}
            
            return {}
            
        except Exception as e:
            logger.error(f"🔴 Error optimizing allocation: {e}")
            return {}

# 테스트 함수
async def test_portfolio_manager():
    """Portfolio Manager 테스트"""
    print("🧪 Testing Portfolio Manager...")
    
    # 포트폴리오 매니저 생성
    portfolio = PortfolioManager(total_capital=50000.0)
    
    # 샘플 성과 데이터 생성
    np.random.seed(42)
    
    strategies_performance = {
        'CCI_Strategy': [
            {'pnl': 150, 'pnl_pct': 3.0, 'timestamp': datetime.now() - timedelta(days=i)}
            for i in range(20)
        ],
        'RSI_MACD_Strategy': [
            {'pnl': 80, 'pnl_pct': 1.6, 'timestamp': datetime.now() - timedelta(days=i)}
            for i in range(15)
        ],
        'Bollinger_Strategy': [
            {'pnl': -30, 'pnl_pct': -0.6, 'timestamp': datetime.now() - timedelta(days=i)}
            for i in range(10)
        ]
    }
    
    # 전략들 추가
    portfolio.add_strategy("CCI_Strategy", 0.4, strategies_performance['CCI_Strategy'])
    portfolio.add_strategy("RSI_MACD_Strategy", 0.35, strategies_performance['RSI_MACD_Strategy'])
    portfolio.add_strategy("Bollinger_Strategy", 0.25, strategies_performance['Bollinger_Strategy'])
    
    # 현재 포지션 시뮬레이션
    current_positions = {
        'CCI_Strategy': {'value': 18000},      # 36% (목표: 40%)
        'RSI_MACD_Strategy': {'value': 20000}, # 40% (목표: 35%)
        'Bollinger_Strategy': {'value': 10000}  # 20% (목표: 25%)
    }
    portfolio.update_positions(current_positions)
    
    # 포트폴리오 상태 확인
    status = portfolio.get_portfolio_status()
    print(f"💼 Portfolio Status:")
    print(f"  - Total Capital: ${status['capital_management']['total_capital']:,.2f}")
    print(f"  - Allocated: {status['capital_management']['allocated_percentage']:.1f}%")
    print(f"  - Available: {status['capital_management']['available_percentage']:.1f}%")
    print(f"  - Active Strategies: {status['strategies']['active_strategies']}")
    
    print(f"\\n📊 Strategy Allocations:")
    for strategy in status['strategies']['strategy_details']:
        print(f"  - {strategy['name']}: {strategy['current_allocation']:.1f}% (target: {strategy['target_allocation']:.1f}%)")
        print(f"    Performance: {strategy['performance_score']:.3f}, Risk: {strategy['risk_score']:.3f}")
        print(f"    Kelly Optimal: {strategy['kelly_optimal']:.1f}%, Deviation: {strategy['deviation']:+.1f}%")
    
    # 리밸런싱 권장사항
    if status['rebalancing']['recommendations']:
        print(f"\\n🔄 Rebalancing Recommendations:")
        for rec in status['rebalancing']['recommendations']:
            print(f"  - {rec['strategy']}: {rec['action']} ${rec['amount']:,.2f} ({rec['urgency']})")
            print(f"    Deviation: {rec['deviation']:+.1f}%")
    
    # 배분 최적화 테스트
    print(f"\\n🎯 Allocation Optimization:")
    risk_parity = portfolio.optimize_allocation(strategies_performance, "risk_parity")
    kelly_optimal = portfolio.optimize_allocation(strategies_performance, "kelly")
    
    print(f"  Risk Parity: {[(k, f'{v:.1%}') for k, v in risk_parity.items()]}")
    print(f"  Kelly Optimal: {[(k, f'{v:.1%}') for k, v in kelly_optimal.items()]}")
    
    # 포트폴리오 메트릭 계산
    sample_returns = [np.random.normal(0.001, 0.02) for _ in range(100)]  # 일간 0.1% 평균, 2% 변동성
    metrics = portfolio.calculate_portfolio_metrics({}, sample_returns)
    
    print(f"\\n📈 Portfolio Metrics:")
    print(f"  - Total PnL: {metrics.total_pnl_pct:.2f}%")
    print(f"  - Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"  - Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
    print(f"  - VaR 95%: {metrics.var_95:.2f}%")
    print(f"  - Diversification Ratio: {metrics.diversification_ratio:.2f}")
    print(f"  - Concentration Risk: {metrics.concentration_risk:.3f}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_portfolio_manager())