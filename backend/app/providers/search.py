"""Ticker search / autocomplete, backed by Yahoo's search index via yfinance."""

from __future__ import annotations

import time

import yfinance as yf

_cache: dict[str, tuple[float, list[dict]]] = {}
_TTL = 300

# Yahoo quoteType -> friendly label
TYPE_LABELS = {
    "EQUITY": "Stock",
    "ETF": "ETF",
    "INDEX": "Index",
    "CURRENCY": "Currency",
    "CRYPTOCURRENCY": "Crypto",
    "FUTURE": "Futures",
    "MUTUALFUND": "Fund",
    "OPTION": "Option",
}


def search(query: str, limit: int = 8) -> list[dict]:
    query = query.strip()
    if not query:
        return []

    hit = _cache.get(query)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1][:limit]

    out: list[dict] = []
    try:
        quotes = yf.Search(query, max_results=max(limit, 8)).quotes
        for q in quotes:
            symbol = q.get("symbol")
            if not symbol:
                continue
            name = q.get("shortname") or q.get("longname") or symbol
            qt = q.get("quoteType", "")
            out.append(
                {
                    "symbol": symbol,
                    "name": " ".join(str(name).split()),
                    "type": TYPE_LABELS.get(qt, qt.title() if qt else ""),
                    "exchange": q.get("exchDisp") or q.get("exchange") or "",
                }
            )
    except Exception:
        out = []

    _cache[query] = (time.time(), out)
    return out[:limit]
