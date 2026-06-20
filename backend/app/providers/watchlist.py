"""File-backed, multi-list watchlists (single user, local-first).

Stored as: {"lists": [{"name": "Default", "symbols": [...]}, ...]}
Migrates the old single-list format ([...]) automatically.
"""

from __future__ import annotations

import json
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


def _read() -> list[dict] | None:
    try:
        data = json.loads(_PATH.read_text())
    except Exception:
        return None
    # Migrate the old single-list format (a bare array of symbols).
    if isinstance(data, list):
        return [{"name": "Default", "symbols": data}]
    if isinstance(data, dict) and isinstance(data.get("lists"), list):
        return data["lists"]
    return None


def _write(lists: list[dict]) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps({"lists": lists}, indent=2))


def _load() -> list[dict]:
    lists = _read()
    if lists is None:
        lists = [dict(name=l["name"], symbols=list(l["symbols"])) for l in DEFAULT_LISTS]
        _write(lists)
    return lists


def get_all() -> list[dict]:
    return _load()


def _find(lists: list[dict], name: str) -> dict | None:
    return next((l for l in lists if l["name"] == name), None)


def create(name: str) -> list[dict]:
    name = name.strip()
    with _lock:
        lists = _load()
        if name and not _find(lists, name):
            lists.append({"name": name, "symbols": []})
            _write(lists)
        return lists


def delete(name: str) -> list[dict]:
    with _lock:
        lists = [l for l in _load() if l["name"] != name]
        if not lists:  # always keep at least one list
            lists = [{"name": "Default", "symbols": []}]
        _write(lists)
        return lists


def rename(old: str, new: str) -> list[dict]:
    new = new.strip()
    with _lock:
        lists = _load()
        target = _find(lists, old)
        if target and new and not _find(lists, new):
            target["name"] = new
            _write(lists)
        return lists


def add(name: str, symbol: str) -> list[dict]:
    symbol = symbol.strip()
    with _lock:
        lists = _load()
        target = _find(lists, name)
        if target and symbol and symbol not in target["symbols"]:
            target["symbols"].append(symbol)
            _write(lists)
        return lists


def remove(name: str, symbol: str) -> list[dict]:
    with _lock:
        lists = _load()
        target = _find(lists, name)
        if target:
            target["symbols"] = [s for s in target["symbols"] if s != symbol]
            _write(lists)
        return lists
