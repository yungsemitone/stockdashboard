"""Price alerts: user-defined rules evaluated server-side on a schedule.

Rules live in DATA_DIR/alerts.json (same pattern as the watchlists). The
scheduler calls check_all() every minute; a rule fires when its condition
*becomes* true (edge-triggered, so a stock sitting at +4% doesn't re-fire every
minute, with a per-rule cooldown against boundary flapping). Fires are recorded
as events for the frontend bell, and — when SMTP is configured — sent as email
and/or a text via the carrier's email→SMS gateway.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path

from ..config import settings
from . import market

log = logging.getLogger("alerts")

_BASE = (
    Path(settings.data_dir)
    if settings.data_dir
    else Path(__file__).resolve().parent.parent.parent / "data"
)
_PATH = _BASE / "alerts.json"
_lock = threading.Lock()

KINDS = ("move", "above", "below")
DIRECTIONS = ("any", "up", "down")

# Free email→SMS gateways. Delivery is carrier-dependent (AT&T discontinued
# theirs in 2025; Verizon/T-Mobile still run theirs as of mid-2026).
SMS_GATEWAYS = {
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "att": "txt.att.net",
    "cricket": "sms.cricketwireless.net",
    "boost": "sms.myboostmobile.com",
    "uscellular": "email.uscc.net",
}

DEFAULT_SETTINGS = {
    "email_enabled": False,
    "email_to": "",
    "sms_enabled": False,
    "sms_number": "",
    "sms_carrier": "verizon",
    "cooldown_min": 60,
}

MAX_RULES = 50
MAX_EVENTS = 100


# --- storage ----------------------------------------------------------------


def _read() -> dict:
    try:
        data = json.loads(_PATH.read_text())
        if isinstance(data, dict):
            return {
                "rules": data.get("rules") or [],
                "settings": {**DEFAULT_SETTINGS, **(data.get("settings") or {})},
                "events": data.get("events") or [],
            }
    except Exception:
        pass
    return {"rules": [], "settings": dict(DEFAULT_SETTINGS), "events": []}


def _write(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        log.warning("couldn't persist alerts.json", exc_info=True)


# --- public state / CRUD -----------------------------------------------------


def get_state() -> dict:
    with _lock:
        data = _read()
    return {
        "rules": data["rules"],
        "settings": data["settings"],
        "events": list(reversed(data["events"][-25:])),  # newest first
        "email_configured": smtp_configured(),
        "sms_carriers": list(SMS_GATEWAYS),
    }


def create_rule(
    symbol: str, name: str | None, kind: str, threshold: float, direction: str
) -> dict:
    kind = kind if kind in KINDS else "move"
    rule = {
        "id": uuid.uuid4().hex[:10],
        "symbol": symbol.strip(),
        "name": (name or symbol).strip(),
        "kind": kind,
        "threshold": float(threshold),
        "direction": direction if (kind == "move" and direction in DIRECTIONS) else "any",
        "enabled": True,
        "active": False,  # is the condition currently true? (edge-trigger state)
        "last_fired": 0.0,
        "created": time.time(),
    }
    with _lock:
        data = _read()
        if len(data["rules"]) >= MAX_RULES:
            raise ValueError(f"Alert limit reached ({MAX_RULES})")
        data["rules"].append(rule)
        _write(data)
    return get_state()


def update_rule(
    rule_id: str,
    enabled: bool | None = None,
    threshold: float | None = None,
    direction: str | None = None,
) -> dict | None:
    with _lock:
        data = _read()
        rule = next((r for r in data["rules"] if r["id"] == rule_id), None)
        if rule is None:
            return None
        if enabled is not None:
            rule["enabled"] = bool(enabled)
            rule["active"] = False  # re-arm on re-enable
        if threshold is not None and threshold > 0:
            rule["threshold"] = float(threshold)
            rule["active"] = False
        if direction in DIRECTIONS and rule["kind"] == "move":
            rule["direction"] = direction
        _write(data)
    return get_state()


def delete_rule(rule_id: str) -> dict:
    with _lock:
        data = _read()
        data["rules"] = [r for r in data["rules"] if r["id"] != rule_id]
        _write(data)
    return get_state()


def update_settings(patch: dict) -> dict:
    with _lock:
        data = _read()
        cfg = data["settings"]
        for key in ("email_enabled", "sms_enabled"):
            if key in patch:
                cfg[key] = bool(patch[key])
        if "email_to" in patch:
            cfg["email_to"] = str(patch["email_to"]).strip()[:200]
        if "sms_number" in patch:
            cfg["sms_number"] = str(patch["sms_number"]).strip()[:20]
        if "sms_carrier" in patch and patch["sms_carrier"] in SMS_GATEWAYS:
            cfg["sms_carrier"] = patch["sms_carrier"]
        if "cooldown_min" in patch:
            try:
                cfg["cooldown_min"] = min(1440, max(0, int(patch["cooldown_min"])))
            except (TypeError, ValueError):
                pass
        _write(data)
    return get_state()


def events_since(ts: float) -> list[dict]:
    with _lock:
        data = _read()
    return [e for e in data["events"] if e["ts"] > ts][-20:]


# --- evaluation ---------------------------------------------------------------


def _condition(rule: dict, quote: dict) -> tuple[bool, float | None]:
    """Whether the rule's condition holds, and the value that matters."""
    price = quote.get("price")
    pct = quote.get("change_pct")
    if rule["kind"] == "move":
        if pct is None:
            return False, None
        if rule["direction"] == "up":
            return pct >= rule["threshold"], pct
        if rule["direction"] == "down":
            return pct <= -rule["threshold"], pct
        return abs(pct) >= rule["threshold"], pct
    if price is None:
        return False, None
    if rule["kind"] == "above":
        return price >= rule["threshold"], price
    return price <= rule["threshold"], price


def _fmt_price(quote: dict) -> str:
    p = quote.get("price")
    if p is None:
        return "n/a"
    if quote.get("is_level"):
        return f"{p:,.2f}"
    if quote.get("is_fx"):
        return f"{p:,.4f}"
    return f"${p:,.2f}"


def _message(rule: dict, quote: dict) -> str:
    name = rule.get("name") or rule["symbol"]
    pct = quote.get("change_pct")
    px = _fmt_price(quote)
    if rule["kind"] == "move":
        arrow = "▲" if (pct or 0) >= 0 else "▼"
        dir_txt = {"up": f"+{rule['threshold']:g}%", "down": f"-{rule['threshold']:g}%"}.get(
            rule["direction"], f"±{rule['threshold']:g}%"
        )
        return f"{name} ({rule['symbol']}) {arrow} {pct:+.2f}% today at {px} — crossed your {dir_txt} alert"
    word = "above" if rule["kind"] == "above" else "below"
    return f"{name} ({rule['symbol']}) is at {px} — {word} your {rule['threshold']:,.2f} target"


def check_all() -> int:
    """Evaluate every enabled rule; record + send fires. Returns the count."""
    with _lock:
        snapshot = _read()
    enabled = [r for r in snapshot["rules"] if r.get("enabled")]
    if not enabled:
        return 0

    symbols = sorted({r["symbol"] for r in enabled})
    quotes = market.snapshot_quotes(symbols)  # network — outside the lock

    now = time.time()
    fired: list[dict] = []
    changed = False
    with _lock:
        data = _read()  # re-read so concurrent edits aren't clobbered
        cooldown = max(0, int(data["settings"].get("cooldown_min", 60))) * 60
        for rule in data["rules"]:
            if not rule.get("enabled"):
                continue
            q = quotes.get(rule["symbol"]) or {}
            active, value = _condition(rule, q)
            was_active = bool(rule.get("active"))
            if active and not was_active and (now - rule.get("last_fired", 0)) >= cooldown:
                event = {
                    "id": uuid.uuid4().hex[:10],
                    "rule_id": rule["id"],
                    "symbol": rule["symbol"],
                    "name": rule.get("name") or rule["symbol"],
                    "kind": rule["kind"],
                    "threshold": rule["threshold"],
                    "value": value,
                    "price": q.get("price"),
                    "message": _message(rule, q),
                    "ts": now,
                }
                data["events"] = (data["events"] + [event])[-MAX_EVENTS:]
                rule["last_fired"] = now
                fired.append(event)
            if active != was_active:
                rule["active"] = active
                changed = True
        if fired or changed:
            _write(data)
        cfg = dict(data["settings"])

    if fired:
        _notify(fired, cfg)
    return len(fired)


# --- delivery -----------------------------------------------------------------


def smtp_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_pass)


def _send_email(to: list[str], subject: str, body: str) -> None:
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = settings.alerts_from or settings.smtp_user
    msg["To"] = ", ".join(to)
    msg["Subject"] = subject
    msg.set_content(body)
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            s.login(settings.smtp_user, settings.smtp_pass)
            s.send_message(msg)


def _sms_address(number: str, carrier: str) -> str | None:
    digits = "".join(ch for ch in number if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    gateway = SMS_GATEWAYS.get(carrier)
    return f"{digits}@{gateway}" if gateway and len(digits) == 10 else None


def _notify(events: list[dict], cfg: dict) -> None:
    if not smtp_configured():
        return
    subject = (
        f"Price alert: {events[0]['symbol']}"
        if len(events) == 1
        else f"{len(events)} price alerts"
    )
    body = "\n\n".join(e["message"] for e in events)
    if cfg.get("email_enabled") and cfg.get("email_to"):
        try:
            _send_email(
                [cfg["email_to"]], f"📈 {subject}", body + "\n\n— your Markets dashboard"
            )
        except Exception as e:
            log.warning("alert email failed: %s", e)
    if cfg.get("sms_enabled"):
        addr = _sms_address(cfg.get("sms_number", ""), cfg.get("sms_carrier", ""))
        if addr:
            try:
                # Gateways truncate around 160 chars — keep texts terse.
                _send_email([addr], subject, body[:150])
            except Exception as e:
                log.warning("alert text failed: %s", e)


def send_test(channel: str) -> dict:
    """Send a test message so delivery can be verified from the UI."""
    if not smtp_configured():
        return {
            "ok": False,
            "error": "Email isn't set up on the server yet (SMTP_HOST / SMTP_USER / SMTP_PASS secrets).",
        }
    cfg = get_state()["settings"]
    try:
        if channel == "sms":
            addr = _sms_address(cfg.get("sms_number", ""), cfg.get("sms_carrier", ""))
            if not addr:
                return {"ok": False, "error": "Enter a valid 10-digit number and pick a carrier first."}
            _send_email([addr], "Markets test", "Test alert from your Markets dashboard")
        else:
            to = (cfg.get("email_to") or "").strip()
            if not to:
                return {"ok": False, "error": "Enter a destination email first."}
            _send_email(
                [to],
                "📈 Markets test alert",
                "Test alert from your Markets dashboard — email delivery works.",
            )
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"Send failed: {e}"}
