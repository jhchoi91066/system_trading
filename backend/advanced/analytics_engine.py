"""
Analytics Engine - 종합 분석 & 보고 시스템
실시간 성과 분석, 리포트 생성, 시장 분석
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import logging
import json
import io
import base64
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class ReportType(Enum):
    """보고서 타입"""
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    CUSTOM = "custom"

class AnalysisType(Enum):
    """분석 타입"""
    PERFORMANCE = "performance"
    RISK = "risk"
    CORRELATION = "correlation"
    VOLATILITY = "volatility"
    DRAWDOWN = "drawdown"

@dataclass
class TradingMetrics:
    """거래 메트릭"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    total_pnl_pct: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    avg_trade_duration: float = 0.0  # 분 단위
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    recovery_factor: float = 0.0
    expectancy: float = 0.0

@dataclass
class RiskMetrics:
    """리스크 메트릭"""
    var_95: float = 0.0  # Value at Risk 95%
    var_99: float = 0.0  # Value at Risk 99%
    cvar_95: float = 0.0  # Conditional VaR 95%
    volatility: float = 0.0  # 변동성
    downside_deviation: float = 0.0  # 하방 편차
    skewness: float = 0.0  # 왜도
    kurtosis: float = 0.0  # 첨도
    beta: float = 0.0  # 베타 (시장 대비)
    correlation_to_market: float = 0.0  # 시장 상관관계
    information_ratio: float = 0.0

@dataclass
class AnalysisResult:
    """분석 결과"""
    analysis_type: AnalysisType
    data: Dict[str, Any]
    charts: List[str] = field(default_factory=list)  # Base64 encoded images
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

class AnalyticsEngine:
    """분석 엔진"""
    
    def __init__(self, data_path: str = "data"):
        self.data_path = Path(data_path)
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # 차트 스타일 설정
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        logger.info("📊 Analytics Engine initialized")
    
    async def calculate_trading_metrics(self, trades_data: List[Dict]) -> TradingMetrics:
        """거래 메트릭 계산"""
        if not trades_data:
            return TradingMetrics()
        
        try:
            # 데이터프레임 생성
            df = pd.DataFrame(trades_data)
            
            # 필요한 컬럼 확인 및 변환
            if 'pnl' not in df.columns or 'pnl_pct' not in df.columns:
                logger.warning("⚠️ Required columns (pnl, pnl_pct) not found in trades data")
                return TradingMetrics()
            
            # 기본 통계
            total_trades = len(df)
            winning_trades = len(df[df['pnl'] > 0])
            losing_trades = len(df[df['pnl'] < 0])
            
            total_pnl = df['pnl'].sum()
            total_pnl_pct = df['pnl_pct'].sum()
            gross_profit = df[df['pnl'] > 0]['pnl'].sum()
            gross_loss = abs(df[df['pnl'] < 0]['pnl'].sum())
            
            # 승률 및 평균
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            avg_win = df[df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
            avg_loss = abs(df[df['pnl'] < 0]['pnl'].mean()) if losing_trades > 0 else 0
            
            # Profit Factor
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
            
            # 연속 승부 계산
            df['win_streak'] = (df['pnl'] > 0).astype(int)
            df['loss_streak'] = (df['pnl'] < 0).astype(int)
            
            max_consecutive_wins = self._calculate_max_streak(df['win_streak'])
            max_consecutive_losses = self._calculate_max_streak(df['loss_streak'])
            
            # 최대/최소
            largest_win = df['pnl'].max() if not df.empty else 0
            largest_loss = df['pnl'].min() if not df.empty else 0
            
            # Expectancy (기댓값)
            expectancy = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss)
            
            # 리스크 조정 수익률
            returns = df['pnl_pct'].values / 100
            sharpe_ratio = self._calculate_sharpe_ratio(returns)
            sortino_ratio = self._calculate_sortino_ratio(returns)
            
            # 최대 낙폭 계산
            cumulative_returns = (1 + pd.Series(returns)).cumprod()
            max_drawdown_pct = self._calculate_max_drawdown(cumulative_returns)
            max_drawdown = max_drawdown_pct * total_pnl if total_pnl > 0 else 0
            
            # Calmar Ratio
            annual_return = returns.mean() * 365 if len(returns) > 0 else 0
            calmar_ratio = annual_return / abs(max_drawdown_pct) if max_drawdown_pct != 0 else 0
            
            # Recovery Factor
            recovery_factor = abs(total_pnl / max_drawdown) if max_drawdown != 0 else 0
            
            # 거래 지속시간 계산 (있는 경우)
            avg_trade_duration = 0
            if 'entry_time' in df.columns and 'exit_time' in df.columns:
                df['duration'] = (pd.to_datetime(df['exit_time']) - pd.to_datetime(df['entry_time'])).dt.total_seconds() / 60
                avg_trade_duration = df['duration'].mean()
            
            metrics = TradingMetrics(
                total_trades=total_trades,
                winning_trades=winning_trades,
                losing_trades=losing_trades,
                total_pnl=round(total_pnl, 2),
                total_pnl_pct=round(total_pnl_pct, 2),
                gross_profit=round(gross_profit, 2),
                gross_loss=round(gross_loss, 2),
                max_consecutive_wins=max_consecutive_wins,
                max_consecutive_losses=max_consecutive_losses,
                avg_trade_duration=round(avg_trade_duration, 2),
                avg_win=round(avg_win, 2),
                avg_loss=round(avg_loss, 2),
                largest_win=round(largest_win, 2),
                largest_loss=round(largest_loss, 2),
                win_rate=round(win_rate, 2),
                profit_factor=round(profit_factor, 2),
                sharpe_ratio=round(sharpe_ratio, 2),
                sortino_ratio=round(sortino_ratio, 2),
                calmar_ratio=round(calmar_ratio, 2),
                max_drawdown=round(max_drawdown, 2),
                max_drawdown_pct=round(max_drawdown_pct * 100, 2),
                recovery_factor=round(recovery_factor, 2),
                expectancy=round(expectancy, 2)
            )
            
            logger.info(f"✅ Calculated trading metrics: {total_trades} trades, {win_rate:.1f}% win rate")
            return metrics
            
        except Exception as e:
            logger.error(f"🔴 Error calculating trading metrics: {e}")
            return TradingMetrics()
    
    async def calculate_risk_metrics(self, returns_data: List[float], benchmark_returns: Optional[List[float]] = None) -> RiskMetrics:
        """리스크 메트릭 계산"""
        if not returns_data:
            return RiskMetrics()
        
        try:
            returns = np.array(returns_data)
            
            # VaR 계산 (95%, 99%)
            var_95 = np.percentile(returns, 5) * 100
            var_99 = np.percentile(returns, 1) * 100
            
            # CVaR (Conditional VaR)
            cvar_95 = returns[returns <= np.percentile(returns, 5)].mean() * 100
            
            # 기본 통계
            volatility = np.std(returns) * np.sqrt(252) * 100  # 연간 변동성
            skewness = self._calculate_skewness(returns)
            kurtosis = self._calculate_kurtosis(returns)
            
            # 하방 편차 (downside deviation)
            downside_returns = returns[returns < 0]
            downside_deviation = np.std(downside_returns) * np.sqrt(252) * 100 if len(downside_returns) > 0 else 0
            
            # 벤치마크 대비 메트릭
            beta = 0
            correlation_to_market = 0
            information_ratio = 0
            
            if benchmark_returns and len(benchmark_returns) == len(returns_data):
                benchmark = np.array(benchmark_returns)
                
                # 베타 계산
                covariance = np.cov(returns, benchmark)[0, 1]
                benchmark_variance = np.var(benchmark)
                beta = covariance / benchmark_variance if benchmark_variance != 0 else 0
                
                # 상관관계
                correlation_to_market = np.corrcoef(returns, benchmark)[0, 1]
                
                # Information Ratio
                excess_returns = returns - benchmark
                tracking_error = np.std(excess_returns)
                information_ratio = np.mean(excess_returns) / tracking_error if tracking_error != 0 else 0
            
            metrics = RiskMetrics(
                var_95=round(var_95, 2),
                var_99=round(var_99, 2),
                cvar_95=round(cvar_95, 2),
                volatility=round(volatility, 2),
                downside_deviation=round(downside_deviation, 2),
                skewness=round(skewness, 2),
                kurtosis=round(kurtosis, 2),
                beta=round(beta, 2),
                correlation_to_market=round(correlation_to_market, 2),
                information_ratio=round(information_ratio, 2)
            )
            
            logger.info(f"✅ Calculated risk metrics: VaR 95%: {var_95:.2f}%, Volatility: {volatility:.2f}%")
            return metrics
            
        except Exception as e:
            logger.error(f"🔴 Error calculating risk metrics: {e}")
            return RiskMetrics()
    
    async def create_performance_analysis(self, trades_data: List[Dict], title: str = "Performance Analysis") -> AnalysisResult:
        """성과 분석 생성"""
        try:
            # 메트릭 계산
            metrics = await self.calculate_trading_metrics(trades_data)
            
            # 차트 생성
            charts = []
            
            if trades_data:
                # 1. PnL 차트
                pnl_chart = await self._create_pnl_chart(trades_data, title)
                if pnl_chart:
                    charts.append(pnl_chart)
                
                # 2. 승률 분석 차트
                winrate_chart = await self._create_winrate_chart(trades_data)
                if winrate_chart:
                    charts.append(winrate_chart)
                
                # 3. 낙폭 분석 차트
                drawdown_chart = await self._create_drawdown_chart(trades_data)
                if drawdown_chart:
                    charts.append(drawdown_chart)
            
            # 요약 생성
            summary = f"""
            성과 분석 요약:
            • 총 거래: {metrics.total_trades}회
            • 승률: {metrics.win_rate:.1f}%
            • 총 수익: {metrics.total_pnl:.2f} ({metrics.total_pnl_pct:.2f}%)
            • Profit Factor: {metrics.profit_factor:.2f}
            • Sharpe Ratio: {metrics.sharpe_ratio:.2f}
            • 최대 낙폭: {metrics.max_drawdown_pct:.2f}%
            """
            
            # 권장사항
            recommendations = []
            
            if metrics.win_rate < 40:
                recommendations.append("승률이 낮습니다. 신호 필터링을 강화하거나 진입 조건을 개선하세요.")
            
            if metrics.profit_factor < 1.2:
                recommendations.append("Profit Factor가 낮습니다. 손절 전략을 재검토하세요.")
            
            if metrics.max_drawdown_pct > 20:
                recommendations.append("최대 낙폭이 큽니다. 포지션 크기를 줄이거나 리스크 관리를 강화하세요.")
            
            if metrics.sharpe_ratio < 0.5:
                recommendations.append("리스크 대비 수익률이 낮습니다. 전략을 재검토하세요.")
            
            return AnalysisResult(
                analysis_type=AnalysisType.PERFORMANCE,
                data={
                    'metrics': metrics.__dict__,
                    'trades_count': len(trades_data),
                    'analysis_period': self._get_analysis_period(trades_data)
                },
                charts=charts,
                summary=summary.strip(),
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"🔴 Error creating performance analysis: {e}")
            return AnalysisResult(
                analysis_type=AnalysisType.PERFORMANCE,
                data={},
                summary="성과 분석 생성 중 오류가 발생했습니다.",
                recommendations=[]
            )
    
    async def _create_pnl_chart(self, trades_data: List[Dict], title: str) -> Optional[str]:
        """PnL 차트 생성"""
        try:
            df = pd.DataFrame(trades_data)
            if 'pnl' not in df.columns or 'timestamp' not in df.columns:
                return None
            
            # 누적 PnL 계산
            df['cumulative_pnl'] = df['pnl'].cumsum()
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 차트 생성
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
            
            # 상단: 누적 PnL
            ax1.plot(df['timestamp'], df['cumulative_pnl'], linewidth=2, color='blue')
            ax1.fill_between(df['timestamp'], df['cumulative_pnl'], alpha=0.3, color='lightblue')
            ax1.set_title(f'{title} - Cumulative PnL', fontsize=14, fontweight='bold')
            ax1.set_ylabel('Cumulative PnL')
            ax1.grid(True, alpha=0.3)
            
            # 하단: 개별 거래 PnL
            colors = ['green' if pnl > 0 else 'red' for pnl in df['pnl']]
            ax2.bar(df['timestamp'], df['pnl'], color=colors, alpha=0.7)
            ax2.set_title('Individual Trade PnL', fontsize=12)
            ax2.set_ylabel('Trade PnL')
            ax2.set_xlabel('Date')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Base64 인코딩
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return image_base64
            
        except Exception as e:
            logger.error(f"🔴 Error creating PnL chart: {e}")
            return None
    
    async def _create_winrate_chart(self, trades_data: List[Dict]) -> Optional[str]:
        """승률 분석 차트 생성"""
        try:
            df = pd.DataFrame(trades_data)
            if 'pnl' not in df.columns:
                return None
            
            # 승부 분석
            wins = len(df[df['pnl'] > 0])
            losses = len(df[df['pnl'] < 0])
            
            # 차트 생성
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            
            # 좌측: 승부 비율 파이차트
            labels = ['Wins', 'Losses']
            sizes = [wins, losses]
            colors = ['green', 'red']
            
            ax1.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
            ax1.set_title('Win/Loss Ratio', fontsize=14, fontweight='bold')
            
            # 우측: PnL 분포 히스토그램
            ax2.hist(df['pnl'], bins=20, alpha=0.7, color='skyblue', edgecolor='black')
            ax2.axvline(0, color='red', linestyle='--', linewidth=2, alpha=0.7)
            ax2.set_title('PnL Distribution', fontsize=14, fontweight='bold')
            ax2.set_xlabel('PnL')
            ax2.set_ylabel('Frequency')
            ax2.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # Base64 인코딩
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return image_base64
            
        except Exception as e:
            logger.error(f"🔴 Error creating winrate chart: {e}")
            return None
    
    async def _create_drawdown_chart(self, trades_data: List[Dict]) -> Optional[str]:
        """낙폭 분석 차트 생성"""
        try:
            df = pd.DataFrame(trades_data)
            if 'pnl' not in df.columns:
                return None
            
            # 누적 수익률 및 낙폭 계산
            df['cumulative_pnl'] = df['pnl'].cumsum()
            df['peak'] = df['cumulative_pnl'].expanding().max()
            df['drawdown'] = df['cumulative_pnl'] - df['peak']
            df['drawdown_pct'] = df['drawdown'] / df['peak'] * 100
            
            # 차트 생성
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 누적 PnL과 최고점
            ax.plot(range(len(df)), df['cumulative_pnl'], label='Cumulative PnL', linewidth=2, color='blue')
            ax.plot(range(len(df)), df['peak'], label='Peak', linewidth=2, color='green', alpha=0.7)
            
            # 낙폭 영역
            ax.fill_between(range(len(df)), df['cumulative_pnl'], df['peak'], 
                          alpha=0.3, color='red', label='Drawdown')
            
            ax.set_title('Drawdown Analysis', fontsize=14, fontweight='bold')
            ax.set_xlabel('Trade Number')
            ax.set_ylabel('PnL')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # 최대 낙폭 표시
            max_dd_idx = df['drawdown'].idxmin()
            max_dd_value = df['drawdown'].min()
            ax.annotate(f'Max DD: {max_dd_value:.2f}', 
                       xy=(max_dd_idx, df['cumulative_pnl'].iloc[max_dd_idx]),
                       xytext=(max_dd_idx, df['cumulative_pnl'].iloc[max_dd_idx] - abs(max_dd_value) * 0.5),
                       arrowprops=dict(arrowstyle='->', color='red'),
                       fontsize=12, color='red', fontweight='bold')
            
            plt.tight_layout()
            
            # Base64 인코딩
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
            buffer.seek(0)
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            plt.close()
            
            return image_base64
            
        except Exception as e:
            logger.error(f"🔴 Error creating drawdown chart: {e}")
            return None
    
    def _calculate_max_streak(self, streak_series: pd.Series) -> int:
        """최대 연속 기록 계산"""
        max_streak = 0
        current_streak = 0
        
        for value in streak_series:
            if value == 1:
                current_streak += 1
                max_streak = max(max_streak, current_streak)
            else:
                current_streak = 0
        
        return max_streak
    
    def _calculate_sharpe_ratio(self, returns: np.ndarray, risk_free_rate: float = 0.02) -> float:
        """샤프 비율 계산"""
        if len(returns) == 0:
            return 0
        
        excess_returns = returns - risk_free_rate / 252  # 일간 무위험 수익률
        if np.std(excess_returns) == 0:
            return 0
        
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
    
    def _calculate_sortino_ratio(self, returns: np.ndarray, target_return: float = 0) -> float:
        """소르티노 비율 계산"""
        if len(returns) == 0:
            return 0
        
        excess_returns = returns - target_return
        downside_returns = excess_returns[excess_returns < 0]
        
        if len(downside_returns) == 0 or np.std(downside_returns) == 0:
            return 0
        
        return np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)
    
    def _calculate_max_drawdown(self, cumulative_returns: pd.Series) -> float:
        """최대 낙폭 계산"""
        peak = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - peak) / peak
        return drawdown.min()
    
    def _calculate_skewness(self, returns: np.ndarray) -> float:
        """왜도 계산"""
        if len(returns) < 3:
            return 0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        return np.mean(((returns - mean_return) / std_return) ** 3)
    
    def _calculate_kurtosis(self, returns: np.ndarray) -> float:
        """첨도 계산 (초과 첨도)"""
        if len(returns) < 4:
            return 0
        
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        return np.mean(((returns - mean_return) / std_return) ** 4) - 3
    
    def _get_analysis_period(self, trades_data: List[Dict]) -> Dict[str, str]:
        """분석 기간 정보"""
        if not trades_data:
            return {'start': 'N/A', 'end': 'N/A', 'days': '0'}
        
        try:
            df = pd.DataFrame(trades_data)
            if 'timestamp' not in df.columns:
                return {'start': 'N/A', 'end': 'N/A', 'days': '0'}
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            start_date = df['timestamp'].min().strftime('%Y-%m-%d')
            end_date = df['timestamp'].max().strftime('%Y-%m-%d')
            days = (df['timestamp'].max() - df['timestamp'].min()).days
            
            return {
                'start': start_date,
                'end': end_date,
                'days': str(days)
            }
        except:
            return {'start': 'N/A', 'end': 'N/A', 'days': '0'}
    
    def export_analysis_report(self, analysis: AnalysisResult, format: str = "json") -> str:
        """분석 보고서 내보내기"""
        try:
            report_data = {
                'title': f'{analysis.analysis_type.value.title()} Analysis Report',
                'generated_at': datetime.now().isoformat(),
                'analysis_type': analysis.analysis_type.value,
                'data': analysis.data,
                'summary': analysis.summary,
                'recommendations': analysis.recommendations,
                'charts_count': len(analysis.charts),
                'timestamp': analysis.timestamp.isoformat()
            }
            
            if format.lower() == "json":
                return json.dumps(report_data, indent=2, ensure_ascii=False)
            else:
                # 향후 PDF, Excel 등 다른 형식 지원
                return json.dumps(report_data, indent=2, ensure_ascii=False)
                
        except Exception as e:
            logger.error(f"🔴 Error exporting analysis report: {e}")
            return "{\"error\": \"Failed to export report\"}"

# 테스트 함수
async def test_analytics_engine():
    """Analytics Engine 테스트"""
    print("🧪 Testing Analytics Engine...")
    
    # 샘플 거래 데이터 생성
    np.random.seed(42)
    trades_data = []
    
    for i in range(50):
        # 60% 승률로 시뮬레이션
        is_win = np.random.random() < 0.6
        
        if is_win:
            pnl = np.random.uniform(100, 500)  # 승리 시 100-500 수익
        else:
            pnl = np.random.uniform(-300, -50)  # 손실 시 -300~-50 손실
        
        trades_data.append({
            'timestamp': datetime.now() - timedelta(days=50-i),
            'pnl': pnl,
            'pnl_pct': pnl / 10000 * 100,  # 1만달러 기준
            'entry_time': datetime.now() - timedelta(days=50-i, hours=2),
            'exit_time': datetime.now() - timedelta(days=50-i, hours=1)
        })
    
    # Analytics Engine 생성
    analytics = AnalyticsEngine()
    
    # 거래 메트릭 계산
    metrics = await analytics.calculate_trading_metrics(trades_data)
    print(f"📊 Trading Metrics:")
    print(f"  - Total Trades: {metrics.total_trades}")
    print(f"  - Win Rate: {metrics.win_rate:.1f}%")
    print(f"  - Total PnL: {metrics.total_pnl:.2f}")
    print(f"  - Profit Factor: {metrics.profit_factor:.2f}")
    print(f"  - Sharpe Ratio: {metrics.sharpe_ratio:.2f}")
    print(f"  - Max Drawdown: {metrics.max_drawdown_pct:.2f}%")
    
    # 리스크 메트릭 계산
    returns = [trade['pnl_pct']/100 for trade in trades_data]
    risk_metrics = await analytics.calculate_risk_metrics(returns)
    print(f"\n📉 Risk Metrics:")
    print(f"  - VaR 95%: {risk_metrics.var_95:.2f}%")
    print(f"  - Volatility: {risk_metrics.volatility:.2f}%")
    print(f"  - Skewness: {risk_metrics.skewness:.2f}")
    print(f"  - Kurtosis: {risk_metrics.kurtosis:.2f}")
    
    # 성과 분석 생성
    analysis = await analytics.create_performance_analysis(trades_data, "Test Strategy")
    print(f"\n📈 Performance Analysis:")
    print(f"  - Charts Generated: {len(analysis.charts)}")
    print(f"  - Summary: {analysis.summary[:100]}...")
    print(f"  - Recommendations: {len(analysis.recommendations)} items")
    
    # 보고서 내보내기
    report_json = analytics.export_analysis_report(analysis)
    print(f"\n📄 Report Export: {len(report_json)} characters generated")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_analytics_engine())