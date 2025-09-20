# Create execution engine
execution_engine_content = """\"\"\"
Execution engine that coordinates order execution, position management,
and trade lifecycle management.
\"\"\"

import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import threading
from queue import Queue, Empty

from .order_manager import order_manager, OrderRequest, OrderResponse
from ..database.db_manager import db_manager
from ..database.models import OrderSide, OrderType, TradeStatus
from ..risk.risk_manager import risk_manager
from ..risk.portfolio_manager import portfolio_manager
from ..data.data_manager import data_manager
from ..utils.helpers import calculate_pnl, format_currency, TradingContext

logger = logging.getLogger(__name__)

class ExecutionMode(Enum):
    PAPER = "PAPER"
    LIVE = "LIVE"
    BACKTEST = "BACKTEST"

class SignalAction(Enum):
    BUY = "BUY"
    SELL = "SELL"
    CLOSE_LONG = "CLOSE_LONG"
    CLOSE_SHORT = "CLOSE_SHORT"
    HOLD = "HOLD"

@dataclass
class TradingSignal:
    \"\"\"Trading signal from strategy\"\"\"
    strategy_id: str
    symbol: str
    action: SignalAction
    strength: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    metadata: Optional[Dict] = None
    timestamp: Optional[datetime] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

@dataclass
class ExecutionResult:
    \"\"\"Result of signal execution\"\"\"
    success: bool
    signal: TradingSignal
    order_response: Optional[OrderResponse] = None
    trade_id: Optional[int] = None
    error_message: Optional[str] = None
    execution_price: Optional[float] = None

class ExecutionEngine:
    \"\"\"Main execution engine for coordinating trades\"\"\"
    
    def __init__(self, mode: ExecutionMode = ExecutionMode.PAPER):
        self.mode = mode
        self.is_running = False
        
        # Signal processing
        self.signal_queue = Queue()
        self.execution_callbacks = []
        
        # Position tracking
        self.open_positions = {}  # strategy_id -> {symbol: position_data}
        self.pending_exits = {}   # position_id -> exit_order_data
        
        # Execution settings
        self.slippage_buffer = 0.001  # 0.1% slippage buffer
        self.execution_timeout = 30   # seconds
        self.max_retries = 3
        
        # Performance tracking
        self.execution_stats = {
            'signals_processed': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_slippage': 0.0,
            'avg_execution_time': 0.0
        }
        
        # Setup callbacks
        order_manager.add_fill_callback(self._handle_order_fill)
        order_manager.add_error_callback(self._handle_order_error)
        
        # Initialize position tracking
        self._initialize_positions()
    
    def _initialize_positions(self):
        \"\"\"Initialize position tracking from database\"\"\"
        try:
            open_trades = db_manager.get_open_trades()
            
            for trade in open_trades:
                strategy_id = trade.strategy_id
                symbol = trade.symbol
                
                if strategy_id not in self.open_positions:
                    self.open_positions[strategy_id] = {}
                
                self.open_positions[strategy_id][symbol] = {
                    'trade_id': trade.id,
                    'side': trade.side,
                    'quantity': trade.quantity,
                    'entry_price': trade.entry_price,
                    'entry_time': trade.entry_time,
                    'unrealized_pnl': trade.unrealized_pnl
                }
            
            logger.info(f"Initialized {len(open_trades)} open positions")
            
        except Exception as e:
            logger.error(f"Error initializing positions: {e}")
    
    async def start(self):
        \"\"\"Start the execution engine\"\"\"
        if self.is_running:
            logger.warning("Execution engine is already running")
            return
        
        self.is_running = True
        logger.info(f"Starting execution engine in {self.mode.value} mode")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._process_signals()),
            asyncio.create_task(self._monitor_positions()),
            asyncio.create_task(self._update_unrealized_pnl()),
        ]
        
        if self.mode == ExecutionMode.LIVE:
            tasks.append(asyncio.create_task(order_manager.monitor_orders()))
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in execution engine: {e}")
        finally:
            self.is_running = False
    
    async def stop(self):
        \"\"\"Stop the execution engine\"\"\"
        logger.info("Stopping execution engine")
        self.is_running = False
        
        # Cancel any pending orders if in live mode
        if self.mode == ExecutionMode.LIVE:
            await order_manager.cancel_all_orders()
    
    def submit_signal(self, signal: TradingSignal) -> bool:
        \"\"\"Submit a trading signal for execution\"\"\"
        try:
            self.signal_queue.put(signal)
            logger.debug(f"Signal queued: {signal.strategy_id} {signal.symbol} {signal.action.value}")
            return True
        except Exception as e:
            logger.error(f"Error submitting signal: {e}")
            return False
    
    async def _process_signals(self):
        \"\"\"Process signals from the queue\"\"\"
        while self.is_running:
            try:
                # Get signal with timeout
                try:
                    signal = self.signal_queue.get(timeout=1.0)
                except Empty:
                    await asyncio.sleep(0.1)
                    continue
                
                # Process the signal
                result = await self._execute_signal(signal)
                
                # Update statistics
                self.execution_stats['signals_processed'] += 1
                if result.success:
                    self.execution_stats['successful_executions'] += 1
                else:
                    self.execution_stats['failed_executions'] += 1
                
                # Call callbacks
                for callback in self.execution_callbacks:
                    try:
                        await callback(result)
                    except Exception as e:
                        logger.error(f"Error in execution callback: {e}")
                
                # Mark signal as processed
                self.signal_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing signals: {e}")
                await asyncio.sleep(1)
    
    async def _execute_signal(self, signal: TradingSignal) -> ExecutionResult:
        \"\"\"Execute a trading signal\"\"\"
        start_time = datetime.utcnow()
        
        try:
            with TradingContext(signal.strategy_id) as context:
                context.add_operation("signal_received", {
                    "symbol": signal.symbol,
                    "action": signal.action.value,
                    "strength": signal.strength,
                    "confidence": signal.confidence
                })
                
                # Determine execution action
                execution_result = await self._determine_execution_action(signal)
                if not execution_result.success:
                    return execution_result
                
                # Execute the action
                if signal.action in [SignalAction.BUY, SignalAction.SELL]:
                    result = await self._execute_entry_signal(signal)
                elif signal.action in [SignalAction.CLOSE_LONG, SignalAction.CLOSE_SHORT]:
                    result = await self._execute_exit_signal(signal)
                else:  # HOLD
                    result = ExecutionResult(
                        success=True,
                        signal=signal,
                        error_message="Signal action is HOLD - no execution needed"
                    )
                
                # Update execution time
                execution_time = (datetime.utcnow() - start_time).total_seconds()
                self._update_execution_time(execution_time)
                
                context.add_operation("signal_executed", {
                    "success": result.success,
                    "execution_time": execution_time,
                    "error": result.error_message
                })
                
                return result
                
        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return ExecutionResult(
                success=False,
                signal=signal,
                error_message=str(e)
            )
    
    async def _determine_execution_action(self, signal: TradingSignal) -> ExecutionResult:
        \"\"\"Determine if signal should be executed\"\"\"
        try:
            # Check if strategy is enabled
            # This would check against strategy manager
            
            # Check signal strength and confidence thresholds
            if signal.strength < 0.5 or signal.confidence < 0.6:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    error_message=f"Signal strength ({signal.strength}) or confidence ({signal.confidence}) too low"
                )
            
            # Check for conflicting positions
            existing_position = self._get_existing_position(signal.strategy_id, signal.symbol)
            if existing_position and signal.action in [SignalAction.BUY, SignalAction.SELL]:
                # Check if we're trying to add to position in same direction
                if ((existing_position['side'] == OrderSide.BUY and signal.action == SignalAction.BUY) or
                    (existing_position['side'] == OrderSide.SELL and signal.action == SignalAction.SELL)):
                    return ExecutionResult(
                        success=False,
                        signal=signal,
                        error_message="Position already exists in same direction"
                    )
            
            return ExecutionResult(success=True, signal=signal)
            
        except Exception as e:
            logger.error(f"Error determining execution action: {e}")
            return ExecutionResult(
                success=False,
                signal=signal,
                error_message=str(e)
            )
    
    async def _execute_entry_signal(self, signal: TradingSignal) -> ExecutionResult:
        \"\"\"Execute entry signal (BUY/SELL)\"\"\"
        try:
            # Get current price
            current_price = signal.price or data_manager.get_current_price(signal.symbol)
            if not current_price:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    error_message="Unable to get current price"
                )
            
            # Calculate position size
            position_size = risk_manager.calculate_position_size(
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                entry_price=current_price,
                stop_loss_price=signal.stop_loss or current_price * (0.98 if signal.action == SignalAction.BUY else 1.02)
            )
            
            if position_size <= 0:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    error_message="Calculated position size is zero"
                )
            
            # Create order request
            order_request = OrderRequest(
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                side=OrderSide.BUY if signal.action == SignalAction.BUY else OrderSide.SELL,
                type=OrderType.MARKET if self.mode == ExecutionMode.LIVE else OrderType.LIMIT,
                quantity=position_size,
                price=current_price * (1 + self.slippage_buffer) if signal.action == SignalAction.BUY 
                      else current_price * (1 - self.slippage_buffer)
            )
            
            # Submit order
            if self.mode == ExecutionMode.PAPER:
                order_response = await self._simulate_order_execution(order_request, current_price)
            else:
                order_response = await order_manager.submit_order(order_request)
            
            if order_response.success:
                # Save signal to database
                await self._save_signal_to_db(signal, order_response.order_id)
                
                return ExecutionResult(
                    success=True,
                    signal=signal,
                    order_response=order_response,
                    execution_price=order_response.avg_price or current_price
                )
            else:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    order_response=order_response,
                    error_message=order_response.error_message
                )
                
        except Exception as e:
            logger.error(f"Error executing entry signal: {e}")
            return ExecutionResult(
                success=False,
                signal=signal,
                error_message=str(e)
            )
    
    async def _execute_exit_signal(self, signal: TradingSignal) -> ExecutionResult:
        \"\"\"Execute exit signal (CLOSE_LONG/CLOSE_SHORT)\"\"\"
        try:
            # Find existing position
            existing_position = self._get_existing_position(signal.strategy_id, signal.symbol)
            if not existing_position:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    error_message="No existing position to close"
                )
            
            # Get current price
            current_price = signal.price or data_manager.get_current_price(signal.symbol)
            if not current_price:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    error_message="Unable to get current price"
                )
            
            # Create exit order (opposite side)
            exit_side = OrderSide.SELL if existing_position['side'] == OrderSide.BUY else OrderSide.BUY
            
            order_request = OrderRequest(
                strategy_id=signal.strategy_id,
                symbol=signal.symbol,
                side=exit_side,
                type=OrderType.MARKET if self.mode == ExecutionMode.LIVE else OrderType.LIMIT,
                quantity=existing_position['quantity'],
                price=current_price * (1 - self.slippage_buffer) if exit_side == OrderSide.SELL 
                      else current_price * (1 + self.slippage_buffer)
            )
            
            # Submit exit order
            if self.mode == ExecutionMode.PAPER:
                order_response = await self._simulate_order_execution(order_request, current_price)
            else:
                order_response = await order_manager.submit_order(order_request)
            
            if order_response.success:
                # Update position in database
                await self._close_position(
                    existing_position['trade_id'],
                    current_price,
                    order_response.order_id
                )
                
                return ExecutionResult(
                    success=True,
                    signal=signal,
                    order_response=order_response,
                    trade_id=existing_position['trade_id'],
                    execution_price=order_response.avg_price or current_price
                )
            else:
                return ExecutionResult(
                    success=False,
                    signal=signal,
                    order_response=order_response,
                    error_message=order_response.error_message
                )
                
        except Exception as e:
            logger.error(f"Error executing exit signal: {e}")
            return ExecutionResult(
                success=False,
                signal=signal,
                error_message=str(e)
            )
    
    async def _simulate_order_execution(self, order_request: OrderRequest, current_price: float) -> OrderResponse:
        \"\"\"Simulate order execution for paper trading\"\"\"
        try:
            # Simulate slippage
            slippage = np.random.normal(0, 0.001)  # 0.1% standard deviation
            execution_price = current_price * (1 + slippage)
            
            # Create simulated response
            return OrderResponse(
                success=True,
                order_id=f"SIM_{int(time.time() * 1000)}",
                client_order_id=order_request.client_order_id,
                status=OrderStatus.FILLED,
                filled_quantity=order_request.quantity,
                avg_price=execution_price
            )
            
        except Exception as e:
            logger.error(f"Error simulating order execution: {e}")
            return OrderResponse(
                success=False,
                client_order_id=order_request.client_order_id,
                error_message=str(e)
            )
    
    async def _save_signal_to_db(self, signal: TradingSignal, order_id: Optional[str]):
        \"\"\"Save signal to database\"\"\"
        try:
            signal_data = {
                'strategy_id': signal.strategy_id,
                'symbol': signal.symbol,
                'signal_type': signal.action.value,
                'strength': signal.strength,
                'confidence': signal.confidence,
                'price': signal.price or data_manager.get_current_price(signal.symbol),
                'timestamp': signal.timestamp,
                'executed': order_id is not None,
                'order_id': int(order_id) if order_id and order_id.isdigit() else None
            }
            
            if signal.metadata:
                signal_data['metadata'] = signal.metadata
            
            db_manager.save_signal(signal_data)
            
        except Exception as e:
            logger.error(f"Error saving signal to database: {e}")
    
    def _get_existing_position(self, strategy_id: str, symbol: str) -> Optional[Dict]:
        \"\"\"Get existing position for strategy and symbol\"\"\"
        return self.open_positions.get(strategy_id, {}).get(symbol)
    
    async def _close_position(self, trade_id: int, exit_price: float, exit_order_id: str):
        \"\"\"Close a position and calculate PnL\"\"\"
        try:
            # Get trade from database
            trade = db_manager.get_trade_by_id(trade_id)
            if not trade:
                logger.error(f"Trade {trade_id} not found for closure")
                return
            
            # Calculate realized PnL
            realized_pnl = calculate_pnl(
                entry_price=trade.entry_price,
                exit_price=exit_price,
                quantity=trade.quantity,
                side=trade.side.value
            )
            
            # Update trade in database
            updates = {
                'exit_price': exit_price,
                'exit_order_id': int(exit_order_id) if exit_order_id.isdigit() else None,
                'exit_time': datetime.utcnow(),
                'realized_pnl': realized_pnl,
                'status': TradeStatus.CLOSED,
                'duration_minutes': int((datetime.utcnow() - trade.entry_time).total_seconds() / 60)
            }
            
            db_manager.update_trade(trade_id, updates)
            
            # Remove from open positions
            if trade.strategy_id in self.open_positions:
                if trade.symbol in self.open_positions[trade.strategy_id]:
                    del self.open_positions[trade.strategy_id][trade.symbol]
            
            # Update risk manager
            risk_manager.close_position(trade.strategy_id, trade_id, exit_price)
            
            logger.info(f"Position closed: {trade.symbol} PnL: {format_currency(realized_pnl)}")
            
        except Exception as e:
            logger.error(f"Error closing position {trade_id}: {e}")
    
    async def _handle_order_fill(self, order_id: str, order_response: OrderResponse, trade):
        \"\"\"Handle order fill callback\"\"\"
        try:
            # Update position tracking
            if hasattr(trade, 'strategy_id') and hasattr(trade, 'symbol'):
                strategy_id = trade.strategy_id
                symbol = trade.symbol
                
                if strategy_id not in self.open_positions:
                    self.open_positions[strategy_id] = {}
                
                self.open_positions[strategy_id][symbol] = {
                    'trade_id': trade.id,
                    'side': trade.side,
                    'quantity': trade.quantity,
                    'entry_price': trade.entry_price,
                    'entry_time': trade.entry_time,
                    'unrealized_pnl': 0.0
                }
                
                logger.info(f"Position opened: {symbol} {trade.side.value} {trade.quantity}")
            
        except Exception as e:
            logger.error(f"Error handling order fill: {e}")
    
    async def _handle_order_error(self, order_id: str, error_message: str):
        \"\"\"Handle order error callback\"\"\"
        logger.error(f"Order error for {order_id}: {error_message}")
    
    async def _monitor_positions(self):
        \"\"\"Monitor open positions for stop losses and take profits\"\"\"
        while self.is_running:
            try:
                for strategy_id, positions in self.open_positions.items():
                    for symbol, position in positions.items():
                        await self._check_position_exits(strategy_id, symbol, position)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring positions: {e}")
                await asyncio.sleep(10)
    
    async def _check_position_exits(self, strategy_id: str, symbol: str, position: Dict):
        \"\"\"Check if position should be exited based on stop loss/take profit\"\"\"
        try:
            current_price = data_manager.get_current_price(symbol)
            if not current_price:
                return
            
            # Calculate unrealized PnL
            unrealized_pnl = calculate_pnl(
                entry_price=position['entry_price'],
                exit_price=current_price,
                quantity=position['quantity'],
                side=position['side'].value
            )
            
            position['unrealized_pnl'] = unrealized_pnl
            
            # Check for automatic exits (this would be based on strategy settings)
            # For now, just update the unrealized PnL
            
        except Exception as e:
            logger.error(f"Error checking position exits for {symbol}: {e}")
    
    async def _update_unrealized_pnl(self):
        \"\"\"Update unrealized PnL for all positions\"\"\"
        while self.is_running:
            try:
                total_unrealized = 0.0
                
                for strategy_id, positions in self.open_positions.items():
                    for symbol, position in positions.items():
                        current_price = data_manager.get_current_price(symbol)
                        if current_price:
                            unrealized_pnl = calculate_pnl(
                                entry_price=position['entry_price'],
                                exit_price=current_price,
                                quantity=position['quantity'],
                                side=position['side'].value
                            )
                            
                            position['unrealized_pnl'] = unrealized_pnl
                            total_unrealized += unrealized_pnl
                            
                            # Update in database
                            db_manager.update_trade(
                                position['trade_id'],
                                {'unrealized_pnl': unrealized_pnl}
                            )
                
                # Update portfolio manager
                # This would be called periodically to update the portfolio snapshot
                
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"Error updating unrealized PnL: {e}")
                await asyncio.sleep(60)
    
    def _update_execution_time(self, execution_time: float):
        \"\"\"Update average execution time\"\"\"
        current_avg = self.execution_stats['avg_execution_time']
        count = self.execution_stats['successful_executions']
        
        if count > 0:
            self.execution_stats['avg_execution_time'] = (current_avg * (count - 1) + execution_time) / count
        else:
            self.execution_stats['avg_execution_time'] = execution_time
    
    def add_execution_callback(self, callback: Callable):
        \"\"\"Add callback for execution results\"\"\"
        self.execution_callbacks.append(callback)
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        \"\"\"Get execution statistics\"\"\"
        return {
            **self.execution_stats,
            'open_positions': sum(len(positions) for positions in self.open_positions.values()),
            'pending_signals': self.signal_queue.qsize(),
            'mode': self.mode.value,
            'is_running': self.is_running
        }
    
    def get_open_positions_summary(self) -> Dict[str, Any]:
        \"\"\"Get summary of open positions\"\"\"
        total_positions = 0
        total_unrealized_pnl = 0.0
        positions_by_strategy = {}
        
        for strategy_id, positions in self.open_positions.items():
            strategy_positions = []
            strategy_pnl = 0.0
            
            for symbol, position in positions.items():
                total_positions += 1
                total_unrealized_pnl += position['unrealized_pnl']
                strategy_pnl += position['unrealized_pnl']
                
                strategy_positions.append({
                    'symbol': symbol,
                    'side': position['side'].value,
                    'quantity': position['quantity'],
                    'entry_price': position['entry_price'],
                    'unrealized_pnl': position['unrealized_pnl'],
                    'entry_time': position['entry_time']
                })
            
            positions_by_strategy[strategy_id] = {
                'positions': strategy_positions,
                'count': len(strategy_positions),
                'total_pnl': strategy_pnl
            }
        
        return {
            'total_positions': total_positions,
            'total_unrealized_pnl': total_unrealized_pnl,
            'by_strategy': positions_by_strategy,
            'timestamp': datetime.utcnow()
        }

# Global execution engine instance
execution_engine = ExecutionEngine()
"""

with open('crypto_trading_system/execution/execution_engine.py', 'w') as f:
    f.write(execution_engine_content)

print("✅ Execution engine created!")