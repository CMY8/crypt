"""Command line entry point for the crypto trading system."""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
from typing import Optional, Sequence

from crypto_trading_system.api import serve_dashboard_api
from crypto_trading_system.backtesting import BacktestEngine
from crypto_trading_system.config import Settings, load_settings, BinanceConfig
from crypto_trading_system.data import DataManager, WebSocketClient, HistoricalDataService
from crypto_trading_system.execution import ExecutionEngine, OrderManager
from crypto_trading_system.exchanges import BinanceService
from crypto_trading_system.monitoring import DashboardState, configure_logging
from crypto_trading_system.risk import PortfolioManager, RiskManager
from crypto_trading_system.strategies import MomentumStrategy


logger = logging.getLogger(__name__)


async def run_paper(
    settings: Settings,
    symbols: Sequence[str],
    duration: int,
    api_host: Optional[str] = None,
    api_port: Optional[int] = None,
) -> None:
    configure_logging(settings.log_level)
    portfolio = PortfolioManager(starting_cash=100_000)
    risk_manager = RiskManager(portfolio)
    dashboard = DashboardState(portfolio)
    binance_config = BinanceConfig.from_env(settings)
    binance_service: Optional[BinanceService] = None
    if binance_config.is_configured:
        try:
            binance_service = BinanceService(binance_config)
        except RuntimeError as error:
            logger.warning('Falling back to simulated exchange: %s', error)
    else:
        logger.warning('Binance credentials not configured; running in simulated paper mode.')

    websocket_client = WebSocketClient(settings, config=binance_config, service=binance_service)
    data_manager = DataManager(settings, websocket_client=websocket_client)
    order_manager = OrderManager(binance_service, binance_config if binance_service else None)
    engine = ExecutionEngine(
        data_manager=data_manager,
        portfolio=portfolio,
        risk_manager=risk_manager,
        order_manager=order_manager,
        dashboard=dashboard,
    )
    strategy = MomentumStrategy('momentum', settings)
    engine.register_strategy(strategy)

    server = thread = None
    if api_port is not None:
        def payload() -> dict:
            summary = dashboard.portfolio_summary()
            prices = {
                symbol: {'price': price}
                for symbol, price in dashboard.marks.items()
            }
            open_positions = [
                {
                    'symbol': symbol,
                    'side': 'LONG' if position.quantity >= 0 else 'SHORT',
                    'quantity': position.quantity,
                    'entry_price': position.average_price,
                    'current_price': dashboard.marks.get(symbol, position.average_price),
                    'pnl': (dashboard.marks.get(symbol, position.average_price) - position.average_price) * position.quantity,
                    'strategy': strategy.name,
                }
                for symbol, position in portfolio.positions.items()
            ]
            return {
                'portfolio': summary,
                'prices': prices,
                'open_positions': open_positions,
                'strategies': [
                    {
                        'name': strat.name,
                        'enabled': True,
                        'status': 'ACTIVE',
                        'pnl': 0.0,
                        'trades': 0,
                    }
                    for strat in engine.strategies
                ],
                'system_status': {
                    'api_connected': binance_service is not None,
                    'websocket_connected': binance_service is not None,
                    'database_healthy': True,
                    'last_update': time.time(),
                },
            }

        server, thread = serve_dashboard_api(payload, host=api_host or '127.0.0.1', port=api_port)
        logger.info('Dashboard API available at http://%s:%s/api/dashboard', api_host or '127.0.0.1', api_port)

    await engine.start(symbols)
    await asyncio.sleep(duration)
    await engine.stop()

    if server:
        server.shutdown()
        if thread:
            thread.join(timeout=1)
        logger.info('Dashboard API stopped')


async def run_backtest(settings: Settings, symbol: str, interval: str, limit: int) -> None:
    configure_logging(settings.log_level)
    portfolio = PortfolioManager(starting_cash=100_000)
    risk_manager = RiskManager(portfolio)
    data_service = HistoricalDataService(settings)
    engine = BacktestEngine(
        data_service=data_service,
        strategy=MomentumStrategy('momentum', settings),
        portfolio=portfolio,
        risk_manager=risk_manager,
    )
    result = await engine.run(symbol=symbol, interval=interval, limit=limit)
    logger.info('Backtest completed: total_return=%.2f%%', result.total_return * 100)


async def run_dashboard(settings: Settings) -> None:
    configure_logging(settings.log_level)
    logger.info('Static dashboard lives in index.html/app.js. Serve it with any HTTP server.')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Crypto trading system CLI')
    sub = parser.add_subparsers(dest='command', required=True)

    paper = sub.add_parser('paper', help='Run the paper trading loop')
    paper.add_argument('--symbols', nargs='+', default=['BTCUSDT'])
    paper.add_argument('--duration', type=int, default=30, help='Runtime in seconds')
    paper.add_argument('--api-port', type=int, help='Expose dashboard data on the given port')
    paper.add_argument('--api-host', default='127.0.0.1')

    backtest = sub.add_parser('backtest', help='Run a backtest')
    backtest.add_argument('--symbol', default='BTCUSDT')
    backtest.add_argument('--interval', default='1h')
    backtest.add_argument('--limit', type=int, default=100)

    sub.add_parser('dashboard', help='Serve dashboard instructions')

    return parser


async def async_main(args: argparse.Namespace) -> None:
    settings = load_settings()
    if args.command == 'paper':
        await run_paper(settings, args.symbols, args.duration, args.api_host, args.api_port)
    elif args.command == 'backtest':
        await run_backtest(settings, args.symbol, args.interval, args.limit)
    elif args.command == 'dashboard':
        await run_dashboard(settings)
    else:  # pragma: no cover
        raise ValueError(f'Unknown command {args.command}')


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(async_main(args))


if __name__ == '__main__':
    main()
