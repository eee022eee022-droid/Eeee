# Pump Detector — hosted deploy (FastAPI / Fly.io)

Python port of the Node reference implementation (`../server`) used only for
the hosted deploy. The Node version stays authoritative — this directory
mirrors its behaviour 1:1 (same scoring formulas, same demo payload, same
endpoints) because our deployment pipeline is Python-only.

## Live

- URL: https://pump-detector-dxdckbhn.fly.dev/
- Default exchange: `gate` (Binance is geo-blocked from US edges — Gate works)

## Endpoints

| Path | Notes |
|------|-------|
| `GET /api/health` | `{"ok": true, "exchange": "gate"}` |
| `GET /signals` | live scan, 30 s in-memory cache, request-coalesced |
| `GET /api/signals` | alias of `/signals` (same handler) |
| `GET /signals?demo=1` | pre-recorded 5-signal demo payload |
| `GET /signals?exchange=binance` | force Binance (will 502 from US edges) |
| `GET /signals?minScore=80` | server-side score filter |

## Run locally

```bash
cd deploy
python3 -m venv .venv && .venv/bin/pip install -e .
EXCHANGE=gate .venv/bin/fastapi run main.py --host 0.0.0.0 --port 3100
```

## Redeploy

```bash
# (requires the deploy tool used during development)
# otherwise, flyctl deploy works from this directory.
```
