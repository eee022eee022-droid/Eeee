"""Runtime configuration for the scalper bot."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_list(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [s.strip().upper() for s in raw.split(",") if s.strip()]


@dataclass
class Settings:
    """Configuration loaded from environment variables with sensible defaults."""

    # Market universe. Kept compact to reduce noise and API load.
    # Symbols are given in OKX form (BASE-QUOTE). BTCUSDT-style inputs are
    # auto-normalized by the feed.
    # Top-15 liquid spot USDT pairs on OKX (stables, gold-pegged and memecoin
    # noise excluded). Override with SCALPER_SYMBOLS="BTC-USDT,ETH-USDT,...".
    # Mix of high-liquidity anchors and high-volatility movers on OKX spot.
    # Dead ranges (ADA, TRX, LINK, UNI, DOT, BNB, LTC) were dropped because
    # their 1m ATR is below fee-sensitive thresholds on calm days — a
    # scalper cannot generate edge on them. The dynamic picker (see
    # `dynamic_symbols`) can refresh the volatile half at runtime.
    symbols: list[str] = field(
        default_factory=lambda: _env_list(
            "SCALPER_SYMBOLS",
            [
                "BTC-USDT",
                "ETH-USDT",
                "SOL-USDT",
                "DOGE-USDT",
                "XRP-USDT",
                "PEPE-USDT",
                "ORDI-USDT",
                "AAVE-USDT",
                "ZEC-USDT",
                "HYPE-USDT",
                "SPK-USDT",
                "OFC-USDT",
                "BASED-USDT",
                "CORE-USDT",
                "MERL-USDT",
            ],
        )
    )
    # When true, override the static list at startup with the top-N OKX
    # USDT pairs scored by (24h volume in USDT) * (abs 24h %% change).
    # This keeps the universe focused on what's actually scalpable right
    # now rather than on a stale hand-picked list.
    dynamic_symbols: bool = _env_int("SCALPER_DYNAMIC_SYMBOLS", 1) == 1
    dynamic_symbols_n: int = _env_int("SCALPER_DYNAMIC_N", 15)
    dynamic_min_volume_usdt: float = _env_float(
        "SCALPER_DYNAMIC_MIN_VOLUME_USDT", 5_000_000.0
    )
    # Anchor symbols that are always included even if they don't score
    # highly — useful so the dashboard always shows BTC/ETH alongside the
    # hot movers.
    dynamic_anchor_symbols: list[str] = field(
        default_factory=lambda: _env_list(
            "SCALPER_DYNAMIC_ANCHORS", ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
        )
    )

    # Paper account.
    initial_balance_usdt: float = _env_float("SCALPER_INITIAL_BALANCE", 500.0)
    taker_fee: float = _env_float("SCALPER_TAKER_FEE", 0.001)  # 0.10%
    slippage_bps: float = _env_float("SCALPER_SLIPPAGE_BPS", 2.0)  # 2 bps

    # Strategy: short-term scalper on 1m candles.
    kline_interval: str = os.getenv("SCALPER_INTERVAL", "1m")
    ema_fast: int = _env_int("SCALPER_EMA_FAST", 9)
    ema_slow: int = _env_int("SCALPER_EMA_SLOW", 21)
    rsi_period: int = _env_int("SCALPER_RSI_PERIOD", 14)
    # LONG momentum band: tight enough to be actual momentum, not noise.
    # Naive (42,72) firehosed 29 trades in 6 min with 7% win-rate.
    rsi_long_min: float = _env_float("SCALPER_RSI_LONG_MIN", 54.0)
    rsi_long_max: float = _env_float("SCALPER_RSI_LONG_MAX", 68.0)
    # SHORT momentum band, mirror image.
    rsi_short_min: float = _env_float("SCALPER_RSI_SHORT_MIN", 32.0)
    rsi_short_max: float = _env_float("SCALPER_RSI_SHORT_MAX", 46.0)
    # Mean-reversion bounce thresholds (currently disabled in scalper.py
    # because mean-reversion scalps on 1m alts lose to persistence).
    rsi_oversold: float = _env_float("SCALPER_RSI_OVERSOLD", 32.0)
    rsi_overbought: float = _env_float("SCALPER_RSI_OVERBOUGHT", 68.0)
    # Minimum ATR%% per bar. Below this fees dominate the expected move.
    # Raised from 5bp to 12bp to avoid dead-range symbols (BTC/ETH on
    # slow days) where a 2.2*ATR target is smaller than round-trip fees.
    atr_pct_min: float = _env_float("SCALPER_ATR_PCT_MIN", 0.0012)
    # Bars to wait before firing the same side again on a symbol.
    same_side_cooldown_bars: int = _env_int("SCALPER_SAME_SIDE_COOLDOWN_BARS", 5)
    # Minimum EMA fast/slow separation (%% of price). Filters out chop.
    ema_min_spread_pct: float = _env_float("SCALPER_EMA_MIN_SPREAD_PCT", 0.0015)
    atr_period: int = _env_int("SCALPER_ATR_PERIOD", 14)
    atr_stop_mult: float = _env_float("SCALPER_ATR_STOP", 1.1)
    atr_target_mult: float = _env_float("SCALPER_ATR_TARGET", 2.2)

    # Trailing stop: after price moves +activate*ATR in our favour, the stop
    # is ratcheted to (highest_price - trail*ATR). 0 disables trailing.
    trail_activate_atr: float = _env_float("SCALPER_TRAIL_ACTIVATE_ATR", 0.8)
    trail_atr: float = _env_float("SCALPER_TRAIL_ATR", 0.7)
    # Breakeven move: after price clears +breakeven_atr, raise stop to
    # entry + entry_fee-equivalent, so losing the rest of the trade is
    # essentially free. 0 disables.
    breakeven_atr: float = _env_float("SCALPER_BREAKEVEN_ATR", 0.4)

    # Risk. Lowered from 0.75%% to 0.30%% per trade given the higher-
    # volatility universe — losing streaks chew through equity fast on
    # 0.75%% sizing.
    risk_per_trade: float = _env_float("SCALPER_RISK_PCT", 0.003)
    max_open_positions: int = _env_int("SCALPER_MAX_POS", 3)
    min_notional_usdt: float = _env_float("SCALPER_MIN_NOTIONAL", 15.0)
    cooldown_seconds: int = _env_int("SCALPER_COOLDOWN", 30)
    max_hold_seconds: int = _env_int("SCALPER_MAX_HOLD", 12 * 60)

    # Storage.
    data_dir: str = os.getenv("SCALPER_DATA_DIR", "/data")
    db_filename: str = os.getenv("SCALPER_DB_FILE", "scalper.db")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, self.db_filename)


settings = Settings()
