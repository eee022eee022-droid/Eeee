"""Trend-following micro-scalping strategy.

On each closed 1m candle we update EMA/RSI/ATR. A long signal is fired when:
    * Fast EMA crosses above slow EMA (or is above by a small margin after a cross).
    * RSI is in the momentum sweet spot (not oversold, not overbought).
    * ATR is non-trivial (avoids dead ranges where fees dominate).

Exits are handled by the trading engine using ATR-based stop/target plus a
time-based max-hold. We intentionally only trade long — shorting spot makes
little sense for a paper account.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .indicators import ATR, EMA, RSI


Side = Literal["LONG"]


@dataclass
class Signal:
    side: Side
    price: float
    atr: float
    reason: str


@dataclass
class SymbolState:
    symbol: str
    ema_fast: EMA
    ema_slow: EMA
    rsi: RSI
    atr: ATR
    prev_fast: float | None = None
    prev_slow: float | None = None
    last_price: float | None = None
    last_close_ms: int = 0
    bars_seen: int = 0
    history: list[dict] = field(default_factory=list)

    def ready(self, min_bars: int) -> bool:
        return (
            self.bars_seen >= min_bars
            and self.ema_fast.value is not None
            and self.ema_slow.value is not None
            and self.rsi.value is not None
            and self.atr.value is not None
            and self.atr.value > 0
        )


class Scalper:
    """Multi-symbol scalper. Feed it closed candles; it returns optional signals."""

    def __init__(
        self,
        symbols: list[str],
        ema_fast: int,
        ema_slow: int,
        rsi_period: int,
        atr_period: int,
        rsi_long_min: float,
        rsi_long_max: float,
    ) -> None:
        self.ema_fast_p = ema_fast
        self.ema_slow_p = ema_slow
        self.rsi_long_min = rsi_long_min
        self.rsi_long_max = rsi_long_max
        self.min_bars = max(ema_slow, rsi_period, atr_period) + 2
        self.state: dict[str, SymbolState] = {
            s: SymbolState(
                symbol=s,
                ema_fast=EMA(ema_fast),
                ema_slow=EMA(ema_slow),
                rsi=RSI(rsi_period),
                atr=ATR(atr_period),
            )
            for s in symbols
        }

    def on_candle(
        self,
        symbol: str,
        open_: float,
        high: float,
        low: float,
        close: float,
        close_ms: int,
    ) -> Signal | None:
        st = self.state.get(symbol)
        if st is None:
            return None
        st.prev_fast = st.ema_fast.value
        st.prev_slow = st.ema_slow.value
        st.ema_fast.update(close)
        st.ema_slow.update(close)
        st.rsi.update(close)
        st.atr.update(high, low, close)
        st.last_price = close
        st.last_close_ms = close_ms
        st.bars_seen += 1
        st.history.append(
            {
                "t": close_ms,
                "o": open_,
                "h": high,
                "l": low,
                "c": close,
                "ema_fast": st.ema_fast.value,
                "ema_slow": st.ema_slow.value,
                "rsi": st.rsi.value,
                "atr": st.atr.value,
            }
        )
        # Keep last 240 bars (~4h on 1m candles) for the dashboard chart.
        if len(st.history) > 240:
            del st.history[: len(st.history) - 240]

        if not st.ready(self.min_bars):
            return None
        assert st.ema_fast.value is not None and st.ema_slow.value is not None
        assert st.rsi.value is not None and st.atr.value is not None

        fast_above_slow = st.ema_fast.value > st.ema_slow.value
        fresh_cross = (
            st.prev_fast is not None
            and st.prev_slow is not None
            and st.prev_fast <= st.prev_slow
            and fast_above_slow
        )
        rsi_ok = self.rsi_long_min <= st.rsi.value <= self.rsi_long_max
        atr_pct = st.atr.value / close if close > 0 else 0.0

        # Minimum ATR% filter: don't trade when the market is sleeping.
        if atr_pct < 0.0008:
            return None

        if fresh_cross and rsi_ok:
            return Signal(
                side="LONG",
                price=close,
                atr=st.atr.value,
                reason=(
                    f"EMA{self.ema_fast_p}>{self.ema_slow_p} cross, "
                    f"RSI={st.rsi.value:.1f}, ATR%={atr_pct * 100:.3f}"
                ),
            )
        return None

    def snapshot(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for sym, st in self.state.items():
            out[sym] = {
                "last_price": st.last_price,
                "ema_fast": st.ema_fast.value,
                "ema_slow": st.ema_slow.value,
                "rsi": st.rsi.value,
                "atr": st.atr.value,
                "bars_seen": st.bars_seen,
                "ready": st.ready(self.min_bars),
                "history": st.history[-120:],
            }
        return out
