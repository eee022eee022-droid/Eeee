"""FastAPI application wiring feed + strategy + engine + dashboard."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import httpx

from .config import settings
from .news.collector import NewsCollector
from .strategy.scalper import Scalper
from .trading.engine import TradingEngine
from .trading.feed import OkxFeed
from .trading.storage import Storage


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("scalper.main")


async def _pick_dynamic_symbols() -> list[str]:
    """Pick top-N OKX USDT spot pairs by (volume * |24h change|)."""
    stables = {
        "USDC-USDT", "USDT-USDT", "FDUSD-USDT", "TUSD-USDT", "DAI-USDT",
        "PYUSD-USDT", "USDP-USDT", "USDE-USDT", "USDS-USDT", "USDG-USDT",
        "XAUT-USDT",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get("https://www.okx.com/api/v5/market/tickers?instType=SPOT")
            data = r.json().get("data", [])
    except Exception as exc:  # noqa: BLE001
        log.warning("dynamic symbols fetch failed: %s", exc)
        return []
    scored: list[tuple[float, str]] = []
    for row in data:
        sym = row.get("instId", "")
        if not sym.endswith("-USDT") or sym in stables:
            continue
        try:
            last = float(row.get("last") or 0.0)
            open24 = float(row.get("open24h") or 0.0)
            vol_q = float(row.get("volCcy24h") or 0.0)
        except (TypeError, ValueError):
            continue
        if last <= 0 or open24 <= 0:
            continue
        if vol_q < settings.dynamic_min_volume_usdt:
            continue
        pct = abs(last - open24) / open24 * 100.0
        scored.append(((vol_q / 1e6) * pct, sym))
    scored.sort(reverse=True)
    picked: list[str] = []
    seen: set[str] = set()
    for anchor in settings.dynamic_anchor_symbols:
        if anchor and anchor not in seen:
            picked.append(anchor)
            seen.add(anchor)
    for _, sym in scored:
        if sym in seen:
            continue
        picked.append(sym)
        seen.add(sym)
        if len(picked) >= settings.dynamic_symbols_n:
            break
    return picked


class Bot:
    def __init__(self) -> None:
        self.storage = Storage(settings.db_path)
        self.engine = TradingEngine(settings, self.storage)
        self.news = NewsCollector(self.storage)
        self.active_symbols: list[str] = list(settings.symbols)
        self.strategy: Scalper | None = None
        self.feed: OkxFeed | None = None
        self.last_tick: dict[str, tuple[float, int]] = {}
        self.started_ts: int = 0
        self._cooldown_until: dict[str, int] = {}
        self._equity_task: asyncio.Task | None = None
        self._feed_task: asyncio.Task | None = None
        self._news_task: asyncio.Task | None = None
        self._candle_poll_task: asyncio.Task | None = None
        # Backfill replays historical candles through the strategy to seed
        # indicators. Any signals raised during that replay are stale and
        # must NOT be executed by the paper-trading engine.
        self._warmup = True

    def _build_strategy_and_feed(self, symbols: list[str]) -> None:
        self.active_symbols = symbols
        self.strategy = Scalper(
            symbols=symbols,
            ema_fast=settings.ema_fast,
            ema_slow=settings.ema_slow,
            rsi_period=settings.rsi_period,
            atr_period=settings.atr_period,
            rsi_long_min=settings.rsi_long_min,
            rsi_long_max=settings.rsi_long_max,
            rsi_short_min=settings.rsi_short_min,
            rsi_short_max=settings.rsi_short_max,
            rsi_oversold=settings.rsi_oversold,
            rsi_overbought=settings.rsi_overbought,
            atr_pct_min=settings.atr_pct_min,
            same_side_cooldown_bars=settings.same_side_cooldown_bars,
            ema_min_spread_pct=settings.ema_min_spread_pct,
        )
        self.feed = OkxFeed(
            symbols=symbols,
            interval=settings.kline_interval,
            on_trade=self._on_trade,
            on_candle=self._on_candle,
        )

    async def start(self) -> None:
        self.started_ts = int(time.time() * 1000)
        await self.engine.start()
        symbols = list(settings.symbols)
        if settings.dynamic_symbols:
            try:
                picked = await _pick_dynamic_symbols()
            except Exception as exc:  # noqa: BLE001
                log.warning("dynamic pick failed, falling back to static: %s", exc)
                picked = []
            if picked:
                symbols = picked
                log.info("dynamic universe: %s", ", ".join(symbols))
            else:
                log.info("dynamic pick empty, using static: %s", ", ".join(symbols))
        else:
            log.info("static universe: %s", ", ".join(symbols))
        self._build_strategy_and_feed(symbols)
        # Backfill + live feed run in the background so the HTTP server is
        # available immediately for health checks.
        self._feed_task = asyncio.create_task(self._run_feed(), name="okx-feed")
        self._candle_poll_task = asyncio.create_task(
            self._run_candle_poller(), name="okx-candle-poller"
        )
        self._equity_task = asyncio.create_task(self._equity_loop(), name="equity-loop")
        self._news_task = asyncio.create_task(self.news.run(), name="news-collector")

    async def _run_candle_poller(self) -> None:
        assert self.feed is not None
        # Wait for warmup to finish before polling closes, otherwise the
        # first poll could race with the initial backfill and confuse the
        # strategy state.
        while self._warmup:
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                return
        await self.feed.poll_closes(poll_interval_s=20.0)

    async def _run_feed(self) -> None:
        assert self.feed is not None
        self._warmup = True
        try:
            await self.feed.backfill(limit=max(120, settings.ema_slow * 4))
        except Exception as exc:  # noqa: BLE001
            log.warning("initial backfill failed: %s", exc)
        self._warmup = False
        log.info("warmup complete, entering live mode")
        await self.feed.run()

    async def stop(self) -> None:
        if self.feed is not None:
            self.feed.stop()
        self.news.stop()
        tasks = (
            self._feed_task,
            self._candle_poll_task,
            self._equity_task,
            self._news_task,
        )
        for t in tasks:
            if t is not None:
                t.cancel()
        for t in tasks:
            if t is not None:
                try:
                    await t
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

    async def _on_trade(self, symbol: str, price: float, ts_ms: int) -> None:
        self.last_tick[symbol] = (price, ts_ms)
        if self._warmup:
            return
        await self.engine.on_price(symbol, price)

    async def _on_candle(
        self,
        symbol: str,
        open_: float,
        high: float,
        low: float,
        close: float,
        close_ms: int,
        closed: bool,
    ) -> None:
        self.last_tick[symbol] = (close, close_ms)
        if not closed or self.strategy is None:
            return
        signal = self.strategy.on_candle(symbol, open_, high, low, close, close_ms)
        if signal is None or self._warmup:
            return
        now_s = int(time.time())
        cooldown = self._cooldown_until.get(symbol, 0)
        if now_s < cooldown:
            return
        self._cooldown_until[symbol] = now_s + settings.cooldown_seconds
        # Use the latest market tick as the entry reference — signals fire
        # on a closed 1m candle, but by the time we process them (REST
        # poller runs every ~20s) the live price may have drifted well
        # past the candle's close, which would cause the freshly-opened
        # position to be stopped out on the very next mark-to-market.
        live_tick = self.last_tick.get(symbol)
        entry_ref = live_tick[0] if live_tick is not None else signal.price
        await self.engine.on_signal(
            symbol,
            signal.side,
            entry_ref,
            signal.atr,
            signal.reason,
        )

    async def _equity_loop(self) -> None:
        while True:
            try:
                if self.engine.account is not None:
                    now_ms = int(time.time() * 1000)
                    eq = self.engine.account.equity_usdt
                    bal = self.engine.account.balance_usdt
                    open_pnl = eq - bal
                    await self.storage.append_equity(now_ms, eq, bal, open_pnl)
            except Exception as exc:  # noqa: BLE001
                log.warning("equity loop error: %s", exc)
            try:
                await asyncio.sleep(15.0)
            except asyncio.CancelledError:
                return


bot = Bot()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bot.start()
    try:
        yield
    finally:
        await bot.stop()


app = FastAPI(title="Crypto Scalper", version="0.1.0", lifespan=lifespan)


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "started_ts": bot.started_ts, "symbols": bot.active_symbols}


@app.get("/api/state")
async def state() -> dict[str, Any]:
    snap = bot.engine.snapshot()
    stats = await bot.storage.stats()
    prices = {sym: {"price": p, "ts": t} for sym, (p, t) in bot.last_tick.items()}
    strat = bot.strategy.snapshot() if bot.strategy is not None else {}
    initial = snap.get("initial_balance_usdt", settings.initial_balance_usdt)
    equity = snap.get("equity_usdt", initial)
    ret_pct = ((equity - initial) / initial * 100.0) if initial else 0.0
    return {
        "config": {
            "symbols": bot.active_symbols,
            "interval": settings.kline_interval,
            "initial_balance_usdt": settings.initial_balance_usdt,
            "taker_fee": settings.taker_fee,
            "slippage_bps": settings.slippage_bps,
            "ema_fast": settings.ema_fast,
            "ema_slow": settings.ema_slow,
            "rsi_period": settings.rsi_period,
            "atr_stop_mult": settings.atr_stop_mult,
            "atr_target_mult": settings.atr_target_mult,
            "trail_activate_atr": settings.trail_activate_atr,
            "trail_atr": settings.trail_atr,
            "breakeven_atr": settings.breakeven_atr,
            "risk_per_trade": settings.risk_per_trade,
            "max_open_positions": settings.max_open_positions,
            "max_hold_seconds": settings.max_hold_seconds,
            "cooldown_seconds": settings.cooldown_seconds,
        },
        "account": snap,
        "return_pct": ret_pct,
        "stats": stats,
        "prices": prices,
        "strategy": strat,
        "now_ms": int(time.time() * 1000),
        "started_ts": bot.started_ts,
    }


@app.get("/api/trades")
async def trades(limit: int = 100) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    rows = await bot.storage.recent_trades(limit=limit)
    return {"trades": rows}


@app.get("/api/equity")
async def equity(limit: int = 720) -> dict[str, Any]:
    limit = max(10, min(limit, 4000))
    rows = await bot.storage.equity_curve(limit=limit)
    return {"equity": rows}


@app.get("/api/news")
async def news_api(
    limit: int = 100,
    exchange: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(limit, 500))
    items = await bot.storage.news(limit=limit, exchange=exchange, q=q)
    stats = await bot.storage.news_stats()
    return {"items": items, "stats": stats, "now_ms": int(time.time() * 1000)}


@app.post("/api/close-all")
async def close_all() -> dict[str, Any]:
    prices = {sym: p for sym, (p, _t) in bot.last_tick.items()}
    await bot.engine.force_close_all(prices)
    return {"ok": True}


@app.post("/api/reset")
async def reset(token: str | None = None) -> dict[str, Any]:
    expected = os.getenv("ADMIN_TOKEN")
    if expected and token != expected:
        raise HTTPException(status_code=401, detail="unauthorized")
    await bot.engine.reset()
    return {"ok": True}


STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
STATIC_DIR = os.path.abspath(STATIC_DIR)

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> Any:
    index_path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(index_path):
        return JSONResponse({"ok": True, "message": "Scalper running"})
    return FileResponse(index_path)


@app.get("/news")
async def news_page() -> Any:
    p = os.path.join(STATIC_DIR, "news.html")
    if not os.path.exists(p):
        raise HTTPException(status_code=404, detail="news page missing")
    return FileResponse(p)
