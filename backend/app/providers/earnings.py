"""Earnings awareness: when companies report next, plus the day-before alert.

Next-earnings dates come from yfinance's calendar (no extra API keys). They're
cached to disk with long TTLs and stale-on-error — the dates change rarely and
yfinance throttles aggressively, so a known-stale date beats a missing one
(the same durability pattern as the analyst data).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import yfinance as yf

from .. import universe
from ..config import settings
from . import alerts

log = logging.getLogger("earnings")

_BASE = (
    Path(settings.data_dir)
    if settings.data_dir
    else Path(__file__).resolve().parent.parent.parent / "data"
)
_PATH = _BASE / "earnings_cache.json"
_lock = threading.Lock()

_TTL = 12 * 3600  # refresh twice a day
_NEG_TTL = 3 * 3600  # retry symbols with no date sooner

# {symbol: {"date": "YYYY-MM-DD" | None, "fetched": ts}}
_cache: dict[str, dict] = {}
_loaded = False


def _load_disk() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        _cache.update(json.loads(_PATH.read_text()))
    except Exception:
        pass


def _save_disk() -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(_cache, indent=2))
        import os

        os.replace(tmp, _PATH)
    except Exception:
        pass


def _fetch(symbol: str) -> str | None:
    """The next (future) earnings date from yfinance, ISO string or None."""
    cal = yf.Ticker(symbol).calendar
    dates = (cal or {}).get("Earnings Date") if isinstance(cal, dict) else None
    if not dates:
        return None
    today = date.today()
    future = sorted(d for d in dates if isinstance(d, date) and d >= today)
    return future[0].isoformat() if future else None


def next_earnings(symbol: str) -> str | None:
    """Next earnings date for one symbol (cached; stale beats missing)."""
    if not _reportable(symbol):
        return None
    with _lock:
        _load_disk()
        hit = _cache.get(symbol)
        now = time.time()
        if hit:
            ttl = _TTL if hit.get("date") else _NEG_TTL
            # A cached date that's already passed needs a refetch regardless.
            passed = bool(hit.get("date")) and hit["date"] < date.today().isoformat()
            if now - hit.get("fetched", 0) < ttl and not passed:
                return hit.get("date")
    try:
        d = _fetch(symbol)
    except Exception as e:
        log.info("earnings fetch failed for %s: %s", symbol, e)
        with _lock:
            stale = _cache.get(symbol, {}).get("date")
            return stale if stale and stale >= date.today().isoformat() else None
    with _lock:
        _cache[symbol] = {"date": d, "fetched": time.time()}
        _save_disk()
    return d


def _reportable(symbol: str) -> bool:
    """Only equities report earnings — skip indices, futures, FX, crypto."""
    return not (
        symbol.startswith("^")
        or "=" in symbol
        or symbol.endswith("-USD")
        or symbol == "DX-Y.NYB"
    )


def upcoming_for(symbols: list[str], days: int = 14) -> list[dict]:
    """[{symbol, date, days_away}] for names reporting within `days`, soonest first."""
    today = date.today()
    horizon = (today + timedelta(days=days)).isoformat()
    out = []
    for s in symbols:
        if not _reportable(s):
            continue
        d = next_earnings(s)
        if d and today.isoformat() <= d <= horizon:
            out.append(
                {
                    "symbol": s,
                    "date": d,
                    "days_away": (date.fromisoformat(d) - today).days,
                }
            )
    out.sort(key=lambda e: e["date"])
    return out


def warm(symbols: list[str]) -> None:
    """Scheduler helper: keep the cache fresh off the request path."""
    for s in symbols:
        if _reportable(s):
            try:
                next_earnings(s)
            except Exception:
                pass


# --- the day-before heads-up ----------------------------------------------------


def check_and_notify() -> int:
    """A heads-up when a name with the per-alert earnings toggle reports today
    or tomorrow — delivered via that alert's channels. Runs mornings (ET);
    once per symbol+date."""
    et = universe._et_now()
    if not (7 <= et.hour < 10) or et.weekday() >= 5:
        return 0
    sent = 0
    for uid in alerts.user_ids():
        try:
            watch = alerts.earnings_watch(uid)  # symbol -> merged channels
            if not watch:
                continue
            due = [
                e
                for e in upcoming_for(sorted(watch), days=2)
                if e["days_away"] in (0, 1)
            ]
            for e in due:
                key = f"{e['symbol']}:{e['date']}"
                if alerts.earnings_already_notified(uid, key):
                    continue
                word = "today" if e["days_away"] == 0 else "tomorrow"
                day_word = date.fromisoformat(e["date"]).strftime("%a, %b %-d")
                message = f"{e['symbol']} reports earnings {word} ({day_word})"
                alerts.record_earnings_notice(uid, key, message, watch[e["symbol"]])
                sent += 1
        except Exception as ex:
            log.warning("earnings notify for %s failed: %s", uid, ex)
    return sent
