# Create order manager
order_manager_content = """\"\"\"
Order management system for handling trade orders with proper validation,
execution tracking, and error handling.
\"\"\"

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import uuid
import time

from ..database.db_manager import db_manager
from ..database.models import OrderSide, OrderStatus, OrderType
from ..config.binance_config import binance_config
from ..risk.risk_manager import risk_manager
from ..utils.helpers import (
    normalize_price, normalize_quantity, generate_order_id,
    retry, rate_limit, format_currency, get_symbol_precision, get_min_notional
)

logger = logging.getLogger(__name__)

class OrderState(Enum):
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"

@dataclass
class OrderRequest:
    \"\"\"Order request data\"\"\"
    strategy_id: str
    symbol: str
    side: OrderSide
    type: OrderType
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: str = "GTC"  # Good Till Cancelled
    client_order_id: Optional[str] = None
    
    def __post_init__(self):
        if self.client_order_id is None:
            self.client_order_id = generate_order_id()

@dataclass
class OrderResponse:
    \"\"\"Order response from exchange\"\"\"
    success: bool
    order_id: Optional[str] = None
    client_order_id: Optional[str] = None
    status: Optional[OrderStatus] = None
    filled_quantity: float = 0.0
    avg_price: Optional[float] = None
    error_message: Optional[str] = None
    exchange_response: Optional[Dict] = None

class OrderManager:
    \"\"\"Order management system\"\"\"
    
    def __init__(self):
        self.pending_orders = {}  # client_order_id -> OrderRequest
        self.active_orders = {}   # exchange_order_id -> order_data
        self.order_history = {}   # client_order_id -> order_data
        
        # Order tracking
        self.fill_callbacks = []
        self.error_callbacks = []
        
        # Rate limiting
        self.order_count = 0
        self.last_order_time = 0
        self.min_order_interval = 0.1  # 100ms between orders
        
        # Retry settings
        self.max_retries = 3
        self.retry_delay = 1.0
        
    async def submit_order(self, order_request: OrderRequest) -> OrderResponse:
        \"\"\"Submit an order to the exchange\"\"\"
        try:
            logger.info(f"Submitting order: {order_request.symbol} {order_request.side.value} "
                       f"{order_request.quantity} @ {order_request.price}")
            
            # Validate order request
            validation_result = await self._validate_order(order_request)
            if not validation_result[0]:
                return OrderResponse(
                    success=False,
                    client_order_id=order_request.client_order_id,
                    error_message=validation_result[1]
                )
            
            # Add to pending orders
            self.pending_orders[order_request.client_order_id] = order_request
            
            # Submit to exchange
            response = await self._submit_to_exchange(order_request)
            
            # Handle response
            if response.success:
                # Save to database
                await self._save_order_to_db(order_request, response)
                
                # Add to active orders if not immediately filled
                if response.status not in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    self.active_orders[response.order_id] = {
                        'request': order_request,
                        'response': response,
                        'created_at': datetime.utcnow()
                    }
                
                logger.info(f"Order submitted successfully: {response.order_id}")
            else:
                logger.error(f"Order submission failed: {response.error_message}")
            
            # Remove from pending
            if order_request.client_order_id in self.pending_orders:
                del self.pending_orders[order_request.client_order_id]
            
            # Update order history
            self.order_history[order_request.client_order_id] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error submitting order: {e}")
            return OrderResponse(
                success=False,
                client_order_id=order_request.client_order_id,
                error_message=str(e)
            )
    
    async def _validate_order(self, order_request: OrderRequest) -> Tuple[bool, str]:
        \"\"\"Validate order request\"\"\"
        try:
            # Basic validation
            if order_request.quantity <= 0:
                return False, "Invalid quantity"
            
            if order_request.type in [OrderType.LIMIT, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT_LIMIT]:
                if order_request.price is None or order_request.price <= 0:
                    return False, "Invalid price for limit order"
            
            if order_request.type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT]:
                if order_request.stop_price is None or order_request.stop_price <= 0:
                    return False, "Invalid stop price"
            
            # Get symbol info and validate against exchange filters
            symbol_valid = await self._validate_symbol_filters(order_request)
            if not symbol_valid[0]:
                return symbol_valid
            
            # Risk management validation
            risk_valid = risk_manager.validate_order(
                strategy_id=order_request.strategy_id,
                symbol=order_request.symbol,
                side=order_request.side.value,
                quantity=order_request.quantity,
                price=order_request.price or 0
            )
            
            if not risk_valid[0]:
                return risk_valid
            
            return True, "Order validated"
            
        except Exception as e:
            logger.error(f"Error validating order: {e}")
            return False, f"Validation error: {e}"
    
    async def _validate_symbol_filters(self, order_request: OrderRequest) -> Tuple[bool, str]:
        \"\"\"Validate order against exchange symbol filters\"\"\"
        try:
            # Get symbol information
            client = binance_config.client
            exchange_info = client.get_exchange_info()
            
            symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == order_request.symbol:
                    symbol_info = s
                    break
            
            if not symbol_info:
                return False, f"Symbol {order_request.symbol} not found"
            
            if symbol_info['status'] != 'TRADING':
                return False, f"Symbol {order_request.symbol} not available for trading"
            
            # Check filters
            for filter_info in symbol_info['filters']:
                filter_type = filter_info['filterType']
                
                if filter_type == 'LOT_SIZE':
                    min_qty = float(filter_info['minQty'])
                    max_qty = float(filter_info['maxQty'])
                    step_size = float(filter_info['stepSize'])
                    
                    if order_request.quantity < min_qty:
                        return False, f"Quantity below minimum: {min_qty}"
                    
                    if order_request.quantity > max_qty:
                        return False, f"Quantity above maximum: {max_qty}"
                    
                    # Check step size
                    remainder = (order_request.quantity - min_qty) % step_size
                    if remainder != 0:
                        return False, f"Invalid quantity step size"
                
                elif filter_type == 'PRICE_FILTER' and order_request.price:
                    min_price = float(filter_info['minPrice'])
                    max_price = float(filter_info['maxPrice'])
                    tick_size = float(filter_info['tickSize'])
                    
                    if order_request.price < min_price:
                        return False, f"Price below minimum: {min_price}"
                    
                    if order_request.price > max_price:
                        return False, f"Price above maximum: {max_price}"
                    
                    # Check tick size
                    remainder = (order_request.price - min_price) % tick_size
                    if remainder != 0:
                        return False, f"Invalid price tick size"
                
                elif filter_type == 'MIN_NOTIONAL':
                    min_notional = float(filter_info['minNotional'])
                    notional_value = order_request.quantity * (order_request.price or 0)
                    
                    if notional_value < min_notional:
                        return False, f"Order value below minimum notional: {min_notional}"
            
            return True, "Symbol filters passed"
            
        except Exception as e:
            logger.error(f"Error validating symbol filters: {e}")
            return False, f"Filter validation error: {e}"
    
    @retry(max_attempts=3)
    @rate_limit(calls=10, period=1.0)
    async def _submit_to_exchange(self, order_request: OrderRequest) -> OrderResponse:
        \"\"\"Submit order to Binance exchange\"\"\"
        try:
            client = binance_config.client
            
            # Prepare order parameters
            order_params = {
                'symbol': order_request.symbol,
                'side': order_request.side.value,
                'type': order_request.type.value,
                'quantity': order_request.quantity,
                'newClientOrderId': order_request.client_order_id,
                'timeInForce': order_request.time_in_force
            }
            
            # Add price for limit orders
            if order_request.type in [OrderType.LIMIT, OrderType.STOP_LOSS_LIMIT, OrderType.TAKE_PROFIT_LIMIT]:
                order_params['price'] = order_request.price
            
            # Add stop price for stop orders
            if order_request.type in [OrderType.STOP_LOSS, OrderType.STOP_LOSS_LIMIT]:
                order_params['stopPrice'] = order_request.stop_price
            
            # Submit order
            if binance_config.testnet:
                # For testnet, we might need to use different method
                result = client.create_order(**order_params)
            else:
                result = client.create_order(**order_params)
            
            # Parse response
            return OrderResponse(
                success=True,
                order_id=str(result['orderId']),
                client_order_id=result['clientOrderId'],
                status=OrderStatus(result['status']),
                filled_quantity=float(result.get('executedQty', 0)),
                avg_price=float(result['fills'][0]['price']) if result.get('fills') else None,
                exchange_response=result
            )
            
        except Exception as e:
            error_message = str(e)
            logger.error(f"Exchange order submission failed: {error_message}")
            
            return OrderResponse(
                success=False,
                client_order_id=order_request.client_order_id,
                error_message=error_message
            )
    
    async def _save_order_to_db(self, order_request: OrderRequest, response: OrderResponse):
        \"\"\"Save order to database\"\"\"
        try:
            order_data = {
                'exchange_order_id': response.order_id,
                'strategy_id': order_request.strategy_id,
                'symbol': order_request.symbol,
                'side': order_request.side,
                'type': order_request.type,
                'status': response.status,
                'quantity': order_request.quantity,
                'price': order_request.price,
                'stop_price': order_request.stop_price,
                'filled_quantity': response.filled_quantity,
                'avg_price': response.avg_price,
                'created_at': datetime.utcnow()
            }
            
            if response.filled_quantity > 0:
                order_data['executed_at'] = datetime.utcnow()
            
            db_manager.save_order(order_data)
            
        except Exception as e:
            logger.error(f"Error saving order to database: {e}")
    
    async def cancel_order(self, order_id: str) -> OrderResponse:
        \"\"\"Cancel an active order\"\"\"
        try:
            client = binance_config.client
            
            # Find order info
            order_info = self.active_orders.get(order_id)
            if not order_info:
                return OrderResponse(
                    success=False,
                    order_id=order_id,
                    error_message="Order not found in active orders"
                )
            
            # Cancel on exchange
            result = client.cancel_order(
                symbol=order_info['request'].symbol,
                orderId=order_id
            )
            
            # Update database
            db_manager.update_order(
                order_id=int(order_id),
                updates={'status': OrderStatus.CANCELLED}
            )
            
            # Remove from active orders
            if order_id in self.active_orders:
                del self.active_orders[order_id]
            
            logger.info(f"Order cancelled successfully: {order_id}")
            
            return OrderResponse(
                success=True,
                order_id=order_id,
                status=OrderStatus.CANCELLED,
                exchange_response=result
            )
            
        except Exception as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            return OrderResponse(
                success=False,
                order_id=order_id,
                error_message=str(e)
            )
    
    async def cancel_all_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        \"\"\"Cancel all active orders for a symbol or all symbols\"\"\"
        results = []
        
        orders_to_cancel = []
        for order_id, order_info in self.active_orders.items():
            if symbol is None or order_info['request'].symbol == symbol:
                orders_to_cancel.append(order_id)
        
        for order_id in orders_to_cancel:
            result = await self.cancel_order(order_id)
            results.append(result)
        
        return results
    
    async def get_order_status(self, order_id: str) -> Optional[OrderResponse]:
        \"\"\"Get current status of an order\"\"\"
        try:
            client = binance_config.client
            
            # Get from active orders first
            if order_id in self.active_orders:
                order_info = self.active_orders[order_id]
                symbol = order_info['request'].symbol
            else:
                # Try to find in database
                db_order = db_manager.get_order(int(order_id))
                if not db_order:
                    return None
                symbol = db_order.symbol
            
            # Query exchange
            result = client.get_order(
                symbol=symbol,
                orderId=order_id
            )
            
            return OrderResponse(
                success=True,
                order_id=str(result['orderId']),
                client_order_id=result['clientOrderId'],
                status=OrderStatus(result['status']),
                filled_quantity=float(result['executedQty']),
                avg_price=float(result['price']) if float(result['executedQty']) > 0 else None,
                exchange_response=result
            )
            
        except Exception as e:
            logger.error(f"Error getting order status for {order_id}: {e}")
            return None
    
    async def update_order_status(self, order_id: str):
        \"\"\"Update order status from exchange\"\"\"
        try:
            status_response = await self.get_order_status(order_id)
            if status_response and status_response.success:
                # Update database
                updates = {
                    'status': status_response.status,
                    'filled_quantity': status_response.filled_quantity,
                    'updated_at': datetime.utcnow()
                }
                
                if status_response.avg_price:
                    updates['avg_price'] = status_response.avg_price
                
                if status_response.status == OrderStatus.FILLED:
                    updates['executed_at'] = datetime.utcnow()
                
                db_manager.update_order(int(order_id), updates)
                
                # Handle fills
                if status_response.filled_quantity > 0:
                    await self._handle_fill(order_id, status_response)
                
                # Remove from active if completed
                if status_response.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    if order_id in self.active_orders:
                        del self.active_orders[order_id]
                
        except Exception as e:
            logger.error(f"Error updating order status for {order_id}: {e}")
    
    async def _handle_fill(self, order_id: str, order_response: OrderResponse):
        \"\"\"Handle order fill event\"\"\"
        try:
            # Get order info
            order_info = self.active_orders.get(order_id)
            if not order_info:
                # Try to get from database
                db_order = db_manager.get_order(int(order_id))
                if not db_order:
                    logger.error(f"Order {order_id} not found for fill handling")
                    return
                
                # Create order_info from db_order
                order_info = {
                    'request': OrderRequest(
                        strategy_id=db_order.strategy_id,
                        symbol=db_order.symbol,
                        side=db_order.side,
                        type=db_order.type,
                        quantity=db_order.quantity,
                        price=db_order.price
                    )
                }
            
            # Create trade record
            trade_data = {
                'strategy_id': order_info['request'].strategy_id,
                'symbol': order_info['request'].symbol,
                'side': order_info['request'].side,
                'quantity': order_response.filled_quantity,
                'entry_price': order_response.avg_price,
                'entry_order_id': int(order_id),
                'entry_time': datetime.utcnow(),
                'status': 'OPEN'
            }
            
            # Save trade to database
            trade = db_manager.save_trade(trade_data)
            
            # Update risk manager
            risk_manager.update_position(
                strategy_id=order_info['request'].strategy_id,
                trade_data=trade_data
            )
            
            # Call fill callbacks
            for callback in self.fill_callbacks:
                try:
                    await callback(order_id, order_response, trade)
                except Exception as e:
                    logger.error(f"Error in fill callback: {e}")
            
            logger.info(f"Order fill handled: {order_id}, quantity: {order_response.filled_quantity}")
            
        except Exception as e:
            logger.error(f"Error handling fill for order {order_id}: {e}")
    
    def add_fill_callback(self, callback):
        \"\"\"Add callback for order fills\"\"\"
        self.fill_callbacks.append(callback)
    
    def add_error_callback(self, callback):
        \"\"\"Add callback for order errors\"\"\"
        self.error_callbacks.append(callback)
    
    async def monitor_orders(self):
        \"\"\"Monitor active orders for status updates\"\"\"
        while True:
            try:
                # Update status for all active orders
                active_order_ids = list(self.active_orders.keys())
                
                for order_id in active_order_ids:
                    await self.update_order_status(order_id)
                    await asyncio.sleep(0.1)  # Small delay between updates
                
                # Clean up old pending orders
                current_time = datetime.utcnow()
                expired_orders = []
                
                for client_order_id, order_request in self.pending_orders.items():
                    # Remove orders that have been pending for more than 5 minutes
                    if (current_time - datetime.utcnow()).seconds > 300:
                        expired_orders.append(client_order_id)
                
                for client_order_id in expired_orders:
                    del self.pending_orders[client_order_id]
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in order monitoring: {e}")
                await asyncio.sleep(10)
    
    def get_active_orders(self) -> List[Dict[str, Any]]:
        \"\"\"Get list of active orders\"\"\"
        return [
            {
                'order_id': order_id,
                'symbol': info['request'].symbol,
                'side': info['request'].side.value,
                'type': info['request'].type.value,
                'quantity': info['request'].quantity,
                'price': info['request'].price,
                'created_at': info['created_at']
            }
            for order_id, info in self.active_orders.items()
        ]
    
    def get_order_statistics(self) -> Dict[str, Any]:
        \"\"\"Get order statistics\"\"\"
        return {
            'active_orders': len(self.active_orders),
            'pending_orders': len(self.pending_orders),
            'total_orders_today': self._count_daily_orders(),
            'order_history_count': len(self.order_history),
            'last_order_time': self.last_order_time
        }
    
    def _count_daily_orders(self) -> int:
        \"\"\"Count orders submitted today\"\"\"
        try:
            today = datetime.utcnow().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            orders = db_manager.get_orders(limit=1000)  # Get recent orders
            daily_count = sum(
                1 for order in orders 
                if order.created_at.date() == today
            )
            
            return daily_count
            
        except Exception as e:
            logger.error(f"Error counting daily orders: {e}")
            return 0

# Global order manager instance
order_manager = OrderManager()
"""

with open('crypto_trading_system/execution/order_manager.py', 'w') as f:
    f.write(order_manager_content)

print("✅ Order manager created!")