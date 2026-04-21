"""Pre-recorded demo signals. Mirrors server/mock.js byte-for-byte.

Used by /signals?demo=1 so the UI has deterministic data for demos and for
deploys where a given exchange may be geo-restricted.
"""
from __future__ import annotations

from datetime import datetime, timezone


def _spark(base: float, drift: float = 0.01, n: int = 20, seed: int = 1) -> list[float]:
    out: list[float] = []
    x = base
    s = seed
    for _ in range(n):
        s = (s * 9301 + 49297) % 233280
        r = (s / 233280 - 0.4) * drift
        x = max(0.0, x * (1 + r + drift * 0.15))
        out.append(round(x, 6))
    return out


DEMO_SIGNALS = [
    {
        "symbol": "DOGEUSDT", "priceChange": 3.4, "volumeSpike": 4.2, "breakout": True,
        "bullish": True, "greenCandles": 4, "closeNearHigh": 0.94, "overextended": False,
        "earlyPump": True, "score": 92,
        "badges": ["Volume Explosion", "Breakout", "Momentum"],
        "price": 0.168, "sparkline": _spark(0.162, 0.012, 20, 11), "timeframe": "5m",
    },
    {
        "symbol": "INJUSDT", "priceChange": 2.7, "volumeSpike": 3.1, "breakout": True,
        "bullish": True, "greenCandles": 3, "closeNearHigh": 0.88, "overextended": False,
        "earlyPump": True, "score": 85,
        "badges": ["Volume Explosion", "Breakout", "Momentum"],
        "price": 25.82, "sparkline": _spark(25.1, 0.009, 20, 23), "timeframe": "5m",
    },
    {
        "symbol": "SEIUSDT", "priceChange": 2.1, "volumeSpike": 2.9, "breakout": True,
        "bullish": True, "greenCandles": 2, "closeNearHigh": 0.81, "overextended": False,
        "earlyPump": True, "score": 79,
        "badges": ["Volume Explosion", "Breakout"],
        "price": 0.412, "sparkline": _spark(0.401, 0.008, 20, 37), "timeframe": "5m",
    },
    {
        "symbol": "PEPEUSDT", "priceChange": 4.8, "volumeSpike": 5.7, "breakout": True,
        "bullish": True, "greenCandles": 5, "closeNearHigh": 0.97, "overextended": False,
        "earlyPump": True, "score": 96,
        "badges": ["Volume Explosion", "Breakout", "Momentum"],
        "price": 0.00000843, "sparkline": _spark(0.00000801, 0.014, 20, 51), "timeframe": "5m",
    },
    {
        "symbol": "TIAUSDT", "priceChange": 1.9, "volumeSpike": 2.6, "breakout": True,
        "bullish": True, "greenCandles": 2, "closeNearHigh": 0.77, "overextended": False,
        "earlyPump": True, "score": 74,
        "badges": ["Volume Explosion", "Breakout"],
        "price": 4.73, "sparkline": _spark(4.64, 0.007, 20, 73), "timeframe": "5m",
    },
]


def mock_scan(exchange_id: str = "binance") -> dict:
    def binance_chart(sym: str) -> str:
        return f"https://www.binance.com/en/trade/{sym.replace('USDT', '_USDT')}?type=spot"

    def gate_chart(sym: str) -> str:
        return f"https://www.gate.io/trade/{sym.replace('USDT', '_USDT')}"

    chart = gate_chart if exchange_id == "gate" else binance_chart
    return {
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "exchange": exchange_id,
        "demo": True,
        "scanned": len(DEMO_SIGNALS),
        "total": len(DEMO_SIGNALS),
        "signals": [
            {**s, "exchange": exchange_id, "chartUrl": chart(s["symbol"])}
            for s in DEMO_SIGNALS
        ],
    }
