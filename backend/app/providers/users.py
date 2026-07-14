"""User accounts + sessions (file-backed, family-scale).

Passwords are salted PBKDF2-HMAC-SHA256 (600k iterations — stdlib only, no new
dependencies). Sessions are opaque server-side tokens with a 90-day life.
Writes are atomic (tmp file + os.replace) so a crash can't corrupt the store.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

from ..config import settings

_BASE = (
    Path(settings.data_dir)
    if settings.data_dir
    else Path(__file__).resolve().parent.parent.parent / "data"
)
_PATH = _BASE / "users.json"
_lock = threading.Lock()

PBKDF2_ITERS = 600_000
SESSION_DAYS = 90
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9 _-]{2,24}$")


def _read() -> dict:
    try:
        data = json.loads(_PATH.read_text())
        if isinstance(data, dict):
            return {
                "users": data.get("users") or [],
                "sessions": data.get("sessions") or {},
            }
    except Exception:
        pass
    return {"users": [], "sessions": {}}


def _write(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, _PATH)


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2${PBKDF2_ITERS}${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


def _public(u: dict) -> dict:
    return {"id": u["id"], "username": u["username"], "email": u["email"]}


def _new_session(data: dict, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    cutoff = time.time() - SESSION_DAYS * 86400
    data["sessions"] = {
        t: s for t, s in data["sessions"].items() if s.get("created", 0) > cutoff
    }
    data["sessions"][token] = {"user_id": user_id, "created": time.time()}
    return token


def signup(email: str, username: str, password: str) -> tuple[dict, str]:
    """Create an account; returns (public user, session token) or raises ValueError."""
    email = email.strip().lower()
    username = username.strip()
    if not _EMAIL_RE.match(email):
        raise ValueError("That email doesn't look right.")
    if not _USERNAME_RE.match(username):
        raise ValueError("Usernames are 2-24 letters, numbers, spaces, - or _.")
    if len(password) < 8:
        raise ValueError("Password needs at least 8 characters.")
    with _lock:
        data = _read()
        for u in data["users"]:
            if u["email"] == email:
                raise ValueError("That email already has an account.")
            if u["username"].lower() == username.lower():
                raise ValueError("That username is taken.")
        user = {
            "id": "u_" + secrets.token_hex(6),
            "email": email,
            "username": username,
            "pw_hash": _hash_password(password),
            "created": time.time(),
        }
        data["users"].append(user)
        token = _new_session(data, user["id"])
        _write(data)
    return _public(user), token


def login(identifier: str, password: str) -> tuple[dict, str] | None:
    """identifier = email or username (case-insensitive)."""
    ident = identifier.strip().lower()
    with _lock:
        data = _read()
        user = next(
            (
                u
                for u in data["users"]
                if u["email"] == ident or u["username"].lower() == ident
            ),
            None,
        )
        if user is None or not _verify_password(password, user["pw_hash"]):
            return None
        token = _new_session(data, user["id"])
        _write(data)
    return _public(user), token


def logout(token: str) -> None:
    with _lock:
        data = _read()
        if data["sessions"].pop(token, None) is not None:
            _write(data)


def user_for_token(token: str) -> dict | None:
    """The public user for a session token, or None."""
    if not token:
        return None
    with _lock:
        data = _read()
    sess = data["sessions"].get(token)
    if not sess or sess.get("created", 0) < time.time() - SESSION_DAYS * 86400:
        return None
    user = next((u for u in data["users"] if u["id"] == sess["user_id"]), None)
    return _public(user) if user else None


def public_by_id(user_id: str) -> dict | None:
    with _lock:
        data = _read()
    user = next((u for u in data["users"] if u["id"] == user_id), None)
    return _public(user) if user else None


def public_by_username(username: str) -> dict | None:
    name = username.strip().lower()
    with _lock:
        data = _read()
    user = next((u for u in data["users"] if u["username"].lower() == name), None)
    return _public(user) if user else None


# --- password reset -----------------------------------------------------------


def start_reset(identifier: str) -> tuple[dict, str] | None:
    """If the account exists, set a short-lived 6-digit reset code and return
    (public user, code) for emailing; None otherwise (caller stays silent so
    the form can't probe for accounts)."""
    ident = identifier.strip().lower()
    with _lock:
        data = _read()
        user = next(
            (
                u
                for u in data["users"]
                if u["email"] == ident or u["username"].lower() == ident
            ),
            None,
        )
        if user is None:
            return None
        code = f"{secrets.randbelow(1_000_000):06d}"
        user["reset"] = {
            "code_hash": hashlib.sha256(code.encode()).hexdigest(),
            "expires": time.time() + 15 * 60,
            "attempts": 0,
        }
        _write(data)
    return _public(user), code


def finish_reset(identifier: str, code: str, new_password: str) -> tuple[dict, str] | None:
    """Verify the emailed code and set the new password. Old sessions are
    revoked; returns (public user, fresh session token) or None."""
    if len(new_password) < 8:
        raise ValueError("Password needs at least 8 characters.")
    ident = identifier.strip().lower()
    with _lock:
        data = _read()
        user = next(
            (
                u
                for u in data["users"]
                if u["email"] == ident or u["username"].lower() == ident
            ),
            None,
        )
        r = (user or {}).get("reset")
        if not user or not r:
            return None
        if r.get("expires", 0) < time.time() or r.get("attempts", 0) >= 5:
            user.pop("reset", None)
            _write(data)
            return None
        supplied = hashlib.sha256(code.strip().encode()).hexdigest()
        if not hmac.compare_digest(supplied, r.get("code_hash", "")):
            r["attempts"] = r.get("attempts", 0) + 1
            _write(data)
            return None
        user.pop("reset", None)
        user["pw_hash"] = _hash_password(new_password)
        # Sign out everywhere — old sessions die with the old password.
        data["sessions"] = {
            t: s for t, s in data["sessions"].items() if s.get("user_id") != user["id"]
        }
        token = _new_session(data, user["id"])
        _write(data)
    return _public(user), token


def primary_user_id() -> str | None:
    """The first account ever created — it inherits the pre-accounts shared
    data, and it's what the Morning Desk's service token reads as."""
    with _lock:
        data = _read()
    users = sorted(data["users"], key=lambda u: u.get("created", 0))
    return users[0]["id"] if users else None


def count() -> int:
    with _lock:
        return len(_read()["users"])
