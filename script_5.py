# Create websocket client for real-time data
websocket_client_content = """\"\"\"
WebSocket client for real-time market data from Binance.
Handles connection management, reconnection, and data streaming.
\"\"\"

import asyncio
import json
import logging
from typing import Dict, List, Callable, Optional, Any
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosedError, WebSocketException
import threading
import time
from queue import Queue, Empty
import aiohttp

from ..config.binance_config import binance_config
from ..database.db_manager import db_manager

logger = logging.getLogger(__name__)

class BinanceWebSocketClient:
    \"\"\"Binance WebSocket client for real-time data\"\"\"
    
    def __init__(self):
        self.base_url = "wss://stream.binance.com:9443/ws/"
        self.testnet_url = "wss://testnet.binance.vision/ws/"
        
        self.connections: Dict[str, websockets.WebSocketServerProtocol] = {}
        self.callbacks: Dict[str, List[Callable]] = {}
        self.reconnect_intervals = [1, 2, 5, 10, 30, 60]  # Progressive backoff
        self.max_reconnect_attempts = 6
        
        self.is_running = False
        self.data_queue = Queue()
        
        # Connection health tracking
        self.last_message_time = {}
        self.ping_interval = 30  # seconds
        
        # Message rate limiting
        self.message_counts = {}
        self.rate_limit_window = 60  # 1 minute
        
    async def connect(self, stream: str) -> bool:
        \"\"\"Connect to a specific stream\"\"\"
        url = (self.testnet_url if binance_config.testnet else self.base_url) + stream
        
        attempts = 0
        while attempts < self.max_reconnect_attempts:
            try:
                logger.info(f"Connecting to stream: {stream} (attempt {attempts + 1})")
                
                websocket = await websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                )
                
                self.connections[stream] = websocket
                self.last_message_time[stream] = time.time()
                
                logger.info(f"Connected to stream: {stream}")
                return True
                
            except Exception as e:
                attempts += 1
                wait_time = self.reconnect_intervals[min(attempts - 1, len(self.reconnect_intervals) - 1)]
                
                logger.error(f"Failed to connect to {stream} (attempt {attempts}): {e}")
                
                if attempts < self.max_reconnect_attempts:
                    logger.info(f"Retrying in {wait_time} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max reconnection attempts reached for {stream}")
                    return False
        
        return False
    
    async def disconnect(self, stream: str):
        \"\"\"Disconnect from a specific stream\"\"\"
        if stream in self.connections:
            try:
                await self.connections[stream].close()
                del self.connections[stream]
                logger.info(f"Disconnected from stream: {stream}")
            except Exception as e:
                logger.error(f"Error disconnecting from {stream}: {e}")
    
    async def disconnect_all(self):
        \"\"\"Disconnect from all streams\"\"\"
        self.is_running = False
        
        for stream in list(self.connections.keys()):
            await self.disconnect(stream)
        
        logger.info("Disconnected from all streams")
    
    def add_callback(self, stream: str, callback: Callable):
        \"\"\"Add callback for stream data\"\"\"
        if stream not in self.callbacks:
            self.callbacks[stream] = []
        self.callbacks[stream].append(callback)
    
    def remove_callback(self, stream: str, callback: Callable):
        \"\"\"Remove callback for stream\"\"\"
        if stream in self.callbacks and callback in self.callbacks[stream]:
            self.callbacks[stream].remove(callback)
    
    async def listen_to_stream(self, stream: str):
        \"\"\"Listen to a specific stream and handle messages\"\"\"
        while self.is_running:
            if stream not in self.connections:
                if not await self.connect(stream):
                    break
            
            try:
                websocket = self.connections[stream]
                async for message in websocket:
                    if not self.is_running:
                        break
                    
                    await self._handle_message(stream, message)
                    
            except ConnectionClosedError as e:
                logger.warning(f"Connection closed for {stream}: {e}")
                if stream in self.connections:
                    del self.connections[stream]
                
                if self.is_running:
                    logger.info(f"Attempting to reconnect to {stream}")
                    await asyncio.sleep(1)
            
            except WebSocketException as e:
                logger.error(f"WebSocket error for {stream}: {e}")
                if stream in self.connections:
                    del self.connections[stream]
                
                if self.is_running:
                    await asyncio.sleep(5)
            
            except Exception as e:
                logger.error(f"Unexpected error for {stream}: {e}")
                await asyncio.sleep(10)
    
    async def _handle_message(self, stream: str, message: str):
        \"\"\"Handle incoming WebSocket message\"\"\"
        try:
            data = json.loads(message)
            self.last_message_time[stream] = time.time()
            
            # Rate limiting check
            current_time = time.time()
            if stream not in self.message_counts:
                self.message_counts[stream] = []
            
            # Clean old messages
            self.message_counts[stream] = [
                t for t in self.message_counts[stream]
                if current_time - t < self.rate_limit_window
            ]
            
            self.message_counts[stream].append(current_time)
            
            # Check rate limit (max 1000 messages per minute per stream)
            if len(self.message_counts[stream]) > 1000:
                logger.warning(f"Rate limit exceeded for stream {stream}")
                return
            
            # Process different message types
            if 'e' in data:  # Event message
                await self._process_event_message(stream, data)
            
            # Call registered callbacks
            if stream in self.callbacks:
                for callback in self.callbacks[stream]:
                    try:
                        await callback(data)
                    except Exception as e:
                        logger.error(f"Callback error for {stream}: {e}")
            
            # Queue data for processing
            self.data_queue.put((stream, data))
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse message from {stream}: {e}")
        except Exception as e:
            logger.error(f"Error handling message from {stream}: {e}")
    
    async def _process_event_message(self, stream: str, data: Dict[str, Any]):
        \"\"\"Process specific event types\"\"\"
        event_type = data.get('e')
        
        if event_type == '24hrTicker':
            await self._handle_ticker_message(data)
        elif event_type == 'kline':
            await self._handle_kline_message(data)
        elif event_type == 'depthUpdate':
            await self._handle_depth_message(data)
        elif event_type == 'trade':
            await self._handle_trade_message(data)
    
    async def _handle_ticker_message(self, data: Dict[str, Any]):
        \"\"\"Handle 24hr ticker message\"\"\"
        try:
            ticker_data = {
                'symbol': data['s'],
                'timestamp': datetime.fromtimestamp(data['E'] / 1000),
                'price': float(data['c']),
                'bid_price': float(data['b']),
                'ask_price': float(data['a']),
                'bid_quantity': float(data['B']),
                'ask_quantity': float(data['A']),
                'volume_24h': float(data['v']),
                'price_change_24h': float(data['p']),
                'price_change_percent_24h': float(data['P'])
            }
            
            # Save to database (non-blocking)
            asyncio.create_task(self._save_ticker_async(ticker_data))
            
        except (KeyError, ValueError) as e:
            logger.error(f"Error processing ticker message: {e}")
    
    async def _handle_kline_message(self, data: Dict[str, Any]):
        \"\"\"Handle kline/candlestick message\"\"\"
        try:
            kline = data['k']
            if kline['x']:  # Only process closed candles
                ohlcv_data = {
                    'symbol': kline['s'],
                    'timeframe': self._convert_interval(kline['i']),
                    'timestamp': datetime.fromtimestamp(kline['t'] / 1000),
                    'open': float(kline['o']),
                    'high': float(kline['h']),
                    'low': float(kline['l']),
                    'close': float(kline['c']),
                    'volume': float(kline['v'])
                }
                
                # Save to database (non-blocking)
                asyncio.create_task(self._save_ohlcv_async(ohlcv_data))
                
        except (KeyError, ValueError) as e:
            logger.error(f"Error processing kline message: {e}")
    
    async def _handle_depth_message(self, data: Dict[str, Any]):
        \"\"\"Handle order book depth message\"\"\"
        # Order book updates - can be implemented for advanced strategies
        pass
    
    async def _handle_trade_message(self, data: Dict[str, Any]):
        \"\"\"Handle individual trade message\"\"\"
        # Individual trades - can be used for volume analysis
        pass
    
    async def _save_ticker_async(self, ticker_data: Dict[str, Any]):
        \"\"\"Save ticker data asynchronously\"\"\"
        try:
            db_manager.save_ticker(ticker_data)
        except Exception as e:
            logger.error(f"Error saving ticker data: {e}")
    
    async def _save_ohlcv_async(self, ohlcv_data: Dict[str, Any]):
        \"\"\"Save OHLCV data asynchronously\"\"\"
        try:
            db_manager.save_ohlcv_data(
                ohlcv_data['symbol'],
                ohlcv_data['timeframe'],
                [ohlcv_data]
            )
        except Exception as e:
            logger.error(f"Error saving OHLCV data: {e}")
    
    def _convert_interval(self, binance_interval: str) -> str:
        \"\"\"Convert Binance interval to standard format\"\"\"
        interval_map = {
            '1m': '1m', '3m': '3m', '5m': '5m', '15m': '15m', '30m': '30m',
            '1h': '1h', '2h': '2h', '4h': '4h', '6h': '6h', '8h': '8h', '12h': '12h',
            '1d': '1d', '3d': '3d', '1w': '1w', '1M': '1M'
        }
        return interval_map.get(binance_interval, binance_interval)
    
    # High-level subscription methods
    async def subscribe_ticker(self, symbol: str):
        \"\"\"Subscribe to 24hr ticker for a symbol\"\"\"
        stream = f"{symbol.lower()}@ticker"
        if not self.is_running:
            self.is_running = True
        
        task = asyncio.create_task(self.listen_to_stream(stream))
        return task
    
    async def subscribe_kline(self, symbol: str, interval: str):
        \"\"\"Subscribe to kline/candlestick data for a symbol\"\"\"
        stream = f"{symbol.lower()}@kline_{interval}"
        if not self.is_running:
            self.is_running = True
        
        task = asyncio.create_task(self.listen_to_stream(stream))
        return task
    
    async def subscribe_multiple_tickers(self, symbols: List[str]):
        \"\"\"Subscribe to multiple ticker streams\"\"\"
        streams = [f"{symbol.lower()}@ticker" for symbol in symbols]
        combined_stream = "/".join(streams)
        
        if not self.is_running:
            self.is_running = True
        
        task = asyncio.create_task(self.listen_to_stream(combined_stream))
        return task
    
    async def subscribe_multiple_klines(self, symbol_intervals: List[tuple]):
        \"\"\"Subscribe to multiple kline streams\"\"\"
        streams = [f"{symbol.lower()}@kline_{interval}" for symbol, interval in symbol_intervals]
        combined_stream = "/".join(streams)
        
        if not self.is_running:
            self.is_running = True
        
        task = asyncio.create_task(self.listen_to_stream(combined_stream))
        return task
    
    def get_data(self, timeout: float = 1.0) -> Optional[tuple]:
        \"\"\"Get data from queue (for synchronous code)\"\"\"
        try:
            return self.data_queue.get(timeout=timeout)
        except Empty:
            return None
    
    async def health_check(self):
        \"\"\"Check connection health and reconnect if needed\"\"\"
        current_time = time.time()
        
        for stream in list(self.connections.keys()):
            last_message = self.last_message_time.get(stream, 0)
            
            if current_time - last_message > 60:  # No message for 1 minute
                logger.warning(f"No messages received from {stream} for 60 seconds")
                
                # Try to reconnect
                await self.disconnect(stream)
                await asyncio.sleep(1)
                await self.connect(stream)
    
    async def start_health_monitor(self):
        \"\"\"Start health monitoring task\"\"\"
        while self.is_running:
            await self.health_check()
            await asyncio.sleep(self.ping_interval)

# Global WebSocket client instance
ws_client = BinanceWebSocketClient()
"""

with open('crypto_trading_system/data/websocket_client.py', 'w') as f:
    f.write(websocket_client_content)

print("✅ WebSocket client created!")