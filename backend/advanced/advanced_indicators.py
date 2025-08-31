"""
고급 기술적 지표 계산기
CCI, RSI, MACD 외 추가 지표들과 조합 전략
"""

import pandas as pd
import numpy as np
import talib
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SignalStrength(Enum):
    """신호 강도"""
    VERY_WEAK = 1
    WEAK = 2
    MODERATE = 3
    STRONG = 4
    VERY_STRONG = 5

class TrendDirection(Enum):
    """트렌드 방향"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"

@dataclass
class IndicatorSignal:
    """지표 신호"""
    indicator: str
    signal: str  # BUY, SELL, HOLD
    strength: SignalStrength
    confidence: float  # 0-1
    value: float
    timestamp: datetime
    metadata: Dict[str, Any] = None

@dataclass
class CompositeSignal:
    """복합 신호"""
    overall_signal: str  # BUY, SELL, HOLD
    confidence: float  # 0-1
    strength: SignalStrength
    contributing_signals: List[IndicatorSignal]
    trend_direction: TrendDirection
    timestamp: datetime

class AdvancedIndicators:
    """고급 기술적 지표 계산기"""
    
    def __init__(self):
        self.indicators_cache = {}
        self.signal_history = []
        self.max_history = 1000
        
        # 지표별 가중치 설정
        self.indicator_weights = {
            'cci': 0.25,
            'rsi': 0.20, 
            'macd': 0.20,
            'bollinger': 0.15,
            'stochastic': 0.10,
            'adx': 0.10
        }
        
        logger.info("🔢 Advanced Indicators initialized")
    
    def calculate_all_indicators(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """모든 지표 계산"""
        if df is None or len(df) < 50:
            logger.warning("⚠️ Insufficient data for indicator calculation")
            return {}
        
        try:
            indicators = {}
            
            # 기본 가격 정보
            high = df['high'].values
            low = df['low'].values  
            close = df['close'].values
            volume = df['volume'].values if 'volume' in df.columns else np.ones(len(close))
            
            # 1. CCI (Commodity Channel Index)
            indicators['cci'] = self._calculate_cci(high, low, close)
            
            # 2. RSI (Relative Strength Index)
            indicators['rsi'] = self._calculate_rsi(close)
            
            # 3. MACD (Moving Average Convergence Divergence)
            indicators['macd'] = self._calculate_macd(close)
            
            # 4. Bollinger Bands
            indicators['bollinger'] = self._calculate_bollinger_bands(close)
            
            # 5. Stochastic Oscillator  
            indicators['stochastic'] = self._calculate_stochastic(high, low, close)
            
            # 6. ADX (Average Directional Index)
            indicators['adx'] = self._calculate_adx(high, low, close)
            
            # 7. Williams %R
            indicators['williams_r'] = self._calculate_williams_r(high, low, close)
            
            # 8. Ichimoku Cloud
            indicators['ichimoku'] = self._calculate_ichimoku(high, low, close)
            
            # 9. Volume indicators
            indicators['volume_sma'] = self._calculate_volume_indicators(close, volume)
            
            logger.info(f"✅ Calculated {len(indicators)} indicators")
            return indicators
            
        except Exception as e:
            logger.error(f"🔴 Error calculating indicators: {e}")
            return {}
    
    def _calculate_cci(self, high, low, close, period=20) -> Dict:
        """CCI 계산"""
        try:
            cci = talib.CCI(high, low, close, timeperiod=period)
            
            return {
                'values': cci,
                'current': cci[-1] if not np.isnan(cci[-1]) else 0,
                'previous': cci[-2] if len(cci) > 1 and not np.isnan(cci[-2]) else 0,
                'overbought': cci[-1] > 100,
                'oversold': cci[-1] < -100,
                'crossover_up': cci[-2] < -100 and cci[-1] > -100,
                'crossover_down': cci[-2] > 100 and cci[-1] < 100
            }
        except:
            return {'values': np.array([]), 'current': 0, 'previous': 0}
    
    def _calculate_rsi(self, close, period=14) -> Dict:
        """RSI 계산"""
        try:
            rsi = talib.RSI(close, timeperiod=period)
            
            return {
                'values': rsi,
                'current': rsi[-1] if not np.isnan(rsi[-1]) else 50,
                'previous': rsi[-2] if len(rsi) > 1 and not np.isnan(rsi[-2]) else 50,
                'overbought': rsi[-1] > 70,
                'oversold': rsi[-1] < 30,
                'neutral': 30 <= rsi[-1] <= 70
            }
        except:
            return {'values': np.array([]), 'current': 50, 'previous': 50}
    
    def _calculate_macd(self, close) -> Dict:
        """MACD 계산"""
        try:
            macd_line, macd_signal, macd_histogram = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
            
            return {
                'macd_line': macd_line,
                'signal_line': macd_signal,
                'histogram': macd_histogram,
                'current_macd': macd_line[-1] if not np.isnan(macd_line[-1]) else 0,
                'current_signal': macd_signal[-1] if not np.isnan(macd_signal[-1]) else 0,
                'current_histogram': macd_histogram[-1] if not np.isnan(macd_histogram[-1]) else 0,
                'bullish_crossover': (macd_line[-2] < macd_signal[-2] and macd_line[-1] > macd_signal[-1]),
                'bearish_crossover': (macd_line[-2] > macd_signal[-2] and macd_line[-1] < macd_signal[-1])
            }
        except:
            return {'macd_line': np.array([]), 'signal_line': np.array([]), 'histogram': np.array([])}
    
    def _calculate_bollinger_bands(self, close, period=20, std_dev=2) -> Dict:
        """볼린저 밴드 계산"""
        try:
            upper, middle, lower = talib.BBANDS(close, timeperiod=period, nbdevup=std_dev, nbdevdn=std_dev)
            
            current_price = close[-1]
            bb_width = (upper[-1] - lower[-1]) / middle[-1] * 100
            bb_position = (current_price - lower[-1]) / (upper[-1] - lower[-1])
            
            return {
                'upper': upper,
                'middle': middle,
                'lower': lower,
                'current_upper': upper[-1],
                'current_middle': middle[-1],
                'current_lower': lower[-1],
                'bb_width': bb_width,
                'bb_position': bb_position,
                'price_above_upper': current_price > upper[-1],
                'price_below_lower': current_price < lower[-1],
                'squeeze': bb_width < 10  # 밴드 폭이 좁은 경우
            }
        except:
            return {'upper': np.array([]), 'middle': np.array([]), 'lower': np.array([])}
    
    def _calculate_stochastic(self, high, low, close, k_period=14, d_period=3) -> Dict:
        """스토캐스틱 계산"""
        try:
            slowk, slowd = talib.STOCH(high, low, close, fastk_period=k_period, slowk_period=3, slowd_period=d_period)
            
            return {
                'k_line': slowk,
                'd_line': slowd,
                'current_k': slowk[-1] if not np.isnan(slowk[-1]) else 50,
                'current_d': slowd[-1] if not np.isnan(slowd[-1]) else 50,
                'overbought': slowk[-1] > 80,
                'oversold': slowk[-1] < 20,
                'bullish_crossover': (slowk[-2] < slowd[-2] and slowk[-1] > slowd[-1]),
                'bearish_crossover': (slowk[-2] > slowd[-2] and slowk[-1] < slowd[-1])
            }
        except:
            return {'k_line': np.array([]), 'd_line': np.array([])}
    
    def _calculate_adx(self, high, low, close, period=14) -> Dict:
        """ADX 계산 (트렌드 강도)"""
        try:
            adx = talib.ADX(high, low, close, timeperiod=period)
            plus_di = talib.PLUS_DI(high, low, close, timeperiod=period)
            minus_di = talib.MINUS_DI(high, low, close, timeperiod=period)
            
            current_adx = adx[-1] if not np.isnan(adx[-1]) else 0
            
            # 트렌드 강도 분류
            if current_adx > 50:
                trend_strength = "very_strong"
            elif current_adx > 25:
                trend_strength = "strong"
            elif current_adx > 20:
                trend_strength = "moderate"
            else:
                trend_strength = "weak"
            
            return {
                'adx': adx,
                'plus_di': plus_di,
                'minus_di': minus_di,
                'current_adx': current_adx,
                'current_plus_di': plus_di[-1] if not np.isnan(plus_di[-1]) else 0,
                'current_minus_di': minus_di[-1] if not np.isnan(minus_di[-1]) else 0,
                'trend_strength': trend_strength,
                'bullish_trend': plus_di[-1] > minus_di[-1],
                'bearish_trend': plus_di[-1] < minus_di[-1]
            }
        except:
            return {'adx': np.array([]), 'trend_strength': 'weak'}
    
    def _calculate_williams_r(self, high, low, close, period=14) -> Dict:
        """Williams %R 계산"""
        try:
            williams_r = talib.WILLR(high, low, close, timeperiod=period)
            
            return {
                'values': williams_r,
                'current': williams_r[-1] if not np.isnan(williams_r[-1]) else -50,
                'overbought': williams_r[-1] > -20,
                'oversold': williams_r[-1] < -80
            }
        except:
            return {'values': np.array([]), 'current': -50}
    
    def _calculate_ichimoku(self, high, low, close) -> Dict:
        """이치모쿠 계산"""
        try:
            # Tenkan-sen (전환선): 9일 최고가+최저가의 중간값
            tenkan_high = pd.Series(high).rolling(9).max()
            tenkan_low = pd.Series(low).rolling(9).min()
            tenkan_sen = (tenkan_high + tenkan_low) / 2
            
            # Kijun-sen (기준선): 26일 최고가+최저가의 중간값
            kijun_high = pd.Series(high).rolling(26).max()
            kijun_low = pd.Series(low).rolling(26).min()
            kijun_sen = (kijun_high + kijun_low) / 2
            
            # Senkou Span A (선행스팬A): (전환선+기준선)/2 을 26일 앞으로
            senkou_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
            
            # Senkou Span B (선행스팬B): 52일 최고가+최저가의 중간값을 26일 앞으로
            senkou_b_high = pd.Series(high).rolling(52).max()
            senkou_b_low = pd.Series(low).rolling(52).min()
            senkou_b = ((senkou_b_high + senkou_b_low) / 2).shift(26)
            
            current_price = close[-1]
            cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1]) if not pd.isna(senkou_a.iloc[-1]) else current_price
            cloud_bottom = min(senkou_a.iloc[-1], senkou_b.iloc[-1]) if not pd.isna(senkou_a.iloc[-1]) else current_price
            
            return {
                'tenkan_sen': tenkan_sen.values,
                'kijun_sen': kijun_sen.values,
                'senkou_a': senkou_a.values,
                'senkou_b': senkou_b.values,
                'current_tenkan': tenkan_sen.iloc[-1] if not pd.isna(tenkan_sen.iloc[-1]) else current_price,
                'current_kijun': kijun_sen.iloc[-1] if not pd.isna(kijun_sen.iloc[-1]) else current_price,
                'price_above_cloud': current_price > cloud_top,
                'price_below_cloud': current_price < cloud_bottom,
                'price_in_cloud': cloud_bottom <= current_price <= cloud_top,
                'bullish_tk_cross': tenkan_sen.iloc[-1] > kijun_sen.iloc[-1] and tenkan_sen.iloc[-2] <= kijun_sen.iloc[-2],
                'bearish_tk_cross': tenkan_sen.iloc[-1] < kijun_sen.iloc[-1] and tenkan_sen.iloc[-2] >= kijun_sen.iloc[-2]
            }
        except:
            return {'tenkan_sen': np.array([]), 'kijun_sen': np.array([])}
    
    def _calculate_volume_indicators(self, close, volume) -> Dict:
        """거래량 지표"""
        try:
            # Volume SMA
            vol_sma = pd.Series(volume).rolling(20).mean()
            
            # On-Balance Volume (OBV)
            obv = talib.OBV(close, volume)
            
            # Volume Rate of Change
            vol_roc = pd.Series(volume).pct_change(20) * 100
            
            current_volume = volume[-1]
            avg_volume = vol_sma.iloc[-1] if not pd.isna(vol_sma.iloc[-1]) else current_volume
            
            return {
                'volume_sma': vol_sma.values,
                'obv': obv,
                'volume_roc': vol_roc.values,
                'current_volume': current_volume,
                'avg_volume': avg_volume,
                'volume_surge': current_volume > avg_volume * 1.5,
                'volume_dry': current_volume < avg_volume * 0.5,
                'obv_trending_up': obv[-1] > obv[-20] if len(obv) > 20 else False
            }
        except:
            return {'volume_sma': np.array([]), 'obv': np.array([])}
    
    def generate_individual_signals(self, indicators: Dict) -> List[IndicatorSignal]:
        """각 지표별 개별 신호 생성"""
        signals = []
        timestamp = datetime.now()
        
        try:
            # 1. CCI 신호
            if 'cci' in indicators:
                cci_data = indicators['cci']
                if cci_data.get('crossover_up'):
                    signals.append(IndicatorSignal(
                        indicator='cci',
                        signal='BUY',
                        strength=SignalStrength.STRONG,
                        confidence=0.8,
                        value=cci_data['current'],
                        timestamp=timestamp,
                        metadata={'crossover_type': 'oversold_recovery'}
                    ))
                elif cci_data.get('crossover_down'):
                    signals.append(IndicatorSignal(
                        indicator='cci',
                        signal='SELL',
                        strength=SignalStrength.STRONG,
                        confidence=0.8,
                        value=cci_data['current'],
                        timestamp=timestamp,
                        metadata={'crossover_type': 'overbought_correction'}
                    ))
            
            # 2. RSI 신호
            if 'rsi' in indicators:
                rsi_data = indicators['rsi']
                rsi_value = rsi_data['current']
                
                if rsi_value < 30:
                    signals.append(IndicatorSignal(
                        indicator='rsi',
                        signal='BUY',
                        strength=SignalStrength.MODERATE,
                        confidence=0.6,
                        value=rsi_value,
                        timestamp=timestamp,
                        metadata={'condition': 'oversold'}
                    ))
                elif rsi_value > 70:
                    signals.append(IndicatorSignal(
                        indicator='rsi',
                        signal='SELL', 
                        strength=SignalStrength.MODERATE,
                        confidence=0.6,
                        value=rsi_value,
                        timestamp=timestamp,
                        metadata={'condition': 'overbought'}
                    ))
            
            # 3. MACD 신호
            if 'macd' in indicators:
                macd_data = indicators['macd']
                if macd_data.get('bullish_crossover'):
                    signals.append(IndicatorSignal(
                        indicator='macd',
                        signal='BUY',
                        strength=SignalStrength.MODERATE,
                        confidence=0.7,
                        value=macd_data['current_macd'],
                        timestamp=timestamp,
                        metadata={'crossover': 'bullish'}
                    ))
                elif macd_data.get('bearish_crossover'):
                    signals.append(IndicatorSignal(
                        indicator='macd',
                        signal='SELL',
                        strength=SignalStrength.MODERATE, 
                        confidence=0.7,
                        value=macd_data['current_macd'],
                        timestamp=timestamp,
                        metadata={'crossover': 'bearish'}
                    ))
            
            # 4. 볼린저 밴드 신호
            if 'bollinger' in indicators:
                bb_data = indicators['bollinger']
                if bb_data.get('price_below_lower'):
                    signals.append(IndicatorSignal(
                        indicator='bollinger',
                        signal='BUY',
                        strength=SignalStrength.WEAK,
                        confidence=0.5,
                        value=bb_data['bb_position'],
                        timestamp=timestamp,
                        metadata={'condition': 'below_lower_band'}
                    ))
                elif bb_data.get('price_above_upper'):
                    signals.append(IndicatorSignal(
                        indicator='bollinger',
                        signal='SELL',
                        strength=SignalStrength.WEAK,
                        confidence=0.5,
                        value=bb_data['bb_position'],
                        timestamp=timestamp,
                        metadata={'condition': 'above_upper_band'}
                    ))
            
            # 5. 스토캐스틱 신호
            if 'stochastic' in indicators:
                stoch_data = indicators['stochastic']
                if stoch_data.get('bullish_crossover') and stoch_data.get('oversold'):
                    signals.append(IndicatorSignal(
                        indicator='stochastic',
                        signal='BUY',
                        strength=SignalStrength.MODERATE,
                        confidence=0.6,
                        value=stoch_data['current_k'],
                        timestamp=timestamp,
                        metadata={'crossover': 'bullish_from_oversold'}
                    ))
                elif stoch_data.get('bearish_crossover') and stoch_data.get('overbought'):
                    signals.append(IndicatorSignal(
                        indicator='stochastic',
                        signal='SELL',
                        strength=SignalStrength.MODERATE,
                        confidence=0.6,
                        value=stoch_data['current_k'],
                        timestamp=timestamp,
                        metadata={'crossover': 'bearish_from_overbought'}
                    ))
            
            logger.info(f"📊 Generated {len(signals)} individual signals")
            
        except Exception as e:
            logger.error(f"🔴 Error generating individual signals: {e}")
        
        return signals
    
    def create_composite_signal(self, signals: List[IndicatorSignal], indicators: Dict) -> CompositeSignal:
        """복합 신호 생성"""
        try:
            if not signals:
                return CompositeSignal(
                    overall_signal='HOLD',
                    confidence=0.0,
                    strength=SignalStrength.VERY_WEAK,
                    contributing_signals=[],
                    trend_direction=TrendDirection.SIDEWAYS,
                    timestamp=datetime.now()
                )
            
            # 신호 점수 계산
            buy_score = 0.0
            sell_score = 0.0
            total_weight = 0.0
            
            for signal in signals:
                weight = self.indicator_weights.get(signal.indicator, 0.1)
                score = signal.confidence * signal.strength.value * weight
                
                if signal.signal == 'BUY':
                    buy_score += score
                elif signal.signal == 'SELL':
                    sell_score += score
                
                total_weight += weight
            
            # 정규화
            if total_weight > 0:
                buy_score /= total_weight
                sell_score /= total_weight
            
            # 최종 신호 결정
            if buy_score > sell_score and buy_score > 0.5:
                overall_signal = 'BUY'
                confidence = buy_score
            elif sell_score > buy_score and sell_score > 0.5:
                overall_signal = 'SELL'
                confidence = sell_score
            else:
                overall_signal = 'HOLD'
                confidence = abs(buy_score - sell_score)
            
            # 신호 강도 결정
            if confidence > 0.8:
                strength = SignalStrength.VERY_STRONG
            elif confidence > 0.6:
                strength = SignalStrength.STRONG
            elif confidence > 0.4:
                strength = SignalStrength.MODERATE
            elif confidence > 0.2:
                strength = SignalStrength.WEAK
            else:
                strength = SignalStrength.VERY_WEAK
            
            # 트렌드 방향 결정
            trend_direction = self._determine_trend_direction(indicators)
            
            composite = CompositeSignal(
                overall_signal=overall_signal,
                confidence=confidence,
                strength=strength,
                contributing_signals=signals,
                trend_direction=trend_direction,
                timestamp=datetime.now()
            )
            
            # 히스토리에 추가
            self.signal_history.append(composite)
            if len(self.signal_history) > self.max_history:
                self.signal_history.pop(0)
            
            logger.info(f"🎯 Composite signal: {overall_signal} (confidence: {confidence:.2f}, strength: {strength.name})")
            
            return composite
            
        except Exception as e:
            logger.error(f"🔴 Error creating composite signal: {e}")
            return CompositeSignal(
                overall_signal='HOLD',
                confidence=0.0,
                strength=SignalStrength.VERY_WEAK,
                contributing_signals=signals,
                trend_direction=TrendDirection.SIDEWAYS,
                timestamp=datetime.now()
            )
    
    def _determine_trend_direction(self, indicators: Dict) -> TrendDirection:
        """트렌드 방향 결정"""
        try:
            bullish_count = 0
            bearish_count = 0
            
            # ADX 기반 트렌드 강도 확인
            if 'adx' in indicators:
                adx_data = indicators['adx']
                if adx_data.get('current_adx', 0) < 20:
                    return TrendDirection.SIDEWAYS
                
                if adx_data.get('bullish_trend'):
                    bullish_count += 2
                elif adx_data.get('bearish_trend'):
                    bearish_count += 2
            
            # 이치모쿠 구름 위치
            if 'ichimoku' in indicators:
                ich_data = indicators['ichimoku']
                if ich_data.get('price_above_cloud'):
                    bullish_count += 1
                elif ich_data.get('price_below_cloud'):
                    bearish_count += 1
            
            # MACD 히스토그램 방향
            if 'macd' in indicators:
                macd_data = indicators['macd']
                if macd_data.get('current_histogram', 0) > 0:
                    bullish_count += 1
                else:
                    bearish_count += 1
            
            if bullish_count > bearish_count:
                return TrendDirection.BULLISH
            elif bearish_count > bullish_count:
                return TrendDirection.BEARISH
            else:
                return TrendDirection.SIDEWAYS
                
        except Exception as e:
            logger.error(f"🔴 Error determining trend direction: {e}")
            return TrendDirection.SIDEWAYS
    
    def get_signal_summary(self) -> Dict[str, Any]:
        """신호 요약 정보"""
        if not self.signal_history:
            return {'message': 'No signals generated yet'}
        
        recent_signals = self.signal_history[-10:]  # 최근 10개 신호
        
        signal_counts = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
        confidence_sum = 0
        
        for signal in recent_signals:
            signal_counts[signal.overall_signal] += 1
            confidence_sum += signal.confidence
        
        avg_confidence = confidence_sum / len(recent_signals)
        
        return {
            'total_signals': len(self.signal_history),
            'recent_signals': len(recent_signals),
            'signal_distribution': signal_counts,
            'average_confidence': round(avg_confidence, 3),
            'latest_signal': {
                'signal': recent_signals[-1].overall_signal,
                'confidence': round(recent_signals[-1].confidence, 3),
                'strength': recent_signals[-1].strength.name,
                'trend': recent_signals[-1].trend_direction.value,
                'contributing_indicators': len(recent_signals[-1].contributing_signals),
                'timestamp': recent_signals[-1].timestamp.isoformat()
            }
        }

# 테스트 함수
async def test_advanced_indicators():
    """Advanced Indicators 테스트"""
    print("🧪 Testing Advanced Indicators...")
    
    # 샘플 데이터 생성
    dates = pd.date_range('2025-01-01', periods=100, freq='5min')
    np.random.seed(42)
    
    price_base = 50000
    price_data = price_base + np.cumsum(np.random.randn(100) * 100)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': price_data + np.random.randn(100) * 50,
        'high': price_data + np.abs(np.random.randn(100) * 100),
        'low': price_data - np.abs(np.random.randn(100) * 100),
        'close': price_data,
        'volume': np.random.randint(1000, 10000, 100)
    })
    
    # 테스트 실행
    indicator_calc = AdvancedIndicators()
    
    # 모든 지표 계산
    indicators = indicator_calc.calculate_all_indicators(df)
    print(f"📊 Calculated indicators: {list(indicators.keys())}")
    
    # 개별 신호 생성
    individual_signals = indicator_calc.generate_individual_signals(indicators)
    print(f"🎯 Generated {len(individual_signals)} individual signals")
    
    for signal in individual_signals:
        print(f"  - {signal.indicator}: {signal.signal} ({signal.strength.name}, conf: {signal.confidence:.2f})")
    
    # 복합 신호 생성
    composite = indicator_calc.create_composite_signal(individual_signals, indicators)
    print(f"🏆 Composite signal: {composite.overall_signal}")
    print(f"  - Confidence: {composite.confidence:.2f}")
    print(f"  - Strength: {composite.strength.name}")
    print(f"  - Trend: {composite.trend_direction.value}")
    print(f"  - Contributing signals: {len(composite.contributing_signals)}")
    
    # 요약 정보
    summary = indicator_calc.get_signal_summary()
    print(f"📈 Summary: {summary}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_advanced_indicators())