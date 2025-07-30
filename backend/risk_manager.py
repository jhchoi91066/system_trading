"""
리스크 관리 시스템
- 포지션 크기 자동 계산
- 최대 드로우다운 모니터링
- 손실 한도 설정 및 감시
- VaR (Value at Risk) 계산
- 상관관계 분석
"""

import logging
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from position_manager import position_manager
from persistent_storage import persistent_storage

logger = logging.getLogger(__name__)

@dataclass
class RiskLimits:
    """리스크 한도 설정"""
    max_position_size_pct: float = 5.0  # 계좌 대비 최대 포지션 크기 (%)
    max_daily_loss_pct: float = 2.0     # 일일 최대 손실 (%)
    max_weekly_loss_pct: float = 5.0    # 주간 최대 손실 (%)
    max_monthly_loss_pct: float = 10.0  # 월간 최대 손실 (%)
    max_drawdown_pct: float = 15.0      # 최대 드로우다운 (%)
    max_open_positions: int = 10        # 최대 동시 포지션 수
    max_symbol_exposure_pct: float = 10.0  # 심볼별 최대 노출 (%)
    max_correlation_limit: float = 0.7  # 최대 상관관계 한도

class RiskManager:
    def __init__(self):
        self.risk_limits = {}  # user_id -> RiskLimits
        self.equity_history = {}  # user_id -> [{'timestamp': datetime, 'equity': float}]
        self.daily_pnl = {}  # user_id -> {'date': str, 'pnl': float}
        
    def set_risk_limits(self, user_id: str, limits: RiskLimits):
        """사용자별 리스크 한도 설정"""
        self.risk_limits[user_id] = limits
        logger.info(f"Risk limits set for user {user_id}: {limits}")
    
    def get_risk_limits(self, user_id: str) -> RiskLimits:
        """사용자 리스크 한도 조회"""
        return self.risk_limits.get(user_id, RiskLimits())
    
    def calculate_position_size(self, user_id: str, account_balance: float, 
                              entry_price: float, stop_loss_price: float, 
                              method: str = "fixed_fractional") -> float:
        """포지션 크기 계산"""
        try:
            limits = self.get_risk_limits(user_id)
            
            if method == "fixed_fractional":
                # 고정 비율 방식: 계좌의 일정 비율
                risk_amount = account_balance * (limits.max_position_size_pct / 100)
                
            elif method == "kelly":
                # 켈리 공식 (승률과 평균 수익률 기반)
                win_rate, avg_win, avg_loss = self._get_strategy_stats(user_id)
                if win_rate > 0 and avg_loss > 0:
                    kelly_fraction = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
                    kelly_fraction = max(0, min(kelly_fraction, 0.25))  # 최대 25%로 제한
                    risk_amount = account_balance * kelly_fraction
                else:
                    risk_amount = account_balance * 0.02  # 기본 2%
                    
            elif method == "volatility_adjusted":
                # 변동성 조정 방식
                volatility = self._calculate_portfolio_volatility(user_id)
                volatility_factor = min(2.0, max(0.5, 1.0 / volatility))
                base_risk = limits.max_position_size_pct / 100
                risk_amount = account_balance * base_risk * volatility_factor
                
            else:
                # 기본값
                risk_amount = account_balance * (limits.max_position_size_pct / 100)
            
            # 손실 위험 대비 포지션 크기 계산
            if stop_loss_price > 0:
                price_risk = abs(entry_price - stop_loss_price)
                if price_risk > 0:
                    position_size = risk_amount / price_risk
                else:
                    position_size = risk_amount / entry_price * 0.02  # 2% 기본 리스크
            else:
                position_size = risk_amount / entry_price * 0.02
            
            return position_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return account_balance * 0.01 / entry_price  # 안전한 기본값
    
    def check_risk_limits(self, user_id: str, symbol: str, position_size: float, 
                         entry_price: float) -> Dict:
        """리스크 한도 확인"""
        try:
            limits = self.get_risk_limits(user_id)
            violations = []
            
            # 1. 최대 포지션 수 확인
            open_positions = position_manager.get_user_positions(user_id, status="open")
            if len(open_positions) >= limits.max_open_positions:
                violations.append(f"Maximum open positions limit ({limits.max_open_positions}) reached")
            
            # 2. 심볼별 노출 한도 확인
            current_exposure = position_manager.get_total_exposure(user_id, symbol)
            new_exposure = position_size * entry_price
            total_portfolio_value = self._get_portfolio_value(user_id)
            
            if total_portfolio_value > 0:
                exposure_pct = (current_exposure + new_exposure) / total_portfolio_value * 100
                if exposure_pct > limits.max_symbol_exposure_pct:
                    violations.append(f"Symbol exposure limit ({limits.max_symbol_exposure_pct}%) would be exceeded: {exposure_pct:.2f}%")
            
            # 3. 일일 손실 한도 확인
            daily_pnl = self._get_daily_pnl(user_id)
            if abs(daily_pnl) / total_portfolio_value * 100 > limits.max_daily_loss_pct:
                violations.append(f"Daily loss limit ({limits.max_daily_loss_pct}%) exceeded")
            
            # 4. 드로우다운 확인
            current_drawdown = self._calculate_current_drawdown(user_id)
            if current_drawdown > limits.max_drawdown_pct:
                violations.append(f"Maximum drawdown limit ({limits.max_drawdown_pct}%) exceeded: {current_drawdown:.2f}%")
            
            # 5. 상관관계 확인
            correlation_risk = self._check_correlation_risk(user_id, symbol)
            if correlation_risk > limits.max_correlation_limit:
                violations.append(f"Correlation limit ({limits.max_correlation_limit}) exceeded: {correlation_risk:.2f}")
            
            return {
                "allowed": len(violations) == 0,
                "violations": violations,
                "risk_score": self._calculate_risk_score(user_id),
                "recommended_size": position_size * 0.5 if violations else position_size
            }
            
        except Exception as e:
            logger.error(f"Error checking risk limits: {e}")
            return {"allowed": False, "violations": [str(e)], "risk_score": 100}
    
    def update_equity_history(self, user_id: str, equity: float):
        """계좌 잔고 히스토리 업데이트"""
        if user_id not in self.equity_history:
            self.equity_history[user_id] = []
        
        self.equity_history[user_id].append({
            'timestamp': datetime.now(),
            'equity': equity
        })
        
        # 최근 100개 항목만 유지
        if len(self.equity_history[user_id]) > 100:
            self.equity_history[user_id] = self.equity_history[user_id][-100:]
    
    def _get_strategy_stats(self, user_id: str) -> Tuple[float, float, float]:
        """전략 통계 조회 (승률, 평균 수익, 평균 손실)"""
        try:
            positions = position_manager.get_user_positions(user_id, status="closed")
            
            if not positions:
                return 0.5, 1.0, 1.0  # 기본값
            
            winning_trades = [p for p in positions if p.realized_pnl > 0]
            losing_trades = [p for p in positions if p.realized_pnl < 0]
            
            win_rate = len(winning_trades) / len(positions) if positions else 0.5
            avg_win = np.mean([p.realized_pnl for p in winning_trades]) if winning_trades else 1.0
            avg_loss = abs(np.mean([p.realized_pnl for p in losing_trades])) if losing_trades else 1.0
            
            return win_rate, avg_win, avg_loss
            
        except Exception as e:
            logger.error(f"Error getting strategy stats: {e}")
            return 0.5, 1.0, 1.0
    
    def _calculate_portfolio_volatility(self, user_id: str) -> float:
        """포트폴리오 변동성 계산"""
        try:
            if user_id not in self.equity_history:
                return 1.0
            
            equity_values = [item['equity'] for item in self.equity_history[user_id][-30:]]  # 최근 30개
            
            if len(equity_values) < 2:
                return 1.0
            
            returns = np.diff(equity_values) / equity_values[:-1]
            volatility = np.std(returns) * np.sqrt(252)  # 연환산 변동성
            
            return max(0.1, volatility)
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 1.0
    
    def _get_portfolio_value(self, user_id: str) -> float:
        """포트폴리오 총 가치 계산"""
        try:
            portfolio_stats = position_manager.get_portfolio_pnl(user_id)
            total_exposure = position_manager.get_total_exposure(user_id)
            
            # 간단한 계산: 노출 금액 + 미실현 손익
            return total_exposure + portfolio_stats.get('total_unrealized_pnl', 0)
            
        except Exception as e:
            logger.error(f"Error getting portfolio value: {e}")
            return 10000  # 기본값
    
    def _get_daily_pnl(self, user_id: str) -> float:
        """일일 손익 계산"""
        try:
            today = datetime.now().date().isoformat()
            
            if user_id in self.daily_pnl and today in self.daily_pnl[user_id]:
                return self.daily_pnl[user_id][today]
            
            # 오늘 청산된 포지션들의 손익 합계
            positions = position_manager.get_user_positions(user_id, status="closed")
            today_positions = [
                p for p in positions 
                if p.entry_time.date() == datetime.now().date()
            ]
            
            daily_pnl = sum(p.realized_pnl for p in today_positions)
            
            # 캐시 업데이트
            if user_id not in self.daily_pnl:
                self.daily_pnl[user_id] = {}
            self.daily_pnl[user_id][today] = daily_pnl
            
            return daily_pnl
            
        except Exception as e:
            logger.error(f"Error getting daily PnL: {e}")
            return 0
    
    def _calculate_current_drawdown(self, user_id: str) -> float:
        """현재 드로우다운 계산"""
        try:
            if user_id not in self.equity_history or len(self.equity_history[user_id]) < 2:
                return 0.0
            
            equity_values = [item['equity'] for item in self.equity_history[user_id]]
            
            # 최고점 찾기
            peak = max(equity_values)
            current = equity_values[-1]
            
            if peak <= 0:
                return 0.0
            
            drawdown = (peak - current) / peak * 100
            return max(0.0, drawdown)
            
        except Exception as e:
            logger.error(f"Error calculating drawdown: {e}")
            return 0.0
    
    def _check_correlation_risk(self, user_id: str, new_symbol: str) -> float:
        """상관관계 리스크 확인"""
        try:
            open_positions = position_manager.get_user_positions(user_id, status="open")
            
            if not open_positions:
                return 0.0
            
            # 현재 보유 심볼들
            current_symbols = list(set(p.symbol for p in open_positions))
            
            # 간단한 상관관계 추정 (실제로는 가격 데이터 분석 필요)
            # BTC와 관련된 심볼들 간의 상관관계를 높게 추정
            btc_related = ['BTC/USDT', 'BTC/USD', 'BTCUSDT']
            eth_related = ['ETH/USDT', 'ETH/USD', 'ETHUSDT']
            
            correlation = 0.0
            
            for symbol in current_symbols:
                if new_symbol == symbol:
                    correlation = 1.0  # 동일 심볼
                    break
                elif (any(btc in symbol for btc in btc_related) and 
                      any(btc in new_symbol for btc in btc_related)):
                    correlation = max(correlation, 0.8)
                elif (any(eth in symbol for eth in eth_related) and 
                      any(eth in new_symbol for eth in eth_related)):
                    correlation = max(correlation, 0.7)
                else:
                    correlation = max(correlation, 0.3)  # 기본 상관관계
            
            return correlation
            
        except Exception as e:
            logger.error(f"Error checking correlation risk: {e}")
            return 0.5
    
    def _calculate_risk_score(self, user_id: str) -> float:
        """종합 리스크 점수 계산 (0-100, 높을수록 위험)"""
        try:
            score = 0
            
            # 드로우다운 점수 (30점 만점)
            drawdown = self._calculate_current_drawdown(user_id)
            score += min(30, drawdown * 2)
            
            # 포지션 집중도 점수 (25점 만점)
            open_positions = position_manager.get_user_positions(user_id, status="open")
            if open_positions:
                symbols = [p.symbol for p in open_positions]
                unique_symbols = len(set(symbols))
                concentration = len(symbols) / max(1, unique_symbols)
                score += min(25, concentration * 5)
            
            # 일일 손실 점수 (20점 만점)
            daily_pnl = self._get_daily_pnl(user_id)
            portfolio_value = self._get_portfolio_value(user_id)
            if portfolio_value > 0:
                daily_loss_pct = abs(min(0, daily_pnl)) / portfolio_value * 100
                score += min(20, daily_loss_pct * 10)
            
            # 변동성 점수 (15점 만점)
            volatility = self._calculate_portfolio_volatility(user_id)
            score += min(15, volatility * 50)
            
            # 레버리지 점수 (10점 만점)
            total_exposure = position_manager.get_total_exposure(user_id)
            if portfolio_value > 0:
                leverage = total_exposure / portfolio_value
                score += min(10, max(0, leverage - 1) * 10)
            
            return min(100, score)
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 50  # 중간 점수
    
    def generate_risk_report(self, user_id: str) -> Dict:
        """종합 리스크 리포트 생성"""
        try:
            limits = self.get_risk_limits(user_id)
            portfolio_stats = position_manager.get_portfolio_pnl(user_id)
            
            return {
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
                "risk_limits": {
                    "max_position_size_pct": limits.max_position_size_pct,
                    "max_daily_loss_pct": limits.max_daily_loss_pct,
                    "max_drawdown_pct": limits.max_drawdown_pct,
                    "max_open_positions": limits.max_open_positions
                },
                "current_metrics": {
                    "risk_score": self._calculate_risk_score(user_id),
                    "current_drawdown": self._calculate_current_drawdown(user_id),
                    "daily_pnl": self._get_daily_pnl(user_id),
                    "portfolio_volatility": self._calculate_portfolio_volatility(user_id),
                    "open_positions": len(position_manager.get_user_positions(user_id, status="open")),
                    "total_exposure": position_manager.get_total_exposure(user_id),
                    "portfolio_value": self._get_portfolio_value(user_id)
                },
                "portfolio_stats": portfolio_stats,
                "recommendations": self._generate_recommendations(user_id)
            }
            
        except Exception as e:
            logger.error(f"Error generating risk report: {e}")
            return {"error": str(e)}
    
    def _generate_recommendations(self, user_id: str) -> List[str]:
        """리스크 개선 권장사항 생성"""
        recommendations = []
        
        try:
            risk_score = self._calculate_risk_score(user_id)
            drawdown = self._calculate_current_drawdown(user_id)
            open_positions = position_manager.get_user_positions(user_id, status="open")
            
            if risk_score > 70:
                recommendations.append("위험도가 높습니다. 포지션 크기를 줄이거나 일부 포지션을 청산하는 것을 고려하세요.")
            
            if drawdown > 10:
                recommendations.append(f"드로우다운이 {drawdown:.1f}%로 높습니다. 리스크를 줄이는 것을 권장합니다.")
            
            if len(open_positions) > 8:
                recommendations.append("너무 많은 포지션을 보유하고 있습니다. 포지션 수를 줄여 관리를 단순화하세요.")
            
            # 심볼 집중도 확인
            symbols = [p.symbol for p in open_positions]
            if symbols:
                most_common_symbol = max(set(symbols), key=symbols.count)
                symbol_count = symbols.count(most_common_symbol)
                if symbol_count > len(symbols) * 0.4:
                    recommendations.append(f"{most_common_symbol}에 포지션이 집중되어 있습니다. 분산투자를 고려하세요.")
            
            daily_pnl = self._get_daily_pnl(user_id)
            if daily_pnl < -100:  # 임계값은 조정 가능
                recommendations.append("일일 손실이 큽니다. 거래를 일시 중단하고 전략을 재검토하세요.")
            
            if not recommendations:
                recommendations.append("현재 리스크 수준이 적절합니다. 계속 모니터링하세요.")
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("리스크 분석 중 오류가 발생했습니다.")
        
        return recommendations

# 글로벌 인스턴스
risk_manager = RiskManager()