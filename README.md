# Pump Detector

Real-time crypto scanner that detects **early pump signals** on Binance USDT
pairs (volume explosions, breakouts, momentum) — before the move is obvious.
Structured so Gate.io, Telegram alerts, paid tiers, etc. can be added without
touching the scanner core.

## One-command run

Requires Node **18+** (for native `fetch`).

```bash
npm install && npm start
```

Open <http://localhost:3000>.

## Stack

- Backend: Node.js + Express (ESM), native `fetch`, no axios
- Frontend: vanilla HTML/CSS/JS (dark trading UI, neon green)
- Hosting: Replit / Vercel / any Node host

## How it works

Every scan (cached 30s) the server:

1. Lists actively-traded spot USDT pairs on Binance, sorted by 24h quote volume
   (min volume & universe size configurable).
2. Pulls the last 50 × 5m candles per pair in parallel (bounded concurrency).
3. Runs the scorer (`server/scanner.js`), which produces a 0–100 score from:
   - **Price change** (last 4 candles) — up to **30**
   - **Volume spike** (latest vs avg of previous 20) — up to **30**
   - **Breakout** (close > highest high of prior 20) — **20**
   - **Candle strength** (close near high & bullish body) — up to **10**
   - **Momentum** (consecutive green closes) — up to **10**
4. Returns only early-pump signals: `priceChange ≥ 1.5%`, `volumeSpike ≥ 2.5×`,
   breakout, bullish, not already overextended (>10% move), and `score ≥ 70`.

## API

`GET /signals`

Query params:

| param      | default   | notes                                                             |
| ---------- | --------- | ----------------------------------------------------------------- |
| `demo`     | `0`       | `1` → return pre-recorded signals (no network call)               |
| `exchange` | `binance` | `binance` \| `gate`                                               |
| `minScore` | `0`       | extra filter on top of the server's min score                     |

Response:

```json
{
  "scannedAt": "2025-01-01T12:00:00.000Z",
  "exchange": "binance",
  "scanned": 112,
  "total": 120,
  "signals": [
    {
      "symbol": "DOGEUSDT",
      "priceChange": 3.2,
      "volumeSpike": 4.1,
      "breakout": true,
      "score": 87,
      "timeframe": "5m",
      "badges": ["Volume Explosion", "Breakout", "Momentum"],
      "sparkline": [0.161, 0.162, ...],
      "chartUrl": "https://www.binance.com/en/trade/DOGE_USDT?type=spot"
    }
  ]
}
```

`/api/signals` is an alias (handy on Vercel where everything lives under
`/api/*`). `/api/health` returns `{ ok: true }`.

## Config (env vars)

| var                 | default   | meaning                                              |
| ------------------- | --------- | ---------------------------------------------------- |
| `PORT`              | `3000`    |                                                      |
| `EXCHANGE`          | `binance` | default exchange id (`binance` \| `gate`)            |
| `SIGNALS_CACHE_MS`  | `30000`   | cache TTL for `/signals`                             |
| `MIN_QUOTE_VOLUME`  | `5000000` | min 24h USDT quote volume to consider a pair         |
| `SYMBOL_LIMIT`      | `120`     | max pairs to scan (top-N by quote volume)            |
| `MIN_SCORE`         | `70`      | minimum signal score returned                        |

## Demo mode

The UI has a **Demo mode** toggle; it calls `/signals?demo=1` which returns
static sample signals. Use this when Binance is geo-blocked from your host
(e.g. Vercel US edges) or during presentations.

## Project layout

```
server/
  index.js             # Express app + in-memory cache
  scanner.js           # indicators + scoring (exchange-agnostic)
  mock.js              # demo-mode payload
  exchanges/
    index.js           # registry + getExchange()
    binance.js         # Binance adapter
    gate.js            # Gate.io adapter (ready; swap via EXCHANGE=gate)
public/
  index.html
  styles.css
  app.js
```

## Deploy

- **Replit**: import the repo, it will run `npm start`.
- **Vercel**: the project runs as a standard Node server; set `PORT` if needed.
  Keep an eye on Binance geo-blocks on Vercel's US regions — Demo mode works
  regardless, and you can switch to `EXCHANGE=gate` for live data.

## Roadmap (future-ready hooks)

- `server/exchanges/` pattern → drop in Bybit / OKX adapters with the same shape.
- Telegram alerts: subscribe to new signals via a simple poll on `/signals`.
- Paid tier: gate `/signals` behind an auth middleware and serve a free
  `demo=1` tier from the same endpoint.

Not financial advice.
