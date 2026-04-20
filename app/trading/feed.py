"""Live market data feed (OKX v5 public streams).

We do NOT trade against the exchange — trading is simulated locally — but
we use OKX's public market-data endpoints as ground truth for prices and
candles. OKX is chosen because its public endpoints are reachable from
virtually any region (unlike Binance or Bybit, which block many IPs).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Awaitable, Callable

import httpx
import websockets


log = logging.getLogger("scalper.feed")

OKX_WS = os.getenv("OKX_WS", "wss://ws.okx.com:8443/ws/v5/public")
OKX_REST = os.getenv("OKX_REST", "https://www.okx.com")


# Map our canonical interval spec to OKX "bar" strings.
_INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "4h": "4H",
}


TradeCb = Callable[[str, float, int], Awaitable[None]]
CandleCb = Callable[[str, float, float, float, float, int, bool], Awaitable[None]]


def _okx_bar(interval: str) -> str:
    return _INTERVAL_MAP.get(interval, "1m")


class OkxFeed:
    """Live feed for a fixed set of spot symbols on OKX."""

    def __init__(
        self,
        symbols: list[str],
        interval: str,
        on_trade: TradeCb,
        on_candle: CandleCb,
    ) -> None:
        # OKX uses BASE-QUOTE form ("BTC-USDT"). Accept both forms.
        self.symbols = [_normalize(s) for s in symbols]
        self.interval = interval
        self.bar = _okx_bar(interval)
        self.on_trade = on_trade
        self.on_candle = on_candle
        self._stop = asyncio.Event()
        # Per-symbol last-seen bar state. Used to synthesise the "closed"
        # event from the candle stream by detecting the start_ms boundary
        # crossing — some OKX pushes skip the confirm=1 update, but the
        # next bar always arrives with a fresh start_ms.
        self._active_bar: dict[str, tuple[int, float, float, float, float]] = {}

    def _sub_msg(self) -> str:
        # Only subscribe to trades over WS. Candle-close events are
        # derived either from a dedicated REST poller (see `poll_closes`)
        # or from the candle channel if enabled. We've observed OKX
        # occasionally dropping the confirm=1 push on the WS candle
        # channel, which silently broke the scalper — polling is more
        # reliable for the 1m-close event.
        args: list[dict] = []
        for s in self.symbols:
            args.append({"channel": "trades", "instId": s})
        return json.dumps({"op": "subscribe", "args": args})

    async def poll_closes(self, poll_interval_s: float = 20.0) -> None:
        """Dedicated loop that pulls the most recent confirmed 1m candle
        for every symbol and emits an on_candle(closed=True) whenever a
        new bar is observed.

        This is the authoritative signal source — it survives WS outages
        and doesn't depend on OKX pushing the confirm=1 flag on time.
        """
        minute_ms = _interval_to_ms(self.bar)
        last_emitted: dict[str, int] = {}
        async with httpx.AsyncClient(timeout=15.0) as client:
            while not self._stop.is_set():
                try:
                    await self._poll_closes_once(client, minute_ms, last_emitted)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    log.warning("candle poller error: %s", exc)
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=poll_interval_s
                    )
                    return  # _stop was set → exit the loop
                except asyncio.TimeoutError:
                    pass  # poll_interval_s elapsed, next iteration

    async def _poll_closes_once(
        self,
        client: httpx.AsyncClient,
        minute_ms: int,
        last_emitted: dict[str, int],
    ) -> None:
        for sym in self.symbols:
            try:
                r = await client.get(
                    f"{OKX_REST}/api/v5/market/candles",
                    params={"instId": sym, "bar": self.bar, "limit": 3},
                )
                r.raise_for_status()
                rows = r.json().get("data") or []
            except Exception as exc:  # noqa: BLE001
                log.debug("poll_closes %s failed: %s", sym, exc)
                continue
            # rows are newest-first; only confirm=1 entries count.
            for row in sorted(rows, key=lambda r_: int(r_[0])):
                try:
                    confirm = str(row[8]) if len(row) > 8 else "0"
                    if confirm != "1":
                        continue
                    start_ms = int(row[0])
                    open_ = float(row[1])
                    high = float(row[2])
                    low = float(row[3])
                    close = float(row[4])
                except (TypeError, ValueError, IndexError):
                    continue
                if last_emitted.get(sym, 0) >= start_ms:
                    continue
                last_emitted[sym] = start_ms
                close_ms = start_ms + minute_ms - 1
                await self.on_candle(
                    sym, open_, high, low, close, close_ms, True
                )

    async def backfill(self, limit: int = 120) -> None:
        """Seed the strategy with recent closed candles via REST."""
        limit = max(2, min(limit, 300))
        async with httpx.AsyncClient(timeout=15.0) as client:
            for sym in self.symbols:
                try:
                    r = await client.get(
                        f"{OKX_REST}/api/v5/market/candles",
                        params={"instId": sym, "bar": self.bar, "limit": limit},
                    )
                    r.raise_for_status()
                    payload = r.json()
                    rows = payload.get("data") or []
                except Exception as exc:  # noqa: BLE001 - resilient backfill
                    log.warning("backfill failed for %s: %s", sym, exc)
                    continue
                # OKX returns newest-first. Convert to oldest-first, drop any
                # unconfirmed (still-forming) candle.
                rows_sorted = sorted(rows, key=lambda r_: int(r_[0]))
                minute_ms = _interval_to_ms(self.bar)
                count = 0
                for row in rows_sorted:
                    confirm = str(row[8]) if len(row) > 8 else "1"
                    if confirm != "1":
                        continue
                    start_ms = int(row[0])
                    open_ = float(row[1])
                    high = float(row[2])
                    low = float(row[3])
                    close = float(row[4])
                    close_ms = start_ms + minute_ms - 1
                    await self.on_candle(sym, open_, high, low, close, close_ms, True)
                    count += 1
                log.info("backfilled %d candles for %s", count, sym)

    async def run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(
                    OKX_WS,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=2**20,
                ) as ws:
                    await ws.send(self._sub_msg())
                    log.info("ws connected: %d symbols", len(self.symbols))
                    backoff = 1.0
                    heartbeat = asyncio.create_task(self._heartbeat(ws))
                    try:
                        async for raw in ws:
                            if self._stop.is_set():
                                break
                            await self._handle(raw)
                    finally:
                        heartbeat.cancel()
                        try:
                            await heartbeat
                        except (asyncio.CancelledError, Exception):  # noqa: BLE001
                            pass
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("ws error: %s (reconnecting in %.1fs)", exc, backoff)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2.0, 30.0)

    async def _heartbeat(self, ws) -> None:
        # OKX requires app-level "ping" every ~25s to keep the socket alive.
        while True:
            try:
                await asyncio.sleep(20)
                await ws.send("ping")
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                return

    async def _handle(self, raw: str | bytes) -> None:
        if raw == "pong" or raw == b"pong":
            return
        try:
            msg = json.loads(raw)
        except Exception:  # noqa: BLE001
            return
        arg = msg.get("arg") or {}
        channel = arg.get("channel", "")
        inst = arg.get("instId")
        data = msg.get("data")
        if not channel or not data or not inst:
            return
        if channel == "trades":
            for t in data:
                try:
                    price = float(t.get("px", 0.0) or 0.0)
                    ts = int(t.get("ts", 0) or 0)
                except (TypeError, ValueError):
                    continue
                if price > 0:
                    await self.on_trade(inst, price, ts)
        elif channel.startswith("candle"):
            minute_ms = _interval_to_ms(self.bar)
            for row in data:
                try:
                    start_ms = int(row[0])
                    open_ = float(row[1])
                    high = float(row[2])
                    low = float(row[3])
                    close = float(row[4])
                    confirm = str(row[8]) if len(row) > 8 else "0"
                except (TypeError, ValueError, IndexError):
                    continue
                if close <= 0:
                    continue
                close_ms = start_ms + minute_ms - 1
                # Bar-boundary synthesis: if a new start_ms appears while we
                # still have an "active" older bar cached, emit a closed=True
                # event for the cached bar before propagating the new one.
                prev = self._active_bar.get(inst)
                if prev is not None and prev[0] < start_ms:
                    p_start, p_open, p_high, p_low, p_close = prev
                    p_close_ms = p_start + minute_ms - 1
                    await self.on_candle(
                        inst, p_open, p_high, p_low, p_close, p_close_ms, True
                    )
                # Track current in-progress bar (keep max high, min low).
                if prev is not None and prev[0] == start_ms:
                    _, p_open, p_high, p_low, _ = prev
                    new_high = max(p_high, high)
                    new_low = min(p_low, low)
                    self._active_bar[inst] = (
                        start_ms, p_open, new_high, new_low, close,
                    )
                else:
                    self._active_bar[inst] = (start_ms, open_, high, low, close)
                # Propagate the in-progress update to listeners.
                await self.on_candle(inst, open_, high, low, close, close_ms, False)
                # If OKX explicitly confirmed the bar, also emit closed=True
                # and forget the cached bar so we don't double-fire.
                if confirm == "1":
                    await self.on_candle(
                        inst, open_, high, low, close, close_ms, True
                    )
                    self._active_bar.pop(inst, None)

    def stop(self) -> None:
        self._stop.set()


def _normalize(symbol: str) -> str:
    s = symbol.upper().strip()
    if "-" in s:
        return s
    # BTCUSDT -> BTC-USDT, ETHUSDC -> ETH-USDC, SOLUSDT -> SOL-USDT, etc.
    for quote in ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            return f"{s[: -len(quote)]}-{quote}"
    return s


def _interval_to_ms(bar: str) -> int:
    unit = bar[-1]
    try:
        n = int(bar[:-1])
    except ValueError:
        return 60_000
    if unit in ("m", "M"):
        return n * 60_000
    if unit in ("h", "H"):
        return n * 3_600_000
    if unit in ("d", "D"):
        return n * 86_400_000
    return 60_000
