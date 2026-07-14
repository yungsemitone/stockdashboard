"""Morning brief + evening wrap: per-account weekday email newsletters.

The scheduler calls check_and_send() every minute; each account gets its
enabled editions once per weekday at its chosen ET times (a two-hour grace
window makes restarts safe; "digest_last"/"evening_last" track the sent date).

Both editions carry the index snapshot, the account's watchlist, and the day's
economic calendar. The morning take looks FORWARD (what to watch at the open);
the evening take sums up the day. Emails go out as a warm HTML newsletter with
a plain-text fallback.
"""

from __future__ import annotations

import logging

from .. import universe
from ..config import settings
from . import alerts, market, users, watchlist
from . import calendar as econ_calendar

log = logging.getLogger("digest")

GRACE_MINUTES = 120

KINDS = {
    "morning": {
        "emoji": "☀️",
        "title": "Morning Brief",
        "enabled_key": "digest_enabled",
        "time_key": "digest_time",
        "last_key": "digest_last",
        "accent": "#d97706",  # warm amber
        "wash": "#fff7ed",
    },
    "evening": {
        "emoji": "🌙",
        "title": "Evening Wrap",
        "enabled_key": "evening_enabled",
        "time_key": "evening_time",
        "last_key": "evening_last",
        "accent": "#b45309",  # deeper amber
        "wash": "#fef3e2",
    },
}


# --- data --------------------------------------------------------------------


def _gather(user_id: str) -> dict:
    et = universe._et_now()
    overview = market.get_overview()
    indices = (overview.get("indices") or [])[:5]

    wl: list[dict] = []
    try:
        lists = watchlist.get_all(user_id)
        symbols = sorted({s for l in lists for s in l["symbols"]})[:25]
        if symbols:
            quotes = market.snapshot_quotes(symbols)
            wl = sorted(
                (q for q in quotes.values() if q.get("change_pct") is not None),
                key=lambda q: abs(q["change_pct"]),
                reverse=True,
            )[:8]
    except Exception:
        pass

    cal: list[dict] = []
    try:
        today = et.strftime("%Y-%m-%d")
        for e in econ_calendar.upcoming(2):
            if e.get("date") == today:
                cal.append({"name": e["name"], "time": e.get("time_et") or "time TBD"})
    except Exception:
        pass

    return {
        "date_word": et.strftime("%A, %b %-d"),
        "indices": indices,
        "watchlist": wl,
        "calendar": cal,
    }


def _quote_bits(q: dict) -> tuple[str, str, float | None]:
    """(name, price string, pct) for a quote."""
    price = q.get("price")
    px = (
        "n/a"
        if price is None
        else f"{price:,.2f}" if q.get("is_level") else f"${price:,.2f}"
    )
    return q.get("name") or q.get("symbol", "?"), px, q.get("change_pct")


# --- the take ------------------------------------------------------------------


def _data_block(d: dict) -> str:
    lines = ["Indices:"]
    for q in d["indices"]:
        n, px, pct = _quote_bits(q)
        lines.append(f"  {n}: {px} ({pct:+.2f}%)" if pct is not None else f"  {n}: {px}")
    lines.append("Watchlist:")
    for q in d["watchlist"]:
        n, px, pct = _quote_bits(q)
        sym = q.get("symbol", "")
        lines.append(f"  {sym}: {px} ({pct:+.2f}%)" if pct is not None else f"  {sym}: {px}")
    lines.append("Today's economic calendar:")
    for e in d["calendar"] or [{"name": "no major releases", "time": ""}]:
        lines.append(f"  {e['name']} at {e['time']}".rstrip())
    return "\n".join(lines)


def _ai_take(d: dict, kind: str, username: str) -> str:
    if not settings.anthropic_api_key:
        return ""
    if kind == "morning":
        ask = (
            "This goes out BEFORE the market opens. In 3-5 sentences: briefly say "
            "what overnight futures and pre-market moves imply, then focus on WHAT "
            "TO WATCH once the market opens today — both in general (which economic "
            "releases matter and when, what could move the tape) and specifically on "
            "the watchlist (which names deserve attention at the open and why)."
        )
    else:
        ask = (
            "This goes out AFTER the close. In 3-5 sentences, summarize what "
            "happened today: the broad market story (indices, any notable rotation "
            "or driver) and the watchlist story (best and worst names, moves worth "
            "remembering)."
        )
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            f"You write the 'take' in {username}'s personal market brief. Ground it "
            f"ONLY in this data:\n\n{_data_block(d)}\n\n{ask} Plain English, "
            "specific, no preamble, no disclaimers."
        )
        msg = client.messages.create(
            model=settings.narrative_model,
            max_tokens=350,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
    except Exception as e:
        log.warning("digest AI take failed: %s", e)
        return ""


# --- rendering -----------------------------------------------------------------


def _plain(d: dict, take: str, kind: str, username: str) -> str:
    k = KINDS[kind]
    out = [f"Good {'morning' if kind == 'morning' else 'evening'} {username} — {d['date_word']}", ""]
    out += ["MARKETS" if kind == "morning" else "MARKETS AT THE CLOSE"]
    for q in d["indices"]:
        n, px, pct = _quote_bits(q)
        out.append(f"  {n}: {px}" + (f" ({pct:+.2f}%)" if pct is not None else ""))
    out.append("")
    out.append("YOUR WATCHLIST")
    for q in d["watchlist"]:
        n, px, pct = _quote_bits(q)
        out.append(f"  {q.get('symbol')}: {px}" + (f" ({pct:+.2f}%)" if pct is not None else ""))
    out.append("")
    out.append("TODAY'S ECONOMIC CALENDAR")
    if d["calendar"]:
        out += [f"  {e['name']} — {e['time']}" for e in d["calendar"]]
    else:
        out.append("  No major releases today.")
    out.append("")
    if take:
        out += ["THE TAKE", take, ""]
    out.append("— your Markets dashboard")
    return "\n".join(out)


def _pct_chip(pct: float | None) -> str:
    if pct is None:
        return ""
    up = pct >= 0
    color = "#047857" if up else "#b91c1c"
    bg = "#ecfdf3" if up else "#fdf0ef"
    return (
        f'<span style="background:{bg};color:{color};border-radius:999px;'
        f'padding:2px 9px;font-size:12px;font-weight:700;white-space:nowrap;">'
        f"{pct:+.2f}%</span>"
    )


def _rows(quotes: list[dict], use_symbol: bool) -> str:
    rows = []
    for q in quotes:
        n, px, pct = _quote_bits(q)
        label = q.get("symbol") if use_symbol else n
        sub = n if use_symbol and n != label else ""
        sub_html = (
            f'<div style="font-size:11px;color:#a8a29e;">{sub}</div>' if sub else ""
        )
        rows.append(
            '<tr><td style="padding:7px 0;font-size:14px;color:#44403c;">'
            f"<strong>{label}</strong>{sub_html}</td>"
            '<td align="right" style="padding:7px 0;white-space:nowrap;">'
            f'<span style="font-size:14px;color:#292524;font-weight:600;">{px}</span>'
            f"&nbsp;&nbsp;{_pct_chip(pct)}</td></tr>"
        )
    return "".join(rows)


def _card(label: str, accent: str, inner: str, wash: str = "#ffffff") -> str:
    return (
        f'<div style="background:{wash};border:1px solid #f0e4d2;border-radius:14px;'
        'padding:16px 18px;margin:0 0 14px 0;">'
        f'<div style="font-size:11px;font-weight:700;letter-spacing:0.08em;'
        f'color:{accent};text-transform:uppercase;margin-bottom:8px;">{label}</div>'
        f"{inner}</div>"
    )


def _html(d: dict, take: str, kind: str, username: str) -> str:
    k = KINDS[kind]
    idx = f'<table width="100%" cellpadding="0" cellspacing="0">{_rows(d["indices"], False)}</table>'
    wl = (
        f'<table width="100%" cellpadding="0" cellspacing="0">{_rows(d["watchlist"], True)}</table>'
        if d["watchlist"]
        else '<div style="font-size:13px;color:#a8a29e;">Nothing on your watchlist yet.</div>'
    )
    if d["calendar"]:
        cal = "".join(
            '<tr><td style="padding:6px 0;font-size:14px;color:#44403c;">'
            f'{e["name"]}</td><td align="right" style="padding:6px 0;font-size:13px;'
            f'color:#78716c;white-space:nowrap;">{e["time"]}</td></tr>'
            for e in d["calendar"]
        )
        cal = f'<table width="100%" cellpadding="0" cellspacing="0">{cal}</table>'
    else:
        cal = '<div style="font-size:13px;color:#a8a29e;">No major releases today.</div>'

    take_card = (
        _card(
            "The take",
            k["accent"],
            f'<div style="font-size:14px;line-height:1.65;color:#44403c;">{take}</div>',
            k["wash"],
        )
        if take
        else ""
    )

    markets_label = "Markets" if kind == "morning" else "Markets at the close"
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#faf3e7;">
<div style="display:none;max-height:0;overflow:hidden;">{k['title']} — {d['date_word']}</div>
<table width="100%" cellpadding="0" cellspacing="0" style="background:#faf3e7;">
<tr><td align="center" style="padding:28px 12px;">
<table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<tr><td style="padding:0 4px 18px 4px;">
  <div style="font-size:30px;line-height:1;">{k['emoji']}</div>
  <div style="font-size:24px;font-weight:800;color:#292524;margin-top:8px;">{k['title']}</div>
  <div style="font-size:14px;color:#a16207;font-weight:600;margin-top:2px;">{d['date_word']} · for {username}</div>
</td></tr>
<tr><td>
{_card(markets_label, k['accent'], idx)}
{_card('Your watchlist', k['accent'], wl)}
{_card("Today's economic calendar", k['accent'], cal)}
{take_card}
<div style="text-align:center;font-size:12px;color:#bda88c;padding:6px 0 20px 0;">— your Markets dashboard —</div>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


# --- sending -------------------------------------------------------------------


def send_to(user_id: str, kind: str = "morning") -> dict:
    """Build + send one account's edition right now (the bell's Send-now)."""
    if kind not in KINDS:
        kind = "morning"
    if not alerts.smtp_configured():
        return {"ok": False, "error": "Email isn't set up on the server."}
    account = users.public_by_id(user_id)
    if account is None:
        return {"ok": False, "error": "No such account."}
    cfg = alerts.get_state(user_id)["settings"]
    to = (cfg.get("email_to") or account["email"]).strip()
    if not to:
        return {"ok": False, "error": "No destination email on the account."}
    d = _gather(user_id)
    take = _ai_take(d, kind, account["username"])
    k = KINDS[kind]
    subject = f"{k['emoji']} {k['title']} — {d['date_word']}"
    try:
        alerts.send_email(
            [to],
            subject,
            _plain(d, take, kind, account["username"]),
            html=_html(d, take, kind, account["username"]),
        )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"Send failed: {e}"}


def _due(cfg: dict, et, kind: str) -> bool:
    """Within the send window for today, and not yet sent today?"""
    k = KINDS[kind]
    if not cfg.get(k["enabled_key"]):
        return False
    if et.weekday() >= 5:  # weekends: markets closed, no brief
        return False
    if cfg.get(k["last_key"]) == et.strftime("%Y-%m-%d"):
        return False
    default = "07:30" if kind == "morning" else "16:30"
    try:
        hh, mm = (int(x) for x in str(cfg.get(k["time_key"], default)).split(":"))
    except ValueError:
        hh, mm = (int(x) for x in default.split(":"))
    minutes_now = et.hour * 60 + et.minute
    start = hh * 60 + mm
    return start <= minutes_now < start + GRACE_MINUTES


def check_and_send() -> int:
    """Scheduler entry point: send every due edition. Returns the count sent."""
    et = universe._et_now()
    sent = 0
    for uid in alerts.user_ids():
        for kind in KINDS:
            try:
                cfg = alerts.get_state(uid)["settings"]
                if not _due(cfg, et, kind):
                    continue
                # Mark first so a slow send can't double-fire on overlap.
                alerts.mark_digest_sent(uid, et.strftime("%Y-%m-%d"), kind)
                result = send_to(uid, kind)
                if result.get("ok"):
                    sent += 1
                    log.info("%s digest sent for %s", kind, uid)
                else:
                    log.warning("%s digest for %s failed: %s", kind, uid, result.get("error"))
            except Exception as e:
                log.warning("%s digest for %s errored: %s", kind, uid, e)
    return sent
