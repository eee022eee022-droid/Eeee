"""SQLite persistence for the paper-trading engine."""
from __future__ import annotations

import json
import os
from typing import Any

import aiosqlite


SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    balance_usdt REAL NOT NULL,
    initial_balance_usdt REAL NOT NULL,
    created_ts INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    qty REAL NOT NULL,
    entry_price REAL NOT NULL,
    stop_price REAL NOT NULL,
    target_price REAL NOT NULL,
    opened_ts INTEGER NOT NULL,
    closed_ts INTEGER,
    exit_price REAL,
    exit_reason TEXT,
    pnl_usdt REAL,
    fees_usdt REAL NOT NULL DEFAULT 0,
    reason TEXT
);

CREATE INDEX IF NOT EXISTS positions_open_idx
    ON positions(symbol, closed_ts);

CREATE TABLE IF NOT EXISTS equity (
    ts INTEGER PRIMARY KEY,
    equity_usdt REAL NOT NULL,
    balance_usdt REAL NOT NULL,
    open_pnl_usdt REAL NOT NULL
);
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    async def init(self, initial_balance: float, now_ms: int) -> float:
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            cur = await db.execute(
                "SELECT balance_usdt FROM account WHERE id = 1"
            )
            row = await cur.fetchone()
            if row is None:
                await db.execute(
                    "INSERT INTO account(id, balance_usdt, initial_balance_usdt, created_ts)"
                    " VALUES (1, ?, ?, ?)",
                    (initial_balance, initial_balance, now_ms),
                )
                await db.commit()
                return initial_balance
            return float(row[0])

    async def set_balance(self, balance: float) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE account SET balance_usdt = ? WHERE id = 1", (balance,)
            )
            await db.commit()

    async def account(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT balance_usdt, initial_balance_usdt, created_ts"
                " FROM account WHERE id = 1"
            )
            row = await cur.fetchone()
            if row is None:
                return {}
            return {
                "balance_usdt": float(row[0]),
                "initial_balance_usdt": float(row[1]),
                "created_ts": int(row[2]),
            }

    async def insert_open_position(self, pos: dict[str, Any]) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "INSERT INTO positions(symbol, side, qty, entry_price, stop_price,"
                " target_price, opened_ts, fees_usdt, reason)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    pos["symbol"],
                    pos["side"],
                    pos["qty"],
                    pos["entry_price"],
                    pos["stop_price"],
                    pos["target_price"],
                    pos["opened_ts"],
                    pos.get("fees_usdt", 0.0),
                    pos.get("reason", ""),
                ),
            )
            await db.commit()
            return int(cur.lastrowid or 0)

    async def close_position(
        self,
        position_id: int,
        exit_price: float,
        exit_reason: str,
        pnl: float,
        fees: float,
        closed_ts: int,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE positions SET closed_ts = ?, exit_price = ?, exit_reason = ?,"
                " pnl_usdt = ?, fees_usdt = ? WHERE id = ?",
                (closed_ts, exit_price, exit_reason, pnl, fees, position_id),
            )
            await db.commit()

    async def open_positions(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM positions WHERE closed_ts IS NULL"
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def recent_trades(self, limit: int = 50) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM positions WHERE closed_ts IS NOT NULL"
                " ORDER BY closed_ts DESC LIMIT ?",
                (limit,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def stats(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            cur = await db.execute(
                "SELECT COUNT(*), SUM(pnl_usdt),"
                " SUM(CASE WHEN pnl_usdt > 0 THEN 1 ELSE 0 END),"
                " SUM(CASE WHEN pnl_usdt <= 0 THEN 1 ELSE 0 END)"
                " FROM positions WHERE closed_ts IS NOT NULL"
            )
            row = await cur.fetchone()
            total = int(row[0] or 0)
            pnl = float(row[1] or 0.0)
            wins = int(row[2] or 0)
            losses = int(row[3] or 0)
        return {
            "closed_trades": total,
            "realized_pnl_usdt": pnl,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total) if total else 0.0,
        }

    async def append_equity(
        self, ts: int, equity: float, balance: float, open_pnl: float
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO equity(ts, equity_usdt, balance_usdt, open_pnl_usdt)"
                " VALUES (?, ?, ?, ?)",
                (ts, equity, balance, open_pnl),
            )
            await db.commit()

    async def equity_curve(self, limit: int = 720) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT ts, equity_usdt, balance_usdt, open_pnl_usdt FROM ("
                " SELECT * FROM equity ORDER BY ts DESC LIMIT ?"
                ") ORDER BY ts ASC",
                (limit,),
            )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=float, separators=(",", ":"))
