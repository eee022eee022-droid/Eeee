"""Pump Detector — FastAPI server used for the hosted deploy.

Serves the same static frontend (../public) and /signals API as the Node
reference implementation, with the default exchange set to Gate.io so the
live scan works from US edges where Binance is geo-restricted.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from exchanges import get_exchange
from mock import mock_scan
from paper import DEFAULT_COLLATERAL, DEFAULT_LEVERAGE, DEFAULT_SL_PCT, DEFAULT_TP_PCT, make_book
from probability import ProbConfig
from probability import scan as prob_scan
from scanner import ScanConfig, scan

DEFAULT_EXCHANGE = os.getenv("EXCHANGE", "gate")
CACHE_TTL_S = float(os.getenv("SIGNALS_CACHE_MS", "30000")) / 1000
MIN_QUOTE_VOLUME = float(os.getenv("MIN_QUOTE_VOLUME", "1000000"))
SYMBOL_LIMIT = int(os.getenv("SYMBOL_LIMIT", "120"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "70"))
PROB_CACHE_TTL_S = float(os.getenv("PROB_CACHE_MS", "45000")) / 1000
PROB_SYMBOL_LIMIT = int(os.getenv("PROB_SYMBOL_LIMIT", "500"))
PROB_MIN_QUOTE_VOLUME = float(os.getenv("PROB_MIN_QUOTE_VOLUME", "200000"))
PROB_CONCURRENCY = int(os.getenv("PROB_CONCURRENCY", "16"))

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Pump Detector")

# Per-exchange cache with request coalescing.
_cache: dict[str, tuple[float, dict]] = {}
_inflight: dict[str, asyncio.Task] = {}


async def _get_signals(exchange_id: str) -> dict:
    now = time.time()
    hit = _cache.get(exchange_id)
    if hit and now - hit[0] < CACHE_TTL_S:
        return hit[1]
    if exchange_id in _inflight:
        return await _inflight[exchange_id]

    cfg = ScanConfig(
        min_quote_volume=MIN_QUOTE_VOLUME,
        symbol_limit=SYMBOL_LIMIT,
        min_score=MIN_SCORE,
    )
    exchange = get_exchange(exchange_id)

    async def _run() -> dict:
        try:
            data = await scan(exchange, cfg)
            _cache[exchange_id] = (time.time(), data)
            return data
        finally:
            _inflight.pop(exchange_id, None)

    task = asyncio.create_task(_run())
    _inflight[exchange_id] = task
    return await task


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "exchange": DEFAULT_EXCHANGE}


# ---------------- paper trading ----------------

book = make_book()


class OpenTradeReq(BaseModel):
    symbol: str
    exchange: str = Field(default_factory=lambda: DEFAULT_EXCHANGE)
    side: str = "long"
    collateral: float = DEFAULT_COLLATERAL
    leverage: float = DEFAULT_LEVERAGE
    tpPct: float = DEFAULT_TP_PCT
    slPct: float = DEFAULT_SL_PCT


@app.post("/api/trades")
async def open_trade(req: OpenTradeReq) -> JSONResponse:
    try:
        trade = await book.open_trade(
            symbol=req.symbol,
            exchange_id=req.exchange,
            side=req.side,
            collateral=req.collateral,
            leverage=req.leverage,
            tp_pct=req.tpPct,
            sl_pct=req.slPct,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except RuntimeError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    snap = await book.snapshot()
    opened = next((t for t in snap["open"] + snap["closed"] if t["id"] == trade.id), None)
    return JSONResponse({"trade": opened, **snap})


@app.get("/api/trades")
async def list_trades() -> JSONResponse:
    return JSONResponse(await book.snapshot())


@app.post("/api/trades/{trade_id}/close")
async def close_trade(trade_id: str) -> JSONResponse:
    try:
        await book.close_trade(trade_id, reason="manual")
    except KeyError:
        raise HTTPException(status_code=404, detail="trade not found")
    return JSONResponse(await book.snapshot())


# ---------------- probability scanner ----------------

_prob_cache: dict[str, tuple[float, dict]] = {}
_prob_inflight: dict[str, asyncio.Task] = {}


async def _get_probability(exchange_id: str) -> dict:
    now = time.time()
    hit = _prob_cache.get(exchange_id)
    if hit and now - hit[0] < PROB_CACHE_TTL_S:
        return hit[1]
    if exchange_id in _prob_inflight:
        return await _prob_inflight[exchange_id]

    cfg = ProbConfig(
        symbol_limit=PROB_SYMBOL_LIMIT,
        min_quote_volume=PROB_MIN_QUOTE_VOLUME,
        concurrency=PROB_CONCURRENCY,
    )
    exchange = get_exchange(exchange_id)

    async def _run() -> dict:
        try:
            data = await prob_scan(exchange, cfg, top_n=10)
            _prob_cache[exchange_id] = (time.time(), data)
            return data
        finally:
            _prob_inflight.pop(exchange_id, None)

    task = asyncio.create_task(_run())
    _prob_inflight[exchange_id] = task
    return await task


@app.get("/api/probability")
async def probability(
    exchange: str = Query(default=DEFAULT_EXCHANGE),
    minProb: int = Query(default=0),
    tag: str | None = Query(default=None),
) -> JSONResponse:
    try:
        data = await _get_probability(exchange)
    except Exception as err:  # noqa: BLE001
        return JSONResponse(
            status_code=502,
            content={"error": "scan_failed", "message": str(err)},
        )
    rows = data["top"]
    if minProb > 0:
        rows = [r for r in rows if r["probability"] >= minProb]
    if tag in ("EARLY", "LATE"):
        rows = [r for r in rows if r["tag"] == tag]
    return JSONResponse({**data, "top": rows, "filtered": len(rows) != len(data["top"])})


async def _handle_signals(
    demo: bool, exchange_id: str, min_score: int
) -> JSONResponse:
    try:
        data = mock_scan(exchange_id) if demo else await _get_signals(exchange_id)
        signals = (
            [s for s in data["signals"] if s["score"] >= min_score]
            if min_score > 0
            else data["signals"]
        )
        return JSONResponse({**data, "signals": signals})
    except Exception as err:  # noqa: BLE001
        return JSONResponse(
            status_code=502,
            content={
                "error": "scan_failed",
                "message": str(err),
                "hint": "Try demo mode or a different exchange (?exchange=gate).",
            },
        )


@app.get("/signals")
async def signals(
    demo: str | None = Query(default=None),
    exchange: str = Query(default=DEFAULT_EXCHANGE),
    minScore: int = Query(default=0),
) -> JSONResponse:
    return await _handle_signals(demo in ("1", "true"), exchange, minScore)


@app.get("/api/signals")
async def signals_alias(
    demo: str | None = Query(default=None),
    exchange: str = Query(default=DEFAULT_EXCHANGE),
    minScore: int = Query(default=0),
) -> JSONResponse:
    return await _handle_signals(demo in ("1", "true"), exchange, minScore)


# Static assets. Mounted last so the API routes win; StaticFiles(html=True)
# serves index.html at /. SPA fallback returns index.html for unknown paths.
if STATIC_DIR.is_dir():
    app.mount(
        "/",
        StaticFiles(directory=STATIC_DIR, html=True),
        name="static",
    )
