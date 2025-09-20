# Crypto Trading System - Implementation Guide

## Directory Overview

crypto_trading_system/
- main.py                  # Async entry point wiring modules together (to be implemented)
- requirements.txt         # Python dependency pins
- Dockerfile               # Container definition for the trading service
- docker-compose.yml       # Optional multi-service orchestration
- README.md                # Project introduction (high-level)
- api/
  - __init__.py
  - server.py            # Lightweight HTTP endpoint for dashboard data
- config/
  - __init__.py
  - config.py            # Central settings object (env-aware)
  - binance_config.py    # Exchange connection parameters
  - .env.example         # Sample environment variables
- data/
  - __init__.py
  - data_manager.py      # Coordinates historical/live data feeds
  - websocket_client.py  # Real-time sockets (Binance)
  - historical_data.py   # Historical download helpers
- strategies/
  - __init__.py
  - base_strategy.py     # Shared lifecycle and risk hooks
  - momentum_strategy.py # Example momentum implementation
  - mean_reversion_strategy.py
  - grid_strategy.py
- risk/
  - __init__.py
  - risk_manager.py      # Exposure and limit checks
  - portfolio_manager.py # Balance tracking utilities
- execution/
  - __init__.py
  - order_manager.py
  - execution_engine.py
- backtesting/
  - __init__.py
  - backtest_engine.py
  - performance_metrics.py
- database/
  - __init__.py
  - db_manager.py
  - models.py
- monitoring/
  - __init__.py
  - dashboard.py
  - alerts.py
  - logger.py
- exchanges/
  - __init__.py
  - binance_service.py    # Shared AsyncClient lifecycle
- utils/
  - __init__.py
  - helpers.py
  - indicators.py

static-dashboard/
- index.html               # Trading dashboard UI
- style.css                # Dashboard styling
- app.js                   # Front-end logic and mock data

## High-Level Architecture

1. Data ingestion populates a unified market data stream (websocket) and a historical archive.
2. Strategies subscribe to normalized data updates and emit trade intents.
3. Risk and portfolio managers validate intents against exposure limits and account balances.
4. The execution engine converts approved intents into exchange orders (live or paper modes).
5. The backtesting engine replays historical data through the same strategy and risk interfaces.
6. Monitoring surfaces health metrics, PnL, risk status, and alerts to the dashboard.
7. The API layer exposes aggregated state to the static dashboard via JSON endpoints.

## Suggested Implementation Order

1. Finish the configuration layer: load `.env`, validate keys, expose settings data classes.
2. Implement market data adapters: websocket streaming and historical fetch with caching.
3. Build the base strategy contract (`on_data`, `on_start`, `on_stop`, `generate_signals`).
4. Fill the risk management hooks (max exposure, drawdown guard, position sizing helpers).
5. Connect the execution layer (Binance REST for live, simulated book for paper/backtest).
6. Implement persistence using SQLAlchemy models in `database/models.py` with a manager wrapper.
7. Flesh out monitoring utilities and connect them to the static dashboard (or replace mock data with API endpoints).

## Running Modes

- Paper trading uses exchange market data but routes through simulated execution.
- Live trading requires valid API keys, risk controls, and exchange permissions.
- Backtesting replays stored candles or order book snapshots.
- The dashboard can be hosted as static assets or served by a lightweight API for live metrics.

## Next Steps Checklist

- [ ] Populate each placeholder Python module with real implementations (see README for module responsibilities).
- [ ] Provide unit and integration tests for critical risk and execution paths.
- [ ] Replace mock dashboard JSON (`app.js`) with API calls to your backend once endpoints are ready.
- [ ] Decide on a deployment target (Docker container, bare-metal service, or cloud).
- [ ] Set up logging and metrics aggregation (for example Prometheus, ELK, or a hosted alternative).

## Operational Notes

- Keep secrets out of the repository; load them via environment variables or secret managers.
- Respect exchange rate limits and add retries or backoff for transient failures.
- Start in paper or backtest mode before enabling live trading.
- Monitor PnL, latency, and error rates continuously when running in production.
