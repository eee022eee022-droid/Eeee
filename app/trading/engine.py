"""Paper-trading execution engine.

The engine tracks a single cash balance in USDT and any number of open
positions (both LONG and SHORT). Fills are simulated at the latest
market price with a configurable slippage and taker fee. Stop-loss,
take-profit and a hard max-hold timer are enforced on every tick.

SHORT positions are simulated: we pay fees and realise PnL, but the
notional is never actually debited from the paper cash balance (as if
a perpetual-style margin account escrows it). Real spot accounts
cannot short without a margin facility — the dashboard makes this clear.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from ..config import Settings
from .storage import Storage


log = logging.getLogger("scalper.engine")


@dataclass
class OpenPosition:
    id: int
    symbol: str
    side: str
    qty: float
    entry_price: float
    stop_price: float
    target_price: float
    opened_ts: int
    entry_fee: float
    reason: str
    atr_at_entry: float = 0.0
    # Volatile, mutated in-place on every tick.
    last_mark: float = 0.0
    unrealized_pnl: float = 0.0
    # Extreme favourable price seen since entry. LONG: running max; SHORT: running min.
    # Stored as `highest_price` in SQLite for backwards compatibility.
    extreme_price: float = 0.0

    @property
    def dir_sign(self) -> int:
        return 1 if self.side == "LONG" else -1

    def mark_to_market(self, price: float) -> None:
        self.last_mark = price
        self.unrealized_pnl = (price - self.entry_price) * self.qty * self.dir_sign
        if self.side == "LONG":
            if price > self.extreme_price:
                self.extreme_price = price
        else:
            if self.extreme_price == 0.0 or price < self.extreme_price:
                self.extreme_price = price


@dataclass
class Account:
    balance_usdt: float
    initial_balance_usdt: float
    created_ts: int
    open_positions: dict[str, OpenPosition] = field(default_factory=dict)

    @property
    def equity_usdt(self) -> float:
        return self.balance_usdt + sum(
            p.unrealized_pnl for p in self.open_positions.values()
        )


class TradingEngine:
    """Owns the paper account and executes fills in response to ticks/signals."""

    def __init__(self, settings: Settings, storage: Storage) -> None:
        self.s = settings
        self.storage = storage
        self.account: Account | None = None
        self._last_close_ts: dict[str, int] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        now_ms = int(time.time() * 1000)
        balance = await self.storage.init(self.s.initial_balance_usdt, now_ms)
        acct_row = await self.storage.account()
        self.account = Account(
            balance_usdt=balance,
            initial_balance_usdt=float(
                acct_row.get("initial_balance_usdt", self.s.initial_balance_usdt)
            ),
            created_ts=int(acct_row.get("created_ts", now_ms)),
        )
        open_rows = await self.storage.open_positions()
        for row in open_rows:
            pos = OpenPosition(
                id=int(row["id"]),
                symbol=row["symbol"],
                side=row["side"],
                qty=float(row["qty"]),
                entry_price=float(row["entry_price"]),
                stop_price=float(row["stop_price"]),
                target_price=float(row["target_price"]),
                opened_ts=int(row["opened_ts"]),
                entry_fee=float(row["fees_usdt"] or 0.0),
                reason=row.get("reason") or "",
                atr_at_entry=float(row.get("atr_at_entry") or 0.0),
                extreme_price=float(row.get("highest_price") or row["entry_price"]),
            )
            pos.last_mark = pos.entry_price
            self.account.open_positions[pos.symbol] = pos
        log.info(
            "engine started: balance=%.2f open_positions=%d",
            self.account.balance_usdt,
            len(self.account.open_positions),
        )

    def _apply_slippage(self, price: float, side: str, opening: bool) -> float:
        bps = self.s.slippage_bps / 10_000.0
        if side == "LONG":
            # Longs buy up on entry and hit the bid on exit.
            return price * (1.0 + bps) if opening else price * (1.0 - bps)
        # Shorts hit the bid on entry (sell) and pay up on exit (buy back).
        return price * (1.0 - bps) if opening else price * (1.0 + bps)

    async def on_signal(
        self, symbol: str, side: str, price: float, atr: float, reason: str
    ) -> None:
        if self.account is None:
            return
        if side not in ("LONG", "SHORT"):
            return
        async with self._lock:
            if symbol in self.account.open_positions:
                return
            if len(self.account.open_positions) >= self.s.max_open_positions:
                return
            equity = self.account.equity_usdt
            risk_usd = equity * self.s.risk_per_trade
            stop_dist = atr * self.s.atr_stop_mult
            if stop_dist <= 0:
                return
            qty = risk_usd / stop_dist
            entry_price = self._apply_slippage(price, side, opening=True)
            notional = qty * entry_price
            if notional < self.s.min_notional_usdt:
                qty = self.s.min_notional_usdt / entry_price
                notional = qty * entry_price
            # Cap by available balance — even for paper shorts we want
            # position sizing to track the account, not explode.
            max_notional = self.account.balance_usdt * 0.95
            if notional > max_notional:
                qty = max_notional / entry_price
                notional = qty * entry_price
            if notional < self.s.min_notional_usdt:
                return
            fee = notional * self.s.taker_fee
            if side == "LONG":
                stop_price = entry_price - stop_dist
                target_price = entry_price + atr * self.s.atr_target_mult
                # Spot-style: buying the asset consumes cash.
                self.account.balance_usdt -= notional + fee
            else:
                stop_price = entry_price + stop_dist
                target_price = entry_price - atr * self.s.atr_target_mult
                # Paper short: no cash leaves the account on open (the
                # proceeds from the virtual borrow+sell net to zero).
                self.account.balance_usdt -= fee
            opened_ts = int(time.time() * 1000)

            await self.storage.set_balance(self.account.balance_usdt)
            pos_id = await self.storage.insert_open_position(
                {
                    "symbol": symbol,
                    "side": side,
                    "qty": qty,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "opened_ts": opened_ts,
                    "fees_usdt": fee,
                    "reason": reason,
                    "atr_at_entry": atr,
                    "highest_price": entry_price,
                }
            )
            pos = OpenPosition(
                id=pos_id,
                symbol=symbol,
                side=side,
                qty=qty,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                opened_ts=opened_ts,
                entry_fee=fee,
                reason=reason,
                atr_at_entry=atr,
                last_mark=entry_price,
                extreme_price=entry_price,
            )
            self.account.open_positions[symbol] = pos
            log.info(
                "OPEN %s %s %.6f @ %.4f SL=%.4f TP=%.4f notional=%.2f fee=%.4f",
                side,
                symbol,
                qty,
                entry_price,
                stop_price,
                target_price,
                notional,
                fee,
            )

    async def on_price(self, symbol: str, price: float) -> None:
        """Mark-to-market, ratchet trailing stop, and check exits."""
        if self.account is None:
            return
        pos = self.account.open_positions.get(symbol)
        if pos is None:
            return
        pos.mark_to_market(price)
        await self._maybe_trail(pos, price)
        now_ms = int(time.time() * 1000)
        exit_reason: str | None = None
        if pos.side == "LONG":
            if price <= pos.stop_price:
                exit_reason = "STOP"
            elif price >= pos.target_price:
                exit_reason = "TARGET"
        else:
            if price >= pos.stop_price:
                exit_reason = "STOP"
            elif price <= pos.target_price:
                exit_reason = "TARGET"
        if exit_reason is None and now_ms - pos.opened_ts >= self.s.max_hold_seconds * 1000:
            exit_reason = "TIME"
        if exit_reason is not None:
            await self._close(pos, price, exit_reason, now_ms)

    async def _maybe_trail(self, pos: OpenPosition, price: float) -> None:
        """Move the stop in the favourable direction (never back against us)."""
        atr = pos.atr_at_entry
        if atr <= 0:
            return
        gain = (price - pos.entry_price) * pos.dir_sign
        new_stop = pos.stop_price
        # Breakeven bump: cover fees + a sliver once we've seen some profit.
        if self.s.breakeven_atr > 0 and gain >= atr * self.s.breakeven_atr:
            if pos.side == "LONG":
                breakeven = pos.entry_price * (1.0 + 2.0 * self.s.taker_fee)
                if breakeven > new_stop:
                    new_stop = breakeven
            else:
                breakeven = pos.entry_price * (1.0 - 2.0 * self.s.taker_fee)
                if breakeven < new_stop:
                    new_stop = breakeven
        # Trailing ratchet: once well in profit, chase the extreme.
        if self.s.trail_activate_atr > 0 and gain >= atr * self.s.trail_activate_atr:
            if pos.side == "LONG":
                trail = pos.extreme_price - atr * self.s.trail_atr
                if trail > new_stop:
                    new_stop = trail
            else:
                trail = pos.extreme_price + atr * self.s.trail_atr
                if trail < new_stop:
                    new_stop = trail
        improved = (
            (pos.side == "LONG" and new_stop > pos.stop_price)
            or (pos.side == "SHORT" and new_stop < pos.stop_price)
        )
        if improved:
            pos.stop_price = new_stop
            try:
                await self.storage.update_trailing(
                    pos.id, pos.stop_price, pos.extreme_price
                )
            except Exception as exc:  # noqa: BLE001 - persistence best-effort
                log.debug("trailing persist failed: %s", exc)

    async def _close(
        self, pos: OpenPosition, price: float, reason: str, now_ms: int
    ) -> None:
        async with self._lock:
            if self.account is None:
                return
            if pos.symbol not in self.account.open_positions:
                return
            exit_price = self._apply_slippage(price, pos.side, opening=False)
            notional_out = pos.qty * exit_price
            exit_fee = notional_out * self.s.taker_fee
            gross = (exit_price - pos.entry_price) * pos.qty * pos.dir_sign
            pnl = gross - pos.entry_fee - exit_fee
            if pos.side == "LONG":
                # Unwind spot buy: cash comes back, minus exit fee.
                self.account.balance_usdt += notional_out - exit_fee
            else:
                # Paper short: realised PnL hits cash directly, minus exit fee.
                self.account.balance_usdt += gross - exit_fee
            total_fees = pos.entry_fee + exit_fee
            await self.storage.set_balance(self.account.balance_usdt)
            await self.storage.close_position(
                pos.id, exit_price, reason, pnl, total_fees, now_ms
            )
            self.account.open_positions.pop(pos.symbol, None)
            log.info(
                "CLOSE %s qty=%.6f entry=%.4f exit=%.4f reason=%s pnl=%.4f",
                pos.symbol,
                pos.qty,
                pos.entry_price,
                exit_price,
                reason,
                pnl,
            )

    async def force_close_all(self, price_by_symbol: dict[str, float]) -> None:
        if self.account is None:
            return
        now_ms = int(time.time() * 1000)
        for sym, pos in list(self.account.open_positions.items()):
            price = price_by_symbol.get(sym, pos.last_mark or pos.entry_price)
            await self._close(pos, price, "MANUAL", now_ms)

    async def reset(self) -> None:
        """Wipe all state back to initial balance. Exposed via API."""
        async with self._lock:
            import aiosqlite

            async with aiosqlite.connect(self.storage.db_path) as db:
                await db.execute("DELETE FROM positions")
                await db.execute("DELETE FROM equity")
                await db.execute(
                    "UPDATE account SET balance_usdt = initial_balance_usdt WHERE id = 1"
                )
                await db.commit()
            if self.account is not None:
                self.account.balance_usdt = self.account.initial_balance_usdt
                self.account.open_positions.clear()

    def snapshot(self) -> dict[str, Any]:
        if self.account is None:
            return {}
        return {
            "balance_usdt": self.account.balance_usdt,
            "initial_balance_usdt": self.account.initial_balance_usdt,
            "equity_usdt": self.account.equity_usdt,
            "open_pnl_usdt": sum(
                p.unrealized_pnl for p in self.account.open_positions.values()
            ),
            "open_positions": [
                {
                    "id": p.id,
                    "symbol": p.symbol,
                    "side": p.side,
                    "qty": p.qty,
                    "entry_price": p.entry_price,
                    "stop_price": p.stop_price,
                    "target_price": p.target_price,
                    "opened_ts": p.opened_ts,
                    "last_mark": p.last_mark,
                    "unrealized_pnl": p.unrealized_pnl,
                    "reason": p.reason,
                }
                for p in self.account.open_positions.values()
            ],
        }
