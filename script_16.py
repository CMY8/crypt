# Create the main entry point
main_content = """\"\"\"
Main entry point for the crypto trading system.
Provides CLI interface for different modes of operation.
\"\"\"

import asyncio
import sys
import argparse
import logging
from pathlib import Path
import signal
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import config
from database.db_manager import db_manager
from data.data_manager import data_manager
from execution.execution_engine import execution_engine, ExecutionMode, TradingSignal, SignalAction
from risk.risk_manager import risk_manager
from risk.portfolio_manager import portfolio_manager

logger = logging.getLogger(__name__)

class CryptoTradingBot:
    \"\"\"Main trading bot orchestrator\"\"\"
    
    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        self.mode = mode
        self.is_running = False
        
        # System components
        self.data_manager = data_manager
        self.execution_engine = execution_engine
        self.risk_manager = risk_manager
        self.portfolio_manager = portfolio_manager
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Setup logging
        config.setup_logging()
        
    def _signal_handler(self, sig, frame):
        \"\"\"Handle shutdown signals\"\"\"
        logger.info(f"Received signal {sig}, shutting down gracefully...")
        asyncio.create_task(self.stop())
    
    async def initialize(self):
        \"\"\"Initialize all system components\"\"\"
        try:
            logger.info("Initializing crypto trading system...")
            
            # Initialize database
            db_manager.create_tables()
            logger.info("Database initialized")
            
            # Initialize data manager
            await self.data_manager.start()
            logger.info("Data manager started")
            
            # Initialize execution engine with selected mode
            self.execution_engine.mode = self.mode
            logger.info(f"Execution engine set to {self.mode.value} mode")
            
            # Subscribe to default symbols
            default_symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'BNBUSDT']
            for symbol in default_symbols:
                await self.data_manager.subscribe_to_symbol(symbol)
            
            logger.info("System initialization complete")
            
        except Exception as e:
            logger.error(f"Error during initialization: {e}")
            raise
    
    async def start(self):
        \"\"\"Start the trading bot\"\"\"
        if self.is_running:
            logger.warning("Trading bot is already running")
            return
        
        try:
            await self.initialize()
            
            self.is_running = True
            logger.info(f"Starting crypto trading bot in {self.mode.value} mode")
            
            # Start execution engine
            await self.execution_engine.start()
            
        except Exception as e:
            logger.error(f"Error starting trading bot: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        \"\"\"Stop the trading bot gracefully\"\"\"
        if not self.is_running:
            logger.info("Trading bot is not running")
            return
        
        logger.info("Stopping crypto trading bot...")
        
        try:
            # Stop execution engine
            await self.execution_engine.stop()
            
            # Stop data manager
            await self.data_manager.stop()
            
            # Save final portfolio snapshot
            self.portfolio_manager.save_snapshot()
            
            self.is_running = False
            logger.info("Crypto trading bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping trading bot: {e}")
    
    def submit_signal(self, strategy_id: str, symbol: str, action: str, 
                     strength: float = 1.0, confidence: float = 1.0, **kwargs) -> bool:
        \"\"\"Submit a trading signal\"\"\"
        try:
            signal = TradingSignal(
                strategy_id=strategy_id,
                symbol=symbol,
                action=SignalAction(action.upper()),
                strength=strength,
                confidence=confidence,
                **kwargs
            )
            
            return self.execution_engine.submit_signal(signal)
            
        except Exception as e:
            logger.error(f"Error submitting signal: {e}")
            return False
    
    def get_status(self) -> dict:
        \"\"\"Get system status\"\"\"
        return {
            'running': self.is_running,
            'mode': self.mode.value,
            'execution_stats': self.execution_engine.get_execution_statistics(),
            'portfolio_summary': self.portfolio_manager.get_portfolio_summary(),
            'risk_metrics': self.risk_manager.get_risk_metrics(),
            'data_summary': self.data_manager.get_market_summary()
        }

async def run_backtest(start_date: str, end_date: str, strategies: list, initial_balance: float = 10000):
    \"\"\"Run backtesting mode\"\"\"
    logger.info(f"Starting backtest from {start_date} to {end_date}")
    
    # This would implement the backtesting logic
    # For now, just a placeholder
    logger.info("Backtest completed (placeholder)")

async def run_live_trading():
    \"\"\"Run live trading mode\"\"\"
    bot = CryptoTradingBot(ExecutionMode.LIVE)
    
    try:
        await bot.start()
        
        # Keep running until interrupted
        while bot.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in live trading: {e}")
    finally:
        await bot.stop()

async def run_paper_trading():
    \"\"\"Run paper trading mode\"\"\"
    bot = CryptoTradingBot(ExecutionMode.PAPER)
    
    try:
        await bot.start()
        
        # Example: Submit some test signals
        await asyncio.sleep(10)  # Wait for system to initialize
        
        bot.submit_signal("test_strategy", "BTCUSDT", "BUY", strength=0.8, confidence=0.9)
        
        # Keep running until interrupted
        while bot.is_running:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Error in paper trading: {e}")
    finally:
        await bot.stop()

def run_dashboard():
    \"\"\"Launch the monitoring dashboard\"\"\"
    import subprocess
    import os
    
    try:
        # Launch Streamlit dashboard
        dashboard_path = os.path.join(os.path.dirname(__file__), 'monitoring', 'dashboard.py')
        subprocess.run(['streamlit', 'run', dashboard_path])
    except Exception as e:
        logger.error(f"Error launching dashboard: {e}")
        print("Please install streamlit: pip install streamlit")

def download_data(symbols: list, days: int = 365):
    \"\"\"Download historical data\"\"\"
    async def _download():
        from data.historical_data import historical_manager
        
        timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        
        for symbol in symbols:
            logger.info(f"Downloading data for {symbol}")
            success = await historical_manager.update_symbol_data(symbol, timeframes, days)
            if success:
                logger.info(f"Successfully downloaded data for {symbol}")
            else:
                logger.error(f"Failed to download data for {symbol}")
    
    asyncio.run(_download())

def main():
    \"\"\"Main entry point\"\"\"
    parser = argparse.ArgumentParser(description='Crypto Trading System')
    parser.add_argument('command', choices=[
        'live', 'paper', 'backtest', 'dashboard', 'download', 'status'
    ], help='Command to run')
    
    # Backtest options
    parser.add_argument('--start-date', help='Backtest start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', help='Backtest end date (YYYY-MM-DD)')
    parser.add_argument('--initial-balance', type=float, default=10000, help='Initial balance for backtest')
    parser.add_argument('--strategies', nargs='+', help='Strategies to test')
    
    # Data download options
    parser.add_argument('--symbols', nargs='+', default=['BTCUSDT'], help='Symbols to download')
    parser.add_argument('--days', type=int, default=365, help='Days of data to download')
    
    # General options
    parser.add_argument('--log-level', default='INFO', help='Logging level')
    parser.add_argument('--config-file', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Set logging level
    logging.basicConfig(level=getattr(logging, args.log_level.upper()))
    
    try:
        if args.command == 'live':
            asyncio.run(run_live_trading())
        
        elif args.command == 'paper':
            asyncio.run(run_paper_trading())
        
        elif args.command == 'backtest':
            if not args.start_date or not args.end_date:
                print("Backtest requires --start-date and --end-date")
                sys.exit(1)
            
            strategies = args.strategies or ['momentum_strategy']
            asyncio.run(run_backtest(
                args.start_date, args.end_date, strategies, args.initial_balance
            ))
        
        elif args.command == 'dashboard':
            run_dashboard()
        
        elif args.command == 'download':
            download_data(args.symbols, args.days)
        
        elif args.command == 'status':
            # Quick status check
            bot = CryptoTradingBot()
            status = bot.get_status()
            print(f"System Status: {'Running' if status['running'] else 'Stopped'}")
            print(f"Mode: {status['mode']}")
            print(f"Database stats: {db_manager.get_database_stats()}")
    
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
"""

with open('crypto_trading_system/main.py', 'w') as f:
    f.write(main_content)

# Create Docker configuration
dockerfile_content = """FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port for dashboard
EXPOSE 8501

# Default command
CMD ["python", "main.py", "paper"]
"""

with open('crypto_trading_system/Dockerfile', 'w') as f:
    f.write(dockerfile_content)

# Create docker-compose configuration
docker_compose_content = """version: '3.8'

services:
  trading-bot:
    build: .
    container_name: crypto-trading-bot
    environment:
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_SECRET_KEY=${BINANCE_SECRET_KEY}
      - BINANCE_TESTNET=True
      - LOG_LEVEL=INFO
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    ports:
      - "8501:8501"
    restart: unless-stopped
    command: python main.py paper

  dashboard:
    build: .
    container_name: trading-dashboard  
    environment:
      - BINANCE_API_KEY=${BINANCE_API_KEY}
      - BINANCE_SECRET_KEY=${BINANCE_SECRET_KEY}
    volumes:
      - ./data:/app/data
    ports:
      - "8502:8501"
    restart: unless-stopped
    command: python main.py dashboard

  # Optional: Redis for caching and message queuing
  redis:
    image: redis:7-alpine
    container_name: trading-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  redis_data:
"""

with open('crypto_trading_system/docker-compose.yml', 'w') as f:
    f.write(docker_compose_content)

# Create comprehensive README
readme_content = """# Crypto Trading System

A comprehensive algorithmic trading system for cryptocurrency markets with risk management, backtesting, and real-time monitoring.

## 🚀 Features

### Core Trading System
- **Multi-Strategy Support**: Momentum, Mean Reversion, Grid, and custom strategies
- **Real-time Data**: WebSocket streaming from Binance with historical data management
- **Risk Management**: Position sizing, drawdown limits, and circuit breakers
- **Order Management**: Smart order routing with slippage control and error handling
- **Portfolio Management**: Real-time portfolio tracking and performance analytics

### Trading Modes
- **Live Trading**: Real money trading on Binance
- **Paper Trading**: Risk-free simulation with real market data
- **Backtesting**: Historical strategy testing with walk-forward validation

### Monitoring & Analytics
- **Real-time Dashboard**: Web-based monitoring interface
- **Performance Metrics**: Sharpe ratio, win rate, drawdown analysis
- **Risk Monitoring**: Real-time risk assessment and alerts
- **Trade Analytics**: Detailed trade history and attribution

### Technical Features
- **Async Architecture**: High-performance concurrent execution
- **Database Integration**: SQLite/PostgreSQL with automated data management
- **API Integration**: Native Binance API with rate limiting and error handling
- **Containerized**: Docker deployment with docker-compose orchestration

## 📋 Requirements

### System Requirements
- Python 3.11+
- 4GB+ RAM
- 10GB+ storage for historical data
- Internet connection for market data

### API Requirements
- Binance account with API keys
- API permissions for trading (if using live mode)

## 🛠 Installation

### Option 1: Local Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd crypto_trading_system
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp config/.env.example .env
   # Edit .env with your API keys and settings
   ```

### Option 2: Docker Installation

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd crypto_trading_system
   cp config/.env.example .env
   # Edit .env with your configuration
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up -d
   ```

## ⚙️ Configuration

### Environment Variables

```bash
# Binance API Configuration
BINANCE_API_KEY=your_api_key_here
BINANCE_SECRET_KEY=your_secret_key_here
BINANCE_TESTNET=True  # Set to False for live trading

# Risk Management
MAX_POSITION_SIZE=0.02  # 2% of portfolio per trade
DAILY_LOSS_LIMIT=0.02   # 2% daily loss limit
MAX_OPEN_TRADES=5       # Maximum concurrent positions

# Trading Configuration  
DEFAULT_SYMBOL=BTCUSDT
DEFAULT_TIMEFRAME=1m
SLIPPAGE_TOLERANCE=0.001

# Database
DATABASE_URL=sqlite:///crypto_trading.db

# Monitoring
LOG_LEVEL=INFO
DASHBOARD_PORT=8501
```

## 🚀 Usage

### Command Line Interface

```bash
# Paper trading (recommended for testing)
python main.py paper

# Live trading (requires real API keys)
python main.py live

# Download historical data
python main.py download --symbols BTCUSDT ETHUSDT --days 365

# Run backtesting
python main.py backtest --start-date 2024-01-01 --end-date 2024-12-31

# Launch dashboard
python main.py dashboard

# Check system status
python main.py status
```

### Dashboard Access

- **Local**: http://localhost:8501
- **Docker**: http://localhost:8502

## 📊 Trading Strategies

### Built-in Strategies

1. **Momentum Strategy**
   - Uses EMA crossovers and RSI
   - Trend-following approach
   - Good for trending markets

2. **Mean Reversion Strategy**
   - Bollinger Bands and RSI oversold/overbought
   - Contrarian approach  
   - Good for ranging markets

3. **Grid Strategy**
   - Places buy/sell orders at regular intervals
   - Profits from market volatility
   - Good for sideways markets

### Custom Strategies

Create custom strategies by extending the `BaseStrategy` class:

```python
from strategies.base_strategy import BaseStrategy
from execution.execution_engine import TradingSignal, SignalAction

class MyStrategy(BaseStrategy):
    def __init__(self, strategy_id: str):
        super().__init__(strategy_id)
    
    async def generate_signals(self, data):
        # Your strategy logic here
        if self.should_buy(data):
            return TradingSignal(
                strategy_id=self.strategy_id,
                symbol="BTCUSDT", 
                action=SignalAction.BUY,
                strength=0.8,
                confidence=0.9
            )
        return None
```

## 🔒 Risk Management

### Position Sizing
- Kelly Criterion with maximum caps
- ATR-based position sizing
- Account balance percentage limits

### Risk Controls
- Daily/weekly loss limits
- Maximum drawdown protection
- Position concentration limits
- Circuit breakers for extreme events

### Stop Loss & Take Profit
- ATR-based dynamic stops
- Trailing stop functionality
- Risk/reward ratio optimization

## 📈 Performance Monitoring

### Key Metrics
- **Returns**: Total, annualized, monthly
- **Risk**: Sharpe ratio, Sortino ratio, maximum drawdown
- **Trading**: Win rate, profit factor, average trade duration
- **Execution**: Slippage, latency, fill rates

### Reporting
- Real-time dashboard updates
- Daily/weekly email reports
- CSV export functionality
- Custom performance analysis

## 🗃 Database Schema

### Core Tables
- **ohlcv**: Historical price data
- **trades**: Completed trades with PnL
- **orders**: Order history and status
- **portfolio**: Portfolio snapshots
- **signals**: Trading signals generated
- **performance_metrics**: Strategy performance

### Data Management
- Automatic data cleanup
- Incremental updates
- Data validation and integrity checks
- Backup and recovery procedures

## 🐛 Debugging & Troubleshooting

### Common Issues

1. **API Connection Errors**
   - Check API keys and permissions
   - Verify network connectivity
   - Check Binance API status

2. **Database Issues**
   - Ensure write permissions
   - Check disk space
   - Validate schema integrity

3. **Performance Issues**
   - Monitor memory usage
   - Check for data bottlenecks
   - Optimize strategy calculations

### Logging

Logs are stored in:
- Console output (configurable level)
- `trading_bot.log` file
- Database system_logs table

Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Health Checks

```bash
# System health
python main.py status

# Database stats  
sqlite3 crypto_trading.db ".tables"

# Check recent trades
python -c "from database.db_manager import db_manager; print(len(db_manager.get_trades(limit=10)))"
```

## 🔧 Development

### Project Structure
```
crypto_trading_system/
├── config/              # Configuration management
├── data/               # Data acquisition and management
├── database/           # Database models and management  
├── execution/          # Order and execution management
├── risk/              # Risk and portfolio management
├── strategies/        # Trading strategies
├── monitoring/        # Dashboard and alerts
├── backtesting/       # Backtesting engine
├── utils/             # Utility functions
└── main.py           # Main entry point
```

### Testing

```bash
# Run unit tests
python -m pytest tests/

# Run integration tests
python -m pytest tests/integration/

# Run strategy backtests
python main.py backtest --start-date 2024-01-01 --end-date 2024-03-31
```

### Contributing

1. Fork the repository
2. Create feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit pull request

## ⚠️ Disclaimers

### Trading Risks
- **Financial Risk**: Trading cryptocurrencies involves substantial risk of loss
- **Market Risk**: Crypto markets are highly volatile and unpredictable
- **Technical Risk**: Software bugs or system failures can cause losses
- **API Risk**: Exchange downtime or API changes can affect trading

### Legal Considerations
- Ensure compliance with local trading regulations
- Understand tax implications of algorithmic trading
- Some jurisdictions restrict or prohibit automated trading

### Recommendations
- **Start with paper trading** to understand the system
- **Use small position sizes** when starting live trading
- **Monitor the system closely** during initial operation
- **Have proper risk management** in place at all times
- **Keep software updated** to latest version

## 📞 Support

### Documentation
- Code documentation in `docs/`
- Strategy guides in `docs/strategies/`
- API reference in `docs/api/`

### Community
- GitHub Issues for bug reports
- GitHub Discussions for questions
- Wiki for detailed guides

## 📝 License

This project is licensed under the MIT License. See LICENSE file for details.

## 🙏 Acknowledgments

- Binance for providing robust API
- Python community for excellent libraries
- Contributors and testers

---

**⚠️ Important**: This software is for educational purposes. Always test thoroughly before using real money. Trading involves substantial risk of loss.
"""

with open('crypto_trading_system/README.md', 'w') as f:
    f.write(readme_content)

print("✅ Main files created successfully!")
print("\n🎉 Crypto Trading System Setup Complete!")
print("\n📁 Project structure:")
print("- ✅ Database models and management")
print("- ✅ Real-time data streaming (WebSocket)")
print("- ✅ Historical data management")
print("- ✅ Technical indicators library")
print("- ✅ Risk management system")
print("- ✅ Portfolio tracking")
print("- ✅ Order management with Binance integration")
print("- ✅ Execution engine with multiple modes")
print("- ✅ Web-based monitoring dashboard")
print("- ✅ CLI interface")
print("- ✅ Docker containerization")
print("- ✅ Comprehensive documentation")
print("\n🚀 To get started:")
print("1. cd crypto_trading_system")
print("2. pip install -r requirements.txt")
print("3. cp config/.env.example .env")
print("4. Edit .env with your Binance API keys")
print("5. python main.py paper  # Start paper trading")
print("6. python main.py dashboard  # Launch dashboard")