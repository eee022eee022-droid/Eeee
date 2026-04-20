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
    symbols: list[str] = field(
        default_factory=lambda: _env_list(
            "SCALPER_SYMBOLS", ["BTC-USDT", "ETH-USDT", "SOL-USDT"]
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
    rsi_long_max: float = _env_float("SCALPER_RSI_LONG_MAX", 70.0)
    rsi_long_min: float = _env_float("SCALPER_RSI_LONG_MIN", 45.0)
    atr_period: int = _env_int("SCALPER_ATR_PERIOD", 14)
    atr_stop_mult: float = _env_float("SCALPER_ATR_STOP", 1.2)
    atr_target_mult: float = _env_float("SCALPER_ATR_TARGET", 1.8)

    # Risk.
    risk_per_trade: float = _env_float("SCALPER_RISK_PCT", 0.01)  # 1% of equity
    max_open_positions: int = _env_int("SCALPER_MAX_POS", 2)
    min_notional_usdt: float = _env_float("SCALPER_MIN_NOTIONAL", 15.0)
    cooldown_seconds: int = _env_int("SCALPER_COOLDOWN", 60)
    max_hold_seconds: int = _env_int("SCALPER_MAX_HOLD", 20 * 60)

    # Storage.
    data_dir: str = os.getenv("SCALPER_DATA_DIR", "/data")
    db_filename: str = os.getenv("SCALPER_DB_FILE", "scalper.db")

    @property
    def db_path(self) -> str:
        return os.path.join(self.data_dir, self.db_filename)


settings = Settings()
