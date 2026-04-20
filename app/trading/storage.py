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

CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    category TEXT NOT NULL,
    external_id TEXT NOT NULL UNIQUE,
    published_ts INTEGER NOT NULL,
    fetched_ts INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS news_published_idx ON news(published_ts DESC);
CREATE INDEX IF NOT EXISTS news_exchange_idx ON news(exchange, published_ts DESC);
"""


class Storage:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    async def reset(self) -> None:
        """Blow away the persisted paper account + trade history.

        Useful when the bot's cash state has been corrupted by earlier
        buggy logic and we want a clean slate without redeploying.
        """
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def init(self, initial_balance: float, now_ms: int) -> float:
        if os.getenv("SCALPER_RESET_ON_START", "").strip() in ("1", "true", "yes"):
            await self.reset()
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            # Forward-compatible schema upgrades.
            for ddl in (
                "ALTER TABLE positions ADD COLUMN atr_at_entry REAL",
                "ALTER TABLE positions ADD COLUMN highest_price REAL",
            ):
                try:
                    await db.execute(ddl)
                except aiosqlite.OperationalError:
                    pass  # column already exists
            await db.commit()
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
                " target_price, opened_ts, fees_usdt, reason, atr_at_entry,"
                " highest_price)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                    pos.get("atr_at_entry", 0.0),
                    pos.get("highest_price", pos["entry_price"]),
                ),
            )
            await db.commit()
            return int(cur.lastrowid or 0)

    async def update_trailing(
        self, position_id: int, stop_price: float, highest_price: float
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE positions SET stop_price = ?, highest_price = ? WHERE id = ?",
                (stop_price, highest_price, position_id),
            )
            await db.commit()

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

    async def insert_news(self, items: list[dict[str, Any]], fetched_ts: int) -> int:
        """Insert new items; ignore ones we've already seen via external_id."""
        if not items:
            return 0
        new_count = 0
        async with aiosqlite.connect(self.db_path) as db:
            for it in items:
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO news"
                        "(exchange, title, url, category, external_id,"
                        " published_ts, fetched_ts)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            it["exchange"],
                            it["title"],
                            it["url"],
                            it.get("category", ""),
                            it["external_id"],
                            int(it.get("published_ts") or 0),
                            fetched_ts,
                        ),
                    )
                except aiosqlite.Error:
                    continue
                if db.total_changes and db.total_changes > new_count:
                    new_count = db.total_changes
            await db.commit()
        return new_count

    async def news(
        self,
        limit: int = 200,
        exchange: str | None = None,
        q: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM news"
        clauses: list[str] = []
        args: list[Any] = []
        if exchange:
            clauses.append("exchange = ?")
            args.append(exchange)
        if q:
            clauses.append("LOWER(title) LIKE ?")
            args.append(f"%{q.lower()}%")
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY published_ts DESC, id DESC LIMIT ?"
        args.append(limit)
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, args)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def news_stats(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT exchange, COUNT(*) AS n, MAX(published_ts) AS last_ts"
                " FROM news GROUP BY exchange"
            )
            rows = await cur.fetchall()
            by_ex = {
                r["exchange"]: {"count": int(r["n"]), "last_ts": int(r["last_ts"] or 0)}
                for r in rows
            }
            cur = await db.execute("SELECT COUNT(*) FROM news")
            row = await cur.fetchone()
            total = int(row[0] if row else 0)
        return {"total": total, "by_exchange": by_ex}

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
