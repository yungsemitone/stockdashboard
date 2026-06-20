"""Background refresh loop so the cache stays warm and data stays current.

Every interval it re-pulls the overview and the day summary. Because the
providers cache by key, the frontend then gets near-instant responses, and the
data is never more than one interval stale.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .providers import market

log = logging.getLogger("scheduler")

REFRESH_SECONDS = 60

_scheduler: BackgroundScheduler | None = None


def _refresh() -> None:
    try:
        # Force fresh pulls by clearing the relevant cache entries first.
        keys = [k for k in list(market._cache) if k.startswith(("batch:", "hist:"))]
        for k in keys:
            market._cache.pop(k, None)
        market.get_overview()
        market.get_summary("day")
        log.info("market data refreshed")
    except Exception as e:  # never let a bad pull kill the scheduler
        log.warning("refresh failed: %s", e)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_refresh, "interval", seconds=REFRESH_SECONDS, id="refresh")
    _scheduler.start()
    log.info("scheduler started (every %ss)", REFRESH_SECONDS)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
