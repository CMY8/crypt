# Fix the helpers utility by removing problematic characters
helpers_content = """\"\"\"
Utility helper functions for the crypto trading system.
\"\"\"

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
import logging
import json
import asyncio
import time
from functools import wraps, lru_cache
import hashlib
import os

logger = logging.getLogger(__name__)

# Decorators
def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    \"\"\"Retry decorator with exponential backoff\"\"\"
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}")
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def rate_limit(calls: int, period: float):
    \"\"\"Rate limiting decorator\"\"\"
    def decorator(func):
        call_times = []
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            nonlocal call_times
            now = time.time()
            
            # Remove old calls outside the period
            call_times = [t for t in call_times if now - t < period]
            
            # Check if we've exceeded the rate limit
            if len(call_times) >= calls:
                wait_time = period - (now - call_times[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    call_times = call_times[1:]  # Remove the oldest call
            
            call_times.append(now)
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            nonlocal call_times
            now = time.time()
            
            # Remove old calls outside the period
            call_times = [t for t in call_times if now - t < period]
            
            # Check if we've exceeded the rate limit
            if len(call_times) >= calls:
                wait_time = period - (now - call_times[0])
                if wait_time > 0:
                    time.sleep(wait_time)
                    call_times = call_times[1:]  # Remove the oldest call
            
            call_times.append(now)
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

def timing(func):
    \"\"\"Timing decorator to measure function execution time\"\"\"
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.debug(f"{func.__name__} took {end_time - start_time:.4f} seconds")
        return result
    return wrapper

# Data processing utilities
def normalize_price(price: float, precision: int = 8) -> float:
    \"\"\"Normalize price to specified precision\"\"\"
    return round(price, precision)

def normalize_quantity(quantity: float, precision: int = 6) -> float:
    \"\"\"Normalize quantity to specified precision\"\"\"
    return round(quantity, precision)

def calculate_position_size(account_balance: float, risk_per_trade: float, 
                          entry_price: float, stop_loss_price: float) -> float:
    \"\"\"Calculate position size based on risk management\"\"\"
    if entry_price == stop_loss_price:
        return 0.0
    
    risk_amount = account_balance * risk_per_trade
    price_diff = abs(entry_price - stop_loss_price)
    position_size = risk_amount / price_diff
    
    return position_size

def calculate_pnl(entry_price: float, exit_price: float, quantity: float, 
                 side: str, commission: float = 0.0) -> float:
    \"\"\"Calculate PnL for a trade\"\"\"
    if side.upper() == 'BUY':
        pnl = (exit_price - entry_price) * quantity
    else:  # SELL
        pnl = (entry_price - exit_price) * quantity
    
    # Subtract commission
    pnl -= commission
    
    return pnl

def calculate_commission(price: float, quantity: float, commission_rate: float) -> float:
    \"\"\"Calculate trading commission\"\"\"
    return price * quantity * commission_rate

def format_currency(amount: float, currency: str = 'USD', decimals: int = 2) -> str:
    \"\"\"Format amount as currency\"\"\"
    return f"{amount:,.{decimals}f} {currency}"

def format_percentage(value: float, decimals: int = 2) -> str:
    \"\"\"Format value as percentage\"\"\"
    return f"{value * 100:,.{decimals}f}%"

# Time utilities
def get_trading_session(timestamp: datetime) -> str:
    \"\"\"Get trading session for a timestamp (UTC)\"\"\"
    hour = timestamp.hour
    
    if 0 <= hour < 8:
        return "ASIAN"
    elif 8 <= hour < 16:
        return "EUROPEAN"
    else:
        return "AMERICAN"

def is_market_open(timestamp: datetime) -> bool:
    \"\"\"Check if crypto market is open (24/7 for crypto)\"\"\"
    return True  # Crypto markets are always open

def get_next_timeframe_close(timestamp: datetime, timeframe: str) -> datetime:
    \"\"\"Get the next timeframe close time\"\"\"
    timeframe_minutes = {
        '1m': 1, '3m': 3, '5m': 5, '15m': 15, '30m': 30,
        '1h': 60, '2h': 120, '4h': 240, '6h': 360, '8h': 480, '12h': 720,
        '1d': 1440, '3d': 4320, '1w': 10080
    }
    
    minutes = timeframe_minutes.get(timeframe, 1)
    
    # Round to next timeframe boundary
    next_minute = ((timestamp.minute // minutes) + 1) * minutes
    next_close = timestamp.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=next_minute)
    
    return next_close

# Data validation
def validate_price(price: float) -> bool:
    \"\"\"Validate if price is valid\"\"\"
    return price > 0 and not np.isnan(price) and np.isfinite(price)

def validate_quantity(quantity: float) -> bool:
    \"\"\"Validate if quantity is valid\"\"\"
    return quantity > 0 and not np.isnan(quantity) and np.isfinite(quantity)

def validate_ohlcv_data(data: Dict[str, float]) -> bool:
    \"\"\"Validate OHLCV data\"\"\"
    required_keys = ['open', 'high', 'low', 'close', 'volume']
    
    # Check all keys exist
    if not all(key in data for key in required_keys):
        return False
    
    # Validate prices
    for key in required_keys[:-1]:  # Exclude volume
        if not validate_price(data[key]):
            return False
    
    # Validate volume
    if not validate_quantity(data['volume']):
        return False
    
    # Check OHLC relationships
    if not (data['low'] <= data['open'] <= data['high'] and
            data['low'] <= data['close'] <= data['high']):
        return False
    
    return True

# Statistical utilities
def calculate_statistics(data: pd.Series) -> Dict[str, float]:
    \"\"\"Calculate basic statistics for a data series\"\"\"
    return {
        'count': len(data),
        'mean': data.mean(),
        'std': data.std(),
        'min': data.min(),
        'max': data.max(),
        'median': data.median(),
        'skewness': data.skew(),
        'kurtosis': data.kurtosis(),
        'quantile_25': data.quantile(0.25),
        'quantile_75': data.quantile(0.75)
    }

def calculate_correlation_matrix(data: pd.DataFrame) -> pd.DataFrame:
    \"\"\"Calculate correlation matrix\"\"\"
    return data.corr()

def detect_outliers(data: pd.Series, method: str = 'iqr', threshold: float = 1.5) -> pd.Series:
    \"\"\"Detect outliers in data\"\"\"
    if method == 'iqr':
        Q1 = data.quantile(0.25)
        Q3 = data.quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - threshold * IQR
        upper_bound = Q3 + threshold * IQR
        return (data < lower_bound) | (data > upper_bound)
    
    elif method == 'zscore':
        z_scores = np.abs((data - data.mean()) / data.std())
        return z_scores > threshold
    
    else:
        raise ValueError("Method must be 'iqr' or 'zscore'")

# File utilities
def save_to_json(data: Any, filename: str) -> bool:
    \"\"\"Save data to JSON file\"\"\"
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logger.error(f"Error saving to JSON: {e}")
        return False

def load_from_json(filename: str) -> Optional[Any]:
    \"\"\"Load data from JSON file\"\"\"
    try:
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"Error loading from JSON: {e}")
        return None

def save_dataframe_to_csv(df: pd.DataFrame, filename: str) -> bool:
    \"\"\"Save DataFrame to CSV\"\"\"
    try:
        df.to_csv(filename, index=True)
        return True
    except Exception as e:
        logger.error(f"Error saving DataFrame to CSV: {e}")
        return False

def load_dataframe_from_csv(filename: str) -> Optional[pd.DataFrame]:
    \"\"\"Load DataFrame from CSV\"\"\"
    try:
        if os.path.exists(filename):
            return pd.read_csv(filename, index_col=0, parse_dates=True)
        return None
    except Exception as e:
        logger.error(f"Error loading DataFrame from CSV: {e}")
        return None

# Hash utilities
def generate_order_id() -> str:
    \"\"\"Generate unique order ID\"\"\"
    timestamp = str(int(time.time() * 1000000))  # Microsecond precision
    hash_object = hashlib.md5(timestamp.encode())
    return hash_object.hexdigest()[:12].upper()

def generate_strategy_id(strategy_name: str, params: Dict) -> str:
    \"\"\"Generate unique strategy ID based on name and parameters\"\"\"
    params_str = json.dumps(params, sort_keys=True)
    combined = f"{strategy_name}_{params_str}"
    hash_object = hashlib.md5(combined.encode())
    return f"{strategy_name}_{hash_object.hexdigest()[:8]}"

# Message formatting
def format_trade_message(trade_data: Dict[str, Any]) -> str:
    \"\"\"Format trade data for notifications\"\"\"
    return f'''
[TRADE ALERT]
Symbol: {trade_data.get('symbol', 'N/A')}
Side: {trade_data.get('side', 'N/A')}
Quantity: {trade_data.get('quantity', 'N/A')}
Price: {trade_data.get('price', 'N/A')}
PnL: {format_currency(trade_data.get('pnl', 0))}
Time: {trade_data.get('timestamp', 'N/A')}
    '''.strip()

def format_portfolio_summary(portfolio_data: Dict[str, Any]) -> str:
    \"\"\"Format portfolio data for notifications\"\"\"
    return f'''
[PORTFOLIO SUMMARY]
Total Balance: {format_currency(portfolio_data.get('total_balance', 0))}
Available: {format_currency(portfolio_data.get('available_balance', 0))}
Unrealized PnL: {format_currency(portfolio_data.get('unrealized_pnl', 0))}
Daily PnL: {format_currency(portfolio_data.get('daily_pnl', 0))}
Open Trades: {portfolio_data.get('open_trades', 0)}
    '''.strip()

# Configuration helpers
@lru_cache(maxsize=128)
def get_symbol_precision(symbol: str) -> Tuple[int, int]:
    \"\"\"Get price and quantity precision for a symbol (cached)\"\"\"
    # Default precisions - should be updated from exchange info
    price_precision = 8
    quantity_precision = 6
    
    # Special cases for common symbols
    if 'USDT' in symbol:
        price_precision = 4
    if 'BTC' in symbol and not symbol.startswith('BTC'):
        quantity_precision = 8
    
    return price_precision, quantity_precision

def get_min_notional(symbol: str) -> float:
    \"\"\"Get minimum notional value for a symbol\"\"\"
    # Default minimum notional - should be updated from exchange info
    return 10.0  # $10 minimum

# Performance monitoring
class PerformanceMonitor:
    \"\"\"Monitor function performance\"\"\"
    
    def __init__(self):
        self.metrics = {}
    
    def record_execution_time(self, function_name: str, execution_time: float):
        \"\"\"Record execution time for a function\"\"\"
        if function_name not in self.metrics:
            self.metrics[function_name] = []
        
        self.metrics[function_name].append(execution_time)
        
        # Keep only last 1000 measurements
        if len(self.metrics[function_name]) > 1000:
            self.metrics[function_name] = self.metrics[function_name][-1000:]
    
    def get_statistics(self, function_name: str) -> Optional[Dict[str, float]]:
        \"\"\"Get performance statistics for a function\"\"\"
        if function_name not in self.metrics or not self.metrics[function_name]:
            return None
        
        times = self.metrics[function_name]
        return {
            'count': len(times),
            'mean': np.mean(times),
            'std': np.std(times),
            'min': np.min(times),
            'max': np.max(times),
            'median': np.median(times),
            'p95': np.percentile(times, 95),
            'p99': np.percentile(times, 99)
        }
    
    def get_all_statistics(self) -> Dict[str, Dict[str, float]]:
        \"\"\"Get performance statistics for all functions\"\"\"
        return {
            func_name: self.get_statistics(func_name)
            for func_name in self.metrics.keys()
        }

# Global performance monitor
performance_monitor = PerformanceMonitor()

def monitor_performance(func):
    \"\"\"Decorator to monitor function performance\"\"\"
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        
        execution_time = end_time - start_time
        performance_monitor.record_execution_time(func.__name__, execution_time)
        
        return result
    return wrapper

# Context managers
class TradingContext:
    \"\"\"Context manager for trading operations\"\"\"
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.start_time = None
        self.operations = []
    
    def __enter__(self):
        self.start_time = time.time()
        logger.info(f"Starting trading context for strategy {self.strategy_id}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        duration = end_time - self.start_time
        
        if exc_type is None:
            logger.info(f"Trading context completed successfully for {self.strategy_id} in {duration:.4f}s")
        else:
            logger.error(f"Trading context failed for {self.strategy_id}: {exc_val}")
        
        return False  # Don't suppress exceptions
    
    def add_operation(self, operation: str, details: Dict = None):
        \"\"\"Add operation to context log\"\"\"
        self.operations.append({
            'timestamp': datetime.utcnow(),
            'operation': operation,
            'details': details or {}
        })

# Data structure utilities
class CircularBuffer:
    \"\"\"Circular buffer for efficient data storage\"\"\"
    
    def __init__(self, size: int):
        self.size = size
        self.buffer = [None] * size
        self.head = 0
        self.count = 0
    
    def append(self, item):
        \"\"\"Append item to buffer\"\"\"
        self.buffer[self.head] = item
        self.head = (self.head + 1) % self.size
        if self.count < self.size:
            self.count += 1
    
    def get_all(self) -> List:
        \"\"\"Get all items in order\"\"\"
        if self.count < self.size:
            return self.buffer[:self.count]
        else:
            return self.buffer[self.head:] + self.buffer[:self.head]
    
    def get_latest(self, n: int = 1) -> List:
        \"\"\"Get latest n items\"\"\"
        if n <= 0:
            return []
        
        all_items = self.get_all()
        return all_items[-n:]
    
    def is_full(self) -> bool:
        \"\"\"Check if buffer is full\"\"\"
        return self.count == self.size
    
    def clear(self):
        \"\"\"Clear the buffer\"\"\"
        self.buffer = [None] * self.size
        self.head = 0
        self.count = 0
"""

with open('crypto_trading_system/utils/helpers.py', 'w') as f:
    f.write(helpers_content)

print("✅ Helpers utility module created successfully!")