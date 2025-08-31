"""
Advanced Trading Features Package

고급 거래 기능 패키지:
- 다중 전략 시스템
- AI 기반 신호 분석
- 고급 리스크 관리
- 백테스팅 엔진
- 포트폴리오 관리
"""

from .multi_strategy_engine import MultiStrategyEngine
from .advanced_indicators import AdvancedIndicators

__version__ = "1.0.0"
__author__ = "Claude Trading Bot"

__all__ = [
    "MultiStrategyEngine",
    "AdvancedIndicators"
]