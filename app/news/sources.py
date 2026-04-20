"""Async fetchers for exchange announcement feeds.

Each source returns a list of dicts with a stable shape:

    {
        "exchange": "binance" | "okx" | "kucoin" | "kraken" | ...,
        "title": str,
        "url": str,
        "published_ts": int (ms since epoch),
        "category": str,           # human label
        "external_id": str,        # stable identifier for dedup
    }

Sources that get geoblocked (Bybit, Gate, HTX, Bitget, MEXC, Upbit,
Coinbase blog) are intentionally omitted — polling them from Fly
returns Cloudflare/Akamai challenges and would add noise, not news.
"""
from __future__ import annotations

import html
import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

import httpx


log = logging.getLogger("scalper.news")


UA = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/xml, */*",
}

DELIST_KEYWORDS = (
    "delist",
    "de-list",
    "removal",
    "remove ",
    "removes ",
    "removed",
    "suspension",
    "suspend",
    "terminate",
    "termination",
    "discontinue",
    "discontinued",
    "retire",
    "retired",
    "sunset",
    "offboard",
    "wind down",
    "winding down",
    "cease",
    "cessation",
)


def _matches_delist(title: str) -> bool:
    t = title.lower()
    return any(k in t for k in DELIST_KEYWORDS)


async def _get_json(client: httpx.AsyncClient, url: str) -> Any:
    r = await client.get(url, headers=UA, timeout=15.0)
    r.raise_for_status()
    return r.json()


async def _get_text(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, headers=UA, timeout=15.0)
    r.raise_for_status()
    return r.text


async def fetch_binance(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Binance delisting category (catalogId=161)."""
    url = (
        "https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
        "?type=1&catalogId=161&pageNo=1&pageSize=20"
    )
    data = await _get_json(client, url)
    items: list[dict[str, Any]] = []
    for cat in data.get("data", {}).get("catalogs") or []:
        for a in cat.get("articles") or []:
            code = a.get("code")
            title = a.get("title") or ""
            ts = int(a.get("releaseDate") or 0)
            if not code or not title:
                continue
            items.append(
                {
                    "exchange": "binance",
                    "title": title,
                    "url": f"https://www.binance.com/en/support/announcement/{code}",
                    "published_ts": ts,
                    "category": "delisting",
                    "external_id": f"binance:{code}",
                }
            )
    return items


async def fetch_okx(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """OKX public announcements filtered to the delistings channel."""
    url = (
        "https://www.okx.com/api/v5/support/announcements"
        "?annType=announcements-delistings"
    )
    data = await _get_json(client, url)
    items: list[dict[str, Any]] = []
    for group in data.get("data") or []:
        for det in group.get("details") or []:
            title = det.get("title") or ""
            link = det.get("url") or ""
            if not title or not link:
                continue
            try:
                ts = int(det.get("pTime") or 0)
            except (TypeError, ValueError):
                ts = 0
            items.append(
                {
                    "exchange": "okx",
                    "title": title,
                    "url": link,
                    "published_ts": ts,
                    "category": "delisting",
                    "external_id": f"okx:{link}",
                }
            )
    return items


async def fetch_kucoin(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """KuCoin: pull the latest-announcements stream, filter client-side.

    KuCoin has a `delisting` annType but at the time of writing it returns
    an empty list; latest-announcements contains the real delist posts,
    they're just tagged as "latest".
    """
    url = (
        "https://api.kucoin.com/api/v3/announcements"
        "?annType=latest-announcements&pageSize=50"
    )
    data = await _get_json(client, url)
    items: list[dict[str, Any]] = []
    for a in data.get("data", {}).get("items") or []:
        title = a.get("annTitle") or ""
        if not _matches_delist(title):
            continue
        link = a.get("annUrl") or ""
        ann_id = a.get("annId")
        try:
            ts = int(a.get("cTime") or 0)
        except (TypeError, ValueError):
            ts = 0
        if not link or ann_id is None:
            continue
        items.append(
            {
                "exchange": "kucoin",
                "title": title,
                "url": link,
                "published_ts": ts,
                "category": "delisting",
                "external_id": f"kucoin:{ann_id}",
            }
        )
    return items


async def fetch_kraken(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Kraken blog RSS, filtered to delist-style posts."""
    text = await _get_text(client, "https://blog.kraken.com/feed")
    root = ET.fromstring(text)
    items: list[dict[str, Any]] = []
    channel = root.find("channel")
    if channel is None:
        return items
    for it in channel.findall("item"):
        title = (it.findtext("title") or "").strip()
        if not _matches_delist(title):
            continue
        link = (it.findtext("link") or "").strip()
        guid = (it.findtext("guid") or link).strip()
        pub = (it.findtext("pubDate") or "").strip()
        ts = _parse_rfc2822(pub)
        if not title or not link:
            continue
        items.append(
            {
                "exchange": "kraken",
                "title": html.unescape(title),
                "url": link,
                "published_ts": ts,
                "category": "delisting",
                "external_id": f"kraken:{guid}",
            }
        )
    return items


_RFC2822_RE = re.compile(
    r"^[A-Za-z]{3}, (\d{1,2}) ([A-Za-z]{3}) (\d{4}) (\d{2}):(\d{2}):(\d{2})"
)
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    )
}


def _parse_rfc2822(s: str) -> int:
    """Best-effort RFC 2822 -> epoch ms. Returns 0 if unparseable."""
    import calendar

    m = _RFC2822_RE.match(s)
    if not m:
        return 0
    day, mon_name, year, hh, mm, ss = m.groups()
    mon = _MONTHS.get(mon_name)
    if mon is None:
        return 0
    try:
        epoch = calendar.timegm(
            (int(year), mon, int(day), int(hh), int(mm), int(ss), 0, 0, 0)
        )
    except (ValueError, OverflowError):
        return 0
    return int(epoch * 1000)


SOURCES = (
    ("binance", fetch_binance),
    ("okx", fetch_okx),
    ("kucoin", fetch_kucoin),
    ("kraken", fetch_kraken),
)
