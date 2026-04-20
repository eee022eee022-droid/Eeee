"""Polls exchange announcement sources and persists new items."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import httpx

from .sources import SOURCES
from ..trading.storage import Storage


log = logging.getLogger("scalper.news")


class NewsCollector:
    """Fan-out poller. Each source is polled on its own cadence."""

    def __init__(
        self,
        storage: Storage,
        *,
        poll_seconds: int = 25,
    ) -> None:
        self.storage = storage
        self.poll_seconds = poll_seconds
        self._stop = asyncio.Event()

    async def run(self) -> None:
        log.info("news collector starting: sources=%d", len(SOURCES))
        async with httpx.AsyncClient(http2=False, follow_redirects=True) as client:
            # First pass populates the database quickly, then we loop.
            await self._poll_all(client, initial=True)
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self.poll_seconds
                    )
                    break
                except asyncio.TimeoutError:
                    pass
                await self._poll_all(client, initial=False)

    def stop(self) -> None:
        self._stop.set()

    async def _poll_all(
        self, client: httpx.AsyncClient, *, initial: bool
    ) -> None:
        tasks = [
            asyncio.create_task(self._poll_one(name, fetch, client))
            for name, fetch in SOURCES
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_new = 0
        for name_fetch, res in zip(SOURCES, results):
            name, _ = name_fetch
            if isinstance(res, Exception):
                log.warning("news source %s failed: %s", name, res)
                continue
            total_new += res or 0
        if total_new or initial:
            log.info(
                "news poll: %s %d new",
                "initial" if initial else "tick",
                total_new,
            )

    async def _poll_one(
        self,
        name: str,
        fetch: Any,
        client: httpx.AsyncClient,
    ) -> int:
        try:
            items = await fetch(client)
        except Exception as exc:  # noqa: BLE001 - one bad source shouldn't kill the loop
            raise RuntimeError(f"{name}: {exc}") from exc
        now_ms = int(time.time() * 1000)
        return await self.storage.insert_news(items, now_ms)
