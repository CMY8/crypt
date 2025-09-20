# Create requirements.txt with all necessary dependencies
requirements_content = """# Core dependencies
ccxt==4.4.22
pandas==2.1.4
numpy==1.24.3
python-binance==1.0.19
websocket-client==1.6.4
requests==2.31.0
python-dotenv==1.0.0

# Technical analysis
ta-lib==0.4.29
pandas-ta==0.3.14b0

# Database
sqlite3
sqlalchemy==2.0.23
alembic==1.13.1

# Async programming
asyncio
aiohttp==3.9.1
aiofiles==23.2.0

# Machine learning (optional)
scikit-learn==1.3.2
scipy==1.11.4

# Visualization and monitoring
matplotlib==3.8.2
plotly==5.17.0
streamlit==1.29.0
flask==3.0.0
flask-cors==4.0.0

# Backtesting
backtrader==1.9.78.123

# Logging and monitoring
structlog==23.2.0
prometheus-client==0.19.0

# Testing
pytest==7.4.3
pytest-asyncio==0.21.1

# Utilities
click==8.1.7
pydantic==2.5.1
schedule==1.2.0
"""

with open('crypto_trading_system/requirements.txt', 'w') as f:
    f.write(requirements_content)

# Create .env.example
env_example = """# Binance API Configuration
BINANCE_API_KEY=your_binance_api_key_here
BINANCE_SECRET_KEY=your_binance_secret_key_here
BINANCE_TESTNET=True

# Database Configuration
DATABASE_URL=sqlite:///crypto_trading.db
REDIS_URL=redis://localhost:6379/0

# Risk Management
MAX_POSITION_SIZE=0.02
DAILY_LOSS_LIMIT=0.02
MAX_OPEN_TRADES=5

# Trading Configuration
DEFAULT_SYMBOL=BTCUSDT
DEFAULT_TIMEFRAME=1m
SLIPPAGE_TOLERANCE=0.001

# Monitoring and Alerts
LOG_LEVEL=INFO
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
WEBHOOK_URL=https://hooks.slack.com/your/webhook/url

# Dashboard Configuration
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8501
"""

with open('crypto_trading_system/config/.env.example', 'w') as f:
    f.write(env_example)

print("✅ Requirements and environment configuration created!")