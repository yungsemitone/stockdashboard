"""Morning brief + evening wrap: per-account weekday email newsletters.

The scheduler calls check_and_send() every minute; each account gets its
enabled editions once per weekday at its chosen ET times (a two-hour grace
window makes restarts safe; "digest_last"/"evening_last" track the sent date).

Both editions carry the index snapshot, every watchlist (categorized), the
portfolio with P/L, and the day's economic calendar. Two AI takes — one for
the market/watchlists, one just for the portfolio — are grounded in real
inputs (headlines market-wide and per-name, analyst targets, upcoming
earnings, macro data), so the morning names catalysts and the evening names
causes. Emails go out as a warm HTML newsletter with a plain-text fallback.
"""

from __future__ import annotations

import logging

from .. import universe
from ..config import settings
from . import alerts, analyst, earnings, economy, market, news, portfolio, users, watchlist
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

    # Every watchlist, kept categorized; movers first within each list.
    lists = []
    all_syms: set[str] = set()
    try:
        raw_lists = [l for l in watchlist.get_all(user_id) if l["symbols"]][:4]
        for l in raw_lists:
            all_syms.update(l["symbols"][:15])
        quotes = market.snapshot_quotes(sorted(all_syms)) if all_syms else {}
        for l in raw_lists:
            rows = [quotes[s] for s in l["symbols"][:15] if s in quotes]
            rows.sort(key=lambda q: -abs(q.get("change_pct") or 0))
            if rows:
                lists.append({"name": l["name"], "rows": rows[:8]})
    except Exception:
        pass

    # The portfolio, valued.
    pf = None
    try:
        got = portfolio.valued(user_id)
        if got["holdings"]:
            pf = got
    except Exception:
        pass

    # Today's calendar (exact-day, all tiers — same as the dashboard).
    cal: list[dict] = []
    try:
        for e in econ_calendar.events_for_date(et.date()):
            t = e.get("time_et") or "time TBD"
            if e.get("approximate"):
                t = f"≈ {t}"
            cal.append({"name": e["name"], "time": t, "importance": e["importance"]})
    except Exception:
        pass

    # --- context that makes the takes smart (not shown as email sections) ---
    headlines: list[str] = []
    try:
        headlines = [
            f"{a['title']} ({a.get('publisher', '')})"
            for a in news.market_news(8)
            if a.get("title")
        ]
    except Exception:
        pass

    pf_symbols = [h["symbol"] for h in (pf["holdings"] if pf else [])]
    focus = list(dict.fromkeys(pf_symbols + sorted(all_syms)))[:12]

    sym_news: dict[str, str] = {}
    for s in focus[:10]:
        try:
            a = news.top_headline(s)
            if a and a.get("title"):
                sym_news[s] = a["title"]
        except Exception:
            continue

    analyst_notes: list[str] = []
    for s in pf_symbols[:8]:
        try:
            c = analyst.consensus(s)
            if c.get("available") and c.get("targets", {}).get("mean"):
                up = c.get("upside_pct")
                buy = (c.get("distribution") or {}).get("buy_pct")
                bits = f"{s}: mean analyst target ${c['targets']['mean']:,.0f}"
                if up is not None:
                    bits += f" ({up:+.0f}% vs price)"
                if buy is not None:
                    bits += f", {buy:.0f}% buy ratings"
                analyst_notes.append(bits)
        except Exception:
            continue

    earn_soon: list[str] = []
    try:
        for e in earnings.upcoming_for(focus, days=10):
            earn_soon.append(
                f"{e['symbol']} reports earnings {e['date']} (in {e['days_away']}d)"
            )
    except Exception:
        pass

    econ_ctx = ""
    try:
        econ_ctx = economy.headline_context()
    except Exception:
        pass

    return {
        "date_word": et.strftime("%A, %b %-d"),
        "indices": indices,
        "watchlists": lists,
        "portfolio": pf,
        "calendar": cal,
        "headlines": headlines,
        "sym_news": sym_news,
        "analyst_notes": analyst_notes,
        "earnings_soon": earn_soon,
        "econ_ctx": econ_ctx,
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


def _money(n: float | None, digits: int = 2) -> str:
    return "n/a" if n is None else f"${n:,.{digits}f}"


def _signed(n: float | None) -> str:
    if n is None:
        return "n/a"
    return f"{'+' if n >= 0 else '-'}${abs(n):,.2f}"


# --- the takes -----------------------------------------------------------------


def _context_block(d: dict, include_portfolio: bool) -> str:
    out = ["Indices:"]
    for q in d["indices"]:
        n, px, pct = _quote_bits(q)
        out.append(f"  {n}: {px}" + (f" ({pct:+.2f}%)" if pct is not None else ""))
    for wl in d["watchlists"]:
        out.append(f"Watchlist '{wl['name']}':")
        for q in wl["rows"]:
            _, px, pct = _quote_bits(q)
            out.append(
                f"  {q.get('symbol')}: {px}"
                + (f" ({pct:+.2f}%)" if pct is not None else "")
            )
    if include_portfolio and d["portfolio"]:
        t = d["portfolio"]["totals"]
        out.append(
            f"Portfolio: value {_money(t['value'], 0)}, today {_signed(t['day_pl'])}"
            + (f" ({t['day_pl_pct']:+.2f}%)" if t["day_pl_pct"] is not None else "")
            + f", all-time {_signed(t['total_pl'])}"
        )
        for h in d["portfolio"]["holdings"]:
            out.append(
                f"  {h['symbol']}: {h['shares']} sh @ {_money(h['cost'])} avg, now {_money(h['price'])}"
                + (f" ({h['change_pct']:+.2f}% today)" if h["change_pct"] is not None else "")
                + (f", day P/L {_signed(h['day_pl'])}" if h["day_pl"] is not None else "")
                + (
                    f", total {_signed(h['total_pl'])} ({h['total_pl_pct']:+.1f}%)"
                    if h["total_pl"] is not None and h["total_pl_pct"] is not None
                    else ""
                )
            )
    if d["calendar"]:
        out.append("Today's economic calendar:")
        out += [f"  {e['name']} at {e['time']}" for e in d["calendar"]]
    if d["headlines"]:
        out.append("Market headlines:")
        out += [f"  - {h}" for h in d["headlines"]]
    if d["sym_news"]:
        out.append("Latest headline per name:")
        out += [f"  {s}: {t}" for s, t in d["sym_news"].items()]
    if d["analyst_notes"]:
        out.append("Analyst consensus:")
        out += [f"  {a}" for a in d["analyst_notes"]]
    if d["earnings_soon"]:
        out.append("Upcoming earnings:")
        out += [f"  {e}" for e in d["earnings_soon"]]
    if d["econ_ctx"]:
        out.append("Macro backdrop:\n" + d["econ_ctx"])
    return "\n".join(out)


def _claude(prompt: str, max_tokens: int = 700) -> str:
    if not settings.anthropic_api_key:
        return ""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.narrative_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
    except Exception as e:
        log.warning("digest AI take failed: %s", e)
        return ""


def _market_take(d: dict, kind: str, username: str) -> str:
    if kind == "morning":
        ask = (
            "Write the market take for the PRE-OPEN morning note, two short "
            "paragraphs. Paragraph 1: the setup — what overnight futures, the "
            "macro backdrop, and today's scheduled releases imply for the day, "
            "with the mechanism (e.g. how a hot print would hit rates and "
            "high-multiple names), not just direction. Paragraph 2: what "
            "specifically to watch on the watchlists and WHY, the way an "
            "analyst would — name the catalyst (an earnings date, the specific "
            "headline, an analyst target gap, a macro release that hits that "
            "sector), never 'watch X because it's up'. If a headline or "
            "earnings date above explains a move or sets up a decision point, "
            "cite it by name."
        )
    else:
        ask = (
            "Write the market wrap for the AFTER-CLOSE note, two short "
            "paragraphs. Paragraph 1: what happened and WHY — connect the "
            "index moves to the actual drivers in the data (headlines, macro "
            "prints, rates) with the causal chain, not a recitation of "
            "percentages. Paragraph 2: the watchlist story — which names "
            "moved, the REASON behind each notable move (cite the specific "
            "headline or catalyst when one is given above), and what today's "
            "action sets up for tomorrow."
        )
    return _claude(
        f"You are a sharp, plain-spoken buy-side analyst writing {username}'s "
        f"personal market brief. Ground every claim ONLY in this data — never "
        f"invent numbers, headlines, or events:\n\n{_context_block(d, False)}\n\n"
        f"{ask} No preamble, no disclaimers, no bullet lists — flowing prose."
    )


def _portfolio_take(d: dict, kind: str, username: str) -> str:
    if not d["portfolio"]:
        return ""
    if kind == "morning":
        ask = (
            "Write the PORTFOLIO section of the pre-open note: one tight "
            "paragraph (3-6 sentences) ONLY about the holdings above. What "
            "should the owner watch today and WHY — upcoming earnings on a "
            "holding, a specific headline, an analyst target gap, concentration "
            "risk if one position dominates, or a macro release that hits a "
            "holding hardest. Be concrete and cite the data points."
        )
    else:
        ask = (
            "Write the PORTFOLIO section of the after-close note: one tight "
            "paragraph (3-6 sentences) ONLY about the holdings above. Explain "
            "today's P/L — which positions drove it and why (cite the specific "
            "headline or catalyst when given), how the day changed the total "
            "picture vs cost basis, and anything the data says to watch next."
        )
    return _claude(
        f"You are a sharp, plain-spoken buy-side analyst writing {username}'s "
        f"personal portfolio note. Ground every claim ONLY in this data — never "
        f"invent numbers, headlines, or events:\n\n{_context_block(d, True)}\n\n"
        f"{ask} No preamble, no disclaimers — flowing prose."
    )


# --- rendering -----------------------------------------------------------------


def _plain(d: dict, take: str, pf_take: str, kind: str, username: str) -> str:
    out = [
        f"Good {'morning' if kind == 'morning' else 'evening'} {username} — {d['date_word']}",
        "",
        "MARKETS" if kind == "morning" else "MARKETS AT THE CLOSE",
    ]
    for q in d["indices"]:
        n, px, pct = _quote_bits(q)
        out.append(f"  {n}: {px}" + (f" ({pct:+.2f}%)" if pct is not None else ""))
    for wl in d["watchlists"]:
        out += ["", f"WATCHLIST — {wl['name'].upper()}"]
        for q in wl["rows"]:
            _, px, pct = _quote_bits(q)
            out.append(
                f"  {q.get('symbol')}: {px}"
                + (f" ({pct:+.2f}%)" if pct is not None else "")
            )
    if d["portfolio"]:
        t = d["portfolio"]["totals"]
        out += [
            "",
            "YOUR PORTFOLIO",
            f"  Value {_money(t['value'], 0)} · today {_signed(t['day_pl'])}"
            + (f" ({t['day_pl_pct']:+.2f}%)" if t["day_pl_pct"] is not None else "")
            + f" · all-time {_signed(t['total_pl'])}"
            + (f" ({t['total_pl_pct']:+.1f}%)" if t["total_pl_pct"] is not None else ""),
        ]
        for h in d["portfolio"]["holdings"]:
            out.append(
                f"  {h['symbol']}: {_money(h['price'])}"
                + (f" ({h['change_pct']:+.2f}%)" if h["change_pct"] is not None else "")
                + (f" · day {_signed(h['day_pl'])}" if h["day_pl"] is not None else "")
            )
    out += ["", "TODAY'S ECONOMIC CALENDAR"]
    if d["calendar"]:
        out += [f"  {e['name']} — {e['time']}" for e in d["calendar"]]
    else:
        out.append("  No major releases today.")
    if take:
        out += ["", "THE TAKE", take]
    if pf_take:
        out += ["", "YOUR PORTFOLIO — THE TAKE", pf_take]
    out += ["", "— your Markets dashboard"]
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


def _html(d: dict, take: str, pf_take: str, kind: str, username: str) -> str:
    k = KINDS[kind]
    idx = f'<table width="100%" cellpadding="0" cellspacing="0">{_rows(d["indices"], False)}</table>'

    wl_cards = "".join(
        _card(
            f"Watchlist · {wl['name']}",
            k["accent"],
            f'<table width="100%" cellpadding="0" cellspacing="0">{_rows(wl["rows"], True)}</table>',
        )
        for wl in d["watchlists"]
    )

    pf_card = ""
    if d["portfolio"]:
        t = d["portfolio"]["totals"]
        day_txt = _signed(t["day_pl"]) + (
            f" ({t['day_pl_pct']:+.2f}%)" if t["day_pl_pct"] is not None else ""
        )
        all_txt = _signed(t["total_pl"]) + (
            f" ({t['total_pl_pct']:+.1f}%)" if t["total_pl_pct"] is not None else ""
        )
        day_color = "#047857" if t["day_pl"] >= 0 else "#b91c1c"
        all_color = "#047857" if t["total_pl"] >= 0 else "#b91c1c"
        totals = (
            '<div style="margin-bottom:10px;">'
            f'<span style="font-size:22px;font-weight:800;color:#292524;">{_money(t["value"], 0)}</span>'
            f'<div style="font-size:13px;margin-top:2px;">'
            f'<span style="color:{day_color};font-weight:600;">{day_txt}</span>'
            f'<span style="color:#a8a29e;"> today · </span>'
            f'<span style="color:{all_color};font-weight:600;">{all_txt}</span>'
            f'<span style="color:#a8a29e;"> all time</span></div></div>'
        )
        prows = []
        for h in d["portfolio"]["holdings"]:
            day = (
                f'<span style="font-size:12px;color:{"#047857" if (h["day_pl"] or 0) >= 0 else "#b91c1c"};">{_signed(h["day_pl"])}</span>'
                if h["day_pl"] is not None
                else ""
            )
            prows.append(
                '<tr><td style="padding:7px 0;font-size:14px;color:#44403c;">'
                f"<strong>{h['symbol']}</strong>"
                f'<div style="font-size:11px;color:#a8a29e;">{h["shares"]:g} sh · {_money(h["value"], 0)}</div></td>'
                '<td align="right" style="padding:7px 0;white-space:nowrap;">'
                f"{day}&nbsp;&nbsp;{_pct_chip(h['change_pct'])}</td></tr>"
            )
        pf_card = _card(
            "Your portfolio",
            k["accent"],
            totals
            + f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(prows)}</table>',
        )

    if d["calendar"]:
        dot_colors = {"high": "#e11d48", "medium": "#d97706"}
        crows = []
        for e in d["calendar"]:
            dot = (
                f'<span style="display:inline-block;width:8px;height:8px;'
                f'border-radius:999px;background:{dot_colors.get(e.get("importance", ""), "#d6d3d1")};'
                'margin-right:8px;"></span>'
            )
            crows.append(
                '<tr><td style="padding:6px 0;font-size:14px;color:#44403c;">'
                f'{dot}{e["name"]}</td><td align="right" style="padding:6px 0;'
                f'font-size:13px;color:#78716c;white-space:nowrap;">{e["time"]}</td></tr>'
            )
        cal = f'<table width="100%" cellpadding="0" cellspacing="0">{"".join(crows)}</table>'
    else:
        cal = '<div style="font-size:13px;color:#a8a29e;">No major releases today.</div>'

    def take_html(text: str) -> str:
        paras = [p.strip() for p in text.split("\n") if p.strip()]
        return "".join(
            f'<p style="font-size:14px;line-height:1.65;color:#44403c;margin:0 0 10px 0;">{p}</p>'
            for p in paras
        )

    take_card = (
        _card("The take", k["accent"], take_html(take), k["wash"]) if take else ""
    )
    pf_take_card = (
        _card("Your portfolio — the take", k["accent"], take_html(pf_take), k["wash"])
        if pf_take
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
{wl_cards}
{pf_card}
{_card("Today's economic calendar", k['accent'], cal)}
{take_card}
{pf_take_card}
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
    take = _market_take(d, kind, account["username"])
    pf_take = _portfolio_take(d, kind, account["username"])
    k = KINDS[kind]
    subject = f"{k['emoji']} {k['title']} — {d['date_word']}"
    try:
        alerts.send_email(
            [to],
            subject,
            _plain(d, take, pf_take, kind, account["username"]),
            html=_html(d, take, pf_take, kind, account["username"]),
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
