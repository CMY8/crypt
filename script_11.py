# Create risk management system
risk_manager_content = """\"\"\"
Risk management system for the crypto trading bot.
Implements position sizing, drawdown limits, and risk controls.
\"\"\"

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np
from enum import Enum

from ..database.db_manager import db_manager
from ..config.config import config
from ..utils.helpers import calculate_position_size, calculate_pnl, format_percentage

logger = logging.getLogger(__name__)

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass
class RiskMetrics:
    \"\"\"Current risk metrics\"\"\"
    total_exposure: float = 0.0
    daily_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    max_drawdown: float = 0.0
    current_drawdown: float = 0.0
    open_positions: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    violations: List[str] = None
    
    def __post_init__(self):
        if self.violations is None:
            self.violations = []

class RiskManager:
    \"\"\"Main risk management system\"\"\"
    
    def __init__(self):
        self.risk_config = config.risk
        self.trading_config = config.trading
        
        # Risk tracking
        self.daily_start_balance = 0.0
        self.peak_balance = 0.0
        self.current_balance = 0.0
        
        # Trade tracking
        self.daily_trades = 0
        self.open_positions = {}  # strategy_id -> positions
        self.risk_violations = []
        
        # Circuit breaker
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.circuit_breaker_time = None
        
        # Performance tracking
        self.equity_curve = []
        self.daily_returns = []
        
        self._initialize_risk_state()
    
    def _initialize_risk_state(self):
        \"\"\"Initialize risk management state\"\"\"
        try:
            # Get current portfolio state
            latest_portfolio = db_manager.get_latest_portfolio()
            if latest_portfolio:
                self.current_balance = latest_portfolio.total_balance
                self.peak_balance = max(self.peak_balance, self.current_balance)
                self.daily_start_balance = latest_portfolio.total_balance
            
            # Load open positions
            open_trades = db_manager.get_open_trades()
            for trade in open_trades:
                if trade.strategy_id not in self.open_positions:
                    self.open_positions[trade.strategy_id] = []
                self.open_positions[trade.strategy_id].append(trade)
            
            logger.info("Risk management state initialized")
            
        except Exception as e:
            logger.error(f"Error initializing risk state: {e}")
    
    def validate_order(self, strategy_id: str, symbol: str, side: str, 
                      quantity: float, price: float) -> Tuple[bool, str]:
        \"\"\"Validate if an order meets risk requirements\"\"\"
        try:
            # Check circuit breaker
            if self.circuit_breaker_active:
                return False, f"Circuit breaker active: {self.circuit_breaker_reason}"
            
            # Calculate order value
            order_value = quantity * price
            
            # Check position size limits
            if not self._validate_position_size(order_value):
                return False, f"Order exceeds position size limit ({format_percentage(self.risk_config.max_position_size)})"
            
            # Check maximum open trades
            current_positions = len(self.open_positions.get(strategy_id, []))
            if current_positions >= self.trading_config.max_open_trades:
                return False, f"Maximum open trades reached ({self.trading_config.max_open_trades})"
            
            # Check daily loss limit
            if not self._validate_daily_loss_limit():
                return False, f"Daily loss limit exceeded ({format_percentage(self.risk_config.daily_loss_limit)})"
            
            # Check symbol exposure
            if not self._validate_symbol_exposure(symbol, order_value):
                return False, f"Symbol exposure limit exceeded for {symbol}"
            
            # Check correlation limits (if multiple positions)
            if not self._validate_correlation_limits(symbol, order_value):
                return False, "Correlation limits exceeded"
            
            return True, "Order validated"
            
        except Exception as e:
            logger.error(f"Error validating order: {e}")
            return False, f"Validation error: {e}"
    
    def _validate_position_size(self, order_value: float) -> bool:
        \"\"\"Validate position size against account balance\"\"\"
        if self.current_balance <= 0:
            return False
        
        position_size_ratio = order_value / self.current_balance
        return position_size_ratio <= self.risk_config.max_position_size
    
    def _validate_daily_loss_limit(self) -> bool:
        \"\"\"Check if daily loss limit is exceeded\"\"\"
        if self.daily_start_balance <= 0:
            return True
        
        current_loss = (self.daily_start_balance - self.current_balance) / self.daily_start_balance
        return current_loss <= self.risk_config.daily_loss_limit
    
    def _validate_symbol_exposure(self, symbol: str, order_value: float) -> bool:
        \"\"\"Validate exposure to a specific symbol\"\"\"
        # Calculate current exposure to symbol
        current_exposure = 0.0
        for positions in self.open_positions.values():
            for position in positions:
                if position.symbol == symbol:
                    current_exposure += position.quantity * position.entry_price
        
        # Check if adding this order would exceed limits
        total_exposure = current_exposure + order_value
        max_symbol_exposure = self.current_balance * 0.3  # 30% max per symbol
        
        return total_exposure <= max_symbol_exposure
    
    def _validate_correlation_limits(self, symbol: str, order_value: float) -> bool:
        \"\"\"Validate correlation limits between positions\"\"\"
        # Simplified correlation check - in reality would use actual correlation data
        # For now, limit total crypto exposure to 80% of account
        
        total_crypto_exposure = 0.0
        for positions in self.open_positions.values():
            for position in positions:
                total_crypto_exposure += position.quantity * position.entry_price
        
        total_crypto_exposure += order_value
        max_crypto_exposure = self.current_balance * 0.8  # 80% max crypto
        
        return total_crypto_exposure <= max_crypto_exposure
    
    def calculate_position_size(self, strategy_id: str, symbol: str, 
                              entry_price: float, stop_loss_price: float,
                              risk_per_trade: Optional[float] = None) -> float:
        \"\"\"Calculate optimal position size based on risk parameters\"\"\"
        try:
            if risk_per_trade is None:
                risk_per_trade = self.trading_config.position_size
            
            # Calculate base position size
            base_position_size = calculate_position_size(
                account_balance=self.current_balance,
                risk_per_trade=risk_per_trade,
                entry_price=entry_price,
                stop_loss_price=stop_loss_price
            )
            
            # Apply risk adjustments
            adjusted_size = self._apply_risk_adjustments(
                base_position_size, strategy_id, symbol
            )
            
            # Apply maximum position size limit
            max_position_value = self.current_balance * self.risk_config.max_position_size
            max_quantity = max_position_value / entry_price
            
            final_size = min(adjusted_size, max_quantity)
            
            logger.debug(f"Position size calculated: {final_size} for {symbol}")
            return final_size
            
        except Exception as e:
            logger.error(f"Error calculating position size: {e}")
            return 0.0
    
    def _apply_risk_adjustments(self, base_size: float, strategy_id: str, symbol: str) -> float:
        \"\"\"Apply risk adjustments based on current conditions\"\"\"
        adjustment_factor = 1.0
        
        # Reduce size if in drawdown
        if self.current_drawdown > 0.05:  # 5% drawdown
            adjustment_factor *= 0.5
            logger.warning("Reducing position size due to drawdown")
        
        # Reduce size based on recent performance
        recent_performance = self._get_recent_strategy_performance(strategy_id)
        if recent_performance < -0.1:  # 10% loss in recent trades
            adjustment_factor *= 0.3
            logger.warning(f"Reducing position size for {strategy_id} due to poor performance")
        
        # Reduce size if volatility is high
        volatility_adjustment = self._get_volatility_adjustment(symbol)
        adjustment_factor *= volatility_adjustment
        
        return base_size * adjustment_factor
    
    def _get_recent_strategy_performance(self, strategy_id: str, days: int = 7) -> float:
        \"\"\"Get recent performance for a strategy\"\"\"
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            trades = db_manager.get_trades(
                strategy_id=strategy_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if not trades:
                return 0.0
            
            total_pnl = sum(trade.realized_pnl for trade in trades if trade.realized_pnl)
            initial_capital = sum(trade.quantity * trade.entry_price for trade in trades)
            
            if initial_capital > 0:
                return total_pnl / initial_capital
            
            return 0.0
            
        except Exception as e:
            logger.error(f"Error calculating recent performance: {e}")
            return 0.0
    
    def _get_volatility_adjustment(self, symbol: str) -> float:
        \"\"\"Get volatility-based position size adjustment\"\"\"
        try:
            # Get recent price data
            df = db_manager.get_ohlcv_data(
                symbol=symbol,
                timeframe='1h',
                start_time=datetime.utcnow() - timedelta(days=7),
                end_time=datetime.utcnow()
            )
            
            if len(df) < 24:  # Need at least 24 hours of data
                return 1.0
            
            # Calculate volatility (standard deviation of returns)
            returns = df['close'].pct_change().dropna()
            volatility = returns.std()
            
            # Adjust position size based on volatility
            if volatility > 0.05:  # High volatility (5% hourly)
                return 0.5
            elif volatility > 0.03:  # Medium volatility (3% hourly)
                return 0.7
            else:
                return 1.0
            
        except Exception as e:
            logger.error(f"Error calculating volatility adjustment: {e}")
            return 1.0
    
    def update_position(self, strategy_id: str, trade_data: Dict[str, Any]):
        \"\"\"Update position tracking when trade is executed\"\"\"
        try:
            if strategy_id not in self.open_positions:
                self.open_positions[strategy_id] = []
            
            # Add new position or update existing
            # This would be more sophisticated in practice
            self.open_positions[strategy_id].append(trade_data)
            
            # Update balance
            if 'realized_pnl' in trade_data:
                self.current_balance += trade_data['realized_pnl']
                self.peak_balance = max(self.peak_balance, self.current_balance)
            
            # Update drawdown
            self.current_drawdown = (self.peak_balance - self.current_balance) / self.peak_balance
            
            logger.debug(f"Position updated for {strategy_id}")
            
        except Exception as e:
            logger.error(f"Error updating position: {e}")
    
    def close_position(self, strategy_id: str, trade_id: int, exit_price: float):
        \"\"\"Handle position closure\"\"\"
        try:
            # Update position in open_positions
            if strategy_id in self.open_positions:
                # Remove closed position
                self.open_positions[strategy_id] = [
                    pos for pos in self.open_positions[strategy_id] 
                    if pos.get('id') != trade_id
                ]
            
            logger.debug(f"Position closed for {strategy_id}, trade {trade_id}")
            
        except Exception as e:
            logger.error(f"Error closing position: {e}")
    
    def get_risk_metrics(self) -> RiskMetrics:
        \"\"\"Get current risk metrics\"\"\"
        try:
            # Calculate total exposure
            total_exposure = 0.0
            open_positions_count = 0
            
            for positions in self.open_positions.values():
                for position in positions:
                    if hasattr(position, 'quantity') and hasattr(position, 'entry_price'):
                        total_exposure += position.quantity * position.entry_price
                        open_positions_count += 1
            
            # Calculate daily PnL
            daily_pnl = self.current_balance - self.daily_start_balance
            
            # Get unrealized PnL (simplified)
            unrealized_pnl = self._calculate_unrealized_pnl()
            
            # Determine risk level
            risk_level = self._assess_risk_level()
            
            # Get violations
            violations = self._get_current_violations()
            
            return RiskMetrics(
                total_exposure=total_exposure,
                daily_pnl=daily_pnl,
                unrealized_pnl=unrealized_pnl,
                max_drawdown=self._calculate_max_drawdown(),
                current_drawdown=self.current_drawdown,
                open_positions=open_positions_count,
                risk_level=risk_level,
                violations=violations
            )
            
        except Exception as e:
            logger.error(f"Error calculating risk metrics: {e}")
            return RiskMetrics()
    
    def _calculate_unrealized_pnl(self) -> float:
        \"\"\"Calculate unrealized PnL for open positions\"\"\"
        # This would require current market prices
        # Simplified implementation
        return 0.0
    
    def _calculate_max_drawdown(self) -> float:
        \"\"\"Calculate maximum drawdown from equity curve\"\"\"
        if not self.equity_curve:
            return 0.0
        
        equity_series = pd.Series(self.equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max
        
        return abs(drawdown.min())
    
    def _assess_risk_level(self) -> RiskLevel:
        \"\"\"Assess current risk level\"\"\"
        risk_factors = 0
        
        # Check drawdown
        if self.current_drawdown > 0.15:  # 15%
            risk_factors += 3
        elif self.current_drawdown > 0.10:  # 10%
            risk_factors += 2
        elif self.current_drawdown > 0.05:  # 5%
            risk_factors += 1
        
        # Check daily loss
        daily_loss = (self.daily_start_balance - self.current_balance) / self.daily_start_balance
        if daily_loss > 0.03:  # 3%
            risk_factors += 2
        elif daily_loss > 0.02:  # 2%
            risk_factors += 1
        
        # Check position concentration
        total_positions = sum(len(positions) for positions in self.open_positions.values())
        if total_positions > self.trading_config.max_open_trades * 0.8:
            risk_factors += 1
        
        # Determine risk level
        if risk_factors >= 5:
            return RiskLevel.CRITICAL
        elif risk_factors >= 3:
            return RiskLevel.HIGH
        elif risk_factors >= 1:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
    
    def _get_current_violations(self) -> List[str]:
        \"\"\"Get list of current risk violations\"\"\"
        violations = []
        
        # Check daily loss limit
        if not self._validate_daily_loss_limit():
            violations.append("Daily loss limit exceeded")
        
        # Check maximum drawdown
        if self.current_drawdown > self.risk_config.max_drawdown:
            violations.append("Maximum drawdown exceeded")
        
        # Check position limits
        total_positions = sum(len(positions) for positions in self.open_positions.values())
        if total_positions > self.trading_config.max_open_trades:
            violations.append("Maximum open trades exceeded")
        
        return violations
    
    def trigger_circuit_breaker(self, reason: str):
        \"\"\"Trigger circuit breaker to halt trading\"\"\"
        self.circuit_breaker_active = True
        self.circuit_breaker_reason = reason
        self.circuit_breaker_time = datetime.utcnow()
        
        logger.critical(f"CIRCUIT BREAKER ACTIVATED: {reason}")
        
        # Record in database
        db_manager.save_log(
            level="CRITICAL",
            module="RiskManager",
            message=f"Circuit breaker activated: {reason}",
            context={
                'current_balance': self.current_balance,
                'current_drawdown': self.current_drawdown,
                'daily_pnl': self.current_balance - self.daily_start_balance
            }
        )
    
    def reset_circuit_breaker(self):
        \"\"\"Reset circuit breaker (manual override)\"\"\"
        self.circuit_breaker_active = False
        self.circuit_breaker_reason = ""
        self.circuit_breaker_time = None
        
        logger.warning("Circuit breaker reset manually")
        
        db_manager.save_log(
            level="WARNING",
            module="RiskManager",
            message="Circuit breaker reset manually"
        )
    
    def check_risk_conditions(self):
        \"\"\"Check various risk conditions and trigger actions if needed\"\"\"
        try:
            # Check for critical drawdown
            if self.current_drawdown > self.risk_config.max_drawdown:
                self.trigger_circuit_breaker(f"Maximum drawdown exceeded: {format_percentage(self.current_drawdown)}")
            
            # Check daily loss limit
            daily_loss = (self.daily_start_balance - self.current_balance) / self.daily_start_balance
            if daily_loss > self.risk_config.daily_loss_limit:
                self.trigger_circuit_breaker(f"Daily loss limit exceeded: {format_percentage(daily_loss)}")
            
            # Update equity curve
            self.equity_curve.append(self.current_balance)
            
            # Keep only recent data
            if len(self.equity_curve) > 1440:  # Keep 24 hours of minute data
                self.equity_curve = self.equity_curve[-1440:]
            
        except Exception as e:
            logger.error(f"Error checking risk conditions: {e}")
    
    def get_position_limits(self, strategy_id: str) -> Dict[str, Any]:
        \"\"\"Get position limits for a strategy\"\"\"
        current_positions = len(self.open_positions.get(strategy_id, []))
        
        return {
            'max_positions': self.trading_config.max_open_trades,
            'current_positions': current_positions,
            'remaining_positions': max(0, self.trading_config.max_open_trades - current_positions),
            'max_position_size_pct': self.risk_config.max_position_size,
            'max_position_value': self.current_balance * self.risk_config.max_position_size,
            'daily_loss_limit_pct': self.risk_config.daily_loss_limit,
            'remaining_daily_risk': max(0, self.risk_config.daily_loss_limit - 
                                      ((self.daily_start_balance - self.current_balance) / self.daily_start_balance))
        }
    
    def emergency_close_all(self, reason: str = "Emergency closure"):
        \"\"\"Emergency closure of all positions\"\"\"
        logger.critical(f"EMERGENCY CLOSE ALL POSITIONS: {reason}")
        
        # Trigger circuit breaker
        self.trigger_circuit_breaker(f"Emergency closure: {reason}")
        
        # Clear open positions tracking
        self.open_positions.clear()
        
        # This would send close orders to all strategies
        # Implementation depends on strategy management system

# Global risk manager instance
risk_manager = RiskManager()
"""

with open('crypto_trading_system/risk/risk_manager.py', 'w') as f:
    f.write(risk_manager_content)

print("✅ Risk manager created!")