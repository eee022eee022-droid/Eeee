"""Incremental technical indicators used by the scalping strategy.

All indicators are updated candle-by-candle so we can react the moment a
candle closes on the Binance kline stream.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class EMA:
    period: int
    value: float | None = None
    _alpha: float = field(init=False)

    def __post_init__(self) -> None:
        self._alpha = 2.0 / (self.period + 1.0)

    def update(self, price: float) -> float | None:
        if self.value is None:
            self.value = price
        else:
            self.value = self._alpha * price + (1.0 - self._alpha) * self.value
        return self.value


@dataclass
class RSI:
    period: int = 14
    _prev_close: float | None = None
    _avg_gain: float | None = None
    _avg_loss: float | None = None
    _count: int = 0
    value: float | None = None

    def update(self, price: float) -> float | None:
        if self._prev_close is None:
            self._prev_close = price
            return None
        change = price - self._prev_close
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        self._count += 1
        if self._count <= self.period:
            self._avg_gain = (self._avg_gain or 0.0) + gain / self.period
            self._avg_loss = (self._avg_loss or 0.0) + loss / self.period
            if self._count == self.period:
                self._compute()
        else:
            assert self._avg_gain is not None and self._avg_loss is not None
            self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
            self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period
            self._compute()
        self._prev_close = price
        return self.value

    def _compute(self) -> None:
        assert self._avg_gain is not None and self._avg_loss is not None
        if self._avg_loss == 0:
            self.value = 100.0
        else:
            rs = self._avg_gain / self._avg_loss
            self.value = 100.0 - (100.0 / (1.0 + rs))


@dataclass
class ATR:
    period: int = 14
    _prev_close: float | None = None
    _trs: deque[float] = field(default_factory=deque)
    value: float | None = None

    def update(self, high: float, low: float, close: float) -> float | None:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close),
            )
        self._prev_close = close
        if self.value is None:
            self._trs.append(tr)
            if len(self._trs) >= self.period:
                self.value = sum(self._trs) / self.period
                self._trs.clear()
        else:
            self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value
