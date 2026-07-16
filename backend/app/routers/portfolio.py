from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from .. import universe
from ..providers import market, portfolio
from . import auth

router = APIRouter()


class HoldingIn(BaseModel):
    symbol: str
    shares: float
    cost: float  # average cost per share


def _valued(user_id: str) -> dict:
    """Holdings enriched with live quotes + portfolio totals/allocation."""
    holdings = portfolio.get(user_id)
    symbols = [h["symbol"] for h in holdings]
    quotes = market.snapshot_quotes(symbols) if symbols else {}

    rows: list[dict] = []
    for h in holdings:
        q = quotes.get(h["symbol"]) or {}
        price = q.get("price")
        change = q.get("change")
        value = price * h["shares"] if price is not None else None
        rows.append(
            {
                "symbol": h["symbol"],
                "name": q.get("name") or universe.name_for(h["symbol"]),
                "shares": h["shares"],
                "cost": h["cost"],
                "price": price,
                "change_pct": q.get("change_pct"),
                "value": value,
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


@router.get("/portfolio")
def get_portfolio(request: Request):
    user = auth.current_account(request)
    return _valued(user["id"])


@router.post("/portfolio/holdings")
def upsert_holding(body: HoldingIn, request: Request):
    user = auth.require_account(request)
    try:
        portfolio.upsert(user["id"], body.symbol, body.shares, body.cost)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _valued(user["id"])


@router.delete("/portfolio/holdings/{symbol:path}")
def remove_holding(symbol: str, request: Request):
    user = auth.require_account(request)
    portfolio.remove(user["id"], symbol)
    return _valued(user["id"])


@router.get("/portfolio/history")
def portfolio_history(request: Request, range: str = "6mo"):
    """Portfolio value vs the S&P 500, both normalized to 100 at the window
    start (constant current holdings — the standard simple comparison)."""
    user = auth.current_account(request)
    if range not in ("1mo", "6mo", "1y"):
        raise HTTPException(400, "range must be 1mo, 6mo, or 1y")
    holdings = portfolio.get(user["id"])
    if not holdings:
        return {"series": []}

    period, interval = market.RANGE_MAP[range]
    symbols = [h["symbol"] for h in holdings]
    closes = market._batch_closes(sorted(set(symbols + ["^GSPC"])), period, interval)

    # Align every series on date strings (sources vary in index format).
    by_date: dict[str, dict[str, float]] = {}
    for sym, series in closes.items():
        for idx, val in series.items():
            if val is None:
                continue
            day = str(idx)[:10]
            by_date.setdefault(day, {})[sym] = float(val)

    shares = {h["symbol"]: h["shares"] for h in holdings}
    need = set(symbols + ["^GSPC"])
    out = []
    for day in sorted(by_date):
        row = by_date[day]
        if not need.issubset(row):
            continue  # only days where every holding + the index have a close
        out.append(
            {
                "t": day,
                "portfolio": sum(shares[s] * row[s] for s in symbols),
                "spx": row["^GSPC"],
            }
        )
    if len(out) < 2:
        return {"series": []}
    p0, s0 = out[0]["portfolio"], out[0]["spx"]
    return {
        "series": [
            {
                "t": r["t"],
                "portfolio": round(r["portfolio"] / p0 * 100, 3),
                "spx": round(r["spx"] / s0 * 100, 3),
            }
            for r in out
        ]
    }
