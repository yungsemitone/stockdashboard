"""Shared-password gate for the dashboard.

One family password (DASHBOARD_PASSWORD env/secret) protects every /api route
via the middleware in main.py. Logging in returns a bearer token the frontend
stores per device; The Morning Desk sends the same token server-to-server.
When no password is configured, everything stays open (local dev, and
production until the secret is set).
"""

import hmac

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..config import settings

router = APIRouter()


def token_ok(request: Request) -> bool:
    """Does the request carry the right bearer token? (True when auth is off.)"""
    if not settings.dashboard_password:
        return True
    supplied = (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
    return hmac.compare_digest(supplied, settings.dashboard_password)


class LoginIn(BaseModel):
    password: str


@router.post("/auth/login")
def login(body: LoginIn):
    if not settings.dashboard_password:
        return {"ok": True, "required": False, "token": ""}
    if hmac.compare_digest(body.password, settings.dashboard_password):
        return {"ok": True, "required": True, "token": settings.dashboard_password}
    return {"ok": False, "required": True}


@router.get("/auth/status")
def status(request: Request):
    """Whether a password is required, and whether this request has it."""
    return {"required": bool(settings.dashboard_password), "ok": token_ok(request)}
