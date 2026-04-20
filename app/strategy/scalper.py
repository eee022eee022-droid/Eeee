"""Two-way micro-scalping strategy.

On each closed 1m candle we update EMA/RSI/ATR and fire at most one
signal per candle. Signals are generated in two regimes:

    1. Trend-continuation (the workhorse):
       - LONG  when fast>slow and RSI is in the pullback/momentum band.
       - SHORT when fast<slow and RSI is in the bounce/momentum band.
    2. Mean-reversion bounce (fires less often, catches V-shapes):
       - LONG  when RSI crosses up through `rsi_oversold`.
       - SHORT when RSI crosses down through `rsi_overbought`.

In both cases we require non-trivial ATR (ignore dead ranges where fees
would dominate the move) and a stricter ATR% floor than before so a
signal isn't raised on symbols with 0.01% ATR (TRX, DOGE, etc.).

SHORT fills are simulated on spot — real spot accounts cannot actually
sell short without margin. The README and PR description call this out.
The engine treats a SHORT as a virtual borrow: we sell qty at entry,
buy it back at exit, and credit the difference.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .indicators import ATR, EMA, RSI


Side = Literal["LONG", "SHORT"]


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
    prev_rsi: float | None = None
    prev_fast: float | None = None
    prev_slow: float | None = None
    last_price: float | None = None
    last_close_ms: int = 0
    bars_seen: int = 0
    last_signal_side: Side | None = None
    last_signal_bar: int = -10_000
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
        rsi_short_min: float = 28.0,
        rsi_short_max: float = 55.0,
        rsi_oversold: float = 32.0,
        rsi_overbought: float = 68.0,
        atr_pct_min: float = 0.0005,
        same_side_cooldown_bars: int = 3,
    ) -> None:
        self.ema_fast_p = ema_fast
        self.ema_slow_p = ema_slow
        self.rsi_long_min = rsi_long_min
        self.rsi_long_max = rsi_long_max
        self.rsi_short_min = rsi_short_min
        self.rsi_short_max = rsi_short_max
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.atr_pct_min = atr_pct_min
        self.same_side_cooldown_bars = same_side_cooldown_bars
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
        st.prev_rsi = st.rsi.value
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
        if len(st.history) > 240:
            del st.history[: len(st.history) - 240]

        if not st.ready(self.min_bars):
            return None
        assert st.ema_fast.value is not None and st.ema_slow.value is not None
        assert st.rsi.value is not None and st.atr.value is not None

        atr_pct = st.atr.value / close if close > 0 else 0.0
        if atr_pct < self.atr_pct_min:
            return None

        fast_above = st.ema_fast.value > st.ema_slow.value
        rsi = st.rsi.value
        prev_rsi = st.prev_rsi

        # --- LONG candidates ---------------------------------------------
        long_trend = fast_above and self.rsi_long_min <= rsi <= self.rsi_long_max
        long_bounce = (
            prev_rsi is not None
            and prev_rsi <= self.rsi_oversold
            and rsi > self.rsi_oversold
        )

        # --- SHORT candidates --------------------------------------------
        short_trend = (
            (not fast_above)
            and self.rsi_short_min <= rsi <= self.rsi_short_max
        )
        short_reject = (
            prev_rsi is not None
            and prev_rsi >= self.rsi_overbought
            and rsi < self.rsi_overbought
        )

        # Pick the most specific signal; prefer bounce/reject (reversals)
        # over trend-continuation because reversals are rarer and have
        # cleaner setups. If both long and short fire on the same bar
        # (extremely unlikely), defer to the trend direction.
        side: Side | None = None
        reason_parts: list[str] = []

        if long_bounce and not short_trend:
            side = "LONG"
            reason_parts.append(f"RSI bounce {prev_rsi:.1f}->{rsi:.1f}")
        elif short_reject and not long_trend:
            side = "SHORT"
            reason_parts.append(f"RSI rejection {prev_rsi:.1f}->{rsi:.1f}")
        elif long_trend and not short_trend:
            side = "LONG"
            reason_parts.append(f"trend up, RSI={rsi:.1f}")
        elif short_trend and not long_trend:
            side = "SHORT"
            reason_parts.append(f"trend down, RSI={rsi:.1f}")

        if side is None:
            return None

        # Don't fire the same side again immediately — wait a few bars.
        if (
            side == st.last_signal_side
            and st.bars_seen - st.last_signal_bar < self.same_side_cooldown_bars
        ):
            return None

        st.last_signal_side = side
        st.last_signal_bar = st.bars_seen

        reason_parts.append(f"ATR%={atr_pct * 100:.3f}")
        return Signal(
            side=side,
            price=close,
            atr=st.atr.value,
            reason="; ".join(reason_parts),
        )

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
                "last_signal_side": st.last_signal_side,
            }
        return out
