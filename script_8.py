# Create technical indicators utility
indicators_content = """\"\"\"
Technical indicators module for trading strategies.
Implements common technical analysis indicators.
\"\"\"

import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class TechnicalIndicators:
    \"\"\"Collection of technical analysis indicators\"\"\"
    
    @staticmethod
    def sma(data: pd.Series, window: int) -> pd.Series:
        \"\"\"Simple Moving Average\"\"\"
        return data.rolling(window=window).mean()
    
    @staticmethod
    def ema(data: pd.Series, window: int, alpha: Optional[float] = None) -> pd.Series:
        \"\"\"Exponential Moving Average\"\"\"
        if alpha is None:
            alpha = 2 / (window + 1)
        return data.ewm(alpha=alpha, adjust=False).mean()
    
    @staticmethod
    def rsi(data: pd.Series, window: int = 14) -> pd.Series:
        \"\"\"Relative Strength Index\"\"\"
        delta = data.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        
        avg_gain = gain.rolling(window=window).mean()
        avg_loss = loss.rolling(window=window).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        \"\"\"MACD (Moving Average Convergence Divergence)\"\"\"
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators.ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    @staticmethod
    def bollinger_bands(data: pd.Series, window: int = 20, num_std: float = 2) -> Dict[str, pd.Series]:
        \"\"\"Bollinger Bands\"\"\"
        sma = TechnicalIndicators.sma(data, window)
        std = data.rolling(window=window).std()
        
        upper_band = sma + (std * num_std)
        lower_band = sma - (std * num_std)
        
        return {
            'upper': upper_band,
            'middle': sma,
            'lower': lower_band,
            'bandwidth': (upper_band - lower_band) / sma,
            'percent_b': (data - lower_band) / (upper_band - lower_band)
        }
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                  k_window: int = 14, d_window: int = 3) -> Dict[str, pd.Series]:
        \"\"\"Stochastic Oscillator\"\"\"
        lowest_low = low.rolling(window=k_window).min()
        highest_high = high.rolling(window=k_window).max()
        
        k_percent = 100 * ((close - lowest_low) / (highest_high - lowest_low))
        d_percent = k_percent.rolling(window=d_window).mean()
        
        return {
            'k': k_percent,
            'd': d_percent
        }
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        \"\"\"Average True Range\"\"\"
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        
        true_range = np.maximum(high_low, np.maximum(high_close, low_close))
        return true_range.rolling(window=window).mean()
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> Dict[str, pd.Series]:
        \"\"\"Average Directional Index\"\"\"
        # Calculate True Range
        tr = TechnicalIndicators.atr(high, low, close, 1)
        
        # Calculate Directional Movement
        plus_dm = high.diff()
        minus_dm = low.diff() * -1
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        plus_dm[(plus_dm - minus_dm) <= 0] = 0
        minus_dm[(minus_dm - plus_dm) <= 0] = 0
        
        # Smooth the values
        tr_smooth = tr.ewm(span=window).mean()
        plus_dm_smooth = plus_dm.ewm(span=window).mean()
        minus_dm_smooth = minus_dm.ewm(span=window).mean()
        
        # Calculate DI
        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)
        
        # Calculate ADX
        dx = 100 * np.abs((plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.ewm(span=window).mean()
        
        return {
            'adx': adx,
            'plus_di': plus_di,
            'minus_di': minus_di
        }
    
    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
        \"\"\"Williams %R\"\"\"
        highest_high = high.rolling(window=window).max()
        lowest_low = low.rolling(window=window).min()
        
        williams_r = -100 * ((highest_high - close) / (highest_high - lowest_low))
        
        return williams_r
    
    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20) -> pd.Series:
        \"\"\"Commodity Channel Index\"\"\"
        typical_price = (high + low + close) / 3
        sma_tp = typical_price.rolling(window=window).mean()
        mad = typical_price.rolling(window=window).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (typical_price - sma_tp) / (0.015 * mad)
        
        return cci
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        \"\"\"On-Balance Volume\"\"\"
        obv = pd.Series(index=close.index, dtype=float)
        obv.iloc[0] = volume.iloc[0]
        
        for i in range(1, len(close)):
            if close.iloc[i] > close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + volume.iloc[i]
            elif close.iloc[i] < close.iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - volume.iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        
        return obv
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        \"\"\"Volume Weighted Average Price\"\"\"
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        
        return vwap
    
    @staticmethod
    def money_flow_index(high: pd.Series, low: pd.Series, close: pd.Series, 
                        volume: pd.Series, window: int = 14) -> pd.Series:
        \"\"\"Money Flow Index\"\"\"
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        
        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0).rolling(window).sum()
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0).rolling(window).sum()
        
        money_flow_ratio = positive_flow / negative_flow
        mfi = 100 - (100 / (1 + money_flow_ratio))
        
        return mfi
    
    @staticmethod
    def keltner_channels(high: pd.Series, low: pd.Series, close: pd.Series, 
                        window: int = 20, multiplier: float = 2.0) -> Dict[str, pd.Series]:
        \"\"\"Keltner Channels\"\"\"
        ema = TechnicalIndicators.ema(close, window)
        atr = TechnicalIndicators.atr(high, low, close, window)
        
        upper_channel = ema + (multiplier * atr)
        lower_channel = ema - (multiplier * atr)
        
        return {
            'upper': upper_channel,
            'middle': ema,
            'lower': lower_channel
        }
    
    @staticmethod
    def ichimoku_cloud(high: pd.Series, low: pd.Series, close: pd.Series,
                      tenkan_period: int = 9, kijun_period: int = 26, 
                      senkou_period: int = 52) -> Dict[str, pd.Series]:
        \"\"\"Ichimoku Cloud\"\"\"
        # Tenkan-sen (Conversion Line)
        tenkan_sen = (high.rolling(tenkan_period).max() + low.rolling(tenkan_period).min()) / 2
        
        # Kijun-sen (Base Line)
        kijun_sen = (high.rolling(kijun_period).max() + low.rolling(kijun_period).min()) / 2
        
        # Senkou Span A (Leading Span A)
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(kijun_period)
        
        # Senkou Span B (Leading Span B)
        senkou_span_b = ((high.rolling(senkou_period).max() + low.rolling(senkou_period).min()) / 2).shift(kijun_period)
        
        # Chikou Span (Lagging Span)
        chikou_span = close.shift(-kijun_period)
        
        return {
            'tenkan_sen': tenkan_sen,
            'kijun_sen': kijun_sen,
            'senkou_span_a': senkou_span_a,
            'senkou_span_b': senkou_span_b,
            'chikou_span': chikou_span
        }
    
    @staticmethod
    def parabolic_sar(high: pd.Series, low: pd.Series, acceleration: float = 0.02, 
                     maximum: float = 0.2) -> pd.Series:
        \"\"\"Parabolic SAR\"\"\"
        sar = pd.Series(index=high.index, dtype=float)
        trend = pd.Series(index=high.index, dtype=int)
        af = pd.Series(index=high.index, dtype=float)
        ep = pd.Series(index=high.index, dtype=float)
        
        # Initialize
        sar.iloc[0] = low.iloc[0]
        trend.iloc[0] = 1  # 1 for uptrend, -1 for downtrend
        af.iloc[0] = acceleration
        ep.iloc[0] = high.iloc[0]
        
        for i in range(1, len(high)):
            if trend.iloc[i-1] == 1:  # Uptrend
                sar.iloc[i] = sar.iloc[i-1] + af.iloc[i-1] * (ep.iloc[i-1] - sar.iloc[i-1])
                
                if low.iloc[i] <= sar.iloc[i]:
                    # Trend reversal
                    trend.iloc[i] = -1
                    sar.iloc[i] = ep.iloc[i-1]
                    af.iloc[i] = acceleration
                    ep.iloc[i] = low.iloc[i]
                else:
                    trend.iloc[i] = 1
                    if high.iloc[i] > ep.iloc[i-1]:
                        ep.iloc[i] = high.iloc[i]
                        af.iloc[i] = min(af.iloc[i-1] + acceleration, maximum)
                    else:
                        ep.iloc[i] = ep.iloc[i-1]
                        af.iloc[i] = af.iloc[i-1]
            else:  # Downtrend
                sar.iloc[i] = sar.iloc[i-1] + af.iloc[i-1] * (ep.iloc[i-1] - sar.iloc[i-1])
                
                if high.iloc[i] >= sar.iloc[i]:
                    # Trend reversal
                    trend.iloc[i] = 1
                    sar.iloc[i] = ep.iloc[i-1]
                    af.iloc[i] = acceleration
                    ep.iloc[i] = high.iloc[i]
                else:
                    trend.iloc[i] = -1
                    if low.iloc[i] < ep.iloc[i-1]:
                        ep.iloc[i] = low.iloc[i]
                        af.iloc[i] = min(af.iloc[i-1] + acceleration, maximum)
                    else:
                        ep.iloc[i] = ep.iloc[i-1]
                        af.iloc[i] = af.iloc[i-1]
        
        return sar
    
    # Pattern Recognition
    @staticmethod
    def detect_support_resistance(high: pd.Series, low: pd.Series, 
                                 window: int = 20, min_touches: int = 2) -> Dict[str, list]:
        \"\"\"Detect support and resistance levels\"\"\"
        highs = high.rolling(window, center=True).max() == high
        lows = low.rolling(window, center=True).min() == low
        
        resistance_levels = []
        support_levels = []
        
        # Find local highs (resistance)
        for i in range(len(high)):
            if highs.iloc[i] and not pd.isna(high.iloc[i]):
                level = high.iloc[i]
                touches = ((high >= level * 0.99) & (high <= level * 1.01)).sum()
                if touches >= min_touches:
                    resistance_levels.append({'price': level, 'touches': touches, 'index': i})
        
        # Find local lows (support)
        for i in range(len(low)):
            if lows.iloc[i] and not pd.isna(low.iloc[i]):
                level = low.iloc[i]
                touches = ((low >= level * 0.99) & (low <= level * 1.01)).sum()
                if touches >= min_touches:
                    support_levels.append({'price': level, 'touches': touches, 'index': i})
        
        return {
            'resistance': sorted(resistance_levels, key=lambda x: x['touches'], reverse=True),
            'support': sorted(support_levels, key=lambda x: x['touches'], reverse=True)
        }
    
    @staticmethod
    def detect_divergence(price: pd.Series, indicator: pd.Series, 
                         window: int = 5) -> Dict[str, list]:
        \"\"\"Detect bullish and bearish divergences\"\"\"
        price_peaks = price.rolling(window, center=True).max() == price
        price_troughs = price.rolling(window, center=True).min() == price
        
        indicator_peaks = indicator.rolling(window, center=True).max() == indicator
        indicator_troughs = indicator.rolling(window, center=True).min() == indicator
        
        bullish_divergences = []
        bearish_divergences = []
        
        # Find divergences between price and indicator
        for i in range(window, len(price) - window):
            if price_troughs.iloc[i] and indicator_troughs.iloc[i]:
                # Look for previous trough
                for j in range(max(0, i - 50), i):
                    if price_troughs.iloc[j] and indicator_troughs.iloc[j]:
                        # Check for bullish divergence
                        if (price.iloc[i] < price.iloc[j] and 
                            indicator.iloc[i] > indicator.iloc[j]):
                            bullish_divergences.append({
                                'current_index': i,
                                'previous_index': j,
                                'strength': abs(indicator.iloc[i] - indicator.iloc[j])
                            })
                        break
            
            if price_peaks.iloc[i] and indicator_peaks.iloc[i]:
                # Look for previous peak
                for j in range(max(0, i - 50), i):
                    if price_peaks.iloc[j] and indicator_peaks.iloc[j]:
                        # Check for bearish divergence
                        if (price.iloc[i] > price.iloc[j] and 
                            indicator.iloc[i] < indicator.iloc[j]):
                            bearish_divergences.append({
                                'current_index': i,
                                'previous_index': j,
                                'strength': abs(indicator.iloc[i] - indicator.iloc[j])
                            })
                        break
        
        return {
            'bullish': bullish_divergences,
            'bearish': bearish_divergences
        }
    
    # Volatility measures
    @staticmethod
    def realized_volatility(returns: pd.Series, window: int = 20) -> pd.Series:
        \"\"\"Calculate realized volatility\"\"\"
        return returns.rolling(window).std() * np.sqrt(252)  # Annualized
    
    @staticmethod
    def parkinson_volatility(high: pd.Series, low: pd.Series, window: int = 20) -> pd.Series:
        \"\"\"Parkinson volatility estimator\"\"\"
        ln_hl = np.log(high / low)
        parkinson_vol = np.sqrt(ln_hl.rolling(window).mean() / (4 * np.log(2)))
        return parkinson_vol * np.sqrt(252)  # Annualized
    
    # Market regime detection
    @staticmethod
    def detect_market_regime(price: pd.Series, volume: pd.Series = None, 
                           window: int = 50) -> pd.Series:
        \"\"\"Detect market regime (trending vs ranging)\"\"\"
        # Calculate trend strength using ADX-like approach
        returns = price.pct_change()
        
        # Trending vs ranging based on price movement efficiency
        price_change = abs(price - price.shift(window))
        path_length = returns.abs().rolling(window).sum()
        
        efficiency_ratio = price_change / (path_length * price.shift(window))
        
        # Categorize regime
        regime = pd.Series('RANGING', index=price.index)
        regime[efficiency_ratio > 0.3] = 'TRENDING'
        regime[returns.rolling(window).std() > returns.rolling(window * 2).std()] = 'VOLATILE'
        
        return regime

# Utility functions
def calculate_returns(prices: pd.Series, method: str = 'simple') -> pd.Series:
    \"\"\"Calculate returns from price series\"\"\"
    if method == 'simple':
        return prices.pct_change()
    elif method == 'log':
        return np.log(prices / prices.shift(1))
    else:
        raise ValueError("Method must be 'simple' or 'log'")

def calculate_drawdown(equity_curve: pd.Series) -> pd.Series:
    \"\"\"Calculate drawdown from equity curve\"\"\"
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return drawdown

def calculate_max_drawdown(equity_curve: pd.Series) -> float:
    \"\"\"Calculate maximum drawdown\"\"\"
    drawdown = calculate_drawdown(equity_curve)
    return drawdown.min()

def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    \"\"\"Calculate Sharpe ratio\"\"\"
    excess_returns = returns - risk_free_rate / 252  # Daily risk-free rate
    return excess_returns.mean() / excess_returns.std() * np.sqrt(252)

def calculate_sortino_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    \"\"\"Calculate Sortino ratio\"\"\"
    excess_returns = returns - risk_free_rate / 252
    downside_returns = excess_returns[excess_returns < 0]
    
    if len(downside_returns) == 0:
        return np.inf
    
    downside_deviation = downside_returns.std()
    return excess_returns.mean() / downside_deviation * np.sqrt(252)

def calculate_calmar_ratio(returns: pd.Series) -> float:
    \"\"\"Calculate Calmar ratio\"\"\"
    equity_curve = (1 + returns).cumprod()
    annual_return = equity_curve.iloc[-1] ** (252 / len(returns)) - 1
    max_dd = abs(calculate_max_drawdown(equity_curve))
    
    if max_dd == 0:
        return np.inf
    
    return annual_return / max_dd
"""

with open('crypto_trading_system/utils/indicators.py', 'w') as f:
    f.write(indicators_content)

print("✅ Technical indicators module created!")