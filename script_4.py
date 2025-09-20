# Create database manager
db_manager_content = """\"\"\"
Database manager for the crypto trading system.
Handles database connections, sessions, and basic CRUD operations.
\"\"\"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator, List, Optional, Dict, Any
import logging
from datetime import datetime, timedelta
import pandas as pd

from .models import Base, OHLCV, Ticker, Order, Trade, Portfolio, Signal, PerformanceMetrics, SystemLog
from ..config.config import config

logger = logging.getLogger(__name__)

class DatabaseManager:
    \"\"\"Database manager for SQLAlchemy operations\"\"\"
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or config.database.url
        
        # Configure engine based on database type
        if self.database_url.startswith('sqlite'):
            self.engine = create_engine(
                self.database_url,
                echo=config.database.echo,
                poolclass=StaticPool,
                connect_args={"check_same_thread": False}
            )
        else:
            self.engine = create_engine(
                self.database_url,
                echo=config.database.echo,
                pool_size=config.database.pool_size,
                max_overflow=config.database.max_overflow
            )
        
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        
        # Enable WAL mode for SQLite for better performance
        if self.database_url.startswith('sqlite'):
            @event.listens_for(self.engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=10000")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.close()
    
    def create_tables(self):
        \"\"\"Create all database tables\"\"\"
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create database tables: {e}")
            raise
    
    def drop_tables(self):
        \"\"\"Drop all database tables\"\"\"
        try:
            Base.metadata.drop_all(bind=self.engine)
            logger.info("Database tables dropped successfully")
        except Exception as e:
            logger.error(f"Failed to drop database tables: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        \"\"\"Get database session with automatic cleanup\"\"\"
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # OHLCV Data Operations
    def save_ohlcv_data(self, symbol: str, timeframe: str, data: List[Dict[str, Any]]) -> None:
        \"\"\"Save OHLCV data to database\"\"\"
        with self.get_session() as session:
            for candle in data:
                existing = session.query(OHLCV).filter_by(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=candle['timestamp']
                ).first()
                
                if not existing:
                    ohlcv = OHLCV(
                        symbol=symbol,
                        timeframe=timeframe,
                        timestamp=candle['timestamp'],
                        open_price=candle['open'],
                        high_price=candle['high'],
                        low_price=candle['low'],
                        close_price=candle['close'],
                        volume=candle['volume']
                    )
                    session.add(ohlcv)
            
            logger.debug(f"Saved {len(data)} OHLCV records for {symbol} {timeframe}")
    
    def get_ohlcv_data(self, symbol: str, timeframe: str, 
                      start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None,
                      limit: Optional[int] = None) -> pd.DataFrame:
        \"\"\"Get OHLCV data as pandas DataFrame\"\"\"
        with self.get_session() as session:
            query = session.query(OHLCV).filter_by(symbol=symbol, timeframe=timeframe)
            
            if start_time:
                query = query.filter(OHLCV.timestamp >= start_time)
            if end_time:
                query = query.filter(OHLCV.timestamp <= end_time)
            
            query = query.order_by(OHLCV.timestamp.asc())
            
            if limit:
                query = query.limit(limit)
            
            results = query.all()
            
            if not results:
                return pd.DataFrame()
            
            data = []
            for r in results:
                data.append({
                    'timestamp': r.timestamp,
                    'open': r.open_price,
                    'high': r.high_price,
                    'low': r.low_price,
                    'close': r.close_price,
                    'volume': r.volume
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            return df
    
    def get_latest_ohlcv(self, symbol: str, timeframe: str) -> Optional[OHLCV]:
        \"\"\"Get the latest OHLCV record for a symbol\"\"\"
        with self.get_session() as session:
            return session.query(OHLCV).filter_by(
                symbol=symbol, timeframe=timeframe
            ).order_by(OHLCV.timestamp.desc()).first()
    
    # Ticker Operations
    def save_ticker(self, ticker_data: Dict[str, Any]) -> None:
        \"\"\"Save ticker data\"\"\"
        with self.get_session() as session:
            ticker = Ticker(**ticker_data)
            session.add(ticker)
    
    def get_latest_ticker(self, symbol: str) -> Optional[Ticker]:
        \"\"\"Get latest ticker for symbol\"\"\"
        with self.get_session() as session:
            return session.query(Ticker).filter_by(symbol=symbol).order_by(
                Ticker.timestamp.desc()
            ).first()
    
    # Order Operations
    def save_order(self, order_data: Dict[str, Any]) -> Order:
        \"\"\"Save order to database\"\"\"
        with self.get_session() as session:
            order = Order(**order_data)
            session.add(order)
            session.flush()  # Get the ID
            session.refresh(order)
            return order
    
    def update_order(self, order_id: int, updates: Dict[str, Any]) -> None:
        \"\"\"Update order status and details\"\"\"
        with self.get_session() as session:
            session.query(Order).filter_by(id=order_id).update(updates)
    
    def get_order(self, order_id: int) -> Optional[Order]:
        \"\"\"Get order by ID\"\"\"
        with self.get_session() as session:
            return session.query(Order).filter_by(id=order_id).first()
    
    def get_orders(self, strategy_id: Optional[str] = None, 
                   symbol: Optional[str] = None,
                   status: Optional[str] = None,
                   limit: Optional[int] = None) -> List[Order]:
        \"\"\"Get orders with filters\"\"\"
        with self.get_session() as session:
            query = session.query(Order)
            
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)
            if symbol:
                query = query.filter_by(symbol=symbol)
            if status:
                query = query.filter_by(status=status)
            
            query = query.order_by(Order.created_at.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    def get_open_orders(self, strategy_id: Optional[str] = None) -> List[Order]:
        \"\"\"Get all open orders\"\"\"
        from .models import OrderStatus
        with self.get_session() as session:
            query = session.query(Order).filter(
                Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED])
            )
            
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)
            
            return query.all()
    
    # Trade Operations
    def save_trade(self, trade_data: Dict[str, Any]) -> Trade:
        \"\"\"Save trade to database\"\"\"
        with self.get_session() as session:
            trade = Trade(**trade_data)
            session.add(trade)
            session.flush()
            session.refresh(trade)
            return trade
    
    def update_trade(self, trade_id: int, updates: Dict[str, Any]) -> None:
        \"\"\"Update trade details\"\"\"
        with self.get_session() as session:
            session.query(Trade).filter_by(id=trade_id).update(updates)
    
    def get_open_trades(self, strategy_id: Optional[str] = None) -> List[Trade]:
        \"\"\"Get all open trades\"\"\"
        from .models import TradeStatus
        with self.get_session() as session:
            query = session.query(Trade).filter_by(status=TradeStatus.OPEN)
            
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)
            
            return query.all()
    
    def get_trades(self, strategy_id: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   limit: Optional[int] = None) -> List[Trade]:
        \"\"\"Get trades with filters\"\"\"
        with self.get_session() as session:
            query = session.query(Trade)
            
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)
            if start_date:
                query = query.filter(Trade.entry_time >= start_date)
            if end_date:
                query = query.filter(Trade.entry_time <= end_date)
            
            query = query.order_by(Trade.entry_time.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    # Portfolio Operations
    def save_portfolio_snapshot(self, portfolio_data: Dict[str, Any]) -> None:
        \"\"\"Save portfolio snapshot\"\"\"
        with self.get_session() as session:
            portfolio = Portfolio(**portfolio_data)
            session.add(portfolio)
    
    def get_latest_portfolio(self) -> Optional[Portfolio]:
        \"\"\"Get latest portfolio snapshot\"\"\"
        with self.get_session() as session:
            return session.query(Portfolio).order_by(Portfolio.timestamp.desc()).first()
    
    def get_portfolio_history(self, days: int = 30) -> List[Portfolio]:
        \"\"\"Get portfolio history\"\"\"
        start_date = datetime.utcnow() - timedelta(days=days)
        with self.get_session() as session:
            return session.query(Portfolio).filter(
                Portfolio.timestamp >= start_date
            ).order_by(Portfolio.timestamp.asc()).all()
    
    # Signal Operations
    def save_signal(self, signal_data: Dict[str, Any]) -> Signal:
        \"\"\"Save trading signal\"\"\"
        with self.get_session() as session:
            signal = Signal(**signal_data)
            session.add(signal)
            session.flush()
            session.refresh(signal)
            return signal
    
    def get_signals(self, strategy_id: Optional[str] = None,
                   symbol: Optional[str] = None,
                   start_date: Optional[datetime] = None,
                   limit: Optional[int] = None) -> List[Signal]:
        \"\"\"Get signals with filters\"\"\"
        with self.get_session() as session:
            query = session.query(Signal)
            
            if strategy_id:
                query = query.filter_by(strategy_id=strategy_id)
            if symbol:
                query = query.filter_by(symbol=symbol)
            if start_date:
                query = query.filter(Signal.timestamp >= start_date)
            
            query = query.order_by(Signal.timestamp.desc())
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    # Performance Metrics Operations
    def save_performance_metrics(self, metrics_data: Dict[str, Any]) -> None:
        \"\"\"Save performance metrics\"\"\"
        with self.get_session() as session:
            # Check if metrics already exist for this strategy and date
            existing = session.query(PerformanceMetrics).filter_by(
                strategy_id=metrics_data['strategy_id'],
                date=metrics_data['date']
            ).first()
            
            if existing:
                # Update existing record
                for key, value in metrics_data.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                # Create new record
                metrics = PerformanceMetrics(**metrics_data)
                session.add(metrics)
    
    def get_performance_metrics(self, strategy_id: str, 
                               start_date: Optional[datetime] = None,
                               end_date: Optional[datetime] = None) -> List[PerformanceMetrics]:
        \"\"\"Get performance metrics\"\"\"
        with self.get_session() as session:
            query = session.query(PerformanceMetrics).filter_by(strategy_id=strategy_id)
            
            if start_date:
                query = query.filter(PerformanceMetrics.date >= start_date)
            if end_date:
                query = query.filter(PerformanceMetrics.date <= end_date)
            
            return query.order_by(PerformanceMetrics.date.asc()).all()
    
    # Logging Operations
    def save_log(self, level: str, module: str, message: str, context: Optional[Dict] = None) -> None:
        \"\"\"Save system log\"\"\"
        try:
            with self.get_session() as session:
                log_entry = SystemLog(
                    level=level,
                    module=module,
                    message=message
                )
                if context:
                    log_entry.set_context(context)
                session.add(log_entry)
        except Exception as e:
            # Don't raise exceptions for logging failures
            logger.error(f"Failed to save log to database: {e}")
    
    def get_logs(self, level: Optional[str] = None,
                module: Optional[str] = None,
                start_date: Optional[datetime] = None,
                limit: int = 1000) -> List[SystemLog]:
        \"\"\"Get system logs\"\"\"
        with self.get_session() as session:
            query = session.query(SystemLog)
            
            if level:
                query = query.filter_by(level=level)
            if module:
                query = query.filter_by(module=module)
            if start_date:
                query = query.filter(SystemLog.timestamp >= start_date)
            
            return query.order_by(SystemLog.timestamp.desc()).limit(limit).all()
    
    # Utility Methods
    def cleanup_old_data(self, days_to_keep: int = 90) -> None:
        \"\"\"Clean up old data to manage database size\"\"\"
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        
        with self.get_session() as session:
            # Clean up old tickers (keep only last 7 days)
            ticker_cutoff = datetime.utcnow() - timedelta(days=7)
            deleted_tickers = session.query(Ticker).filter(
                Ticker.timestamp < ticker_cutoff
            ).delete()
            
            # Clean up old logs
            deleted_logs = session.query(SystemLog).filter(
                SystemLog.timestamp < cutoff_date
            ).delete()
            
            logger.info(f"Cleaned up {deleted_tickers} old tickers and {deleted_logs} old logs")
    
    def get_database_stats(self) -> Dict[str, Any]:
        \"\"\"Get database statistics\"\"\"
        stats = {}
        
        with self.get_session() as session:
            stats['ohlcv_count'] = session.query(OHLCV).count()
            stats['orders_count'] = session.query(Order).count()
            stats['trades_count'] = session.query(Trade).count()
            stats['signals_count'] = session.query(Signal).count()
            stats['portfolio_snapshots'] = session.query(Portfolio).count()
            stats['logs_count'] = session.query(SystemLog).count()
            
            # Get open positions
            from .models import TradeStatus, OrderStatus
            stats['open_trades'] = session.query(Trade).filter_by(status=TradeStatus.OPEN).count()
            stats['open_orders'] = session.query(Order).filter(
                Order.status.in_([OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED])
            ).count()
        
        return stats

# Global database manager instance
db_manager = DatabaseManager()
"""

with open('crypto_trading_system/database/db_manager.py', 'w') as f:
    f.write(db_manager_content)

print("✅ Database manager created!")