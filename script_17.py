# Check current directory and create the main file
import os
print("Current directory:", os.getcwd())
print("Files in crypto_trading_system:", os.listdir('crypto_trading_system'))

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

def main():
    \"\"\"Main entry point\"\"\"
    parser = argparse.ArgumentParser(description='Crypto Trading System')
    parser.add_argument('command', choices=[
        'live', 'paper', 'backtest', 'dashboard', 'download', 'status'
    ], help='Command to run')
    
    args = parser.parse_args()
    
    try:
        if args.command == 'live':
            print("Live trading mode - would start live trading")
        elif args.command == 'paper':
            print("Paper trading mode - would start paper trading")
        elif args.command == 'dashboard':
            print("Dashboard mode - would launch web dashboard")
        else:
            print(f"Command {args.command} not fully implemented yet")
    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
"""

# Write the main file
with open('crypto_trading_system/main.py', 'w') as f:
    f.write(main_content)

print("✅ Main entry point created!")