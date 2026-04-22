"""Paper-trading book.

Trades are opened on click from the frontend, stored on disk (so they
survive Fly machine restarts) and marked up with live mark price + PnL.
TP (+3% on price) and SL (-2% on price) are evaluated every time the
book is listed — the frontend polls every few seconds, so we piggy-back
on that instead of running a separate heartbeat.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx

from exchanges import get_exchange

CloseReason = Literal["tp", "sl", "manual"]

DEFAULT_COLLATERAL = 100.0
DEFAULT_LEVERAGE = 3.0
DEFAULT_TP_PCT = 3.0  # close when mark is >= entry * (1 + 3%)
DEFAULT_SL_PCT = 2.0  # close when mark is <= entry * (1 - 2%)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Trade:
    id: str
    symbol: str
    exchange: str
    side: str
    entry_price: float
    collateral: float
    leverage: float
    tp_pct: float
    sl_pct: float
    opened_at: str
    status: str = "open"  # open | closed
    mark_price: float | None = None
    close_price: float | None = None
    closed_at: str | None = None
    close_reason: CloseReason | None = None


class PriceCache:
    """Tiny per-symbol price cache shared across trade snapshots."""

    def __init__(self, ttl_s: float = 5.0) -> None:
        self.ttl_s = ttl_s
        self._cache: dict[tuple[str, str], tuple[float, float]] = {}
        self._lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient, exchange_id: str, symbol: str) -> float | None:
        import time as _t

        key = (exchange_id, symbol)
        hit = self._cache.get(key)
        if hit and _t.time() - hit[0] < self.ttl_s:
            return hit[1]

        async with self._lock:
            hit = self._cache.get(key)
            if hit and _t.time() - hit[0] < self.ttl_s:
                return hit[1]
            exchange = get_exchange(exchange_id)
            try:
                price = await exchange.get_price(client, symbol)  # type: ignore[attr-defined]
            except Exception:
                return hit[1] if hit else None
            self._cache[key] = (_t.time(), price)
            return price


class PaperBook:
    def __init__(self, data_path: Path) -> None:
        self.data_path = data_path
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.trades: dict[str, Trade] = {}
        self._lock = asyncio.Lock()
        self._prices = PriceCache()
        self._load()

    # ---------- persistence ----------
    def _load(self) -> None:
        if not self.data_path.exists():
            return
        try:
            raw = json.loads(self.data_path.read_text() or "[]")
        except json.JSONDecodeError:
            return
        for t in raw:
            t.pop("mark_price", None)  # mark is transient
            self.trades[t["id"]] = Trade(**t)

    def _save(self) -> None:
        serialisable = []
        for t in self.trades.values():
            d = asdict(t)
            d.pop("mark_price", None)
            serialisable.append(d)
        tmp = self.data_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(serialisable, indent=2))
        tmp.replace(self.data_path)

    # ---------- mutations ----------
    async def open_trade(
        self,
        *,
        symbol: str,
        exchange_id: str,
        side: str = "long",
        collateral: float = DEFAULT_COLLATERAL,
        leverage: float = DEFAULT_LEVERAGE,
        tp_pct: float = DEFAULT_TP_PCT,
        sl_pct: float = DEFAULT_SL_PCT,
    ) -> Trade:
        if side != "long":
            raise ValueError("only long side is supported in paper mode")
        async with httpx.AsyncClient() as client:
            entry = await self._prices.get(client, exchange_id, symbol)
        if not entry or entry <= 0:
            raise RuntimeError(f"could not fetch mark price for {symbol} on {exchange_id}")

        trade = Trade(
            id=uuid.uuid4().hex[:12],
            symbol=symbol,
            exchange=exchange_id,
            side=side,
            entry_price=float(entry),
            collateral=float(collateral),
            leverage=float(leverage),
            tp_pct=float(tp_pct),
            sl_pct=float(sl_pct),
            opened_at=_now(),
            mark_price=float(entry),
        )
        async with self._lock:
            self.trades[trade.id] = trade
            self._save()
        return trade

    async def close_trade(
        self, trade_id: str, *, reason: CloseReason = "manual"
    ) -> Trade:
        async with self._lock:
            trade = self.trades.get(trade_id)
            if not trade:
                raise KeyError(trade_id)
            if trade.status == "closed":
                return trade

            async with httpx.AsyncClient() as client:
                price = await self._prices.get(client, trade.exchange, trade.symbol)
            price = price if price and price > 0 else trade.entry_price

            trade.status = "closed"
            trade.close_price = float(price)
            trade.closed_at = _now()
            trade.close_reason = reason
            trade.mark_price = float(price)
            self._save()
            return trade

    # ---------- snapshot ----------
    async def snapshot(self) -> dict:
        """Refresh marks for every open trade, auto-close TP/SL hits, return
        the full book plus aggregate stats."""
        open_trades = [t for t in self.trades.values() if t.status == "open"]
        symbols_by_exchange: dict[str, set[str]] = {}
        for t in open_trades:
            symbols_by_exchange.setdefault(t.exchange, set()).add(t.symbol)

        async with httpx.AsyncClient() as client:
            async def _fetch_all() -> None:
                tasks = []
                for ex_id, syms in symbols_by_exchange.items():
                    for sym in syms:
                        tasks.append(self._prices.get(client, ex_id, sym))
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

            await _fetch_all()

            async with self._lock:
                for t in list(open_trades):
                    mark = await self._prices.get(client, t.exchange, t.symbol)
                    if mark is None:
                        continue
                    t.mark_price = float(mark)
                    tp = t.entry_price * (1 + t.tp_pct / 100)
                    sl = t.entry_price * (1 - t.sl_pct / 100)
                    if mark >= tp:
                        t.status = "closed"
                        t.close_price = float(mark)
                        t.closed_at = _now()
                        t.close_reason = "tp"
                    elif mark <= sl:
                        t.status = "closed"
                        t.close_price = float(mark)
                        t.closed_at = _now()
                        t.close_reason = "sl"
                if open_trades:
                    self._save()

        opens: list[dict] = []
        closes: list[dict] = []
        total_pnl = 0.0
        wins = 0
        for t in self.trades.values():
            d = _serialise(t)
            total_pnl += d["pnlUsd"]
            if t.status == "closed":
                closes.append(d)
                if d["pnlUsd"] > 0:
                    wins += 1
            else:
                opens.append(d)

        opens.sort(key=lambda d: d["openedAt"], reverse=True)
        closes.sort(key=lambda d: d["closedAt"] or "", reverse=True)
        closed_count = len(closes)

        return {
            "open": opens,
            "closed": closes,
            "stats": {
                "openCount": len(opens),
                "closedCount": closed_count,
                "winCount": wins,
                "winRate": round(wins / closed_count * 100, 1) if closed_count else 0.0,
                "totalPnlUsd": round(total_pnl, 2),
            },
        }


def _serialise(t: Trade) -> dict:
    price = t.close_price if t.status == "closed" else (t.mark_price or t.entry_price)
    ret = (price / t.entry_price - 1) if t.entry_price else 0.0
    pnl_pct = ret * t.leverage * 100
    pnl_usd = t.collateral * ret * t.leverage
    return {
        "id": t.id,
        "symbol": t.symbol,
        "exchange": t.exchange,
        "side": t.side,
        "entryPrice": t.entry_price,
        "markPrice": float(price),
        "closePrice": t.close_price,
        "collateral": t.collateral,
        "leverage": t.leverage,
        "tpPct": t.tp_pct,
        "slPct": t.sl_pct,
        "openedAt": t.opened_at,
        "closedAt": t.closed_at,
        "closeReason": t.close_reason,
        "status": t.status,
        "pnlPct": round(pnl_pct, 2),
        "pnlUsd": round(pnl_usd, 2),
    }


def _env_data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", "/data"))


def make_book() -> PaperBook:
    data_dir = _env_data_dir()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        data_dir = Path(__file__).parent / ".data"
        data_dir.mkdir(parents=True, exist_ok=True)
    return PaperBook(data_dir / "trades.json")
