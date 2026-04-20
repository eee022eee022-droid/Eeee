# Crypto Scalper — live paper trading

A minimal, fully transparent **paper-trading** scalper that runs against
**live Binance spot market data** and exposes a dashboard showing every
trade, open position and PnL in real time.

> **No real money is ever traded.** Orders are filled locally against the
> latest ticker price with a configurable taker fee and slippage. The bot
> does not need and does not use any exchange credentials.

## What it does

- Subscribes to OKX public WebSocket streams (`trades` + `candle1m`) for a
  configurable basket of spot symbols (default: BTC-USDT, ETH-USDT, SOL-USDT).
- Maintains EMA(9/21), RSI(14) and ATR(14) incrementally, candle by candle.
- Fires long-only signals on a fresh fast-over-slow EMA cross when RSI is
  in a healthy momentum band and ATR-% is non-trivial.
- Sizes each trade to risk ~1% of current equity, capped by available cash.
- Manages exits with ATR-based stop-loss, ATR-based take-profit and a hard
  max-hold timer.
- Persists account, positions, closed trades and equity snapshots in a
  local SQLite database on a Fly volume.
- Serves a single-page dashboard with live cards, an equity curve, market
  stats, open positions and recent trades.

## Dashboard

Once deployed, open the root URL to see:

- **Equity / Balance / Open PnL / Realized PnL** summary cards
- **Equity curve** (sampled every 15s)
- **Markets** table with live price, EMA, RSI and ATR-% per symbol
- **Open positions** with entry, mark, stop, target and unrealized PnL
- **Recent trades** with entry/exit/reason/PnL

## Configuration

All tunables are environment variables (see `app/config.py`). Defaults give
a cautious scalper on a $500 virtual balance.

| Variable | Default | Meaning |
| --- | --- | --- |
| `SCALPER_SYMBOLS` | `BTC-USDT,ETH-USDT,SOL-USDT` | Comma-separated universe (OKX format) |
| `SCALPER_INITIAL_BALANCE` | `500` | Starting USDT balance |
| `SCALPER_TAKER_FEE` | `0.001` | 10 bps per fill |
| `SCALPER_SLIPPAGE_BPS` | `2` | Per-side slippage |
| `SCALPER_RISK_PCT` | `0.01` | Risk per trade (fraction of equity) |
| `SCALPER_ATR_STOP` / `SCALPER_ATR_TARGET` | `1.2` / `1.8` | Exit multiples |
| `SCALPER_MAX_POS` | `2` | Max simultaneous positions |
| `SCALPER_MAX_HOLD` | `1200` | Seconds before time-based exit |

## Local run

```bash
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8080
# then open http://localhost:8080
```

## Fly.io deploy

The repo ships a `Dockerfile` and `fly.toml`. The `/data` volume keeps the
SQLite database across restarts.

```bash
flyctl launch --no-deploy       # only on first launch; accept defaults
flyctl volumes create scalper_data --size 1 --region iad
flyctl deploy
```

## Honest disclaimer

This is a demo. A simple EMA/RSI/ATR system with round-trip fees and real
slippage will often **lose money** — and that is a feature of the demo:
you see realistic performance on a real market. Tune parameters, extend
the strategy, or plug in your own signal generator before taking anything
seriously.
