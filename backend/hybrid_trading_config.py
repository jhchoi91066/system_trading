#!/usr/bin/env python3
"""
하이브리드 거래 설정 - 기존 CCI 시스템 + TradingView 신호 병합
"""

import os
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

class SignalSource(Enum):
    """신호 소스 유형"""
    INTERNAL_CCI = "internal_cci"
    TRADINGVIEW = "tradingview"  
    EXTERNAL_CCI = "external_cci"

class SignalPriority(Enum):
    """신호 우선순위"""
    HIGH = 1
    MEDIUM = 2
    LOW = 3

@dataclass
class HybridConfig:
    """하이브리드 거래 설정"""
    
    # 신호 소스 활성화 설정 (TradingView 우선)
    enable_internal_cci: bool = False  # 내부 CCI 비활성화
    enable_tradingview: bool = True    # TradingView만 활성화
    enable_external_cci: bool = False  # 외부 CCI 비활성화
    
    # 신호 우선순위 설정
    signal_priority: Dict[SignalSource, SignalPriority] = None
    
    # 신호 충돌 시 처리 방법
    conflict_resolution: str = "priority"  # "priority", "consensus", "first_win"
    
    # 신호 쿨다운 (초) - TradingView 신호는 즉시 처리
    signal_cooldown: int = 5   # 5초 (매우 짧은 쿨다운으로 즉시 처리)
    
    # 최소 확신도 (0.0 ~ 1.0)
    min_confidence: float = 0.7
    
    # 허용된 심볼
    allowed_symbols: List[str] = None
    
    def __post_init__(self):
        if self.signal_priority is None:
            self.signal_priority = {
                SignalSource.TRADINGVIEW: SignalPriority.HIGH,      # 우선순위 1
                SignalSource.EXTERNAL_CCI: SignalPriority.MEDIUM,   # 우선순위 2  
                SignalSource.INTERNAL_CCI: SignalPriority.LOW       # 우선순위 3
            }
            
        if self.allowed_symbols is None:
            # Pine Script 호환: 다양한 심볼 포맷 지원
            self.allowed_symbols = [
                'BTC/USDT', 'ETH/USDT', 'BTC-USDT', 'ETH-USDT',
                'BTCUSDT', 'ETHUSDT', 'BTCUSD', 'ETHUSD'
            ]

class HybridSignalManager:
    """하이브리드 신호 관리자"""
    
    def __init__(self, config: HybridConfig = None):
        self.config = config or HybridConfig()
        self.recent_signals = {}
        
    def should_process_signal(self, signal_data: dict, source: SignalSource) -> bool:
        """신호 처리 여부 결정"""
        try:
            # 1. 신호 소스 활성화 확인
            if not self._is_source_enabled(source):
                logger.info(f"Signal source {source.value} is disabled")
                return False
            
            # 2. 심볼 허용 여부 확인
            symbol = signal_data.get('symbol', '').upper()
            if symbol not in [s.upper() for s in self.config.allowed_symbols]:
                logger.warning(f"Symbol {symbol} not allowed")
                return False
            
            # 3. 신호 쿨다운 확인
            if self._is_in_cooldown(signal_data, source):
                logger.info(f"Signal in cooldown: {source.value}")
                return False
            
            # 4. 신호 충돌 해결
            if not self._resolve_signal_conflict(signal_data, source):
                logger.info(f"Signal conflict resolved against: {source.value}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking signal processing: {e}")
            return False
    
    def _is_source_enabled(self, source: SignalSource) -> bool:
        """신호 소스 활성화 여부 확인"""
        if source == SignalSource.INTERNAL_CCI:
            return self.config.enable_internal_cci
        elif source == SignalSource.TRADINGVIEW:
            return self.config.enable_tradingview
        elif source == SignalSource.EXTERNAL_CCI:
            return self.config.enable_external_cci
        return False
    
    def _is_in_cooldown(self, signal_data: dict, source: SignalSource) -> bool:
        """신호 쿨다운 여부 확인"""
        import time
        
        try:
            signal_key = f"{signal_data.get('symbol')}_{signal_data.get('signal')}_{source.value}"
            current_time = time.time()
            
            if signal_key in self.recent_signals:
                last_time = self.recent_signals[signal_key]['timestamp']
                if current_time - last_time < self.config.signal_cooldown:
                    return True
            
            # 신호 기록
            self.recent_signals[signal_key] = {
                'timestamp': current_time,
                'source': source.value,
                'data': signal_data
            }
            
            return False
            
        except Exception as e:
            logger.error(f"Cooldown check error: {e}")
            return False
    
    def _resolve_signal_conflict(self, signal_data: dict, source: SignalSource) -> bool:
        """신호 충돌 해결"""
        try:
            if self.config.conflict_resolution == "priority":
                return self._resolve_by_priority(signal_data, source)
            elif self.config.conflict_resolution == "consensus":
                return self._resolve_by_consensus(signal_data, source)  
            elif self.config.conflict_resolution == "first_win":
                return self._resolve_by_first_win(signal_data, source)
            else:
                return True  # 기본값: 모든 신호 허용
                
        except Exception as e:
            logger.error(f"Signal conflict resolution error: {e}")
            return True
    
    def _resolve_by_priority(self, signal_data: dict, source: SignalSource) -> bool:
        """우선순위 기반 충돌 해결"""
        current_priority = self.config.signal_priority.get(source, SignalPriority.LOW)
        
        # 최근 신호들 중 더 높은 우선순위가 있는지 확인
        symbol = signal_data.get('symbol')
        signal_type = signal_data.get('signal')
        
        for recent_signal in self.recent_signals.values():
            recent_data = recent_signal.get('data', {})
            if (recent_data.get('symbol') == symbol and 
                recent_data.get('signal') == signal_type):
                
                recent_source = SignalSource(recent_signal['source'])
                recent_priority = self.config.signal_priority.get(recent_source, SignalPriority.LOW)
                
                if recent_priority.value < current_priority.value:  # 더 높은 우선순위
                    logger.info(f"Higher priority signal exists: {recent_source.value}")
                    return False
        
        return True
    
    def _resolve_by_consensus(self, signal_data: dict, source: SignalSource) -> bool:
        """합의 기반 충돌 해결 (추후 구현)"""
        # 여러 소스에서 같은 신호가 와야 실행
        return True
    
    def _resolve_by_first_win(self, signal_data: dict, source: SignalSource) -> bool:  
        """선착순 기반 충돌 해결 (추후 구현)"""
        # 첫 번째 신호만 허용
        return True
    
    def get_signal_stats(self) -> dict:
        """신호 통계 반환"""
        try:
            stats = {
                'total_signals': len(self.recent_signals),
                'by_source': {},
                'by_symbol': {}
            }
            
            for signal_data in self.recent_signals.values():
                source = signal_data['source']
                symbol = signal_data['data'].get('symbol', 'unknown')
                
                stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
                stats['by_symbol'][symbol] = stats['by_symbol'].get(symbol, 0) + 1
                
            return stats
            
        except Exception as e:
            logger.error(f"Error getting signal stats: {e}")
            return {}

# 전역 설정 인스턴스
def load_hybrid_config() -> HybridConfig:
    """환경변수에서 하이브리드 설정 로드"""
    config = HybridConfig()
    
    # 환경변수에서 설정 오버라이드
    config.enable_internal_cci = os.getenv('ENABLE_INTERNAL_CCI', 'true').lower() == 'true'
    config.enable_tradingview = os.getenv('ENABLE_TRADINGVIEW', 'true').lower() == 'true'  
    config.enable_external_cci = os.getenv('ENABLE_EXTERNAL_CCI', 'true').lower() == 'true'
    
    config.signal_cooldown = int(os.getenv('SIGNAL_COOLDOWN', '300'))
    config.min_confidence = float(os.getenv('MIN_CONFIDENCE', '0.7'))
    
    conflict_resolution = os.getenv('CONFLICT_RESOLUTION', 'priority')
    if conflict_resolution in ['priority', 'consensus', 'first_win']:
        config.conflict_resolution = conflict_resolution
    
    return config

# 전역 신호 매니저
hybrid_signal_manager = HybridSignalManager(load_hybrid_config())

if __name__ == "__main__":
    # 설정 테스트
    config = load_hybrid_config()
    manager = HybridSignalManager(config)
    
    print("🔧 하이브리드 거래 설정:")
    print(f"  Internal CCI: {config.enable_internal_cci}")
    print(f"  TradingView: {config.enable_tradingview}")
    print(f"  External CCI: {config.enable_external_cci}")
    print(f"  신호 쿨다운: {config.signal_cooldown}초")
    print(f"  충돌 해결: {config.conflict_resolution}")
    
    # 테스트 신호
    test_signal = {
        'symbol': 'BTC/USDT',
        'signal': 'buy',
        'price': 95000,
        'source': 'test'
    }
    
    result = manager.should_process_signal(test_signal, SignalSource.TRADINGVIEW)
    print(f"  테스트 신호 처리 여부: {result}")
    
    stats = manager.get_signal_stats()
    print(f"  신호 통계: {stats}")