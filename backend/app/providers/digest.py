"""The morning digest: a per-account weekday email brief.

The scheduler calls check_and_send() every minute; each account with the
digest enabled gets one email per weekday once its chosen ET time comes
around (a two-hour grace window makes restarts safe without double-sending —
"digest_last" in the account's alert settings tracks the last sent date).

Content: the index snapshot, the account's watchlist movers, today's economic
calendar, and a short AI take (plain data still goes out if AI is down).
"""

from __future__ import annotations

import logging

from .. import universe
from ..config import settings
from . import alerts, market, users, watchlist
from . import calendar as econ_calendar

log = logging.getLogger("digest")

GRACE_MINUTES = 120


def _fmt_quote_line(q: dict) -> str:
    price = q.get("price")
    pct = q.get("change_pct")
    if price is None:
        return f"  {q.get('name', q.get('symbol'))}: n/a"
    px = f"{price:,.2f}" if q.get("is_level") else f"${price:,.2f}"
    pc = f" ({pct:+.2f}%)" if pct is not None else ""
    return f"  {q.get('name', q.get('symbol'))}: {px}{pc}"


def _build(user_id: str, username: str) -> tuple[str, str]:
    """(subject, body) for one account's digest."""
    et = universe._et_now()
    day_word = et.strftime("%A, %b %-d")

    # Index snapshot (futures-fed, so these move pre-open).
    overview = market.get_overview()
    idx_lines = [_fmt_quote_line(q) for q in (overview.get("indices") or [])[:5]]

    # The account's watchlist, biggest movers first.
    wl_lines: list[str] = []
    try:
        lists = watchlist.get_all(user_id)
        symbols = sorted({s for l in lists for s in l["symbols"]})[:25]
        if symbols:
            quotes = market.snapshot_quotes(symbols)
            movers = sorted(
                (q for q in quotes.values() if q.get("change_pct") is not None),
                key=lambda q: abs(q["change_pct"]),
                reverse=True,
            )
            wl_lines = [_fmt_quote_line(q) for q in movers[:6]]
    except Exception:
        pass

    # Today's calendar.
    cal_lines: list[str] = []
    try:
        today = et.strftime("%Y-%m-%d")
        for e in econ_calendar.upcoming(2):
            if e.get("date") == today:
                t = f" at {e['time_et']}" if e.get("time_et") else ""
                cal_lines.append(f"  {e['name']}{t}")
    except Exception:
        pass

    sections = [f"Good morning {username} — {day_word}", ""]
    if idx_lines:
        sections += ["MARKETS", *idx_lines, ""]
    if wl_lines:
        sections += ["YOUR WATCHLIST", *wl_lines, ""]
    if cal_lines:
        sections += ["TODAY'S ECONOMIC CALENDAR", *cal_lines, ""]

    take = _ai_take(idx_lines, wl_lines, cal_lines)
    if take:
        sections += ["THE TAKE", take, ""]
    sections += ["— your Markets dashboard"]

    return f"☀️ Morning brief — {day_word}", "\n".join(sections)


def _ai_take(idx: list[str], wl: list[str], cal: list[str]) -> str:
    if not settings.anthropic_api_key:
        return ""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            "Write the 2-3 sentence 'take' for a personal morning market brief. "
            "Ground it ONLY in this data (index futures, the reader's watchlist "
            "movers, today's economic releases):\n\n"
            + "\n".join(["Indices:", *idx, "Watchlist:", *wl, "Today:", *cal])
            + "\n\nPlain English, specific, no preamble, no disclaimers, max 3 sentences."
        )
        msg = client.messages.create(
            model=settings.narrative_model,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
    except Exception as e:
        log.warning("digest AI take failed: %s", e)
        return ""


def send_to(user_id: str) -> dict:
    """Build + send one account's digest right now (the bell's Send-now button)."""
    if not alerts.smtp_configured():
        return {"ok": False, "error": "Email isn't set up on the server."}
    account = users.public_by_id(user_id)
    if account is None:
        return {"ok": False, "error": "No such account."}
    cfg = alerts.get_state(user_id)["settings"]
    to = (cfg.get("email_to") or account["email"]).strip()
    if not to:
        return {"ok": False, "error": "No destination email on the account."}
    subject, body = _build(user_id, account["username"])
    try:
        alerts.send_email([to], subject, body)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"Send failed: {e}"}


def _due(cfg: dict, et) -> bool:
    """Within the send window for today, and not yet sent today?"""
    if not cfg.get("digest_enabled"):
        return False
    if et.weekday() >= 5:  # weekends: markets closed, no brief
        return False
    if cfg.get("digest_last") == et.strftime("%Y-%m-%d"):
        return False
    try:
        hh, mm = (int(x) for x in str(cfg.get("digest_time", "07:30")).split(":"))
    except ValueError:
        hh, mm = 7, 30
    minutes_now = et.hour * 60 + et.minute
    start = hh * 60 + mm
    return start <= minutes_now < start + GRACE_MINUTES


def check_and_send() -> int:
    """Scheduler entry point: send every due digest. Returns the count sent."""
    et = universe._et_now()
    sent = 0
    for uid in alerts.user_ids():
        try:
            cfg = alerts.get_state(uid)["settings"]
            if not _due(cfg, et):
                continue
            # Mark first so a slow send can't double-fire on overlap.
            alerts.mark_digest_sent(uid, et.strftime("%Y-%m-%d"))
            result = send_to(uid)
            if result.get("ok"):
                sent += 1
                log.info("digest sent for %s", uid)
            else:
                log.warning("digest for %s failed: %s", uid, result.get("error"))
        except Exception as e:
            log.warning("digest for %s errored: %s", uid, e)
    return sent
