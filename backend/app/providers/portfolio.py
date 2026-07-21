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


def valued(user_id: str) -> dict:
    """Holdings enriched with live quotes plus portfolio totals/allocation —
    used by the portfolio API and the daily briefs."""
    from .. import universe
    from . import market

    holdings = get(user_id)
    symbols = [h["symbol"] for h in holdings]
    quotes = market.snapshot_quotes(symbols) if symbols else {}

    rows: list[dict] = []
    for h in holdings:
        q = quotes.get(h["symbol"]) or {}
        price = q.get("price")
        change = q.get("change")
        rows.append(
            {
                "symbol": h["symbol"],
                "name": q.get("name") or universe.name_for(h["symbol"]),
                "shares": h["shares"],
                "cost": h["cost"],
                "price": price,
                "change_pct": q.get("change_pct"),
                "value": price * h["shares"] if price is not None else None,
                "day_pl": change * h["shares"] if change is not None else None,
                "total_pl": (price - h["cost"]) * h["shares"] if price is not None else None,
                "total_pl_pct": ((price - h["cost"]) / h["cost"] * 100)
                if price is not None and h["cost"]
                else None,
            }
        )

    total_value = sum(r["value"] for r in rows if r["value"] is not None)
    total_cost = sum(r["shares"] * r["cost"] for r in rows)
    day_pl = sum(r["day_pl"] for r in rows if r["day_pl"] is not None)
    prev_value = total_value - day_pl
    for r in rows:
        r["alloc_pct"] = (
            r["value"] / total_value * 100 if r["value"] and total_value else None
        )
    rows.sort(key=lambda r: -(r["value"] or 0))

    return {
        "holdings": rows,
        "totals": {
            "value": total_value,
            "cost": total_cost,
            "day_pl": day_pl,
            "day_pl_pct": (day_pl / prev_value * 100) if prev_value else None,
            "total_pl": total_value - total_cost,
            "total_pl_pct": ((total_value - total_cost) / total_cost * 100)
            if total_cost
            else None,
        },
    }
