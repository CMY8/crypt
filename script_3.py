# Create database models
models_content = """\"\"\"
Database models for the crypto trading system.
Using SQLAlchemy ORM for data persistence.
\"\"\"

from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, 
    ForeignKey, Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
from enum import Enum
import json

Base = declarative_base()

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class OrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_LOSS = "STOP_LOSS"
    STOP_LOSS_LIMIT = "STOP_LOSS_LIMIT"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_LIMIT = "TAKE_PROFIT_LIMIT"

class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"

class OHLCV(Base):
    \"\"\"OHLCV candlestick data\"\"\"
    __tablename__ = 'ohlcv'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    
    __table_args__ = (
        UniqueConstraint('symbol', 'timeframe', 'timestamp', name='_symbol_timeframe_timestamp_uc'),
        Index('ix_ohlcv_symbol_timestamp', 'symbol', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<OHLCV({self.symbol}, {self.timeframe}, {self.timestamp}, {self.close_price})>"

class Ticker(Base):
    \"\"\"Real-time ticker data\"\"\"
    __tablename__ = 'tickers'
    
    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    price = Column(Float, nullable=False)
    bid_price = Column(Float)
    ask_price = Column(Float)
    bid_quantity = Column(Float)
    ask_quantity = Column(Float)
    volume_24h = Column(Float)
    price_change_24h = Column(Float)
    price_change_percent_24h = Column(Float)
    
    __table_args__ = (
        Index('ix_ticker_symbol_timestamp', 'symbol', 'timestamp'),
    )

class Order(Base):
    \"\"\"Trading orders\"\"\"
    __tablename__ = 'orders'
    
    id = Column(Integer, primary_key=True)
    exchange_order_id = Column(String(100), unique=True, index=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(SQLEnum(OrderSide), nullable=False)
    type = Column(SQLEnum(OrderType), nullable=False)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.NEW)
    
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    stop_price = Column(Float)
    
    filled_quantity = Column(Float, default=0.0)
    filled_value = Column(Float, default=0.0)
    avg_price = Column(Float)
    commission = Column(Float, default=0.0)
    commission_asset = Column(String(10))
    
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    executed_at = Column(DateTime)
    
    # Relationship to trades
    trades = relationship("Trade", back_populates="entry_order")
    
    __table_args__ = (
        Index('ix_orders_strategy_status', 'strategy_id', 'status'),
        Index('ix_orders_symbol_created', 'symbol', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Order({self.symbol}, {self.side.value}, {self.quantity}, {self.status.value})>"

class Trade(Base):
    \"\"\"Completed trades with entry and exit\"\"\"
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(SQLEnum(OrderSide), nullable=False)
    status = Column(SQLEnum(TradeStatus), nullable=False, default=TradeStatus.OPEN)
    
    entry_order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    exit_order_id = Column(Integer, ForeignKey('orders.id'))
    
    quantity = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float)
    
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl = Column(Float, default=0.0)
    commission = Column(Float, default=0.0)
    
    entry_time = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    exit_time = Column(DateTime)
    duration_minutes = Column(Integer)
    
    # Relationships
    entry_order = relationship("Order", foreign_keys=[entry_order_id], back_populates="trades")
    exit_order = relationship("Order", foreign_keys=[exit_order_id])
    
    __table_args__ = (
        Index('ix_trades_strategy_status', 'strategy_id', 'status'),
        Index('ix_trades_symbol_entry_time', 'symbol', 'entry_time'),
    )
    
    def __repr__(self):
        return f"<Trade({self.symbol}, {self.side.value}, {self.quantity}, {self.status.value})>"

class Portfolio(Base):
    \"\"\"Portfolio snapshots\"\"\"
    __tablename__ = 'portfolio'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    total_balance = Column(Float, nullable=False)
    available_balance = Column(Float, nullable=False)
    locked_balance = Column(Float, nullable=False)
    
    unrealized_pnl = Column(Float, default=0.0)
    realized_pnl_daily = Column(Float, default=0.0)
    realized_pnl_total = Column(Float, default=0.0)
    
    drawdown = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    
    open_trades_count = Column(Integer, default=0)
    daily_trades_count = Column(Integer, default=0)
    
    # Asset breakdown as JSON
    assets = Column(Text)  # JSON string of asset balances
    
    def get_assets(self):
        \"\"\"Parse assets JSON\"\"\"
        if self.assets:
            return json.loads(self.assets)
        return {}
    
    def set_assets(self, assets_dict):
        \"\"\"Set assets as JSON\"\"\"
        self.assets = json.dumps(assets_dict)

class Signal(Base):
    \"\"\"Trading signals generated by strategies\"\"\"
    __tablename__ = 'signals'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    signal_type = Column(String(20), nullable=False)  # BUY, SELL, HOLD
    strength = Column(Float, nullable=False)  # Signal strength 0.0 to 1.0
    confidence = Column(Float, nullable=False)  # Confidence level 0.0 to 1.0
    
    price = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # Signal metadata as JSON
    metadata = Column(Text)  # JSON string of additional signal data
    
    # Whether signal was acted upon
    executed = Column(Boolean, default=False)
    order_id = Column(Integer, ForeignKey('orders.id'))
    
    __table_args__ = (
        Index('ix_signals_strategy_timestamp', 'strategy_id', 'timestamp'),
        Index('ix_signals_symbol_timestamp', 'symbol', 'timestamp'),
    )
    
    def get_metadata(self):
        \"\"\"Parse metadata JSON\"\"\"
        if self.metadata:
            return json.loads(self.metadata)
        return {}
    
    def set_metadata(self, metadata_dict):
        \"\"\"Set metadata as JSON\"\"\"
        self.metadata = json.dumps(metadata_dict)

class PerformanceMetrics(Base):
    \"\"\"Strategy performance metrics\"\"\"
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True)
    strategy_id = Column(String(50), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    
    # Return metrics
    total_return = Column(Float, default=0.0)
    daily_return = Column(Float, default=0.0)
    weekly_return = Column(Float, default=0.0)
    monthly_return = Column(Float, default=0.0)
    
    # Risk metrics
    volatility = Column(Float, default=0.0)
    sharpe_ratio = Column(Float, default=0.0)
    sortino_ratio = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    
    # Trade metrics
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    profit_factor = Column(Float, default=0.0)
    avg_win = Column(Float, default=0.0)
    avg_loss = Column(Float, default=0.0)
    
    __table_args__ = (
        UniqueConstraint('strategy_id', 'date', name='_strategy_date_uc'),
    )

class SystemLog(Base):
    \"\"\"System logs and events\"\"\"
    __tablename__ = 'system_logs'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    level = Column(String(10), nullable=False, index=True)  # INFO, WARNING, ERROR, CRITICAL
    module = Column(String(50), nullable=False, index=True)
    message = Column(Text, nullable=False)
    
    # Additional context as JSON
    context = Column(Text)
    
    def get_context(self):
        \"\"\"Parse context JSON\"\"\"
        if self.context:
            return json.loads(self.context)
        return {}
    
    def set_context(self, context_dict):
        \"\"\"Set context as JSON\"\"\"
        self.context = json.dumps(context_dict)
"""

with open('crypto_trading_system/database/models.py', 'w') as f:
    f.write(models_content)

print("✅ Database models created!")