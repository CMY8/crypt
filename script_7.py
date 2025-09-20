# Create historical data manager
historical_data_content = """\"\"\"
Historical data manager for downloading and managing historical market data.
Uses Binance API to download OHLCV data and stores it in the database.
\"\"\"

import asyncio
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import time
from concurrent.futures import ThreadPoolExecutor
import ccxt

from ..config.binance_config import binance_config
from ..database.db_manager import db_manager

logger = logging.getLogger(__name__)

class HistoricalDataManager:
    \"\"\"Manager for historical market data operations\"\"\"
    
    def __init__(self):
        self.exchange = None
        self.rate_limit_delay = 0.1  # 100ms between requests
        self.max_retries = 3
        self.retry_delay = 5  # seconds
        
        # Binance rate limits: 1200 requests per minute
        self.requests_per_minute = 1000  # Conservative limit
        self.request_timestamps = []
        
        self.executor = ThreadPoolExecutor(max_workers=2)
    
    def _get_exchange(self):
        \"\"\"Get CCXT exchange instance\"\"\"
        if self.exchange is None:
            try:
                self.exchange = binance_config.ccxt_client
                logger.info("Connected to Binance via CCXT")
            except Exception as e:
                logger.error(f"Failed to connect to Binance: {e}")
                raise
        
        return self.exchange
    
    def _check_rate_limit(self):
        \"\"\"Check and enforce rate limits\"\"\"
        current_time = time.time()
        
        # Clean old timestamps (older than 1 minute)
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if current_time - ts < 60
        ]
        
        # Check if we're hitting rate limit
        if len(self.request_timestamps) >= self.requests_per_minute:
            sleep_time = 60 - (current_time - self.request_timestamps[0])
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
                self.request_timestamps = []
        
        # Add current request timestamp
        self.request_timestamps.append(current_time)
        time.sleep(self.rate_limit_delay)
    
    def _convert_timeframe(self, timeframe: str) -> str:
        \"\"\"Convert internal timeframe to Binance format\"\"\"
        timeframe_map = {
            '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
            '1d': '1d', '3d': '3d', '1w': '1w', '1M': '1M'
        }
        return timeframe_map.get(timeframe, timeframe)
    
    def _timeframe_to_seconds(self, timeframe: str) -> int:
        \"\"\"Convert timeframe to seconds\"\"\"
        timeframe_seconds = {
            '1m': 60, '3m': 180, '5m': 300, '15m': 900, '30m': 1800,
            '1h': 3600, '2h': 7200, '4h': 14400, '6h': 21600, 
            '8h': 28800, '12h': 43200, '1d': 86400, '3d': 259200,
            '1w': 604800, '1M': 2592000  # Approximate
        }
        return timeframe_seconds.get(timeframe, 60)
    
    async def download_data(self, symbol: str, timeframes: List[str], 
                           start_date: datetime, end_date: datetime) -> bool:
        \"\"\"Download historical data for a symbol and timeframes\"\"\"
        try:
            exchange = self._get_exchange()
            
            total_success = True
            
            for timeframe in timeframes:
                success = await self._download_timeframe_data(
                    exchange, symbol, timeframe, start_date, end_date
                )
                if not success:
                    total_success = False
                    logger.error(f"Failed to download {symbol} {timeframe}")
            
            return total_success
            
        except Exception as e:
            logger.error(f"Error downloading data for {symbol}: {e}")
            return False
    
    async def _download_timeframe_data(self, exchange, symbol: str, timeframe: str,
                                     start_date: datetime, end_date: datetime) -> bool:
        \"\"\"Download data for a specific timeframe\"\"\"
        try:
            binance_timeframe = self._convert_timeframe(timeframe)
            
            # Check what data we already have
            existing_data = db_manager.get_latest_ohlcv(symbol, timeframe)
            
            if existing_data:
                # Continue from where we left off
                start_date = max(start_date, existing_data.timestamp + timedelta(seconds=self._timeframe_to_seconds(timeframe)))
            
            if start_date >= end_date:
                logger.info(f"Data for {symbol} {timeframe} is already up to date")
                return True
            
            logger.info(f"Downloading {symbol} {timeframe} from {start_date} to {end_date}")
            
            # Download in chunks to respect rate limits
            current_start = start_date
            chunk_size = 1000  # Binance limit per request
            
            total_candles = 0
            
            while current_start < end_date:
                # Calculate end time for this chunk
                timeframe_seconds = self._timeframe_to_seconds(timeframe)
                chunk_end = current_start + timedelta(seconds=timeframe_seconds * chunk_size)
                chunk_end = min(chunk_end, end_date)
                
                # Download chunk
                candles = await self._download_chunk(
                    exchange, symbol, binance_timeframe, current_start, chunk_end
                )
                
                if candles:
                    # Process and save candles
                    processed_candles = self._process_candles(candles)
                    
                    if processed_candles:
                        db_manager.save_ohlcv_data(symbol, timeframe, processed_candles)
                        total_candles += len(processed_candles)
                        
                        # Update current_start to continue from last candle
                        last_candle_time = processed_candles[-1]['timestamp']
                        current_start = last_candle_time + timedelta(seconds=timeframe_seconds)
                    else:
                        break
                else:
                    # No more data available
                    break
                
                # Rate limiting
                self._check_rate_limit()
            
            logger.info(f"Downloaded {total_candles} candles for {symbol} {timeframe}")
            return total_candles > 0
            
        except Exception as e:
            logger.error(f"Error downloading {symbol} {timeframe}: {e}")
            return False
    
    async def _download_chunk(self, exchange, symbol: str, timeframe: str, 
                            start_time: datetime, end_time: datetime) -> Optional[List]:
        \"\"\"Download a chunk of OHLCV data\"\"\"
        for attempt in range(self.max_retries):
            try:
                # Convert to milliseconds
                since = int(start_time.timestamp() * 1000)
                until = int(end_time.timestamp() * 1000)
                
                # Fetch OHLCV data
                candles = exchange.fetch_ohlcv(
                    symbol=symbol,
                    timeframe=timeframe,
                    since=since,
                    limit=1000,
                    params={'endTime': until} if until else {}
                )
                
                return candles
                
            except ccxt.RateLimitExceeded:
                wait_time = (attempt + 1) * self.retry_delay
                logger.warning(f"Rate limit exceeded, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                
            except ccxt.NetworkError as e:
                wait_time = (attempt + 1) * self.retry_delay
                logger.warning(f"Network error: {e}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                
            except Exception as e:
                logger.error(f"Unexpected error downloading {symbol} {timeframe}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise
        
        return None
    
    def _process_candles(self, raw_candles: List) -> List[Dict]:
        \"\"\"Process raw candles into database format\"\"\"
        processed = []
        
        for candle in raw_candles:
            try:
                timestamp = datetime.fromtimestamp(candle[0] / 1000)
                
                processed_candle = {
                    'timestamp': timestamp,
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                }
                
                # Basic validation
                if (processed_candle['high'] >= processed_candle['low'] and
                    processed_candle['high'] >= processed_candle['open'] and
                    processed_candle['high'] >= processed_candle['close'] and
                    processed_candle['low'] <= processed_candle['open'] and
                    processed_candle['low'] <= processed_candle['close'] and
                    processed_candle['volume'] >= 0):
                    
                    processed.append(processed_candle)
                else:
                    logger.warning(f"Invalid candle data: {processed_candle}")
                    
            except (IndexError, ValueError, TypeError) as e:
                logger.warning(f"Error processing candle {candle}: {e}")
                continue
        
        return processed
    
    def get_historical_data(self, symbol: str, timeframe: str, 
                           start_date: datetime, end_date: datetime) -> pd.DataFrame:
        \"\"\"Get historical data from database\"\"\"
        return db_manager.get_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_date,
            end_time=end_date
        )
    
    def get_available_symbols(self) -> List[str]:
        \"\"\"Get list of available symbols from exchange\"\"\"
        try:
            exchange = self._get_exchange()
            markets = exchange.load_markets()
            
            # Filter for USDT pairs (most liquid)
            usdt_pairs = [
                symbol for symbol in markets.keys() 
                if symbol.endswith('/USDT') and markets[symbol]['active']
            ]
            
            # Sort by volume (if available)
            return sorted(usdt_pairs)
            
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            return []
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        \"\"\"Get symbol information and trading rules\"\"\"
        try:
            exchange = self._get_exchange()
            markets = exchange.load_markets()
            
            if symbol in markets:
                market = markets[symbol]
                return {
                    'symbol': symbol,
                    'base': market['base'],
                    'quote': market['quote'],
                    'active': market['active'],
                    'min_amount': market['limits']['amount']['min'],
                    'max_amount': market['limits']['amount']['max'],
                    'min_price': market['limits']['price']['min'],
                    'max_price': market['limits']['price']['max'],
                    'min_cost': market['limits']['cost']['min'],
                    'precision_amount': market['precision']['amount'],
                    'precision_price': market['precision']['price'],
                    'fees': market['fees']
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting symbol info for {symbol}: {e}")
            return None
    
    async def update_symbol_data(self, symbol: str, timeframes: List[str], 
                               days_back: int = 7) -> bool:
        \"\"\"Update data for a specific symbol\"\"\"
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        return await self.download_data(symbol, timeframes, start_date, end_date)
    
    async def update_all_symbols(self, symbols: List[str], timeframes: List[str]) -> Dict[str, bool]:
        \"\"\"Update data for multiple symbols\"\"\"
        results = {}
        
        for symbol in symbols:
            try:
                result = await self.update_symbol_data(symbol, timeframes)
                results[symbol] = result
                
                # Add delay between symbols to respect rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error updating {symbol}: {e}")
                results[symbol] = False
        
        return results
    
    def validate_data(self, symbol: str, timeframe: str, 
                     start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        \"\"\"Validate historical data quality\"\"\"
        df = self.get_historical_data(symbol, timeframe, start_date, end_date)
        
        if df.empty:
            return {'valid': False, 'errors': ['No data available']}
        
        errors = []
        warnings = []
        
        # Check for missing data (gaps)
        expected_intervals = self._timeframe_to_seconds(timeframe)
        time_diffs = df.index.to_series().diff().dt.total_seconds()
        gaps = time_diffs[time_diffs > expected_intervals * 1.5]
        
        if len(gaps) > 0:
            warnings.append(f"Found {len(gaps)} data gaps")
        
        # Check for invalid OHLC relationships
        invalid_high = (df['high'] < df['open']) | (df['high'] < df['close']) | (df['high'] < df['low'])
        invalid_low = (df['low'] > df['open']) | (df['low'] > df['close']) | (df['low'] > df['high'])
        
        if invalid_high.any():
            errors.append(f"Found {invalid_high.sum()} invalid high prices")
        
        if invalid_low.any():
            errors.append(f"Found {invalid_low.sum()} invalid low prices")
        
        # Check for zero or negative prices
        zero_prices = (df[['open', 'high', 'low', 'close']] <= 0).any(axis=1)
        if zero_prices.any():
            errors.append(f"Found {zero_prices.sum()} candles with zero/negative prices")
        
        # Check for zero volume (might be valid in some cases)
        zero_volume = (df['volume'] == 0).sum()
        if zero_volume > len(df) * 0.1:  # More than 10%
            warnings.append(f"Found {zero_volume} candles with zero volume")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_candles': len(df),
            'date_range': (df.index.min(), df.index.max()) if not df.empty else None,
            'gaps_count': len(gaps)
        }
    
    def get_data_summary(self) -> Dict[str, Any]:
        \"\"\"Get summary of available historical data\"\"\"
        try:
            stats = db_manager.get_database_stats()
            
            # Get unique symbols and timeframes
            with db_manager.get_session() as session:
                from ..database.models import OHLCV
                
                symbols = session.query(OHLCV.symbol).distinct().all()
                timeframes = session.query(OHLCV.timeframe).distinct().all()
                
                # Get date ranges per symbol
                symbol_ranges = {}
                for (symbol,) in symbols:
                    min_date = session.query(OHLCV.timestamp).filter_by(symbol=symbol).order_by(OHLCV.timestamp.asc()).first()
                    max_date = session.query(OHLCV.timestamp).filter_by(symbol=symbol).order_by(OHLCV.timestamp.desc()).first()
                    
                    if min_date and max_date:
                        symbol_ranges[symbol] = {
                            'start': min_date[0],
                            'end': max_date[0],
                            'days': (max_date[0] - min_date[0]).days
                        }
            
            return {
                'total_candles': stats.get('ohlcv_count', 0),
                'symbols_count': len(symbols),
                'symbols': [s[0] for s in symbols],
                'timeframes_count': len(timeframes),
                'timeframes': [t[0] for t in timeframes],
                'symbol_ranges': symbol_ranges,
                'last_updated': datetime.utcnow()
            }
            
        except Exception as e:
            logger.error(f"Error getting data summary: {e}")
            return {}

# Global historical data manager instance
historical_manager = HistoricalDataManager()
"""

with open('crypto_trading_system/data/historical_data.py', 'w') as f:
    f.write(historical_data_content)

print("✅ Historical data manager created!")