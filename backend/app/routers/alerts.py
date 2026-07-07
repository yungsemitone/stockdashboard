import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..providers import alerts

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


class TestIn(BaseModel):
    channel: str = "email"  # email | sms


@router.get("/alerts")
def get_alerts():
    """Rules, delivery settings, and recent trigger events."""
    return alerts.get_state()


@router.post("/alerts")
def create_alert(rule: RuleIn):
    if not rule.symbol.strip():
        raise HTTPException(400, "symbol required")
    if rule.threshold <= 0:
        raise HTTPException(400, "threshold must be positive")
    try:
        return alerts.create_rule(
            rule.symbol, rule.name, rule.kind, rule.threshold, rule.direction
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# Static paths must be declared before the /{rule_id} catch-alls.


@router.get("/alerts/events")
def alert_events(since: float = 0):
    """Trigger events newer than `since` (epoch seconds) — polled by the bell."""
    return {"events": alerts.events_since(since), "now": time.time()}


@router.put("/alerts/settings")
def update_alert_settings(patch: SettingsPatch):
    return alerts.update_settings(
        {k: v for k, v in patch.model_dump().items() if v is not None}
    )


@router.post("/alerts/test")
def test_alert(body: TestIn):
    return alerts.send_test(body.channel)


@router.post("/alerts/check")
def run_check():
    """Evaluate all rules right now (the scheduler also runs this every minute)."""
    return {"fired": alerts.check_all()}


@router.put("/alerts/{rule_id}")
def update_alert(rule_id: str, patch: RulePatch):
    out = alerts.update_rule(rule_id, patch.enabled, patch.threshold, patch.direction)
    if out is None:
        raise HTTPException(404, "no such alert")
    return out


@router.delete("/alerts/{rule_id}")
def delete_alert(rule_id: str):
    return alerts.delete_rule(rule_id)
