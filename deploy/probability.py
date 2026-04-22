"""Altcoin pump-probability scanner.

Per the product spec: score each USDT pair with a weighted blend of volume
spike, short-term momentum, volatility burst, candle strength and a simple
repeat-pattern flag. Returns a 0–100 probability, human-readable reasons
and an EARLY/LATE tag so the frontend can show a clean top-10 list.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx


@dataclass
class ProbConfig:
    interval: str = "5m"
    limit: int = 50
    volume_lookback: int = 20
    momentum_candles: int = 2  # 2 × 5m ≈ 10 min
    candle_strength_window: int = 5
    pattern_lookback: int = 40
    pattern_spike_threshold: float = 2.0  # vol spike big enough to count as prior burst
    volume_cap: float = 5.0  # 5× = fully saturated volume score
    momentum_cap_pct: float = 10.0  # +10% in the momentum window = saturated
    volatility_cap: float = 3.0  # 3× avg range = saturated
    symbol_limit: int = 500
    concurrency: int = 16
    min_quote_volume: float = 200_000
    weights: dict = field(
        default_factory=lambda: {
            "volume": 0.35,
            "momentum": 0.25,
            "volatility": 0.15,
            "candle": 0.15,
            "pattern": 0.10,
        }
    )


def _clamp01(v: float) -> float:
    return 0.0 if v < 0 else 1.0 if v > 1 else v


def analyze(symbol: str, candles: list[dict], cfg: ProbConfig) -> dict | None:
    needed = max(cfg.volume_lookback, cfg.pattern_lookback) + 2
    if not candles or len(candles) < needed:
        return None

    latest = candles[-1]

    # --- 1. Volume spike ---------------------------------------------------
    vol_window = candles[-1 - cfg.volume_lookback : -1]
    avg_vol = sum(c["volume"] for c in vol_window) / len(vol_window) if vol_window else 0.0
    volume_spike = latest["volume"] / avg_vol if avg_vol > 0 else 0.0
    vol_norm = _clamp01(min(volume_spike, cfg.volume_cap) / cfg.volume_cap)

    # --- 2. Momentum -------------------------------------------------------
    prior_idx = max(0, len(candles) - (cfg.momentum_candles + 1))
    prior_close = candles[prior_idx]["close"]
    mom_pct = (
        (latest["close"] - prior_close) / prior_close * 100 if prior_close > 0 else 0.0
    )
    mom_norm = _clamp01(max(0.0, mom_pct) / cfg.momentum_cap_pct)

    # --- 3. Volatility burst ----------------------------------------------
    ranges = [c["high"] - c["low"] for c in vol_window]
    avg_range = sum(ranges) / len(ranges) if ranges else 0.0
    cur_range = latest["high"] - latest["low"]
    volat_mult = cur_range / avg_range if avg_range > 0 else 0.0
    volat_norm = _clamp01(min(volat_mult, cfg.volatility_cap) / cfg.volatility_cap)

    # --- 4. Candle strength (green count in last N) ------------------------
    last_n = candles[-cfg.candle_strength_window :]
    green_count = sum(1 for c in last_n if c["close"] > c["open"])
    candle_norm = green_count / cfg.candle_strength_window

    # --- 5. Pattern repeat: any similar volume spike in lookback window ----
    pattern_window = candles[-1 - cfg.pattern_lookback : -1]
    pattern_avg = sum(c["volume"] for c in pattern_window) / len(pattern_window) if pattern_window else 0.0
    repeats = 0
    if pattern_avg > 0:
        repeats = sum(
            1
            for c in pattern_window[:-cfg.volume_lookback]  # exclude very recent window
            if c["volume"] >= pattern_avg * cfg.pattern_spike_threshold
        )
    pattern_norm = 1.0 if repeats >= 1 else 0.0

    w = cfg.weights
    score = (
        vol_norm * w["volume"]
        + mom_norm * w["momentum"]
        + volat_norm * w["volatility"]
        + candle_norm * w["candle"]
        + pattern_norm * w["pattern"]
    )
    probability = round(_clamp01(score) * 100)

    # --- Reasons + tag -----------------------------------------------------
    reasons: list[str] = []
    if volume_spike >= 1.5:
        reasons.append(f"Volume ×{volume_spike:.1f}")
    if mom_pct >= 0.3:
        reasons.append(f"Momentum +{mom_pct:.1f}% ({cfg.momentum_candles * 5}m)")
    elif mom_pct <= -0.3:
        reasons.append(f"Momentum {mom_pct:.1f}% ({cfg.momentum_candles * 5}m)")
    if green_count >= 3:
        reasons.append(f"{green_count} green candles")
    if volat_mult >= 1.7:
        reasons.append(f"Range ×{volat_mult:.1f}")
    if repeats:
        reasons.append(f"{repeats} prior spike{'s' if repeats > 1 else ''}")

    # Window move for overextension detection
    low_window = min(c["low"] for c in vol_window) if vol_window else latest["close"]
    window_move_pct = (
        (latest["close"] - low_window) / low_window * 100 if low_window > 0 else 0.0
    )

    if mom_pct >= 8 or window_move_pct >= 15:
        tag = "LATE"
    elif volume_spike >= 2 and mom_pct < 3:
        tag = "EARLY"
    else:
        tag = None

    return {
        "symbol": symbol,
        "probability": probability,
        "score": round(score, 4),
        "tag": tag,
        "reasons": reasons,
        "volumeSpike": round(volume_spike, 2),
        "momentumPct": round(mom_pct, 2),
        "momentumWindowMin": cfg.momentum_candles * 5,
        "volatilityMult": round(volat_mult, 2),
        "greenCandles": green_count,
        "priorSpikes": repeats,
        "windowMovePct": round(window_move_pct, 2),
        "price": latest["close"],
        "sparkline": [c["close"] for c in candles[-20:]],
        "timeframe": cfg.interval,
    }


async def _analyze_symbol(
    exchange, client: httpx.AsyncClient, symbol: str, cfg: ProbConfig
) -> dict | None:
    try:
        candles = await exchange.get_klines(
            client, symbol, interval=cfg.interval, limit=cfg.limit
        )
    except Exception:
        return None
    return analyze(symbol, candles, cfg)


async def scan(exchange, cfg: ProbConfig, *, top_n: int = 10) -> dict:
    async with httpx.AsyncClient(http2=False) as client:
        symbols = await exchange.list_active_usdt_symbols(
            client,
            min_quote_volume=cfg.min_quote_volume,
            limit=cfg.symbol_limit,
        )
        sem = asyncio.Semaphore(cfg.concurrency)

        async def _run(sym: str) -> dict | None:
            async with sem:
                return await _analyze_symbol(exchange, client, sym, cfg)

        analyzed = [a for a in await asyncio.gather(*(_run(s) for s in symbols)) if a]

    analyzed.sort(key=lambda a: a["probability"], reverse=True)
    top = analyzed[:top_n]
    for s in top:
        s["chartUrl"] = exchange.chart_url(s["symbol"])
        s["exchange"] = exchange.id

    return {
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "exchange": exchange.id,
        "scanned": len(analyzed),
        "total": len(symbols),
        "top": top,
    }
