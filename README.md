# Crypto Trading System

A modular framework for building, testing, and monitoring algorithmic cryptocurrency trading strategies. The repository currently contains the project skeleton plus a static dashboard prototype. Core Python modules are placeholders and need full implementations.

## Features (Planned)

- Live, paper, and backtest trading modes that share the same strategy interface
- Binance market data ingestion via WebSocket plus historical download utilities
- Risk engine for exposure checks, drawdown guards, and portfolio accounting
- Execution layer abstraction for exchange REST endpoints and simulators
- Monitoring toolkit and front-end dashboard for status, metrics, and alerts
- SQLAlchemy-backed persistence layer for candles, orders, and trades

## Repository Layout

See `crypto_trading_system_guide.md` for a detailed, component-by-component overview.

- Static dashboard assets live at the repository root (`index.html`, `style.css`, `app.js`).
- Python source code is expected under the `crypto_trading_system/` package (directories listed in the guide).

## Getting Started

1. Create and activate a virtual environment.
2. Populate `config/.env.example` with your Binance API keys (or leave empty to run in mock mode) and copy it to `.env`.
3. Install dependencies: `pip install -r crypto_trading_system/requirements.txt` (pulls in `python-binance`, `aiohttp`, `websockets`, `SQLAlchemy`, `pytest`).
4. Implement the placeholder modules following the guidance in the implementation guide.
5. Run `python main.py paper --api-port 8000` to fire up the paper loop and expose live metrics at `http://127.0.0.1:8000/api/dashboard`.

## Testing

- Execute the unit test suite with `pytest` to validate risk controls, portfolio accounting, and execution flow integration hooks.

If the Binance credentials are omitted or the dependency import fails, the system automatically falls back to the built-in simulator for both data and order flow.

## Dashboard API (Optional)

- The static dashboard (`app.js`) polls the `/api/dashboard` endpoint when available and reverts to bundled mock data otherwise.

## Contributing

- Stick to PEP 8 and include type hints.
- Add tests for new logic.
- Document modules with docstrings and keep the guide up to date.

## Disclaimer

Automated trading is risky. Validate strategies extensively and comply with local regulations before trading with real funds.
