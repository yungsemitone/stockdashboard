"""Background refresh loop so the cache stays warm and data stays current.

Every interval it re-pulls the overview and the day summary. Because the
providers cache by key, the frontend then gets near-instant responses, and the
data is never more than one interval stale.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from . import universe
from .providers import alerts, analyst, digest, market

log = logging.getLogger("scheduler")

REFRESH_SECONDS = 60
ANALYST_WARM_SECONDS = 1800  # keep default stocks' analyst data fresh & cached
ALERTS_SECONDS = 60  # evaluate price-alert rules

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


def _warm_analyst() -> None:
    try:
        analyst.warm(universe.UNIVERSE.get("stocks", []))
        log.info("analyst data warmed")
    except Exception as e:
        log.warning("analyst warm failed: %s", e)


def _check_alerts() -> None:
    try:
        fired = alerts.check_all()
        if fired:
            log.info("price alerts fired: %d", fired)
    except Exception as e:
        log.warning("alerts check failed: %s", e)


def _check_digests() -> None:
    try:
        sent = digest.check_and_send()
        if sent:
            log.info("morning digests sent: %d", sent)
    except Exception as e:
        log.warning("digest check failed: %s", e)


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(_refresh, "interval", seconds=REFRESH_SECONDS, id="refresh")
    # Warm analyst data shortly after boot, then keep it fresh. Runs off the
    # request path so detail pages always have it cached (and survive throttles).
    _scheduler.add_job(
        _warm_analyst,
        "interval",
        seconds=ANALYST_WARM_SECONDS,
        id="warm_analyst",
        next_run_time=datetime.now() + timedelta(seconds=15),
    )
    # Alert rules ride the same warmed caches; start shortly after boot.
    _scheduler.add_job(
        _check_alerts,
        "interval",
        seconds=ALERTS_SECONDS,
        id="alerts",
        next_run_time=datetime.now() + timedelta(seconds=30),
    )
    _scheduler.add_job(
        _check_digests,
        "interval",
        seconds=60,
        id="digests",
        next_run_time=datetime.now() + timedelta(seconds=45),
    )
    _scheduler.start()
    log.info("scheduler started (every %ss)", REFRESH_SECONDS)


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
