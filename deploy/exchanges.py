"""Exchange adapters with a uniform async interface.

Each adapter exposes:
    list_active_usdt_symbols(min_quote_volume, limit) -> list[str]
    get_klines(symbol, interval, limit) -> list[Candle]
    chart_url(symbol) -> str
    id, label

Candles are normalised dicts: {openTime, open, high, low, close, volume, closeTime}.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import httpx

HEADERS = {"User-Agent": "pump-detector/1.0", "Accept": "application/json"}
_LEVERAGED = re.compile(r"(UP|DOWN|BULL|BEAR)USDT$")


class Exchange(Protocol):
    id: str
    label: str

    async def list_active_usdt_symbols(
        self, client: httpx.AsyncClient, *, min_quote_volume: float, limit: int
    ) -> list[str]: ...

    async def get_klines(
        self, client: httpx.AsyncClient, symbol: str, *, interval: str, limit: int
    ) -> list[dict]: ...

    def chart_url(self, symbol: str) -> str: ...


async def _get_json(client: httpx.AsyncClient, url: str) -> object:
    resp = await client.get(url, headers=HEADERS, timeout=10.0)
    if resp.status_code >= 400:
        snippet = resp.text[:200]
        raise RuntimeError(f"{url} {resp.status_code}: {snippet}")
    return resp.json()


@dataclass
class BinanceAdapter:
    id: str = "binance"
    label: str = "Binance"
    base: str = "https://api.binance.com"

    async def list_active_usdt_symbols(
        self,
        client: httpx.AsyncClient,
        *,
        min_quote_volume: float = 5_000_000,
        limit: int = 120,
    ) -> list[str]:
        info, tickers = await _gather(
            _get_json(client, f"{self.base}/api/v3/exchangeInfo"),
            _get_json(client, f"{self.base}/api/v3/ticker/24hr"),
        )
        tradable = {
            s["symbol"]
            for s in info["symbols"]
            if s["status"] == "TRADING"
            and s["quoteAsset"] == "USDT"
            and s.get("isSpotTradingAllowed")
            and not _LEVERAGED.search(s["symbol"])
        }
        rows = [
            t
            for t in tickers
            if t["symbol"] in tradable and float(t["quoteVolume"]) >= min_quote_volume
        ]
        rows.sort(key=lambda t: float(t["quoteVolume"]), reverse=True)
        return [t["symbol"] for t in rows[:limit]]

    async def get_klines(
        self,
        client: httpx.AsyncClient,
        symbol: str,
        *,
        interval: str = "5m",
        limit: int = 50,
    ) -> list[dict]:
        url = f"{self.base}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        raw = await _get_json(client, url)
        return [
            {
                "openTime": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
                "closeTime": int(k[6]),
            }
            for k in raw
        ]

    def chart_url(self, symbol: str) -> str:
        pair = symbol.replace("USDT", "_USDT") if "_" not in symbol else symbol
        return f"https://www.binance.com/en/trade/{pair}?type=spot"


@dataclass
class GateAdapter:
    id: str = "gate"
    label: str = "Gate.io"
    base: str = "https://api.gateio.ws/api/v4"

    async def list_active_usdt_symbols(
        self,
        client: httpx.AsyncClient,
        *,
        min_quote_volume: float = 1_000_000,
        limit: int = 120,
    ) -> list[str]:
        tickers = await _get_json(client, f"{self.base}/spot/tickers")
        rows = [
            t
            for t in tickers
            if t["currency_pair"].endswith("_USDT")
            and float(t.get("quote_volume") or 0) >= min_quote_volume
        ]
        rows.sort(key=lambda t: float(t["quote_volume"]), reverse=True)
        return [t["currency_pair"] for t in rows[:limit]]

    async def get_klines(
        self,
        client: httpx.AsyncClient,
        symbol: str,
        *,
        interval: str = "5m",
        limit: int = 50,
    ) -> list[dict]:
        url = (
            f"{self.base}/spot/candlesticks"
            f"?currency_pair={symbol}&interval={interval}&limit={limit}"
        )
        raw = await _get_json(client, url)
        # Gate order: [timestamp_sec, volume_quote, close, high, low, open, amount, closed]
        return [
            {
                "openTime": int(k[0]) * 1000,
                "open": float(k[5]),
                "high": float(k[3]),
                "low": float(k[4]),
                "close": float(k[2]),
                "volume": float(k[6]) if len(k) > 6 else float(k[1]),
                "closeTime": int(k[0]) * 1000 + 5 * 60 * 1000,
            }
            for k in raw
        ]

    def chart_url(self, symbol: str) -> str:
        pair = symbol if "_" in symbol else symbol.replace("USDT", "_USDT")
        return f"https://www.gate.io/trade/{pair}"


EXCHANGES: dict[str, Exchange] = {
    "binance": BinanceAdapter(),
    "gate": GateAdapter(),
}


def get_exchange(eid: str) -> Exchange:
    ex = EXCHANGES.get(eid)
    if not ex:
        raise ValueError(f"unknown exchange: {eid}")
    return ex


async def _gather(*aws):
    import asyncio

    return await asyncio.gather(*aws)
