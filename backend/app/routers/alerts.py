import time

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..providers import alerts

router = APIRouter()

# Every alerts call is scoped to a named profile (each family member has their
# own rules, delivery settings, and history).
Profile = Query(..., min_length=1, max_length=24)


def _check_name(profile: str) -> str:
    profile = profile.strip()
    if not alerts.valid_name(profile):
        raise HTTPException(400, "Profile names: letters, numbers, spaces, - or _")
    return profile


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


class TestIn(BaseModel):
    channel: str = "email"  # email | sms


@router.get("/alerts")
def get_alerts(profile: str = Profile):
    """One profile's rules, delivery settings, and recent trigger events."""
    return alerts.get_state(_check_name(profile))


@router.post("/alerts")
def create_alert(rule: RuleIn, profile: str = Profile):
    if not rule.symbol.strip():
        raise HTTPException(400, "symbol required")
    if rule.threshold <= 0:
        raise HTTPException(400, "threshold must be positive")
    try:
        return alerts.create_rule(
            _check_name(profile), rule.symbol, rule.name, rule.kind, rule.threshold, rule.direction
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# Static paths must be declared before the /{rule_id} catch-alls.


@router.get("/alerts/profiles")
def alert_profiles():
    """Names with an alerts setup — for the who-is-this picker."""
    return {"profiles": alerts.list_profiles()}


class ProfileIn(BaseModel):
    name: str


@router.post("/alerts/profiles")
def create_alert_profile(body: ProfileIn):
    """Register a name right away so it persists before any rules exist."""
    try:
        return {"profiles": alerts.create_profile(_check_name(body.name))}
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/alerts/events")
def alert_events(since: float = 0, profile: str = Profile):
    """Trigger events newer than `since` (epoch seconds) — polled by the bell."""
    return {"events": alerts.events_since(_check_name(profile), since), "now": time.time()}


@router.put("/alerts/settings")
def update_alert_settings(patch: SettingsPatch, profile: str = Profile):
    return alerts.update_settings(
        _check_name(profile), {k: v for k, v in patch.model_dump().items() if v is not None}
    )


@router.post("/alerts/test")
def test_alert(body: TestIn, profile: str = Profile):
    return alerts.send_test(_check_name(profile), body.channel)


@router.post("/alerts/check")
def run_check():
    """Evaluate all profiles' rules right now (the scheduler also does this every minute)."""
    return {"fired": alerts.check_all()}


@router.put("/alerts/{rule_id}")
def update_alert(rule_id: str, patch: RulePatch, profile: str = Profile):
    out = alerts.update_rule(
        _check_name(profile), rule_id, patch.enabled, patch.threshold, patch.direction
    )
    if out is None:
        raise HTTPException(404, "no such alert")
    return out


@router.delete("/alerts/{rule_id}")
def delete_alert(rule_id: str, profile: str = Profile):
    return alerts.delete_rule(_check_name(profile), rule_id)
