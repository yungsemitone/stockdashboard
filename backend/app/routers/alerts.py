import time

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..providers import alerts, digest, users
from . import auth

router = APIRouter()


class RuleIn(BaseModel):
    symbol: str
    name: str | None = None
    kind: str = "move"  # move | above | below
    threshold: float
    direction: str = "any"  # any | up | down (move rules only)


class RulePatch(BaseModel):
    enabled: bool | None = None
    threshold: float | None = None
    direction: str | None = None


class SettingsPatch(BaseModel):
    email_enabled: bool | None = None
    email_to: str | None = None
    sms_enabled: bool | None = None
    sms_number: str | None = None
    sms_carrier: str | None = None
    cooldown_min: int | None = None
    digest_enabled: bool | None = None
    digest_time: str | None = None
    evening_enabled: bool | None = None
    evening_time: str | None = None
    earnings_alerts: bool | None = None


class TestIn(BaseModel):
    channel: str = "email"  # email | sms


@router.get("/alerts")
def get_alerts(request: Request):
    """The signed-in account's rules, delivery settings, and recent events."""
    user = auth.require_account(request)
    return alerts.get_state(user["id"])


@router.post("/alerts")
def create_alert(rule: RuleIn, request: Request):
    user = auth.require_account(request)
    if not rule.symbol.strip():
        raise HTTPException(400, "symbol required")
    if rule.threshold <= 0:
        raise HTTPException(400, "threshold must be positive")
    try:
        return alerts.create_rule(
            user["id"], rule.symbol, rule.name, rule.kind, rule.threshold, rule.direction
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# Static paths must be declared before the /{rule_id} catch-alls.


@router.get("/alerts/events")
def alert_events(request: Request, since: float = 0):
    """Trigger events newer than `since` (epoch seconds) — polled by the bell."""
    user = auth.require_account(request)
    return {"events": alerts.events_since(user["id"], since), "now": time.time()}


@router.put("/alerts/settings")
def update_alert_settings(patch: SettingsPatch, request: Request):
    user = auth.require_account(request)
    return alerts.update_settings(
        user["id"], {k: v for k, v in patch.model_dump().items() if v is not None}
    )


@router.post("/alerts/test")
def test_alert(body: TestIn, request: Request):
    user = auth.require_account(request)
    return alerts.send_test(user["id"], body.channel)


@router.post("/alerts/check")
def run_check(request: Request):
    """Evaluate all rules right now (the scheduler also does this every minute)."""
    auth.current_account(request)  # any valid credential
    return {"fired": alerts.check_all()}


class AdoptIn(BaseModel):
    legacy_name: str
    username: str


@router.post("/alerts/adopt")
def adopt_legacy(body: AdoptIn, request: Request):
    """Admin (service-token) action: merge a pre-accounts profile into an
    account when the signup username didn't match it."""
    if not auth.is_service(request):
        raise HTTPException(403, "service token required")
    account = users.public_by_username(body.username)
    if account is None:
        raise HTTPException(404, f"no account named {body.username!r}")
    return alerts.adopt_legacy_profile(body.legacy_name, account["id"])


class DigestSendIn(BaseModel):
    kind: str = "morning"  # morning | evening


@router.post("/digest/send")
def send_digest_now(request: Request, body: DigestSendIn | None = None):
    """Send the caller's brief immediately (preview / test)."""
    user = auth.require_account(request)
    return digest.send_to(user["id"], (body or DigestSendIn()).kind)


@router.put("/alerts/{rule_id}")
def update_alert(rule_id: str, patch: RulePatch, request: Request):
    user = auth.require_account(request)
    out = alerts.update_rule(
        user["id"], rule_id, patch.enabled, patch.threshold, patch.direction
    )
    if out is None:
        raise HTTPException(404, "no such alert")
    return out


@router.delete("/alerts/{rule_id}")
def delete_alert(rule_id: str, request: Request):
    user = auth.require_account(request)
    return alerts.delete_rule(user["id"], rule_id)
