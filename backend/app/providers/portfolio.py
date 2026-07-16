"""Portfolio holdings: per-account positions (shares + average cost).

Stored like the watchlists — {"users": {user_id: [{"symbol", "shares",
"cost"}]}} in DATA_DIR/portfolio.json with atomic writes. The file stays tiny
and dumb; valuation happens at read time with live quotes in the router.
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
_PATH = _BASE / "portfolio.json"
_lock = threading.Lock()

MAX_HOLDINGS = 50


def _read() -> dict:
    try:
        data = json.loads(_PATH.read_text())
        if isinstance(data, dict) and isinstance(data.get("users"), dict):
            return {"users": data["users"]}
    except Exception:
        pass
    return {"users": {}}


def _write(data: dict) -> None:
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.replace(tmp, _PATH)


def get(user_id: str) -> list[dict]:
    with _lock:
        return [dict(h) for h in _read()["users"].get(user_id, [])]


def upsert(user_id: str, symbol: str, shares: float, cost: float) -> list[dict]:
    """Add a position, or overwrite it if the symbol's already held."""
    symbol = symbol.strip()
    if not symbol or not (shares > 0) or cost < 0:
        raise ValueError("A holding needs a symbol, positive shares, and a cost.")
    with _lock:
        data = _read()
        holdings = data["users"].setdefault(user_id, [])
        existing = next((h for h in holdings if h["symbol"] == symbol), None)
        if existing:
            existing.update(shares=shares, cost=cost)
        else:
            if len(holdings) >= MAX_HOLDINGS:
                raise ValueError(f"Holding limit reached ({MAX_HOLDINGS}).")
            holdings.append({"symbol": symbol, "shares": shares, "cost": cost})
        _write(data)
        return [dict(h) for h in holdings]


def remove(user_id: str, symbol: str) -> list[dict]:
    with _lock:
        data = _read()
        holdings = [
            h for h in data["users"].get(user_id, []) if h["symbol"] != symbol
        ]
        data["users"][user_id] = holdings
        _write(data)
        return [dict(h) for h in holdings]
