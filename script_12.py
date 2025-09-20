# Create portfolio manager
portfolio_manager_content = """\"\"\"
Portfolio management system for tracking balances, positions, and performance.
\"\"\"

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np
from collections import defaultdict

from ..database.db_manager import db_manager
from ..config.binance_config import binance_config
from ..utils.helpers import calculate_pnl, format_currency, format_percentage
from ..utils.indicators import calculate_returns, calculate_sharpe_ratio, calculate_max_drawdown

logger = logging.getLogger(__name__)

@dataclass
class AssetBalance:
    \"\"\"Asset balance information\"\"\"
    asset: str
    free: float
    locked: float
    total: float
    usd_value: float
    percentage: float

@dataclass
class PortfolioSnapshot:
    \"\"\"Portfolio snapshot at a point in time\"\"\"
    timestamp: datetime
    total_value: float
    available_balance: float
    locked_balance: float
    unrealized_pnl: float
    realized_pnl_daily: float
    realized_pnl_total: float
    drawdown: float
    asset_balances: List[AssetBalance]
    open_positions: int

class PortfolioManager:
    \"\"\"Portfolio management and tracking system\"\"\"
    
    def __init__(self):
        self.current_balances = {}
        self.price_cache = {}
        self.performance_cache = {}
        self.last_update = None
        
        # Performance tracking
        self.equity_curve = []
        self.daily_snapshots = []
        self.benchmark_data = []
        
        # Risk metrics
        self.peak_balance = 0.0
        self.daily_start_balance = 0.0
        
        self._initialize_portfolio()
    
    def _initialize_portfolio(self):
        \"\"\"Initialize portfolio state from database and exchange\"\"\"
        try:
            # Load latest portfolio snapshot from database
            latest_snapshot = db_manager.get_latest_portfolio()
            if latest_snapshot:
                self.peak_balance = latest_snapshot.total_balance
                self.daily_start_balance = latest_snapshot.total_balance
                logger.info("Portfolio state loaded from database")
            
            # Update with live data
            self.update_balances()
            
        except Exception as e:
            logger.error(f"Error initializing portfolio: {e}")
    
    def update_balances(self) -> bool:
        \"\"\"Update account balances from exchange\"\"\"
        try:
            client = binance_config.client
            account_info = client.get_account()
            
            # Update balances
            self.current_balances.clear()
            total_value_usd = 0.0
            
            for balance in account_info['balances']:
                asset = balance['asset']
                free = float(balance['free'])
                locked = float(balance['locked'])
                total = free + locked
                
                if total > 0:
                    # Get USD value
                    usd_value = self._get_asset_usd_value(asset, total)
                    total_value_usd += usd_value
                    
                    self.current_balances[asset] = {
                        'free': free,
                        'locked': locked,
                        'total': total,
                        'usd_value': usd_value
                    }
            
            # Calculate percentages
            for asset, balance in self.current_balances.items():
                if total_value_usd > 0:
                    balance['percentage'] = balance['usd_value'] / total_value_usd
                else:
                    balance['percentage'] = 0.0
            
            self.last_update = datetime.utcnow()
            logger.debug(f"Balances updated. Total value: {format_currency(total_value_usd)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating balances: {e}")
            return False
    
    def _get_asset_usd_value(self, asset: str, amount: float) -> float:
        \"\"\"Get USD value of an asset amount\"\"\"
        if asset == 'USDT' or asset == 'USD':
            return amount
        
        try:
            # Get current price from cache or exchange
            if asset in self.price_cache:
                price_data = self.price_cache[asset]
                # Check if price is recent (within 5 minutes)
                if (datetime.utcnow() - price_data['timestamp']).seconds < 300:
                    return amount * price_data['price']
            
            # Get fresh price
            symbol = f"{asset}USDT"
            client = binance_config.client
            
            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                price = float(ticker['price'])
                
                # Cache the price
                self.price_cache[asset] = {
                    'price': price,
                    'timestamp': datetime.utcnow()
                }
                
                return amount * price
                
            except Exception:
                # If direct USDT pair doesn't exist, try BTC conversion
                if asset != 'BTC':
                    try:
                        btc_symbol = f"{asset}BTC"
                        btc_ticker = client.get_symbol_ticker(symbol=btc_symbol)
                        btc_price = float(btc_ticker['price'])
                        
                        # Get BTC/USDT price
                        btc_usdt_ticker = client.get_symbol_ticker(symbol="BTCUSDT")
                        btc_usdt_price = float(btc_usdt_ticker['price'])
                        
                        usd_price = btc_price * btc_usdt_price
                        
                        # Cache the price
                        self.price_cache[asset] = {
                            'price': usd_price,
                            'timestamp': datetime.utcnow()
                        }
                        
                        return amount * usd_price
                        
                    except Exception:
                        logger.warning(f"Could not get price for {asset}")
                        return 0.0
                
                return 0.0
                
        except Exception as e:
            logger.error(f"Error getting USD value for {asset}: {e}")
            return 0.0
    
    def get_total_balance(self) -> float:
        \"\"\"Get total portfolio value in USD\"\"\"
        return sum(balance['usd_value'] for balance in self.current_balances.values())
    
    def get_available_balance(self) -> float:
        \"\"\"Get available (free) balance in USD\"\"\"
        total_free = 0.0
        for asset, balance in self.current_balances.items():
            if balance['free'] > 0:
                usd_value = self._get_asset_usd_value(asset, balance['free'])
                total_free += usd_value
        return total_free
    
    def get_locked_balance(self) -> float:
        \"\"\"Get locked balance in USD\"\"\"
        total_locked = 0.0
        for asset, balance in self.current_balances.items():
            if balance['locked'] > 0:
                usd_value = self._get_asset_usd_value(asset, balance['locked'])
                total_locked += usd_value
        return total_locked
    
    def get_asset_balance(self, asset: str) -> Optional[AssetBalance]:
        \"\"\"Get balance for a specific asset\"\"\"
        if asset in self.current_balances:
            balance_data = self.current_balances[asset]
            return AssetBalance(
                asset=asset,
                free=balance_data['free'],
                locked=balance_data['locked'],
                total=balance_data['total'],
                usd_value=balance_data['usd_value'],
                percentage=balance_data['percentage']
            )
        return None
    
    def get_all_balances(self) -> List[AssetBalance]:
        \"\"\"Get all asset balances\"\"\"
        balances = []
        for asset, balance_data in self.current_balances.items():
            balances.append(AssetBalance(
                asset=asset,
                free=balance_data['free'],
                locked=balance_data['locked'],
                total=balance_data['total'],
                usd_value=balance_data['usd_value'],
                percentage=balance_data['percentage']
            ))
        
        # Sort by USD value descending
        return sorted(balances, key=lambda x: x.usd_value, reverse=True)
    
    def calculate_unrealized_pnl(self) -> float:
        \"\"\"Calculate unrealized PnL from open positions\"\"\"
        try:
            open_trades = db_manager.get_open_trades()
            total_unrealized = 0.0
            
            for trade in open_trades:
                # Get current price
                current_price = self._get_current_price(trade.symbol)
                if current_price:
                    # Calculate unrealized PnL
                    unrealized = calculate_pnl(
                        entry_price=trade.entry_price,
                        exit_price=current_price,
                        quantity=trade.quantity,
                        side=trade.side.value
                    )
                    total_unrealized += unrealized
            
            return total_unrealized
            
        except Exception as e:
            logger.error(f"Error calculating unrealized PnL: {e}")
            return 0.0
    
    def _get_current_price(self, symbol: str) -> Optional[float]:
        \"\"\"Get current market price for a symbol\"\"\"
        try:
            client = binance_config.client
            ticker = client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    def calculate_daily_pnl(self) -> float:
        \"\"\"Calculate daily realized PnL\"\"\"
        try:
            today = datetime.utcnow().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            trades = db_manager.get_trades(start_date=start_of_day)
            daily_pnl = sum(trade.realized_pnl for trade in trades if trade.realized_pnl)
            
            return daily_pnl
            
        except Exception as e:
            logger.error(f"Error calculating daily PnL: {e}")
            return 0.0
    
    def calculate_total_pnl(self) -> float:
        \"\"\"Calculate total realized PnL\"\"\"
        try:
            trades = db_manager.get_trades()
            total_pnl = sum(trade.realized_pnl for trade in trades if trade.realized_pnl)
            
            return total_pnl
            
        except Exception as e:
            logger.error(f"Error calculating total PnL: {e}")
            return 0.0
    
    def get_current_drawdown(self) -> float:
        \"\"\"Calculate current drawdown from peak\"\"\"
        current_balance = self.get_total_balance()
        self.peak_balance = max(self.peak_balance, current_balance)
        
        if self.peak_balance > 0:
            return (self.peak_balance - current_balance) / self.peak_balance
        return 0.0
    
    def create_snapshot(self) -> PortfolioSnapshot:
        \"\"\"Create a portfolio snapshot\"\"\"
        # Update balances first
        self.update_balances()
        
        total_value = self.get_total_balance()
        available = self.get_available_balance()
        locked = self.get_locked_balance()
        unrealized_pnl = self.calculate_unrealized_pnl()
        daily_pnl = self.calculate_daily_pnl()
        total_pnl = self.calculate_total_pnl()
        drawdown = self.get_current_drawdown()
        asset_balances = self.get_all_balances()
        
        # Count open positions
        open_positions = len(db_manager.get_open_trades())
        
        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_value=total_value,
            available_balance=available,
            locked_balance=locked,
            unrealized_pnl=unrealized_pnl,
            realized_pnl_daily=daily_pnl,
            realized_pnl_total=total_pnl,
            drawdown=drawdown,
            asset_balances=asset_balances,
            open_positions=open_positions
        )
        
        return snapshot
    
    def save_snapshot(self) -> bool:
        \"\"\"Save current portfolio snapshot to database\"\"\"
        try:
            snapshot = self.create_snapshot()
            
            # Prepare asset balances as JSON
            assets_dict = {
                balance.asset: {
                    'free': balance.free,
                    'locked': balance.locked,
                    'total': balance.total,
                    'usd_value': balance.usd_value,
                    'percentage': balance.percentage
                }
                for balance in snapshot.asset_balances
            }
            
            portfolio_data = {
                'timestamp': snapshot.timestamp,
                'total_balance': snapshot.total_value,
                'available_balance': snapshot.available_balance,
                'locked_balance': snapshot.locked_balance,
                'unrealized_pnl': snapshot.unrealized_pnl,
                'realized_pnl_daily': snapshot.realized_pnl_daily,
                'realized_pnl_total': snapshot.realized_pnl_total,
                'drawdown': snapshot.drawdown,
                'max_drawdown': max(self.get_current_drawdown(), 
                                   getattr(db_manager.get_latest_portfolio(), 'max_drawdown', 0.0)),
                'open_trades_count': snapshot.open_positions,
                'daily_trades_count': self._count_daily_trades(),
                'assets': assets_dict
            }
            
            db_manager.save_portfolio_snapshot(portfolio_data)
            
            # Update equity curve
            self.equity_curve.append({
                'timestamp': snapshot.timestamp,
                'balance': snapshot.total_value
            })
            
            # Keep only recent data (last 30 days)
            cutoff_time = datetime.utcnow() - timedelta(days=30)
            self.equity_curve = [
                point for point in self.equity_curve 
                if point['timestamp'] > cutoff_time
            ]
            
            logger.debug("Portfolio snapshot saved")
            return True
            
        except Exception as e:
            logger.error(f"Error saving portfolio snapshot: {e}")
            return False
    
    def _count_daily_trades(self) -> int:
        \"\"\"Count trades executed today\"\"\"
        try:
            today = datetime.utcnow().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            trades = db_manager.get_trades(start_date=start_of_day)
            return len(trades)
            
        except Exception as e:
            logger.error(f"Error counting daily trades: {e}")
            return 0
    
    def get_performance_metrics(self, days: int = 30) -> Dict[str, Any]:
        \"\"\"Calculate portfolio performance metrics\"\"\"
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get historical snapshots
            snapshots = db_manager.get_portfolio_history(days=days)
            
            if len(snapshots) < 2:
                return {}
            
            # Create DataFrame from snapshots
            data = []
            for snapshot in snapshots:
                data.append({
                    'timestamp': snapshot.timestamp,
                    'balance': snapshot.total_balance,
                    'pnl': snapshot.realized_pnl_total + snapshot.unrealized_pnl
                })
            
            df = pd.DataFrame(data)
            df.set_index('timestamp', inplace=True)
            df = df.sort_index()
            
            # Calculate returns
            returns = calculate_returns(df['balance'])
            
            # Calculate metrics
            total_return = (df['balance'].iloc[-1] / df['balance'].iloc[0]) - 1
            annualized_return = (1 + total_return) ** (365 / days) - 1
            volatility = returns.std() * np.sqrt(365)  # Annualized volatility
            sharpe_ratio = calculate_sharpe_ratio(returns)
            max_drawdown = calculate_max_drawdown(df['balance'])
            
            # Win rate and other trade metrics
            trades = db_manager.get_trades(start_date=start_date, end_date=end_date)
            winning_trades = [t for t in trades if t.realized_pnl and t.realized_pnl > 0]
            losing_trades = [t for t in trades if t.realized_pnl and t.realized_pnl < 0]
            
            win_rate = len(winning_trades) / len(trades) if trades else 0
            avg_win = np.mean([t.realized_pnl for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t.realized_pnl for t in losing_trades]) if losing_trades else 0
            profit_factor = abs(sum(t.realized_pnl for t in winning_trades) / 
                               sum(t.realized_pnl for t in losing_trades)) if losing_trades else 0
            
            return {
                'period_days': days,
                'total_return': total_return,
                'annualized_return': annualized_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': abs(max_drawdown),
                'current_drawdown': self.get_current_drawdown(),
                'total_trades': len(trades),
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'profit_factor': profit_factor,
                'start_balance': df['balance'].iloc[0],
                'end_balance': df['balance'].iloc[-1],
                'peak_balance': df['balance'].max(),
                'total_pnl': df['balance'].iloc[-1] - df['balance'].iloc[0]
            }
            
        except Exception as e:
            logger.error(f"Error calculating performance metrics: {e}")
            return {}
    
    def get_asset_allocation(self) -> Dict[str, float]:
        \"\"\"Get current asset allocation percentages\"\"\"
        allocation = {}
        total_value = self.get_total_balance()
        
        if total_value > 0:
            for asset, balance in self.current_balances.items():
                allocation[asset] = balance['percentage']
        
        return allocation
    
    def get_portfolio_summary(self) -> Dict[str, Any]:
        \"\"\"Get comprehensive portfolio summary\"\"\"
        snapshot = self.create_snapshot()
        performance_30d = self.get_performance_metrics(30)
        
        return {
            'timestamp': snapshot.timestamp,
            'total_value': snapshot.total_value,
            'available_balance': snapshot.available_balance,
            'locked_balance': snapshot.locked_balance,
            'unrealized_pnl': snapshot.unrealized_pnl,
            'realized_pnl_daily': snapshot.realized_pnl_daily,
            'realized_pnl_total': snapshot.realized_pnl_total,
            'current_drawdown': snapshot.drawdown,
            'open_positions': snapshot.open_positions,
            'asset_count': len(snapshot.asset_balances),
            'top_assets': [
                {'asset': b.asset, 'value': b.usd_value, 'percentage': b.percentage}
                for b in snapshot.asset_balances[:5]
            ],
            'performance_30d': performance_30d,
            'last_update': self.last_update
        }
    
    def rebalance_check(self, target_allocation: Dict[str, float]) -> Dict[str, Any]:
        \"\"\"Check if portfolio needs rebalancing\"\"\"
        current_allocation = self.get_asset_allocation()
        rebalance_needed = False
        actions = []
        
        for asset, target_pct in target_allocation.items():
            current_pct = current_allocation.get(asset, 0.0)
            difference = abs(current_pct - target_pct)
            
            if difference > 0.05:  # 5% threshold
                rebalance_needed = True
                if current_pct > target_pct:
                    actions.append({
                        'action': 'SELL',
                        'asset': asset,
                        'current_pct': current_pct,
                        'target_pct': target_pct,
                        'difference': difference
                    })
                else:
                    actions.append({
                        'action': 'BUY',
                        'asset': asset,
                        'current_pct': current_pct,
                        'target_pct': target_pct,
                        'difference': difference
                    })
        
        return {
            'rebalance_needed': rebalance_needed,
            'actions': actions,
            'current_allocation': current_allocation,
            'target_allocation': target_allocation
        }
    
    def export_portfolio_data(self, days: int = 30) -> pd.DataFrame:
        \"\"\"Export portfolio data as DataFrame\"\"\"
        try:
            snapshots = db_manager.get_portfolio_history(days=days)
            
            data = []
            for snapshot in snapshots:
                data.append({
                    'timestamp': snapshot.timestamp,
                    'total_balance': snapshot.total_balance,
                    'available_balance': snapshot.available_balance,
                    'locked_balance': snapshot.locked_balance,
                    'unrealized_pnl': snapshot.unrealized_pnl,
                    'realized_pnl_daily': snapshot.realized_pnl_daily,
                    'realized_pnl_total': snapshot.realized_pnl_total,
                    'drawdown': snapshot.drawdown,
                    'open_trades': snapshot.open_trades_count
                })
            
            df = pd.DataFrame(data)
            if not df.empty:
                df.set_index('timestamp', inplace=True)
                df = df.sort_index()
            
            return df
            
        except Exception as e:
            logger.error(f"Error exporting portfolio data: {e}")
            return pd.DataFrame()

# Global portfolio manager instance
portfolio_manager = PortfolioManager()
"""

with open('crypto_trading_system/risk/portfolio_manager.py', 'w') as f:
    f.write(portfolio_manager_content)

print("✅ Portfolio manager created!")