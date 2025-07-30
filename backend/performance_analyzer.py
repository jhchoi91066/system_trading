"""
고급 성과 분석 시스템
- 샤프 비율, 최대 드로우다운 등 고급 지표 계산
- 데모 트레이딩과 백테스팅 결과 비교
- 실시간 성과 추적 및 분석
- 리스크 조정 수익률 계산
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import logging
import math
from enum import Enum

logger = logging.getLogger(__name__)

class AnalysisType(Enum):
    BACKTEST = "backtest"
    DEMO = "demo"
    LIVE = "live"

@dataclass
class PerformanceMetrics:
    """성과 지표 데이터 클래스"""
    total_return: float = 0.0
    annualized_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    calmar_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    average_win: float = 0.0
    average_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    var_95: float = 0.0  # Value at Risk (95%)
    cvar_95: float = 0.0  # Conditional Value at Risk (95%)
    beta: float = 0.0
    alpha: float = 0.0
    information_ratio: float = 0.0
    treynor_ratio: float = 0.0

@dataclass
class ComparisonResult:
    """비교 분석 결과"""
    analysis_type_a: str
    analysis_type_b: str
    metrics_a: PerformanceMetrics
    metrics_b: PerformanceMetrics
    outperformance: Dict[str, float]
    statistical_significance: Dict[str, float]
    correlation: float
    summary: str

class PerformanceAnalyzer:
    """고급 성과 분석기"""
    
    def __init__(self, risk_free_rate: float = 0.02):
        """
        Args:
            risk_free_rate: 무위험 수익률 (연율, 기본값 2%)
        """
        self.risk_free_rate = risk_free_rate
        self.cached_results: Dict[str, Any] = {}
        
    def calculate_basic_metrics(self, returns: List[float], equity_curve: List[float] = None) -> Dict[str, float]:
        """기본 성과 지표 계산"""
        try:
            if not returns or len(returns) < 2:
                return {}
            
            returns_array = np.array(returns)
            
            # 기본 수익률 지표
            total_return = (returns_array + 1).prod() - 1
            annualized_return = (1 + total_return) ** (252 / len(returns)) - 1 if len(returns) > 0 else 0
            
            # 변동성 (연율화)
            volatility = np.std(returns_array) * np.sqrt(252)
            
            # 샤프 비율
            excess_returns = returns_array - (self.risk_free_rate / 252)
            sharpe_ratio = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if np.std(excess_returns) > 0 else 0
            
            # 소르티노 비율 (하방 변동성만 고려)
            negative_returns = returns_array[returns_array < 0]
            downside_deviation = np.std(negative_returns) * np.sqrt(252) if len(negative_returns) > 0 else 0
            sortino_ratio = (annualized_return - self.risk_free_rate) / downside_deviation if downside_deviation > 0 else 0
            
            return {
                'total_return': total_return,
                'annualized_return': annualized_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'sortino_ratio': sortino_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating basic metrics: {e}")
            return {}
    
    def calculate_drawdown_metrics(self, equity_curve: List[float]) -> Dict[str, float]:
        """드로우다운 관련 지표 계산"""
        try:
            if not equity_curve or len(equity_curve) < 2:
                return {}
            
            equity_array = np.array(equity_curve)
            
            # 누적 최고점 계산
            peak = np.maximum.accumulate(equity_array)
            
            # 드로우다운 계산 (백분율)
            drawdown = (equity_array - peak) / peak
            
            # 최대 드로우다운
            max_drawdown = np.min(drawdown)
            
            # 최대 드로우다운 지속 기간
            dd_duration = 0
            max_dd_duration = 0
            for dd in drawdown:
                if dd < 0:
                    dd_duration += 1
                    max_dd_duration = max(max_dd_duration, dd_duration)
                else:
                    dd_duration = 0
            
            # 칼마 비율 (연수익률 / 최대 드로우다운)
            total_return = (equity_array[-1] / equity_array[0]) - 1 if equity_array[0] != 0 else 0
            annualized_return = (1 + total_return) ** (252 / len(equity_array)) - 1 if len(equity_array) > 0 else 0
            calmar_ratio = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0
            
            return {
                'max_drawdown': max_drawdown,
                'max_drawdown_duration': max_dd_duration,
                'calmar_ratio': calmar_ratio,
                'current_drawdown': drawdown[-1]
            }
            
        except Exception as e:
            logger.error(f"Error calculating drawdown metrics: {e}")
            return {}
    
    def calculate_trade_metrics(self, trades: List[Dict]) -> Dict[str, float]:
        """거래 관련 지표 계산"""
        try:
            if not trades:
                return {}
            
            # 거래별 손익 계산
            trade_pnls = []
            for trade in trades:
                pnl = trade.get('pnl', 0)
                if pnl != 0:
                    trade_pnls.append(pnl)
            
            if not trade_pnls:
                return {}
            
            trade_pnls = np.array(trade_pnls)
            
            # 승률 계산
            winning_trades = np.sum(trade_pnls > 0)
            losing_trades = np.sum(trade_pnls < 0)
            total_trades = len(trade_pnls)
            win_rate = winning_trades / total_trades if total_trades > 0 else 0
            
            # 평균 승부 크기
            wins = trade_pnls[trade_pnls > 0]
            losses = trade_pnls[trade_pnls < 0]
            
            average_win = np.mean(wins) if len(wins) > 0 else 0
            average_loss = np.mean(losses) if len(losses) > 0 else 0
            
            # 최대 승부
            largest_win = np.max(wins) if len(wins) > 0 else 0
            largest_loss = np.min(losses) if len(losses) > 0 else 0
            
            # 프로핏 팩터 (총 이익 / 총 손실)
            total_wins = np.sum(wins) if len(wins) > 0 else 0
            total_losses = abs(np.sum(losses)) if len(losses) > 0 else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else float('inf') if total_wins > 0 else 0
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'average_win': average_win,
                'average_loss': average_loss,
                'largest_win': largest_win,
                'largest_loss': largest_loss,
                'profit_factor': profit_factor
            }
            
        except Exception as e:
            logger.error(f"Error calculating trade metrics: {e}")
            return {}
    
    def calculate_risk_metrics(self, returns: List[float], confidence_level: float = 0.95) -> Dict[str, float]:
        """리스크 지표 계산"""
        try:
            if not returns or len(returns) < 2:
                return {}
            
            returns_array = np.array(returns)
            
            # Value at Risk (VaR)
            var_95 = np.percentile(returns_array, (1 - confidence_level) * 100)
            
            # Conditional Value at Risk (CVaR)
            cvar_95 = np.mean(returns_array[returns_array <= var_95])
            
            return {
                'var_95': var_95,
                'cvar_95': cvar_95
            }
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return {}
    
    def calculate_market_metrics(self, returns: List[float], benchmark_returns: List[float]) -> Dict[str, float]:
        """시장 대비 성과 지표 계산"""
        try:
            if not returns or not benchmark_returns or len(returns) != len(benchmark_returns):
                return {}
            
            returns_array = np.array(returns)
            benchmark_array = np.array(benchmark_returns)
            
            # 베타 계산
            covariance = np.cov(returns_array, benchmark_array)[0, 1]
            benchmark_variance = np.var(benchmark_array)
            beta = covariance / benchmark_variance if benchmark_variance > 0 else 0
            
            # 알파 계산
            portfolio_return = np.mean(returns_array) * 252
            benchmark_return = np.mean(benchmark_array) * 252
            alpha = portfolio_return - (self.risk_free_rate + beta * (benchmark_return - self.risk_free_rate))
            
            # 정보 비율 (Information Ratio)
            excess_returns = returns_array - benchmark_array
            tracking_error = np.std(excess_returns) * np.sqrt(252)
            information_ratio = np.mean(excess_returns) * 252 / tracking_error if tracking_error > 0 else 0
            
            # 트레이너 비율 (Treynor Ratio)
            portfolio_excess_return = portfolio_return - self.risk_free_rate
            treynor_ratio = portfolio_excess_return / beta if beta > 0 else 0
            
            return {
                'beta': beta,
                'alpha': alpha,
                'information_ratio': information_ratio,
                'treynor_ratio': treynor_ratio
            }
            
        except Exception as e:
            logger.error(f"Error calculating market metrics: {e}")
            return {}
    
    def analyze_performance(self, 
                           returns: List[float], 
                           equity_curve: List[float] = None,
                           trades: List[Dict] = None,
                           benchmark_returns: List[float] = None) -> PerformanceMetrics:
        """종합 성과 분석"""
        try:
            metrics = PerformanceMetrics()
            
            # 기본 지표
            basic_metrics = self.calculate_basic_metrics(returns, equity_curve)
            metrics.total_return = basic_metrics.get('total_return', 0)
            metrics.annualized_return = basic_metrics.get('annualized_return', 0)
            metrics.volatility = basic_metrics.get('volatility', 0)
            metrics.sharpe_ratio = basic_metrics.get('sharpe_ratio', 0)
            metrics.sortino_ratio = basic_metrics.get('sortino_ratio', 0)
            
            # 드로우다운 지표
            if equity_curve:
                dd_metrics = self.calculate_drawdown_metrics(equity_curve)
                metrics.max_drawdown = dd_metrics.get('max_drawdown', 0)
                metrics.max_drawdown_duration = dd_metrics.get('max_drawdown_duration', 0)
                metrics.calmar_ratio = dd_metrics.get('calmar_ratio', 0)
            
            # 거래 지표
            if trades:
                trade_metrics = self.calculate_trade_metrics(trades)
                metrics.total_trades = trade_metrics.get('total_trades', 0)
                metrics.winning_trades = trade_metrics.get('winning_trades', 0)
                metrics.losing_trades = trade_metrics.get('losing_trades', 0)
                metrics.win_rate = trade_metrics.get('win_rate', 0)
                metrics.profit_factor = trade_metrics.get('profit_factor', 0)
                metrics.average_win = trade_metrics.get('average_win', 0)
                metrics.average_loss = trade_metrics.get('average_loss', 0)
                metrics.largest_win = trade_metrics.get('largest_win', 0)
                metrics.largest_loss = trade_metrics.get('largest_loss', 0)
            
            # 리스크 지표
            risk_metrics = self.calculate_risk_metrics(returns)
            metrics.var_95 = risk_metrics.get('var_95', 0)
            metrics.cvar_95 = risk_metrics.get('cvar_95', 0)
            
            # 시장 대비 지표
            if benchmark_returns:
                market_metrics = self.calculate_market_metrics(returns, benchmark_returns)
                metrics.beta = market_metrics.get('beta', 0)
                metrics.alpha = market_metrics.get('alpha', 0)
                metrics.information_ratio = market_metrics.get('information_ratio', 0)
                metrics.treynor_ratio = market_metrics.get('treynor_ratio', 0)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing performance: {e}")
            return PerformanceMetrics()
    
    def compare_strategies(self, 
                          results_a: Dict[str, Any], 
                          results_b: Dict[str, Any],
                          analysis_type_a: str = "Strategy A",
                          analysis_type_b: str = "Strategy B") -> ComparisonResult:
        """전략 비교 분석"""
        try:
            # 각 전략의 성과 분석
            metrics_a = self.analyze_performance(
                returns=results_a.get('returns', []),
                equity_curve=results_a.get('equity_curve', []),
                trades=results_a.get('trades', []),
                benchmark_returns=results_a.get('benchmark_returns', [])
            )
            
            metrics_b = self.analyze_performance(
                returns=results_b.get('returns', []),
                equity_curve=results_b.get('equity_curve', []),
                trades=results_b.get('trades', []),
                benchmark_returns=results_b.get('benchmark_returns', [])
            )
            
            # 아웃퍼포먼스 계산
            outperformance = {
                'total_return': metrics_a.total_return - metrics_b.total_return,
                'sharpe_ratio': metrics_a.sharpe_ratio - metrics_b.sharpe_ratio,
                'max_drawdown': metrics_a.max_drawdown - metrics_b.max_drawdown,
                'win_rate': metrics_a.win_rate - metrics_b.win_rate,
                'profit_factor': metrics_a.profit_factor - metrics_b.profit_factor
            }
            
            # 상관관계 계산
            correlation = 0.0
            if results_a.get('returns') and results_b.get('returns'):
                returns_a = np.array(results_a['returns'])
                returns_b = np.array(results_b['returns'])
                if len(returns_a) == len(returns_b) and len(returns_a) > 1:
                    correlation = np.corrcoef(returns_a, returns_b)[0, 1]
            
            # 통계적 유의성 검정 (간단한 t-test)
            statistical_significance = {}
            if results_a.get('returns') and results_b.get('returns'):
                returns_a = np.array(results_a['returns'])
                returns_b = np.array(results_b['returns'])
                
                if len(returns_a) > 1 and len(returns_b) > 1:
                    from scipy import stats
                    t_stat, p_value = stats.ttest_ind(returns_a, returns_b)
                    statistical_significance = {
                        't_statistic': t_stat,
                        'p_value': p_value,
                        'significant': p_value < 0.05
                    }
            
            # 요약 생성
            summary = self._generate_comparison_summary(metrics_a, metrics_b, outperformance)
            
            return ComparisonResult(
                analysis_type_a=analysis_type_a,
                analysis_type_b=analysis_type_b,
                metrics_a=metrics_a,
                metrics_b=metrics_b,
                outperformance=outperformance,
                statistical_significance=statistical_significance,
                correlation=correlation,
                summary=summary
            )
            
        except Exception as e:
            logger.error(f"Error comparing strategies: {e}")
            return ComparisonResult(
                analysis_type_a=analysis_type_a,
                analysis_type_b=analysis_type_b,
                metrics_a=PerformanceMetrics(),
                metrics_b=PerformanceMetrics(),
                outperformance={},
                statistical_significance={},
                correlation=0.0,
                summary="Comparison failed due to error"
            )
    
    def _generate_comparison_summary(self, 
                                   metrics_a: PerformanceMetrics, 
                                   metrics_b: PerformanceMetrics, 
                                   outperformance: Dict[str, float]) -> str:
        """비교 분석 요약 생성"""
        try:
            summary_parts = []
            
            # 수익률 비교
            if outperformance.get('total_return', 0) > 0:
                summary_parts.append(f"Strategy A outperformed by {outperformance['total_return']:.2%} in total return")
            else:
                summary_parts.append(f"Strategy B outperformed by {abs(outperformance['total_return']):.2%} in total return")
            
            # 샤프 비율 비교
            if outperformance.get('sharpe_ratio', 0) > 0:
                summary_parts.append(f"Strategy A has better risk-adjusted return (Sharpe: {metrics_a.sharpe_ratio:.2f} vs {metrics_b.sharpe_ratio:.2f})")
            else:
                summary_parts.append(f"Strategy B has better risk-adjusted return (Sharpe: {metrics_b.sharpe_ratio:.2f} vs {metrics_a.sharpe_ratio:.2f})")
            
            # 드로우다운 비교
            if metrics_a.max_drawdown > metrics_b.max_drawdown:
                summary_parts.append(f"Strategy B has lower maximum drawdown ({metrics_b.max_drawdown:.2%} vs {metrics_a.max_drawdown:.2%})")
            else:
                summary_parts.append(f"Strategy A has lower maximum drawdown ({metrics_a.max_drawdown:.2%} vs {metrics_b.max_drawdown:.2%})")
            
            return "; ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error generating comparison summary: {e}")
            return "Summary generation failed"
    
    def generate_performance_report(self, metrics: PerformanceMetrics, analysis_type: str = "Strategy") -> str:
        """성과 보고서 생성"""
        try:
            report = f"""
=== {analysis_type} Performance Report ===

Return Metrics:
- Total Return: {metrics.total_return:.2%}
- Annualized Return: {metrics.annualized_return:.2%}
- Volatility: {metrics.volatility:.2%}

Risk-Adjusted Returns:
- Sharpe Ratio: {metrics.sharpe_ratio:.2f}
- Sortino Ratio: {metrics.sortino_ratio:.2f}
- Calmar Ratio: {metrics.calmar_ratio:.2f}

Risk Metrics:
- Maximum Drawdown: {metrics.max_drawdown:.2%}
- VaR (95%): {metrics.var_95:.2%}
- CVaR (95%): {metrics.cvar_95:.2%}

Trading Performance:
- Total Trades: {metrics.total_trades}
- Win Rate: {metrics.win_rate:.1%}
- Profit Factor: {metrics.profit_factor:.2f}
- Average Win: {metrics.average_win:.2f}
- Average Loss: {metrics.average_loss:.2f}

Market Comparison:
- Beta: {metrics.beta:.2f}
- Alpha: {metrics.alpha:.2%}
- Information Ratio: {metrics.information_ratio:.2f}
- Treynor Ratio: {metrics.treynor_ratio:.2f}
"""
            return report
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            return "Report generation failed"

# 글로벌 인스턴스
performance_analyzer = PerformanceAnalyzer()

# ============= 유틸리티 함수 =============

def convert_trades_to_returns(trades: List[Dict], initial_capital: float = 10000) -> Tuple[List[float], List[float]]:
    """거래 데이터를 수익률과 자본 곡선으로 변환"""
    try:
        if not trades:
            return [], []
        
        capital = initial_capital
        equity_curve = [capital]
        returns = []
        
        for trade in trades:
            pnl = trade.get('pnl', 0)
            capital += pnl
            equity_curve.append(capital)
            
            # 수익률 계산
            if equity_curve[-2] > 0:
                daily_return = pnl / equity_curve[-2]
                returns.append(daily_return)
        
        return returns, equity_curve
        
    except Exception as e:
        logger.error(f"Error converting trades to returns: {e}")
        return [], []

def calculate_rolling_metrics(returns: List[float], window: int = 30) -> Dict[str, List[float]]:
    """롤링 윈도우 성과 지표 계산"""
    try:
        if len(returns) < window:
            return {}
        
        returns_array = np.array(returns)
        rolling_sharpe = []
        rolling_volatility = []
        rolling_return = []
        
        for i in range(window, len(returns_array) + 1):
            window_returns = returns_array[i-window:i]
            
            # 롤링 수익률
            rolling_return.append(np.mean(window_returns) * 252)
            
            # 롤링 변동성
            rolling_volatility.append(np.std(window_returns) * np.sqrt(252))
            
            # 롤링 샤프 비율
            excess_returns = window_returns - (0.02 / 252)  # 2% 무위험 수익률
            if np.std(excess_returns) > 0:
                rolling_sharpe.append(np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252))
            else:
                rolling_sharpe.append(0)
        
        return {
            'rolling_return': rolling_return,
            'rolling_volatility': rolling_volatility,
            'rolling_sharpe': rolling_sharpe
        }
        
    except Exception as e:
        logger.error(f"Error calculating rolling metrics: {e}")
        return {}

if __name__ == "__main__":
    # 테스트 코드
    analyzer = PerformanceAnalyzer()
    
    # 샘플 데이터
    np.random.seed(42)
    returns_a = np.random.normal(0.001, 0.02, 252)  # 1년간 일일 수익률
    returns_b = np.random.normal(0.0005, 0.015, 252)
    
    equity_a = (1 + returns_a).cumprod() * 10000
    equity_b = (1 + returns_b).cumprod() * 10000
    
    # 성과 분석
    metrics_a = analyzer.analyze_performance(returns_a.tolist(), equity_a.tolist())
    metrics_b = analyzer.analyze_performance(returns_b.tolist(), equity_b.tolist())
    
    print("Strategy A Metrics:")
    print(f"Total Return: {metrics_a.total_return:.2%}")
    print(f"Sharpe Ratio: {metrics_a.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {metrics_a.max_drawdown:.2%}")
    
    print("\nStrategy B Metrics:")
    print(f"Total Return: {metrics_b.total_return:.2%}")
    print(f"Sharpe Ratio: {metrics_b.sharpe_ratio:.2f}")
    print(f"Max Drawdown: {metrics_b.max_drawdown:.2%}")
    
    # 전략 비교
    comparison = analyzer.compare_strategies(
        {'returns': returns_a.tolist(), 'equity_curve': equity_a.tolist()},
        {'returns': returns_b.tolist(), 'equity_curve': equity_b.tolist()},
        "Strategy A", "Strategy B"
    )
    
    print(f"\nComparison Summary: {comparison.summary}")
    print(f"Correlation: {comparison.correlation:.2f}")