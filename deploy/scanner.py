"""Core scanner — exchange-agnostic pump detection.

Ported from server/scanner.js. Same inputs and formulas so that scores stay
comparable across the Node and Python versions.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx


@dataclass
class ScanConfig:
    interval: str = "5m"
    limit: int = 50
    min_score: int = 70
    price_change_lookback: int = 4
    volume_lookback: int = 20
    breakout_lookback: int = 20
    overextended_pct: float = 10.0
    concurrency: int = 8
    min_quote_volume: float = 5_000_000
    symbol_limit: int = 120


def analyze(symbol: str, candles: list[dict], cfg: ScanConfig) -> dict | None:
    if not candles or len(candles) < cfg.breakout_lookback + 2:
        return None

    latest = candles[-1]
    prior_close_idx = max(0, len(candles) - (cfg.price_change_lookback + 1))
    prior_close = candles[prior_close_idx]["close"]
    price_change_pct = (
        (latest["close"] - prior_close) / prior_close * 100 if prior_close else 0.0
    )

    vol_window = candles[-1 - cfg.volume_lookback : -1]
    avg_vol = sum(c["volume"] for c in vol_window) / len(vol_window) if vol_window else 0
    volume_spike = latest["volume"] / avg_vol if avg_vol > 0 else 0.0

    breakout_window = candles[-1 - cfg.breakout_lookback : -1]
    prior_high = max(c["high"] for c in breakout_window)
    breakout = latest["close"] > prior_high

    candle_range = latest["high"] - latest["low"]
    body = latest["close"] - latest["open"]
    bullish = body > 0
    close_near_high = (
        (latest["close"] - latest["low"]) / candle_range if candle_range > 0 else 0.0
    )

    greens = 0
    for c in reversed(candles):
        if c["close"] > c["open"]:
            greens += 1
        else:
            break

    low_window = min(c["low"] for c in breakout_window)
    window_move_pct = (
        (latest["close"] - low_window) / low_window * 100 if low_window > 0 else 0.0
    )
    overextended = (
        window_move_pct > cfg.overextended_pct * 2
        or price_change_pct > cfg.overextended_pct
    )

    price_score = max(0, min(30, (price_change_pct / 5) * 30))
    volume_score = max(0, min(30, ((volume_spike - 1) / 4) * 30))
    breakout_score = 20 if breakout else 0
    candle_score = round(close_near_high * 10) if bullish else 0
    momentum_score = min(10, max(0, (greens - 1) * 5))
    score = round(price_score + volume_score + breakout_score + candle_score + momentum_score)

    early_pump = (
        not overextended
        and price_change_pct >= 1.5
        and volume_spike >= 2.5
        and breakout
        and bullish
    )

    badges: list[str] = []
    if volume_spike >= 2.5:
        badges.append("Volume Explosion")
    if breakout:
        badges.append("Breakout")
    if greens >= 3:
        badges.append("Momentum")

    return {
        "symbol": symbol,
        "priceChange": round(price_change_pct, 2),
        "volumeSpike": round(volume_spike, 2),
        "breakout": breakout,
        "bullish": bullish,
        "greenCandles": greens,
        "closeNearHigh": round(close_near_high, 2),
        "overextended": overextended,
        "earlyPump": early_pump,
        "score": score,
        "badges": badges,
        "price": latest["close"],
        "sparkline": [c["close"] for c in candles[-20:]],
        "timeframe": cfg.interval,
    }


async def _analyze_symbol(
    exchange, client: httpx.AsyncClient, symbol: str, cfg: ScanConfig
) -> dict | None:
    try:
        candles = await exchange.get_klines(
            client, symbol, interval=cfg.interval, limit=cfg.limit
        )
    except Exception:
        return None
    return analyze(symbol, candles, cfg)


async def scan(exchange, cfg: ScanConfig) -> dict:
    async with httpx.AsyncClient(http2=False) as client:
        symbols = await exchange.list_active_usdt_symbols(
            client, min_quote_volume=cfg.min_quote_volume, limit=cfg.symbol_limit
        )
        sem = asyncio.Semaphore(cfg.concurrency)

        async def _run(sym: str) -> dict | None:
            async with sem:
                return await _analyze_symbol(exchange, client, sym, cfg)

        analyzed = [a for a in await asyncio.gather(*(_run(s) for s in symbols)) if a]

    signals = sorted(
        (a for a in analyzed if a["earlyPump"] and a["score"] >= cfg.min_score),
        key=lambda a: a["score"],
        reverse=True,
    )
    for s in signals:
        s["chartUrl"] = exchange.chart_url(s["symbol"])
        s["exchange"] = exchange.id

    return {
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "exchange": exchange.id,
        "scanned": len(analyzed),
        "total": len(symbols),
        "signals": signals,
    }
