"""Twelve Data client — real-time quotes, time series, and detail.

When TWELVE_DATA_API_KEY is set this becomes the primary price source. Yahoo
tickers are mapped to Twelve Data symbols; anything unmapped (or that returns
an error/empty) is left to the yfinance fallback in market.py. Results are
normalized into the same shapes yfinance produces so callers don't care which
source answered.
"""

from __future__ import annotations

import math

import httpx
import pandas as pd

from ..config import settings

BASE = "https://api.twelvedata.com"

# Yahoo symbol -> Twelve Data symbol. Anything not here that contains "^" or "="
# is treated as unsupported (use the yfinance fallback). Plain stock/ETF tickers
# pass through unchanged.
#
# Verified live against the account's plan (2026-06-17): stocks, ETFs, FX, and
# spot gold/silver/oil resolve with correct real-time data. Indices, the dollar
# index, and other commodities (brent, nat gas, copper, grains) are NOT on this
# plan's feed (symbol_search returns no index data), so they intentionally fall
# through to yfinance.
SYMBOL_MAP: dict[str, str] = {
    # FX (Twelve Data uses BASE/QUOTE form)
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
    "USDCNY=X": "USD/CNY",
    # Commodities available as real-time spot (proxy for the Yahoo futures)
    "GC=F": "XAU/USD",
    "SI=F": "XAG/USD",
    "CL=F": "WTI/USD",
}


def enabled() -> bool:
    return bool(settings.twelve_data_api_key)


def td_symbol(yahoo: str) -> str | None:
    """Map a Yahoo ticker to its Twelve Data symbol, or None if unsupported."""
    if yahoo in SYMBOL_MAP:
        return SYMBOL_MAP[yahoo]
    # Plain equities / ETFs pass through; skip anything with index/futures markers.
    if "^" in yahoo or "=" in yahoo:
        return None
    return yahoo


def _f(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (math.isnan(v) or math.isinf(v)) else v


def _get(path: str, params: dict) -> dict:
    params = {**params, "apikey": settings.twelve_data_api_key}
    r = httpx.get(f"{BASE}/{path}", params=params, timeout=15)
    r.raise_for_status()
    return r.json()


# range -> (interval, outputsize) for charts
RANGE_TD: dict[str, tuple[str, int]] = {
    "1d": ("5min", 78),
    "5d": ("30min", 170),
    "1mo": ("1day", 23),
    "6mo": ("1day", 130),
    "1y": ("1day", 252),
    "5y": ("1week", 260),
    "max": ("1month", 400),
}

# daily-history lookback sizes for _batch_closes periods
PERIOD_SIZE: dict[str, int] = {"5d": 7, "1mo": 24, "3mo": 70}


def quote(yahoo: str) -> dict | None:
    ts = td_symbol(yahoo)
    if not ts:
        return None
    try:
        d = _get("quote", {"symbol": ts})
    except Exception:
        return None
    if not isinstance(d, dict) or d.get("status") == "error" or d.get("close") is None:
        return None
    fw = d.get("fifty_two_week") or {}
    return {
        "price": _f(d.get("close")),
        "previous_close": _f(d.get("previous_close")),
        "change": _f(d.get("change")),
        "change_pct": _f(d.get("percent_change")),
        "open": _f(d.get("open")),
        "day_high": _f(d.get("high")),
        "day_low": _f(d.get("low")),
        "year_high": _f(fw.get("high")),
        "year_low": _f(fw.get("low")),
        "volume": _f(d.get("volume")) or _f(d.get("average_volume")),
        "currency": d.get("currency"),
    }


# NOTE: market cap is sourced from yfinance in market.py — Twelve Data's
# /statistics endpoint is gated to higher plan tiers (returns 403 here).


def _series(values) -> pd.Series:
    if not values:
        return pd.Series(dtype="float64")
    closes = [_f(v.get("close")) for v in values]
    closes = [c for c in closes if c is not None]
    return pd.Series(closes, dtype="float64")


def closes(yahoo_symbols: list[str], outputsize: int) -> dict[str, pd.Series]:
    """Daily close series for the subset of symbols Twelve Data can map."""
    mapped = {y: td_symbol(y) for y in yahoo_symbols}
    mapped = {y: ts for y, ts in mapped.items() if ts}
    if not mapped:
        return {}
    rev: dict[str, str] = {}
    for y, ts in mapped.items():
        rev.setdefault(ts, y)
    try:
        d = _get(
            "time_series",
            {
                "symbol": ",".join(rev.keys()),
                "interval": "1day",
                "outputsize": outputsize,
                "order": "ASC",
            },
        )
    except Exception:
        return {}

    out: dict[str, pd.Series] = {}
    if "values" in d or d.get("status") == "error":
        # Single-symbol response shape.
        if "values" in d:
            only = next(iter(rev.values()))
            out[only] = _series(d.get("values"))
    else:
        for ts, payload in d.items():
            y = rev.get(ts)
            if y and isinstance(payload, dict) and payload.get("status") != "error":
                out[y] = _series(payload.get("values"))
    return {y: s for y, s in out.items() if s is not None and len(s)}


def candles(yahoo: str, rng: str) -> list[dict] | None:
    ts = td_symbol(yahoo)
    if not ts:
        return None
    interval, outputsize = RANGE_TD.get(rng, RANGE_TD["6mo"])
    try:
        d = _get(
            "time_series",
            {"symbol": ts, "interval": interval, "outputsize": outputsize, "order": "ASC"},
        )
    except Exception:
        return None
    vals = d.get("values") if isinstance(d, dict) else None
    if not vals:
        return None
    return [
        {
            "time": v.get("datetime"),
            "open": _f(v.get("open")),
            "high": _f(v.get("high")),
            "low": _f(v.get("low")),
            "close": _f(v.get("close")),
            "volume": _f(v.get("volume")),
        }
        for v in vals
    ]
