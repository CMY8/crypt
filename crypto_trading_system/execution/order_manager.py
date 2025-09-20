"""Order management backed by Binance REST API."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from ..config import BinanceConfig
from ..exchanges import BinanceService, BinanceAPIException, BinanceRequestException


@dataclass
class OrderRequest:
    symbol: str
    side: str
    quantity: float
    price: float | None = None
    order_type: str = 'MARKET'


@dataclass
class OrderResult:
    order_id: str
    status: str
    filled_quantity: float
    filled_price: float | None
    raw: dict


class OrderManager:
    """Submits orders to Binance or simulates fills when no service is provided."""

    def __init__(
        self,
        service: Optional[BinanceService] = None,
        config: Optional[BinanceConfig] = None,
    ) -> None:
        self._service = service
        self._config = config or (service.config if service else BinanceConfig(api_key='', api_secret=''))
        self._id_counter = 0
        self._lock = asyncio.Lock()

    async def submit(self, request: OrderRequest) -> OrderResult:
        if self._service is None:
            return await self._submit_simulated(request)
        return await self._submit_live(request)

    async def _submit_live(self, request: OrderRequest) -> OrderResult:
        client = await self._service.client()
        params = {
            'symbol': request.symbol.upper(),
            'side': request.side.upper(),
            'type': request.order_type.upper(),
            'quantity': float(request.quantity),
            'recvWindow': self._config.recv_window,
        }
        if request.price is not None and params['type'] != 'MARKET':
            params['price'] = float(request.price)
        try:
            response = await client.create_order(**params)
        except (BinanceAPIException, BinanceRequestException) as exc:  # pragma: no cover - network path
            raise RuntimeError(f'Order rejected: {exc}') from exc

        filled_qty = float(response.get('executedQty', 0.0))
        quote_qty = float(response.get('cummulativeQuoteQty', 0.0))
        filled_price = quote_qty / filled_qty if filled_qty and quote_qty else request.price
        return OrderResult(
            order_id=str(response.get('orderId', '')),
            status=response.get('status', 'UNKNOWN'),
            filled_quantity=filled_qty,
            filled_price=filled_price,
            raw=response,
        )

    async def _submit_simulated(self, request: OrderRequest) -> OrderResult:
        async with self._lock:
            self._id_counter += 1
            order_id = f'sim-{self._id_counter}'
        price = request.price or 0.0
        return OrderResult(
            order_id=order_id,
            status='FILLED',
            filled_quantity=float(request.quantity),
            filled_price=price,
            raw={'simulated': True},
        )

    async def close(self) -> None:
        if self._service is not None:
            await self._service.close()


__all__ = ['OrderManager', 'OrderRequest', 'OrderResult']
