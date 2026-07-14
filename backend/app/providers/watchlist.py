"""File-backed, multi-list watchlists — one set per account.

Stored as: {"users": {user_id: [{"name", "symbols"}, ...]}, "legacy": [...]}.
"legacy" holds the pre-accounts shared lists; the first account created claims
them (see routers/auth.py), and until any account exists the service token
(The Morning Desk) still reads them, so nothing breaks mid-migration.
Older single-user formats migrate automatically on read.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ..config import settings

_BASE = (
    Path(settings.data_dir)
    if settings.data_dir
    else Path(__file__).resolve().parent.parent.parent / "data"
)
_PATH = _BASE / "watchlist.json"
_lock = threading.Lock()

DEFAULT_LISTS = [{"name": "Default", "symbols": ["AAPL", "NVDA", "^GSPC", "BTC-USD"]}]


def _clean_lists(lists) -> list[dict]:
    out = []
    for l in lists or []:
        if isinstance(l, dict) and isinstance(l.get("name"), str):
            out.append(
                {
                    "name": l["name"],
                    "symbols": [s for s in (l.get("symbols") or []) if isinstance(s, str)],
                }
            )
    return out


def _read() -> dict:
    try:
        data = json.loads(_PATH.read_text())
    except Exception:
        return {"users": {}, "legacy": []}
    # Current shape.
    if isinstance(data, dict) and "users" in data:
        return {
            "users": {
                str(uid): _clean_lists(lists)
                for uid, lists in (data.get("users") or {}).items()
            },
            "legacy": _clean_lists(data.get("legacy")),
        }
    # Pre-accounts shape: {"lists": [...]} — becomes the legacy pool.
    if isinstance(data, dict) and isinstance(data.get("lists"), list):
        return {"users": {}, "legacy": _clean_lists(data["lists"])}
    # Original single-list shape: a bare array of symbols.
    if isinstance(data, list):
        return {"users": {}, "legacy": [{"name": "Default", "symbols": data}]}
    return {"users": {}, "legacy": []}


def _write(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, _PATH)


def _fresh() -> list[dict]:
    return [dict(name=l["name"], symbols=list(l["symbols"])) for l in DEFAULT_LISTS]


def _lists_for(data: dict, user_id: str | None) -> list[dict]:
    if user_id and user_id in data["users"]:
        return data["users"][user_id]
    if user_id is None:
        return data["legacy"]  # service caller before any account exists
    # First touch for this account: start with the defaults.
    data["users"][user_id] = _fresh()
    return data["users"][user_id]


def claim_legacy(user_id: str) -> None:
    """Hand the pre-accounts shared lists to their new owner (first account)."""
    with _lock:
        data = _read()
        if data["legacy"] and user_id not in data["users"]:
            data["users"][user_id] = data["legacy"]
            data["legacy"] = []
            _write(data)


def get_all(user_id: str | None) -> list[dict]:
    with _lock:
        data = _read()
        first_touch = bool(user_id) and user_id not in data["users"]
        lists = _lists_for(data, user_id)
        if first_touch:
            _write(data)  # persist the fresh defaults
        return [dict(name=l["name"], symbols=list(l["symbols"])) for l in lists]


def _find(lists: list[dict], name: str) -> dict | None:
    return next((l for l in lists if l["name"] == name), None)


def create(user_id: str, name: str) -> list[dict]:
    name = name.strip()
    with _lock:
        data = _read()
        lists = _lists_for(data, user_id)
        if name and not _find(lists, name):
            lists.append({"name": name, "symbols": []})
        _write(data)
        return [dict(l) for l in lists]


def delete(user_id: str, name: str) -> list[dict]:
    with _lock:
        data = _read()
        lists = [l for l in _lists_for(data, user_id) if l["name"] != name]
        if not lists:  # always keep at least one list
            lists = [{"name": "Default", "symbols": []}]
        data["users"][user_id] = lists
        _write(data)
        return [dict(l) for l in lists]


def rename(user_id: str, old: str, new: str) -> list[dict]:
    new = new.strip()
    with _lock:
        data = _read()
        lists = _lists_for(data, user_id)
        target = _find(lists, old)
        if target and new and not _find(lists, new):
            target["name"] = new
        _write(data)
        return [dict(l) for l in lists]


def add(user_id: str, name: str, symbol: str) -> list[dict]:
    symbol = symbol.strip()
    with _lock:
        data = _read()
        lists = _lists_for(data, user_id)
        target = _find(lists, name)
        if target and symbol and symbol not in target["symbols"]:
            target["symbols"].append(symbol)
        _write(data)
        return [dict(l) for l in lists]


def remove(user_id: str, name: str, symbol: str) -> list[dict]:
    with _lock:
        data = _read()
        lists = _lists_for(data, user_id)
        target = _find(lists, name)
        if target:
            target["symbols"] = [s for s in target["symbols"] if s != symbol]
        _write(data)
        return [dict(l) for l in lists]
