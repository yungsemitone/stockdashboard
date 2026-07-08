"""Price alerts: per-person rules evaluated server-side on a schedule.

Alerts are grouped into named *profiles* (Netflix-style — no passwords, it's a
family app): each person has their own rules, delivery settings, and event
history in DATA_DIR/alerts.json. The scheduler calls check_all() every minute;
a rule fires when its condition *becomes* true (edge-triggered, so a stock
sitting at +4% doesn't re-fire every minute, with a per-rule cooldown against
boundary flapping). Fires are recorded as events for that person's bell, and —
when SMTP is configured — sent to *their* email and/or phone (texts ride the
carrier's email→SMS gateway).
"""

from __future__ import annotations

import json
import logging
import re
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
MAX_PROFILES = 8

# Profile names are shown in the UI and used as storage keys — keep them tame.
_NAME_RE = re.compile(r"^[A-Za-z0-9 _-]{1,24}$")


def valid_name(name: str) -> bool:
    return bool(_NAME_RE.match(name or ""))


# --- storage ----------------------------------------------------------------


def _fresh_profile() -> dict:
    return {"rules": [], "settings": dict(DEFAULT_SETTINGS), "events": []}


def _clean_profile(p: dict) -> dict:
    return {
        "rules": p.get("rules") or [],
        "settings": {**DEFAULT_SETTINGS, **(p.get("settings") or {})},
        "events": p.get("events") or [],
    }


def _read() -> dict:
    """Load {"profiles": {name: {rules, settings, events}}}, migrating the
    original single-user format to a profile for the app's owner."""
    try:
        data = json.loads(_PATH.read_text())
    except Exception:
        return {"profiles": {}}
    if isinstance(data, dict) and isinstance(data.get("profiles"), dict):
        return {
            "profiles": {
                str(name): _clean_profile(p)
                for name, p in data["profiles"].items()
                if isinstance(p, dict)
            }
        }
    if isinstance(data, dict) and "rules" in data:  # pre-profile layout
        return {"profiles": {"Aden": _clean_profile(data)}}
    return {"profiles": {}}


def _write(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        log.warning("couldn't persist alerts.json", exc_info=True)


def _get_or_create(data: dict, profile: str) -> dict:
    profs = data["profiles"]
    if profile not in profs:
        if len(profs) >= MAX_PROFILES:
            raise ValueError(f"Profile limit reached ({MAX_PROFILES})")
        profs[profile] = _fresh_profile()
    return profs[profile]


# --- public state / CRUD -----------------------------------------------------


def list_profiles() -> list[str]:
    with _lock:
        return sorted(_read()["profiles"])


def create_profile(name: str) -> list[str]:
    """Register a profile immediately so the name survives switching even
    before its first rule or setting is saved."""
    with _lock:
        data = _read()
        _get_or_create(data, name)
        _write(data)
        return sorted(data["profiles"])


def delete_profile(name: str) -> list[str]:
    """Remove a profile and everything in it (rules, settings, history)."""
    with _lock:
        data = _read()
        data["profiles"].pop(name, None)
        _write(data)
        return sorted(data["profiles"])


def get_state(profile: str) -> dict:
    with _lock:
        p = _read()["profiles"].get(profile) or _fresh_profile()
    return {
        "profile": profile,
        "rules": p["rules"],
        "settings": p["settings"],
        "events": list(reversed(p["events"][-25:])),  # newest first
        "email_configured": smtp_configured(),
        "sms_carriers": list(SMS_GATEWAYS),
    }


def create_rule(
    profile: str,
    symbol: str,
    name: str | None,
    kind: str,
    threshold: float,
    direction: str,
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
        p = _get_or_create(data, profile)
        if len(p["rules"]) >= MAX_RULES:
            raise ValueError(f"Alert limit reached ({MAX_RULES})")
        p["rules"].append(rule)
        _write(data)
    return get_state(profile)


def update_rule(
    profile: str,
    rule_id: str,
    enabled: bool | None = None,
    threshold: float | None = None,
    direction: str | None = None,
) -> dict | None:
    with _lock:
        data = _read()
        p = data["profiles"].get(profile)
        rule = next((r for r in (p or {}).get("rules", []) if r["id"] == rule_id), None)
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
    return get_state(profile)


def delete_rule(profile: str, rule_id: str) -> dict:
    with _lock:
        data = _read()
        p = data["profiles"].get(profile)
        if p:
            p["rules"] = [r for r in p["rules"] if r["id"] != rule_id]
            _write(data)
    return get_state(profile)


def update_settings(profile: str, patch: dict) -> dict:
    with _lock:
        data = _read()
        cfg = _get_or_create(data, profile)["settings"]
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
    return get_state(profile)


def events_since(profile: str, ts: float) -> list[dict]:
    with _lock:
        p = _read()["profiles"].get(profile)
    if not p:
        return []
    return [e for e in p["events"] if e["ts"] > ts][-20:]


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
    """Evaluate every profile's enabled rules; record + send fires per person.
    One shared quote snapshot covers everyone. Returns the total fired."""
    with _lock:
        snapshot = _read()
    symbols = sorted(
        {
            r["symbol"]
            for p in snapshot["profiles"].values()
            for r in p["rules"]
            if r.get("enabled")
        }
    )
    if not symbols:
        return 0

    quotes = market.snapshot_quotes(symbols)  # network — outside the lock

    now = time.time()
    batches: list[tuple[list[dict], dict]] = []  # (fired events, that profile's settings)
    changed = False
    with _lock:
        data = _read()  # re-read so concurrent edits aren't clobbered
        for prof in data["profiles"].values():
            cooldown = max(0, int(prof["settings"].get("cooldown_min", 60))) * 60
            fired: list[dict] = []
            for rule in prof["rules"]:
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
                    prof["events"] = (prof["events"] + [event])[-MAX_EVENTS:]
                    rule["last_fired"] = now
                    fired.append(event)
                if active != was_active:
                    rule["active"] = active
                    changed = True
            if fired:
                batches.append((fired, dict(prof["settings"])))
        if batches or changed:
            _write(data)

    for fired, cfg in batches:
        _notify(fired, cfg)
    return sum(len(f) for f, _ in batches)


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


def send_test(profile: str, channel: str) -> dict:
    """Send a test message so delivery can be verified from the UI."""
    if not smtp_configured():
        return {
            "ok": False,
            "error": "Email isn't set up on the server yet (SMTP_HOST / SMTP_USER / SMTP_PASS secrets).",
        }
    cfg = get_state(profile)["settings"]
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
