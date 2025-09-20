# Create config.py
config_content = """\"\"\"
Main configuration module for the crypto trading system.
Loads configuration from environment variables and provides default values.
\"\"\"

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import logging

# Load environment variables
load_dotenv()

class TradingConfig(BaseModel):
    \"\"\"Trading configuration settings\"\"\"
    default_symbol: str = Field(default="BTCUSDT")
    default_timeframe: str = Field(default="1m")
    slippage_tolerance: float = Field(default=0.001)
    max_open_trades: int = Field(default=5)
    position_size: float = Field(default=0.02)

class RiskConfig(BaseModel):
    \"\"\"Risk management configuration\"\"\"
    max_position_size: float = Field(default=0.02)  # 2% of portfolio
    daily_loss_limit: float = Field(default=0.02)   # 2% daily loss limit
    weekly_loss_limit: float = Field(default=0.06)  # 6% weekly loss limit
    max_drawdown: float = Field(default=0.15)       # 15% max drawdown
    stop_loss_pct: float = Field(default=0.02)      # 2% stop loss
    take_profit_pct: float = Field(default=0.04)    # 4% take profit (2:1 R/R)

class DatabaseConfig(BaseModel):
    \"\"\"Database configuration\"\"\"
    url: str = Field(default="sqlite:///crypto_trading.db")
    echo: bool = Field(default=False)
    pool_size: int = Field(default=10)
    max_overflow: int = Field(default=20)

class MonitoringConfig(BaseModel):
    \"\"\"Monitoring and alerting configuration\"\"\"
    log_level: str = Field(default="INFO")
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    webhook_url: Optional[str] = None
    dashboard_host: str = Field(default="0.0.0.0")
    dashboard_port: int = Field(default=8501)

class Config:
    \"\"\"Main configuration class\"\"\"
    
    def __init__(self):
        self.trading = TradingConfig(
            default_symbol=os.getenv("DEFAULT_SYMBOL", "BTCUSDT"),
            default_timeframe=os.getenv("DEFAULT_TIMEFRAME", "1m"),
            slippage_tolerance=float(os.getenv("SLIPPAGE_TOLERANCE", "0.001")),
            max_open_trades=int(os.getenv("MAX_OPEN_TRADES", "5")),
            position_size=float(os.getenv("MAX_POSITION_SIZE", "0.02"))
        )
        
        self.risk = RiskConfig(
            max_position_size=float(os.getenv("MAX_POSITION_SIZE", "0.02")),
            daily_loss_limit=float(os.getenv("DAILY_LOSS_LIMIT", "0.02")),
            weekly_loss_limit=float(os.getenv("WEEKLY_LOSS_LIMIT", "0.06"))
        )
        
        self.database = DatabaseConfig(
            url=os.getenv("DATABASE_URL", "sqlite:///crypto_trading.db")
        )
        
        self.monitoring = MonitoringConfig(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
            webhook_url=os.getenv("WEBHOOK_URL"),
            dashboard_host=os.getenv("DASHBOARD_HOST", "0.0.0.0"),
            dashboard_port=int(os.getenv("DASHBOARD_PORT", "8501"))
        )
    
    def setup_logging(self) -> None:
        \"\"\"Configure logging based on settings\"\"\"
        logging.basicConfig(
            level=getattr(logging, self.monitoring.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('trading_bot.log'),
                logging.StreamHandler()
            ]
        )

# Global configuration instance
config = Config()
"""

with open('crypto_trading_system/config/config.py', 'w') as f:
    f.write(config_content)

# Create binance_config.py
binance_config_content = """\"\"\"
Binance-specific configuration and connection management.
\"\"\"

import os
from typing import Optional, Dict, Any
import ccxt
from binance.client import Client
from binance.websockets import BinanceSocketManager
import logging

logger = logging.getLogger(__name__)

class BinanceConfig:
    \"\"\"Binance API configuration and client management\"\"\"
    
    def __init__(self):
        self.api_key = os.getenv("BINANCE_API_KEY", "")
        self.secret_key = os.getenv("BINANCE_SECRET_KEY", "")
        self.testnet = os.getenv("BINANCE_TESTNET", "True").lower() == "true"
        
        if not self.api_key or not self.secret_key:
            logger.warning("Binance API credentials not found. Trading will be disabled.")
        
        self._client: Optional[Client] = None
        self._ccxt_client: Optional[ccxt.binance] = None
        self._socket_manager: Optional[BinanceSocketManager] = None
    
    @property
    def client(self) -> Client:
        \"\"\"Get Binance client instance\"\"\"
        if self._client is None:
            if not self.api_key or not self.secret_key:
                raise ValueError("Binance API credentials required")
            
            self._client = Client(
                api_key=self.api_key,
                api_secret=self.secret_key,
                testnet=self.testnet
            )
            
            # Test connection
            try:
                account_info = self._client.get_account()
                logger.info(f"Connected to Binance {'Testnet' if self.testnet else 'Mainnet'}")
                logger.info(f"Account status: {account_info.get('accountType')}")
            except Exception as e:
                logger.error(f"Failed to connect to Binance: {e}")
                raise
        
        return self._client
    
    @property
    def ccxt_client(self) -> ccxt.binance:
        \"\"\"Get CCXT Binance client for unified interface\"\"\"
        if self._ccxt_client is None:
            if not self.api_key or not self.secret_key:
                raise ValueError("Binance API credentials required")
            
            self._ccxt_client = ccxt.binance({
                'apiKey': self.api_key,
                'secret': self.secret_key,
                'sandbox': self.testnet,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'  # or 'future' for futures trading
                }
            })
            
            try:
                balance = self._ccxt_client.fetch_balance()
                logger.info("CCXT Binance client connected successfully")
            except Exception as e:
                logger.error(f"Failed to connect CCXT Binance client: {e}")
                raise
        
        return self._ccxt_client
    
    @property
    def socket_manager(self) -> BinanceSocketManager:
        \"\"\"Get WebSocket manager for real-time data\"\"\"
        if self._socket_manager is None:
            self._socket_manager = BinanceSocketManager(self.client)
        return self._socket_manager
    
    def get_exchange_info(self) -> Dict[str, Any]:
        \"\"\"Get exchange information and trading rules\"\"\"
        try:
            return self.client.get_exchange_info()
        except Exception as e:
            logger.error(f"Failed to get exchange info: {e}")
            raise
    
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        \"\"\"Get specific symbol information and filters\"\"\"
        exchange_info = self.get_exchange_info()
        for symbol_info in exchange_info['symbols']:
            if symbol_info['symbol'] == symbol:
                return symbol_info
        raise ValueError(f"Symbol {symbol} not found")
    
    def test_connectivity(self) -> bool:
        \"\"\"Test API connectivity and permissions\"\"\"
        try:
            # Test basic connectivity
            self.client.ping()
            
            # Test account access
            account = self.client.get_account()
            
            # Test market data access
            ticker = self.client.get_ticker(symbol='BTCUSDT')
            
            logger.info("All connectivity tests passed")
            return True
        except Exception as e:
            logger.error(f"Connectivity test failed: {e}")
            return False

# Global Binance configuration instance
binance_config = BinanceConfig()
"""

with open('crypto_trading_system/config/binance_config.py', 'w') as f:
    f.write(binance_config_content)

print("✅ Configuration files created!")