# Create data manager
data_manager_content = """\"\"\"
Data manager for handling market data operations.
Coordinates between real-time WebSocket data, historical data, and database storage.
\"\"\"

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading

from .websocket_client import ws_client
from .historical_data import HistoricalDataManager
from ..database.db_manager import db_manager
from ..utils.indicators import TechnicalIndicators
from ..config.config import config

logger = logging.getLogger(__name__)

class DataManager:
    \"\"\"Main data manager for market data operations\"\"\"
    
    def __init__(self):
        self.historical_manager = HistoricalDataManager()
        self.indicators = TechnicalIndicators()
        
        # Data caches for quick access
        self.price_cache: Dict[str, Dict] = {}
        self.ohlcv_cache: Dict[str, pd.DataFrame] = {}
        self.indicator_cache: Dict[str, Dict] = {}
        
        # Real-time data subscribers
        self.subscribers: Dict[str, List] = {}
        
        # Threading for data processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.data_lock = threading.RLock()
        
        # Data update frequencies
        self.cache_ttl = 300  # 5 minutes
        self.last_cache_update: Dict[str, datetime] = {}
        
        # Event handlers
        self.data_handlers = {}
        
    def start(self):
        \"\"\"Start the data manager\"\"\"
        logger.info("Starting data manager...")
        
        # Start background tasks
        asyncio.create_task(self._start_data_processing())
        asyncio.create_task(self._start_cache_maintenance())
        
        logger.info("Data manager started")
    
    async def stop(self):
        \"\"\"Stop the data manager\"\"\"
        logger.info("Stopping data manager...")
        
        # Disconnect WebSocket connections
        await ws_client.disconnect_all()
        
        # Clear caches
        with self.data_lock:
            self.price_cache.clear()
            self.ohlcv_cache.clear()
            self.indicator_cache.clear()
        
        logger.info("Data manager stopped")
    
    # Real-time data subscription
    async def subscribe_to_symbol(self, symbol: str, timeframes: List[str] = None) -> bool:
        \"\"\"Subscribe to real-time data for a symbol\"\"\"
        try:
            if timeframes is None:
                timeframes = ['1m', '5m', '1h']
            
            # Subscribe to ticker
            await ws_client.subscribe_ticker(symbol)
            
            # Subscribe to klines for different timeframes
            symbol_intervals = [(symbol, tf) for tf in timeframes]
            await ws_client.subscribe_multiple_klines(symbol_intervals)
            
            # Add callbacks for processing
            for tf in timeframes:
                stream = f"{symbol.lower()}@kline_{tf}"
                ws_client.add_callback(stream, self._handle_kline_data)
            
            ticker_stream = f"{symbol.lower()}@ticker"
            ws_client.add_callback(ticker_stream, self._handle_ticker_data)
            
            logger.info(f"Subscribed to real-time data for {symbol}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {symbol}: {e}")
            return False
    
    async def unsubscribe_from_symbol(self, symbol: str):
        \"\"\"Unsubscribe from real-time data for a symbol\"\"\"
        # Implementation for unsubscribing
        # Remove from WebSocket streams
        pass
    
    async def _handle_ticker_data(self, data: Dict[str, Any]):
        \"\"\"Handle incoming ticker data\"\"\"
        try:
            symbol = data['s']
            price_data = {
                'symbol': symbol,
                'price': float(data['c']),
                'bid': float(data['b']),
                'ask': float(data['a']),
                'volume_24h': float(data['v']),
                'change_24h': float(data['p']),
                'change_percent_24h': float(data['P']),
                'timestamp': datetime.fromtimestamp(data['E'] / 1000)
            }
            
            # Update price cache
            with self.data_lock:
                self.price_cache[symbol] = price_data
            
            # Notify subscribers
            await self._notify_subscribers('ticker', symbol, price_data)
            
        except Exception as e:
            logger.error(f"Error handling ticker data: {e}")
    
    async def _handle_kline_data(self, data: Dict[str, Any]):
        \"\"\"Handle incoming kline/candlestick data\"\"\"
        try:
            kline = data['k']
            symbol = kline['s']
            timeframe = kline['i']
            
            if kline['x']:  # Only process closed candles
                candle_data = {
                    'timestamp': datetime.fromtimestamp(kline['t'] / 1000),
                    'open': float(kline['o']),
                    'high': float(kline['h']),
                    'low': float(kline['l']),
                    'close': float(kline['c']),
                    'volume': float(kline['v'])
                }
                
                # Update OHLCV cache
                await self._update_ohlcv_cache(symbol, timeframe, candle_data)
                
                # Notify subscribers
                await self._notify_subscribers('kline', symbol, {
                    'timeframe': timeframe,
                    'data': candle_data
                })
            
        except Exception as e:
            logger.error(f"Error handling kline data: {e}")
    
    async def _update_ohlcv_cache(self, symbol: str, timeframe: str, candle_data: Dict):
        \"\"\"Update OHLCV cache with new candle data\"\"\"
        cache_key = f"{symbol}_{timeframe}"
        
        with self.data_lock:
            if cache_key not in self.ohlcv_cache:
                # Load recent data from database
                end_time = datetime.utcnow()
                start_time = end_time - timedelta(days=7)  # Last 7 days
                
                df = db_manager.get_ohlcv_data(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_time=start_time,
                    end_time=end_time
                )
                
                self.ohlcv_cache[cache_key] = df
            
            # Add new candle
            df = self.ohlcv_cache[cache_key]
            new_row = pd.DataFrame([candle_data], index=[candle_data['timestamp']])
            
            # Remove if exists and append
            df = df[df.index != candle_data['timestamp']]
            df = pd.concat([df, new_row]).sort_index()
            
            # Keep only recent data in cache (last 1000 candles)
            if len(df) > 1000:
                df = df.tail(1000)
            
            self.ohlcv_cache[cache_key] = df
            
            # Update indicators cache
            await self._update_indicators_cache(symbol, timeframe, df)
    
    async def _update_indicators_cache(self, symbol: str, timeframe: str, df: pd.DataFrame):
        \"\"\"Update technical indicators cache\"\"\"
        try:
            cache_key = f"{symbol}_{timeframe}"
            
            if len(df) < 50:  # Need minimum data for indicators
                return
            
            indicators = {}
            
            # Calculate common indicators
            indicators['sma_20'] = self.indicators.sma(df['close'], 20)
            indicators['sma_50'] = self.indicators.sma(df['close'], 50)
            indicators['ema_20'] = self.indicators.ema(df['close'], 20)
            indicators['rsi'] = self.indicators.rsi(df['close'])
            indicators['macd'] = self.indicators.macd(df['close'])
            indicators['bb'] = self.indicators.bollinger_bands(df['close'])
            indicators['atr'] = self.indicators.atr(df['high'], df['low'], df['close'])
            
            # Volume indicators if volume available
            if 'volume' in df.columns:
                indicators['volume_sma'] = self.indicators.sma(df['volume'], 20)
            
            self.indicator_cache[cache_key] = indicators
            
        except Exception as e:
            logger.error(f"Error updating indicators cache for {symbol}_{timeframe}: {e}")
    
    # Data retrieval methods
    def get_current_price(self, symbol: str) -> Optional[float]:
        \"\"\"Get current price for a symbol\"\"\"
        with self.data_lock:
            price_data = self.price_cache.get(symbol)
            if price_data:
                return price_data['price']
            return None
    
    def get_ticker_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        \"\"\"Get latest ticker data for a symbol\"\"\"
        with self.data_lock:
            return self.price_cache.get(symbol)
    
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        \"\"\"Get OHLCV data for a symbol and timeframe\"\"\"
        cache_key = f"{symbol}_{timeframe}"
        
        with self.data_lock:
            if cache_key in self.ohlcv_cache:
                df = self.ohlcv_cache[cache_key]
                return df.tail(limit) if limit else df
        
        # If not in cache, load from database
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=30)  # Last 30 days
        
        df = db_manager.get_ohlcv_data(
            symbol=symbol,
            timeframe=timeframe,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Cache the data
        with self.data_lock:
            self.ohlcv_cache[cache_key] = df
        
        return df
    
    def get_historical_data(self, symbol: str, timeframe: str, 
                          start_date: datetime, end_date: datetime) -> pd.DataFrame:
        \"\"\"Get historical data for backtesting\"\"\"
        return self.historical_manager.get_historical_data(
            symbol, timeframe, start_date, end_date
        )
    
    def get_indicators(self, symbol: str, timeframe: str) -> Optional[Dict[str, Any]]:
        \"\"\"Get technical indicators for a symbol and timeframe\"\"\"
        cache_key = f"{symbol}_{timeframe}"
        
        with self.data_lock:
            return self.indicator_cache.get(cache_key)
    
    # Data downloading and updating
    async def download_historical_data(self, symbol: str, timeframes: List[str], 
                                     days_back: int = 365) -> bool:
        \"\"\"Download historical data for a symbol\"\"\"
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days_back)
            
            success = await self.historical_manager.download_data(
                symbol=symbol,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date
            )
            
            if success:
                logger.info(f"Downloaded historical data for {symbol}")
                
                # Refresh cache
                for timeframe in timeframes:
                    cache_key = f"{symbol}_{timeframe}"
                    if cache_key in self.ohlcv_cache:
                        del self.ohlcv_cache[cache_key]
            
            return success
            
        except Exception as e:
            logger.error(f"Error downloading historical data for {symbol}: {e}")
            return False
    
    async def update_all_data(self):
        \"\"\"Update all subscribed symbols with latest data\"\"\"
        symbols = list(set([
            key.split('_')[0] for key in self.ohlcv_cache.keys()
        ]))
        
        for symbol in symbols:
            try:
                await self.download_historical_data(symbol, ['1m', '5m', '1h'], days_back=7)
            except Exception as e:
                logger.error(f"Error updating data for {symbol}: {e}")
    
    # Event subscription and notification
    def subscribe(self, event_type: str, callback):
        \"\"\"Subscribe to data events\"\"\"
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback):
        \"\"\"Unsubscribe from data events\"\"\"
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
    
    async def _notify_subscribers(self, event_type: str, symbol: str, data: Any):
        \"\"\"Notify subscribers of data events\"\"\"
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(symbol, data)
                    else:
                        callback(symbol, data)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
    
    # Background tasks
    async def _start_data_processing(self):
        \"\"\"Start background data processing task\"\"\"
        while True:
            try:
                # Process WebSocket data queue
                data = ws_client.get_data(timeout=0.1)
                if data:
                    stream, message = data
                    # Additional processing can be done here
                
                await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
                
            except Exception as e:
                logger.error(f"Error in data processing task: {e}")
                await asyncio.sleep(1)
    
    async def _start_cache_maintenance(self):
        \"\"\"Start cache maintenance task\"\"\"
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                current_time = datetime.utcnow()
                
                # Clean old cache entries
                with self.data_lock:
                    expired_keys = []
                    for key, last_update in self.last_cache_update.items():
                        if (current_time - last_update).seconds > self.cache_ttl:
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        if key in self.ohlcv_cache:
                            del self.ohlcv_cache[key]
                        if key in self.indicator_cache:
                            del self.indicator_cache[key]
                        del self.last_cache_update[key]
                
                if expired_keys:
                    logger.debug(f"Cleaned {len(expired_keys)} expired cache entries")
                
            except Exception as e:
                logger.error(f"Error in cache maintenance task: {e}")
    
    def get_market_summary(self) -> Dict[str, Any]:
        \"\"\"Get market summary for all tracked symbols\"\"\"
        summary = {
            'symbols_count': len(self.price_cache),
            'cached_timeframes': len(self.ohlcv_cache),
            'indicators_cached': len(self.indicator_cache),
            'last_update': datetime.utcnow(),
            'symbols': {}
        }
        
        with self.data_lock:
            for symbol, data in self.price_cache.items():
                summary['symbols'][symbol] = {
                    'price': data['price'],
                    'change_24h': data.get('change_percent_24h', 0),
                    'volume_24h': data.get('volume_24h', 0),
                    'last_update': data['timestamp']
                }
        
        return summary

# Global data manager instance
data_manager = DataManager()
"""

with open('crypto_trading_system/data/data_manager.py', 'w') as f:
    f.write(data_manager_content)

print("✅ Data manager created!")