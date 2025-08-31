"""
Advanced Risk Manager - 고급 리스크 관리
VaR, 포지션 제한, 동적 손절, 상관관계 리스크
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

class RiskLevel(Enum):
    """리스크 레벨"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RiskAction(Enum):
    """리스크 액션"""
    ALLOW = 1
    WARN = 2
    LIMIT = 3
    BLOCK = 4
    EMERGENCY_CLOSE = 5

@dataclass
class VaRCalculation:
    """VaR 계산 결과"""
    var_95: float  # 95% VaR
    var_99: float  # 99% VaR
    cvar_95: float  # Conditional VaR 95%
    confidence_level: float
    time_horizon: int  # 일수
    portfolio_value: float
    calculation_method: str  # historical, parametric, monte_carlo
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PositionRisk:
    """포지션 리스크"""
    symbol: str
    strategy_name: str
    position_size: float
    position_value: float
    leverage: float
    unrealized_pnl: float
    risk_contribution: float  # 포트폴리오 리스크 기여도
    correlation_risk: float  # 상관관계 리스크
    concentration_risk: float  # 집중도 리스크
    var_contribution: float  # VaR 기여도
    stress_test_loss: float  # 스트레스 테스트 손실
    risk_level: RiskLevel

@dataclass
class RiskLimit:
    """리스크 한도"""
    name: str
    limit_type: str  # position, exposure, var, drawdown, correlation
    max_value: float
    current_value: float
    utilization_pct: float
    warning_threshold: float  # 경고 임계값 (% of limit)
    breach_count: int = 0
    last_breach_time: Optional[datetime] = None
    is_breached: bool = False

@dataclass
class RiskAlert:
    """리스크 알림"""
    alert_id: str
    risk_type: str
    level: RiskLevel
    message: str
    affected_positions: List[str]
    recommended_action: RiskAction
    threshold_breached: float
    current_value: float
    timestamp: datetime = field(default_factory=datetime.now)

class AdvancedRiskManager:
    """고급 리스크 관리자"""
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.risk_limits: Dict[str, RiskLimit] = {}
        self.position_risks: Dict[str, PositionRisk] = {}
        self.risk_alerts: List[RiskAlert] = []
        self.max_alerts = 100
        
        # 기본 리스크 한도 설정
        self._setup_default_risk_limits()
        
        # VaR 계산 설정
        self.var_confidence_levels = [0.95, 0.99]
        self.var_time_horizon = 1  # 1일
        self.returns_history: List[float] = []
        self.max_history = 252  # 1년치 데이터
        
        # 상관관계 모니터링
        self.correlation_matrix: Optional[pd.DataFrame] = None
        self.correlation_threshold = 0.7
        
        logger.info(f"🛡️ Advanced Risk Manager initialized with ${initial_capital:,.2f}")
    
    def _setup_default_risk_limits(self):
        """기본 리스크 한도 설정"""
        limits = [
            ("max_position_size", "position", 0.15, 0.80),  # 15% 최대 포지션, 80%에서 경고
            ("max_portfolio_risk", "exposure", 0.25, 0.75),  # 25% 최대 노출, 75%에서 경고
            ("max_daily_var", "var", 0.05, 0.80),  # 5% 일일 VaR, 80%에서 경고
            ("max_drawdown", "drawdown", 0.20, 0.70),  # 20% 최대 낙폭, 70%에서 경고
            ("max_correlation", "correlation", 0.70, 0.85),  # 70% 최대 상관관계, 85%에서 경고
            ("max_leverage", "leverage", 10.0, 0.80),  # 10배 최대 레버리지, 80%에서 경고
            ("max_sector_exposure", "sector", 0.40, 0.75)  # 40% 최대 섹터 노출, 75%에서 경고
        ]
        
        for name, limit_type, max_val, warning_threshold in limits:
            self.risk_limits[name] = RiskLimit(
                name=name,
                limit_type=limit_type,
                max_value=max_val,
                current_value=0.0,
                utilization_pct=0.0,
                warning_threshold=warning_threshold
            )
        
        logger.info(f"📋 Set up {len(self.risk_limits)} default risk limits")
    
    async def calculate_var(
        self, 
        returns: List[float], 
        confidence_levels: List[float] = None,
        method: str = "historical"
    ) -> VaRCalculation:
        """VaR 계산"""
        try:
            if not returns or len(returns) < 30:
                logger.warning("⚠️ Insufficient data for VaR calculation")
                return VaRCalculation(0, 0, 0, 0.95, 1, self.current_capital, method)
            
            confidence_levels = confidence_levels or [0.95, 0.99]
            returns_array = np.array(returns)
            
            if method == "historical":
                # Historical VaR
                var_95 = np.percentile(returns_array, (1 - 0.95) * 100)
                var_99 = np.percentile(returns_array, (1 - 0.99) * 100)
                
                # Conditional VaR (Expected Shortfall)
                cvar_95 = returns_array[returns_array <= var_95].mean()
                
            elif method == "parametric":
                # Parametric VaR (가정: 정규분포)
                mean_return = np.mean(returns_array)
                std_return = np.std(returns_array)
                
                from scipy import stats
                var_95 = stats.norm.ppf(0.05, mean_return, std_return)
                var_99 = stats.norm.ppf(0.01, mean_return, std_return)
                cvar_95 = mean_return - std_return * stats.norm.pdf(stats.norm.ppf(0.05)) / 0.05
                
            elif method == "monte_carlo":
                # Monte Carlo VaR
                n_simulations = 10000
                simulated_returns = np.random.normal(
                    np.mean(returns_array),
                    np.std(returns_array),
                    n_simulations
                )
                
                var_95 = np.percentile(simulated_returns, 5)
                var_99 = np.percentile(simulated_returns, 1)
                cvar_95 = simulated_returns[simulated_returns <= var_95].mean()
            
            else:
                raise ValueError(f"Unknown VaR method: {method}")
            
            var_calculation = VaRCalculation(
                var_95=var_95 * 100,  # 퍼센트로 변환
                var_99=var_99 * 100,
                cvar_95=cvar_95 * 100,
                confidence_level=0.95,
                time_horizon=self.var_time_horizon,
                portfolio_value=self.current_capital,
                calculation_method=method
            )
            
            logger.info(f"📊 VaR calculated: 95%: {var_95*100:.2f}%, 99%: {var_99*100:.2f}% ({method})")
            
            return var_calculation
            
        except Exception as e:
            logger.error(f"🔴 Error calculating VaR: {e}")
            return VaRCalculation(0, 0, 0, 0.95, 1, self.current_capital, method)
    
    def assess_position_risk(
        self,
        symbol: str,
        strategy_name: str,
        position_size: float,
        current_price: float,
        leverage: float = 1.0,
        portfolio_positions: Dict[str, Any] = None
    ) -> PositionRisk:
        """포지션 리스크 평가"""
        try:
            position_value = position_size * current_price
            
            # 기본 집중도 리스크
            concentration_risk = position_value / self.current_capital
            
            # 상관관계 리스크 계산
            correlation_risk = self._calculate_correlation_risk(symbol, portfolio_positions or {})
            
            # 리스크 기여도 (단순화된 계산)
            risk_contribution = concentration_risk * leverage
            
            # VaR 기여도 (포지션별)
            var_contribution = risk_contribution * 0.05  # 5% 일일 변동성 가정
            
            # 스트레스 테스트 (30% 가격 하락 시나리오)
            stress_test_loss = position_value * 0.30 * leverage
            
            # 리스크 레벨 결정
            if risk_contribution > 0.15:  # 15% 이상
                risk_level = RiskLevel.CRITICAL
            elif risk_contribution > 0.10:  # 10% 이상
                risk_level = RiskLevel.HIGH
            elif risk_contribution > 0.05:  # 5% 이상
                risk_level = RiskLevel.MEDIUM
            else:
                risk_level = RiskLevel.LOW
            
            position_risk = PositionRisk(
                symbol=symbol,
                strategy_name=strategy_name,
                position_size=position_size,
                position_value=position_value,
                leverage=leverage,
                unrealized_pnl=0.0,  # 실시간으로 업데이트
                risk_contribution=risk_contribution,
                correlation_risk=correlation_risk,
                concentration_risk=concentration_risk,
                var_contribution=var_contribution,
                stress_test_loss=stress_test_loss,
                risk_level=risk_level
            )
            
            logger.info(f"🔍 Position risk assessed: {symbol} - {risk_level.value} risk")
            
            return position_risk
            
        except Exception as e:
            logger.error(f"🔴 Error assessing position risk: {e}")
            return PositionRisk(
                symbol=symbol, strategy_name=strategy_name,
                position_size=0, position_value=0, leverage=1,
                unrealized_pnl=0, risk_contribution=0,
                correlation_risk=0, concentration_risk=0,
                var_contribution=0, stress_test_loss=0,
                risk_level=RiskLevel.LOW
            )
    
    def _calculate_correlation_risk(self, symbol: str, portfolio_positions: Dict[str, Any]) -> float:
        """상관관계 리스크 계산"""
        try:
            if not portfolio_positions:
                return 0.0
            
            # 단순화된 상관관계 계산 (실제로는 과거 가격 데이터 필요)
            # 여기서는 심볼 기반 추정치 사용
            
            crypto_symbols = ['BTC', 'ETH', 'BNB', 'ADA', 'DOT']
            
            total_correlation_risk = 0.0
            symbol_base = symbol.split('/')[0] if '/' in symbol else symbol
            
            for pos_symbol, pos_data in portfolio_positions.items():
                pos_base = pos_symbol.split('/')[0] if '/' in pos_symbol else pos_symbol
                
                # 심볼 기반 상관관계 추정
                if symbol_base == pos_base:
                    correlation = 1.0  # 같은 자산
                elif symbol_base in crypto_symbols and pos_base in crypto_symbols:
                    correlation = 0.7  # 암호화폐 간 높은 상관관계
                else:
                    correlation = 0.3  # 기본 상관관계
                
                position_weight = pos_data.get('value', 0) / self.current_capital
                correlation_risk = correlation * position_weight
                total_correlation_risk += correlation_risk
            
            return min(total_correlation_risk, 1.0)
            
        except Exception as e:
            logger.error(f"🔴 Error calculating correlation risk: {e}")
            return 0.0
    
    def check_risk_limits(self, proposed_trade: Dict[str, Any]) -> Tuple[RiskAction, List[str]]:
        """리스크 한도 확인"""
        violations = []
        highest_action = RiskAction.ALLOW
        
        try:
            symbol = proposed_trade.get('symbol', '')
            position_value = proposed_trade.get('position_value', 0)
            leverage = proposed_trade.get('leverage', 1.0)
            
            # 1. 최대 포지션 크기 확인
            position_pct = position_value / self.current_capital
            max_position_limit = self.risk_limits["max_position_size"]
            
            if position_pct > max_position_limit.max_value:
                violations.append(f"Position size {position_pct:.1%} exceeds limit {max_position_limit.max_value:.1%}")
                highest_action = RiskAction.BLOCK
            elif position_pct > max_position_limit.max_value * max_position_limit.warning_threshold:
                violations.append(f"Position size {position_pct:.1%} approaching limit")
                if highest_action.value < RiskAction.WARN.value:
                    highest_action = RiskAction.WARN
            
            # 2. 레버리지 확인
            max_leverage_limit = self.risk_limits["max_leverage"]
            if leverage > max_leverage_limit.max_value:
                violations.append(f"Leverage {leverage}x exceeds limit {max_leverage_limit.max_value}x")
                highest_action = RiskAction.BLOCK
            
            # 3. 포트폴리오 총 노출 확인
            total_exposure = sum(pos.position_value * pos.leverage for pos in self.position_risks.values())
            total_exposure += position_value * leverage
            exposure_pct = total_exposure / self.current_capital
            
            max_exposure_limit = self.risk_limits["max_portfolio_risk"]
            if exposure_pct > max_exposure_limit.max_value:
                violations.append(f"Total exposure {exposure_pct:.1%} exceeds limit {max_exposure_limit.max_value:.1%}")
                highest_action = RiskAction.BLOCK
            
            # 4. 일일 VaR 확인 (비동기 호출을 동기로 변경)
            if self.returns_history and len(self.returns_history) > 30:
                try:
                    # VaR 간단 계산 (동기 방식)
                    recent_returns = self.returns_history[-252:] if len(self.returns_history) >= 252 else self.returns_history
                    var_95 = np.percentile(recent_returns, 5) * 100
                    var_limit = self.risk_limits["max_daily_var"]
                    
                    if abs(var_95) > var_limit.max_value * 100:
                        violations.append(f"Daily VaR {abs(var_95):.2f}% exceeds limit {var_limit.max_value*100:.2f}%")
                        if highest_action.value < RiskAction.LIMIT.value:
                            highest_action = RiskAction.LIMIT
                except Exception:
                    pass  # VaR 계산 실패시 무시
            
            # 5. 상관관계 확인
            if len(self.position_risks) > 0:
                correlation_risk = self._calculate_correlation_risk(symbol, 
                    {pos.symbol: {'value': pos.position_value} for pos in self.position_risks.values()})
                
                correlation_limit = self.risk_limits["max_correlation"]
                if correlation_risk > correlation_limit.max_value:
                    violations.append(f"Correlation risk {correlation_risk:.1%} exceeds limit {correlation_limit.max_value:.1%}")
                    if highest_action.value < RiskAction.WARN.value:
                        highest_action = RiskAction.WARN
            
            # 리스크 한도 업데이트
            self._update_risk_limit_utilization()
            
            if violations:
                logger.warning(f"⚠️ Risk limit violations: {len(violations)} items")
            
            return highest_action, violations
            
        except Exception as e:
            logger.error(f"🔴 Error checking risk limits: {e}")
            return RiskAction.BLOCK, [f"Risk check error: {str(e)}"]
    
    def _update_risk_limit_utilization(self):
        """리스크 한도 사용률 업데이트"""
        try:
            # 현재 포지션 크기
            total_position_value = sum(pos.position_value for pos in self.position_risks.values())
            max_position_value = max([pos.position_value for pos in self.position_risks.values()], default=[0])
            
            # 포지션 크기 한도
            self.risk_limits["max_position_size"].current_value = max_position_value / self.current_capital
            self.risk_limits["max_position_size"].utilization_pct = (
                self.risk_limits["max_position_size"].current_value / 
                self.risk_limits["max_position_size"].max_value * 100
            )
            
            # 포트폴리오 리스크 한도
            total_exposure = sum(pos.position_value * pos.leverage for pos in self.position_risks.values())
            self.risk_limits["max_portfolio_risk"].current_value = total_exposure / self.current_capital
            self.risk_limits["max_portfolio_risk"].utilization_pct = (
                self.risk_limits["max_portfolio_risk"].current_value / 
                self.risk_limits["max_portfolio_risk"].max_value * 100
            )
            
            # 상관관계 한도
            if len(self.position_risks) > 1:
                avg_correlation = np.mean([pos.correlation_risk for pos in self.position_risks.values()])
                self.risk_limits["max_correlation"].current_value = avg_correlation
                self.risk_limits["max_correlation"].utilization_pct = (
                    avg_correlation / self.risk_limits["max_correlation"].max_value * 100
                )
            
        except Exception as e:
            logger.error(f"🔴 Error updating risk limit utilization: {e}")
    
    def calculate_dynamic_stop_loss(
        self,
        entry_price: float,
        symbol: str,
        volatility: float = None,
        atr: float = None
    ) -> Dict[str, float]:
        """동적 손절 계산"""
        try:
            # ATR 기반 손절 (Average True Range)
            if atr:
                atr_multiplier = 2.0  # ATR의 2배
                atr_stop_distance = atr * atr_multiplier
                atr_stop_loss = entry_price - atr_stop_distance
            else:
                atr_stop_loss = entry_price * 0.98  # 2% 기본 손절
            
            # 변동성 기반 손절
            if volatility:
                vol_multiplier = 1.5  # 변동성의 1.5배
                vol_stop_distance = entry_price * volatility * vol_multiplier
                vol_stop_loss = entry_price - vol_stop_distance
            else:
                vol_stop_loss = entry_price * 0.975  # 2.5% 기본 손절
            
            # 고정 퍼센트 손절
            fixed_stop_loss = entry_price * 0.95  # 5% 손절
            
            # 리스크 기반 손절 (포지션 크기 고려)
            position_risk = 0.02  # 2% 리스크 목표
            risk_based_distance = entry_price * position_risk
            risk_based_stop_loss = entry_price - risk_based_distance
            
            # 최종 손절가 선택 (가장 가까운 것)
            stop_losses = {
                'atr_based': atr_stop_loss,
                'volatility_based': vol_stop_loss,
                'fixed_percent': fixed_stop_loss,
                'risk_based': risk_based_stop_loss
            }
            
            # 진입가에서 가장 가까운 손절가 선택 (과도한 손절 방지)
            valid_stops = {k: v for k, v in stop_losses.items() if v < entry_price and v > entry_price * 0.90}
            
            if valid_stops:
                recommended_stop = max(valid_stops.values())  # 가장 높은 손절가 (덜 공격적)
                recommended_method = max(valid_stops, key=valid_stops.get)
            else:
                recommended_stop = fixed_stop_loss
                recommended_method = 'fixed_percent'
            
            return {
                'recommended_stop_loss': recommended_stop,
                'method': recommended_method,
                'stop_loss_options': stop_losses,
                'risk_amount': entry_price - recommended_stop,
                'risk_percentage': (entry_price - recommended_stop) / entry_price * 100
            }
            
        except Exception as e:
            logger.error(f"🔴 Error calculating dynamic stop loss: {e}")
            return {
                'recommended_stop_loss': entry_price * 0.95,
                'method': 'fallback',
                'risk_percentage': 5.0
            }
    
    def monitor_correlation_risk(self, price_data: Dict[str, List[float]]) -> Dict[str, Any]:
        """상관관계 리스크 모니터링"""
        try:
            if len(price_data) < 2:
                return {'correlation_matrix': None, 'max_correlation': 0, 'risk_level': 'low'}
            
            # 수익률 계산
            returns_data = {}
            for symbol, prices in price_data.items():
                if len(prices) > 1:
                    returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
                    returns_data[symbol] = returns
            
            if len(returns_data) < 2:
                return {'correlation_matrix': None, 'max_correlation': 0, 'risk_level': 'low'}
            
            # 상관관계 행렬 계산
            df_returns = pd.DataFrame(returns_data)
            self.correlation_matrix = df_returns.corr()
            
            # 최대 상관관계 찾기 (대각선 제외)
            corr_values = []
            symbols = list(self.correlation_matrix.columns)
            
            for i in range(len(symbols)):
                for j in range(i+1, len(symbols)):
                    corr_val = abs(self.correlation_matrix.iloc[i, j])
                    if not np.isnan(corr_val):
                        corr_values.append(corr_val)
            
            max_correlation = max(corr_values) if corr_values else 0
            avg_correlation = np.mean(corr_values) if corr_values else 0
            
            # 리스크 레벨 결정
            if max_correlation > 0.8:
                risk_level = 'critical'
            elif max_correlation > 0.7:
                risk_level = 'high'
            elif max_correlation > 0.5:
                risk_level = 'medium'
            else:
                risk_level = 'low'
            
            # 위험한 상관관계 쌍 찾기
            high_correlation_pairs = []
            for i in range(len(symbols)):
                for j in range(i+1, len(symbols)):
                    corr_val = self.correlation_matrix.iloc[i, j]
                    if not np.isnan(corr_val) and abs(corr_val) > self.correlation_threshold:
                        high_correlation_pairs.append({
                            'symbol_1': symbols[i],
                            'symbol_2': symbols[j],
                            'correlation': round(corr_val, 3)
                        })
            
            result = {
                'correlation_matrix': self.correlation_matrix.to_dict() if self.correlation_matrix is not None else None,
                'max_correlation': round(max_correlation, 3),
                'avg_correlation': round(avg_correlation, 3),
                'risk_level': risk_level,
                'high_correlation_pairs': high_correlation_pairs,
                'threshold': self.correlation_threshold,
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"🔗 Correlation analysis: Max {max_correlation:.1%}, Risk level: {risk_level}")
            
            return result
            
        except Exception as e:
            logger.error(f"🔴 Error monitoring correlation risk: {e}")
            return {'error': str(e)}
    
    def generate_risk_alerts(self) -> List[RiskAlert]:
        """리스크 알림 생성"""
        new_alerts = []
        
        try:
            # 리스크 한도 위반 확인
            for limit_name, limit in self.risk_limits.items():
                if limit.utilization_pct > 100:  # 한도 위반
                    if not limit.is_breached:
                        alert = RiskAlert(
                            alert_id=f"{limit_name}_{datetime.now().timestamp()}",
                            risk_type=limit.limit_type,
                            level=RiskLevel.CRITICAL,
                            message=f"{limit.name} limit breached: {limit.current_value:.1%} > {limit.max_value:.1%}",
                            affected_positions=[],
                            recommended_action=RiskAction.EMERGENCY_CLOSE,
                            threshold_breached=limit.max_value,
                            current_value=limit.current_value
                        )
                        new_alerts.append(alert)
                        limit.is_breached = True
                        limit.breach_count += 1
                        limit.last_breach_time = datetime.now()
                
                elif limit.utilization_pct > limit.warning_threshold * 100:  # 경고 임계값
                    if not limit.is_breached:
                        alert = RiskAlert(
                            alert_id=f"{limit_name}_warning_{datetime.now().timestamp()}",
                            risk_type=limit.limit_type,
                            level=RiskLevel.HIGH,
                            message=f"{limit.name} approaching limit: {limit.utilization_pct:.1f}%",
                            affected_positions=[],
                            recommended_action=RiskAction.WARN,
                            threshold_breached=limit.warning_threshold,
                            current_value=limit.current_value
                        )
                        new_alerts.append(alert)
                
                else:
                    limit.is_breached = False
            
            # 포지션별 리스크 알림
            for pos_id, position in self.position_risks.items():
                if position.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                    alert = RiskAlert(
                        alert_id=f"position_{pos_id}_{datetime.now().timestamp()}",
                        risk_type="position_risk",
                        level=position.risk_level,
                        message=f"High risk position: {position.symbol} - {position.risk_level.value} risk",
                        affected_positions=[pos_id],
                        recommended_action=RiskAction.LIMIT if position.risk_level == RiskLevel.HIGH else RiskAction.EMERGENCY_CLOSE,
                        threshold_breached=0.10,  # 10% 리스크 임계값
                        current_value=position.risk_contribution
                    )
                    new_alerts.append(alert)
            
            # 알림 히스토리에 추가
            self.risk_alerts.extend(new_alerts)
            
            # 최대 알림 수 유지
            if len(self.risk_alerts) > self.max_alerts:
                self.risk_alerts = self.risk_alerts[-self.max_alerts:]
            
            if new_alerts:
                logger.warning(f"🚨 Generated {len(new_alerts)} new risk alerts")
            
            return new_alerts
            
        except Exception as e:
            logger.error(f"🔴 Error generating risk alerts: {e}")
            return []
    
    def run_stress_test(self, scenarios: List[Dict[str, float]]) -> Dict[str, Any]:
        """스트레스 테스트 실행"""
        try:
            stress_results = {}
            
            default_scenarios = [
                {'name': 'Market Crash', 'btc_change': -0.30, 'eth_change': -0.35, 'alt_change': -0.50},
                {'name': 'Flash Crash', 'btc_change': -0.15, 'eth_change': -0.20, 'alt_change': -0.25},
                {'name': 'Bull Market', 'btc_change': 0.20, 'eth_change': 0.25, 'alt_change': 0.30},
                {'name': 'Volatility Spike', 'btc_change': -0.10, 'eth_change': -0.15, 'alt_change': -0.20}
            ]
            
            test_scenarios = scenarios if scenarios else default_scenarios
            
            for scenario in test_scenarios:
                scenario_name = scenario.get('name', 'Unknown')
                total_loss = 0
                position_impacts = []
                
                for pos_id, position in self.position_risks.items():
                    # 심볼별 시나리오 적용
                    symbol_base = position.symbol.split('/')[0] if '/' in position.symbol else position.symbol
                    
                    # 시나리오에서 해당 심볼의 변화율 찾기
                    change_rate = 0
                    if symbol_base.upper() == 'BTC':
                        change_rate = scenario.get('btc_change', 0)
                    elif symbol_base.upper() == 'ETH':
                        change_rate = scenario.get('eth_change', 0)
                    else:
                        change_rate = scenario.get('alt_change', 0)
                    
                    # 포지션 영향 계산
                    position_impact = position.position_value * change_rate * position.leverage
                    total_loss += position_impact
                    
                    position_impacts.append({
                        'symbol': position.symbol,
                        'strategy': position.strategy_name,
                        'current_value': position.position_value,
                        'scenario_impact': position_impact,
                        'impact_percentage': (position_impact / position.position_value) * 100 if position.position_value > 0 else 0
                    })
                
                # 시나리오 결과
                total_loss_pct = (total_loss / self.current_capital) * 100
                
                stress_results[scenario_name] = {
                    'scenario': scenario,
                    'total_loss': total_loss,
                    'total_loss_percentage': total_loss_pct,
                    'remaining_capital': self.current_capital + total_loss,
                    'survival_rate': max(0, (self.current_capital + total_loss) / self.current_capital * 100),
                    'position_impacts': position_impacts,
                    'risk_level': self._classify_stress_test_risk(total_loss_pct)
                }
            
            # 최악의 시나리오 찾기
            worst_scenario = min(stress_results.items(), key=lambda x: x[1]['total_loss_percentage'])
            
            summary = {
                'scenarios_tested': len(stress_results),
                'worst_scenario': {
                    'name': worst_scenario[0],
                    'loss_percentage': worst_scenario[1]['total_loss_percentage']
                },
                'average_loss': np.mean([result['total_loss_percentage'] for result in stress_results.values()]),
                'stress_test_passed': all(result['survival_rate'] > 50 for result in stress_results.values()),
                'detailed_results': stress_results
            }
            
            logger.info(f"🧪 Stress test completed: Worst case {worst_scenario[1]['total_loss_percentage']:.1f}% loss")
            
            return summary
            
        except Exception as e:
            logger.error(f"🔴 Error running stress test: {e}")
            return {'error': str(e)}
    
    def _classify_stress_test_risk(self, loss_percentage: float) -> str:
        """스트레스 테스트 리스크 분류"""
        if abs(loss_percentage) > 50:
            return 'catastrophic'
        elif abs(loss_percentage) > 30:
            return 'severe'
        elif abs(loss_percentage) > 15:
            return 'high'
        elif abs(loss_percentage) > 5:
            return 'medium'
        else:
            return 'low'
    
    def get_risk_dashboard(self) -> Dict[str, Any]:
        """리스크 대시보드"""
        try:
            # 최근 VaR 계산 (동기 방식)
            var_calc = None
            if self.returns_history and len(self.returns_history) > 10:
                try:
                    recent_returns = self.returns_history[-30:] if len(self.returns_history) >= 30 else self.returns_history
                    var_95 = np.percentile(recent_returns, 5) * 100
                    var_99 = np.percentile(recent_returns, 1) * 100
                    cvar_95 = np.mean([r for r in recent_returns if r <= np.percentile(recent_returns, 5)]) * 100
                    
                    var_calc = VaRCalculation(
                        var_95=var_95, var_99=var_99, cvar_95=cvar_95,
                        confidence_level=0.95, time_horizon=1,
                        portfolio_value=self.current_capital,
                        calculation_method="historical"
                    )
                except Exception as e:
                    logger.error(f"Error calculating VaR for dashboard: {e}")
                    var_calc = None
            
            # 리스크 한도 요약
            risk_limits_summary = {}
            total_breaches = 0
            
            for name, limit in self.risk_limits.items():
                risk_limits_summary[name] = {
                    'current_utilization': round(limit.utilization_pct, 1),
                    'is_breached': limit.is_breached,
                    'breach_count': limit.breach_count,
                    'last_breach': limit.last_breach_time.isoformat() if limit.last_breach_time else None
                }
                
                if limit.is_breached:
                    total_breaches += 1
            
            # 포지션 리스크 요약
            position_summary = {
                'total_positions': len(self.position_risks),
                'high_risk_positions': len([p for p in self.position_risks.values() if p.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]),
                'total_exposure': sum(p.position_value * p.leverage for p in self.position_risks.values()),
                'average_correlation': np.mean([p.correlation_risk for p in self.position_risks.values()]) if self.position_risks else 0
            }
            
            # 최근 알림
            recent_alerts = [
                {
                    'type': alert.risk_type,
                    'level': alert.level.value,
                    'message': alert.message,
                    'timestamp': alert.timestamp.isoformat()
                }
                for alert in self.risk_alerts[-10:]
            ]
            
            dashboard = {
                'overall_status': {
                    'capital': self.current_capital,
                    'total_risk_breaches': total_breaches,
                    'risk_level': 'critical' if total_breaches > 3 else 'high' if total_breaches > 1 else 'medium' if total_breaches > 0 else 'low'
                },
                'var_analysis': {
                    'var_95_pct': var_calc.var_95 if var_calc else 0,
                    'var_99_pct': var_calc.var_99 if var_calc else 0,
                    'cvar_95_pct': var_calc.cvar_95 if var_calc else 0,
                    'calculation_method': var_calc.calculation_method if var_calc else 'none',
                    'last_updated': var_calc.timestamp.isoformat() if var_calc else None
                },
                'risk_limits': risk_limits_summary,
                'positions': position_summary,
                'alerts': {
                    'total_alerts': len(self.risk_alerts),
                    'recent_alerts': recent_alerts,
                    'critical_alerts': len([a for a in self.risk_alerts if a.level == RiskLevel.CRITICAL])
                },
                'correlation_analysis': {
                    'correlation_matrix_available': self.correlation_matrix is not None,
                    'max_correlation_threshold': self.correlation_threshold,
                    'monitoring_active': True
                }
            }
            
            return dashboard
            
        except Exception as e:
            logger.error(f"🔴 Error creating risk dashboard: {e}")
            return {'error': str(e)}

# 테스트 함수
async def test_advanced_risk_manager():
    """Advanced Risk Manager 테스트"""
    print("🧪 Testing Advanced Risk Manager...")
    
    # 리스크 매니저 생성
    risk_manager = AdvancedRiskManager(initial_capital=20000.0)
    
    # 샘플 수익률 데이터 생성
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 100)  # 일간 0.1% 평균, 2% 변동성
    risk_manager.returns_history = returns.tolist()
    
    # 1. VaR 계산 테스트
    print("📊 VaR Calculation Tests:")
    for method in ['historical', 'parametric', 'monte_carlo']:
        try:
            var_result = await risk_manager.calculate_var(returns.tolist(), method=method)
            print(f"  - {method.title()}: VaR 95%: {var_result.var_95:.2f}%, VaR 99%: {var_result.var_99:.2f}%")
        except Exception as e:
            print(f"  - {method.title()}: Error - {e}")
    
    # 2. 포지션 리스크 평가 테스트
    print(f"\\n🔍 Position Risk Assessment:")
    test_positions = [
        ('BTC/USDT', 'CCI_Strategy', 0.05, 50000, 1.0),
        ('ETH/USDT', 'RSI_Strategy', 0.08, 3000, 2.0),
        ('BNB/USDT', 'MACD_Strategy', 0.12, 500, 5.0)
    ]
    
    for symbol, strategy, size, price, leverage in test_positions:
        position_risk = risk_manager.assess_position_risk(symbol, strategy, size, price, leverage)
        risk_manager.position_risks[f"{symbol}_{strategy}"] = position_risk
        
        print(f"  - {symbol}: {position_risk.risk_level.value} risk")
        print(f"    Value: ${position_risk.position_value:,.2f}, Risk contribution: {position_risk.risk_contribution:.1%}")
        print(f"    Correlation risk: {position_risk.correlation_risk:.1%}, Stress loss: ${position_risk.stress_test_loss:,.2f}")
    
    # 3. 리스크 한도 확인 테스트
    print(f"\\n⚖️ Risk Limits Check:")
    test_trade = {
        'symbol': 'ADA/USDT',
        'position_value': 3000,
        'leverage': 10.0
    }
    
    action, violations = risk_manager.check_risk_limits(test_trade)
    print(f"  - Proposed trade action: {action.value}")
    if violations:
        for violation in violations:
            print(f"    ⚠️ {violation}")
    else:
        print(f"    ✅ No risk violations")
    
    # 4. 동적 손절 계산 테스트
    print(f"\\n📉 Dynamic Stop Loss:")
    stop_loss_calc = risk_manager.calculate_dynamic_stop_loss(
        entry_price=50000,
        symbol='BTC/USDT',
        volatility=0.03,  # 3% 일일 변동성
        atr=1500  # $1500 ATR
    )
    
    print(f"  - Recommended stop: ${stop_loss_calc['recommended_stop_loss']:,.2f}")
    print(f"  - Method: {stop_loss_calc['method']}")
    print(f"  - Risk: {stop_loss_calc['risk_percentage']:.2f}%")
    
    # 5. 상관관계 모니터링 테스트
    print(f"\\n🔗 Correlation Monitoring:")
    price_data = {
        'BTC/USDT': [50000 + i*100 + np.random.normal(0, 500) for i in range(50)],
        'ETH/USDT': [3000 + i*20 + np.random.normal(0, 100) for i in range(50)],
        'BNB/USDT': [500 + i*5 + np.random.normal(0, 20) for i in range(50)]
    }
    
    correlation_analysis = risk_manager.monitor_correlation_risk(price_data)
    print(f"  - Max correlation: {correlation_analysis['max_correlation']:.1%}")
    print(f"  - Avg correlation: {correlation_analysis['avg_correlation']:.1%}")
    print(f"  - Risk level: {correlation_analysis['risk_level']}")
    
    # 6. 스트레스 테스트
    print(f"\\n🧪 Stress Testing:")
    stress_result = risk_manager.run_stress_test([])  # 기본 시나리오 사용
    print(f"  - Scenarios tested: {stress_result['scenarios_tested']}")
    print(f"  - Worst case loss: {stress_result['worst_scenario']['loss_percentage']:.1f}%")
    print(f"  - Average loss: {stress_result['average_loss']:.1f}%")
    print(f"  - Stress test passed: {stress_result['stress_test_passed']}")
    
    # 7. 리스크 알림 생성
    print(f"\\n🚨 Risk Alerts:")
    alerts = risk_manager.generate_risk_alerts()
    print(f"  - Generated alerts: {len(alerts)}")
    for alert in alerts[:3]:  # 처음 3개만 출력
        print(f"    {alert.level.value}: {alert.message}")
    
    # 8. 리스크 대시보드
    print(f"\\n📊 Risk Dashboard:")
    dashboard = risk_manager.get_risk_dashboard()
    print(f"  - Overall risk level: {dashboard['overall_status']['risk_level']}")
    print(f"  - Total breaches: {dashboard['overall_status']['total_risk_breaches']}")
    print(f"  - VaR 95%: {dashboard['var_analysis']['var_95_pct']:.2f}%")
    print(f"  - High risk positions: {dashboard['positions']['high_risk_positions']}")
    print(f"  - Critical alerts: {dashboard['alerts']['critical_alerts']}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_advanced_risk_manager())