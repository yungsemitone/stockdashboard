"""Account auth: email + username + password sign-in with server-side sessions.

The old shared family password (DASHBOARD_PASSWORD) lives on in two roles:
  * the *invite code* required to create an account (keeps strangers out of a
    public signup form), and
  * a *service token* for trusted server-to-server callers (The Morning Desk)
    — service calls read as the primary account for user-scoped data but can
    never mutate it.
"""

import hmac
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import settings
from ..providers import alerts, users, watchlist

router = APIRouter()

# Login/signup attempts per IP per 5 minutes.
_attempts: dict[str, list[float]] = defaultdict(list)
_RATE_N = 12


def _rate_ok(request: Request) -> bool:
    ip = request.headers.get("fly-client-ip") or (
        request.client.host if request.client else "anon"
    )
    now = time.time()
    recent = [t for t in _attempts[ip] if now - t < 300]
    recent.append(now)
    _attempts[ip] = recent
    return len(recent) <= _RATE_N


def _bearer(request: Request) -> str:
    return (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()


def is_service(request: Request) -> bool:
    pw = settings.dashboard_password
    return bool(pw) and hmac.compare_digest(_bearer(request), pw)


def token_ok(request: Request) -> bool:
    """May this request use the API at all? (Sessions, the service token, or
    everything when auth is disabled in dev.)"""
    if not settings.dashboard_password:
        return True
    if is_service(request):
        return True
    return users.user_for_token(_bearer(request)) is not None


def current_account(request: Request) -> dict:
    """The account this request acts as. Sessions map to their user; the
    service token (and dev mode with no password) reads as the primary account."""
    u = users.user_for_token(_bearer(request))
    if u:
        return u
    if is_service(request) or not settings.dashboard_password:
        pid = users.primary_user_id()
        if pid:
            pu = users.public_by_id(pid)
            if pu:
                return pu
    raise HTTPException(401, "Sign in required")


def require_account(request: Request) -> dict:
    """A real signed-in session — the service token can't mutate user data."""
    u = users.user_for_token(_bearer(request))
    if not u:
        raise HTTPException(401, "Sign in required")
    return u


class SignupIn(BaseModel):
    email: str
    username: str
    password: str
    code: str = ""  # the family password, as an invite code


class LoginIn(BaseModel):
    identifier: str  # email or username
    password: str


@router.post("/auth/signup")
def signup(body: SignupIn, request: Request):
    if not _rate_ok(request):
        raise HTTPException(429, "Too many attempts — give it a few minutes.")
    if settings.dashboard_password and not hmac.compare_digest(
        body.code.strip(), settings.dashboard_password
    ):
        return {"ok": False, "error": "Wrong family code."}
    try:
        user, token = users.signup(body.email, body.username, body.password)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    # First account inherits the pre-accounts shared watchlists; any account
    # whose username matches an old alerts profile adopts it (rules, delivery
    # settings, history).
    if users.count() == 1:
        watchlist.claim_legacy(user["id"])
    alerts.claim_legacy_profile(user["username"], user["id"], user["email"])
    return {"ok": True, "token": token, "user": user}


@router.post("/auth/login")
def login(body: LoginIn, request: Request):
    if not _rate_ok(request):
        raise HTTPException(429, "Too many attempts — give it a few minutes.")
    got = users.login(body.identifier, body.password)
    if got is None:
        return {"ok": False, "error": "Wrong username/email or password."}
    user, token = got
    return {"ok": True, "token": token, "user": user}


class ForgotIn(BaseModel):
    identifier: str  # email or username


class ResetIn(BaseModel):
    identifier: str
    code: str
    password: str


@router.post("/auth/forgot")
def forgot(body: ForgotIn, request: Request):
    """Email a 6-digit reset code (15-minute life). Always claims success so
    the form can't be used to probe which accounts exist."""
    if not _rate_ok(request):
        raise HTTPException(429, "Too many attempts — give it a few minutes.")
    if not alerts.smtp_configured():
        return {"ok": False, "error": "Email isn't set up on the server."}
    got = users.start_reset(body.identifier)
    if got:
        user, code = got
        try:
            alerts.send_email(
                [user["email"]],
                "Markets password reset",
                f"Hi {user['username']} — your reset code is {code}. "
                "It expires in 15 minutes.\n\nIf you didn't ask for this, ignore it.",
            )
        except Exception:
            return {"ok": False, "error": "Couldn't send the email — try again."}
    return {"ok": True}


@router.post("/auth/reset")
def reset(body: ResetIn, request: Request):
    if not _rate_ok(request):
        raise HTTPException(429, "Too many attempts — give it a few minutes.")
    try:
        got = users.finish_reset(body.identifier, body.code, body.password)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    if got is None:
        return {"ok": False, "error": "That code didn't work — request a new one."}
    user, token = got
    return {"ok": True, "token": token, "user": user}


@router.post("/auth/logout")
def logout(request: Request):
    users.logout(_bearer(request))
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request):
    u = users.user_for_token(_bearer(request))
    if not u:
        raise HTTPException(401, "Not signed in")
    return {"user": u}


@router.get("/auth/status")
def status(request: Request):
    """Whether sign-in is required and whether this request has a session.
    (The service token deliberately doesn't count — browsers must sign in.)"""
    return {
        "required": bool(settings.dashboard_password),
        "ok": users.user_for_token(_bearer(request)) is not None
        or not settings.dashboard_password,
        "has_accounts": users.count() > 0,
    }
