"""Market data provider backed by Yahoo Finance (via the `yfinance` library).

Everything funnels through a tiny in-memory TTL cache so that repeated requests
(and the background scheduler) don't hammer Yahoo and get rate-limited.
"""

from __future__ import annotations

import math
import time
from typing import Callable

import pandas as pd
import yfinance as yf

from .. import universe
from . import twelvedata

# ---------------------------------------------------------------------------
# Tiny TTL cache
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, ttl: int, fn: Callable[[], object]) -> object:
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


def _clean(x) -> float | None:
    """Coerce a value to a JSON-safe float, mapping NaN/inf/None -> None."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f


# ---------------------------------------------------------------------------
# Name resolution
# ---------------------------------------------------------------------------

_name_cache: dict[str, str] = {}


def resolve_name(symbol: str) -> str:
    """A colloquial English name for any ticker.

    Curated names (our universe) win; otherwise we ask Yahoo's search index
    once and remember the answer so detail pages never show a raw ticker like
    "^GSPC" or "GC=F".
    """
    curated = universe.NAMES.get(symbol)
    if curated:
        return curated
    if symbol in _name_cache:
        return _name_cache[symbol]

    name = symbol
    try:
        results = yf.Search(symbol, max_results=5).quotes
        for q in results:
            if q.get("symbol") == symbol:
                name = q.get("shortname") or q.get("longname") or symbol
                break
        else:
            if results:
                name = results[0].get("shortname") or results[0].get("longname") or symbol
    except Exception:
        pass

    name = " ".join(str(name).split())  # collapse the odd double-spaced names
    _name_cache[symbol] = name
    return name


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

# range -> (yfinance period, interval)
RANGE_MAP: dict[str, tuple[str, str]] = {
    "1d": ("1d", "5m"),
    "5d": ("5d", "30m"),
    "1mo": ("1mo", "1d"),
    "6mo": ("6mo", "1d"),
    "1y": ("1y", "1d"),
    "5y": ("5y", "1wk"),
    "max": ("max", "1mo"),
}


def get_history(symbol: str, rng: str = "6mo") -> list[dict]:
    """OHLCV candles for one symbol over a time range."""
    period, interval = RANGE_MAP.get(rng, RANGE_MAP["6mo"])

    def fn() -> list[dict]:
        fs = universe.feed_symbol(symbol)  # futures feed for mapped indices
        if twelvedata.enabled():
            td = twelvedata.candles(fs, rng)
            if td:
                return td
        df = yf.Ticker(fs).history(
            period=period, interval=interval, auto_adjust=False
        )
        out: list[dict] = []
        for idx, row in df.iterrows():
            ts = idx.isoformat() if hasattr(idx, "isoformat") else str(idx)
            out.append(
                {
                    "time": ts,
                    "open": _clean(row.get("Open")),
                    "high": _clean(row.get("High")),
                    "low": _clean(row.get("Low")),
                    "close": _clean(row.get("Close")),
                    "volume": _clean(row.get("Volume")),
                }
            )
        return out

    mode = f":{universe.indices_mode()}" if symbol in universe.INDEX_FEED else ""
    return _cached(f"hist:{symbol}:{rng}{mode}", 60, fn)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Batch closes (used by overview + summaries)
# ---------------------------------------------------------------------------


def _batch_closes(symbols: list[str], period: str, interval: str) -> dict[str, pd.Series]:
    """Download closing prices for many symbols at once, keyed by symbol."""

    def fn() -> dict[str, pd.Series]:
        result: dict[str, pd.Series] = {}

        # Primary: Twelve Data for whatever it can map (daily history only).
        if twelvedata.enabled() and interval == "1d":
            size = twelvedata.PERIOD_SIZE.get(period, 70)
            try:
                result.update(twelvedata.closes(symbols, size))
            except Exception:
                pass

        remaining = [s for s in symbols if s not in result]
        if not remaining:
            return result

        # Fallback: yfinance for the rest. Mapped indices are fetched from their
        # futures feed but stored under the original index symbol.
        feed = {s: universe.feed_symbol(s) for s in remaining}
        data = yf.download(
            list(feed.values()),
            period=period,
            interval=interval,
            progress=False,
            group_by="ticker",
            threads=True,
            auto_adjust=False,
        )
        if isinstance(data.columns, pd.MultiIndex):
            for s in remaining:
                try:
                    result[s] = data[feed[s]]["Close"].dropna()
                except Exception:
                    result[s] = pd.Series(dtype="float64")
        else:
            series = data["Close"].dropna() if "Close" in data else pd.Series(dtype="float64")
            result[remaining[0]] = series
        return result

    # Only vary the cache key by indices-mode when an index is in the batch, so
    # stock/commodity batches stay shared across modes.
    mode = f":{universe.indices_mode()}" if any(s in universe.INDEX_FEED for s in symbols) else ""
    key = f"batch:{','.join(symbols)}:{period}:{interval}{mode}"
    return _cached(key, 45, fn)  # type: ignore[return-value]


def _quote_from_series(symbol: str, s: pd.Series | None) -> dict:
    base = {
        "symbol": symbol,
        "name": universe.name_for(symbol),
        "is_level": symbol in universe.LEVEL_SYMBOLS,
        "is_fx": symbol in universe.FX_SYMBOLS,
    }
    if s is None or len(s) == 0:
        return {**base, "price": None, "change": None, "change_pct": None}
    last = _clean(s.iloc[-1])
    prev = _clean(s.iloc[-2]) if len(s) >= 2 else None
    change = (last - prev) if (last is not None and prev is not None) else None
    pct = (change / prev * 100) if (change is not None and prev) else None
    return {**base, "price": last, "change": change, "change_pct": pct}


def realtime_quotes(symbols: list[str]) -> dict[str, dict]:
    """Real-time prices for the TD-backed subset (short cache — polled often)."""
    if not twelvedata.enabled() or not symbols:
        return {}
    key = "rtq:" + ",".join(symbols)
    return _cached(key, 2, lambda: twelvedata.quotes(symbols))  # type: ignore[return-value]


def get_overview() -> dict[str, list[dict]]:
    """Snapshot quote (price + today's change) for every tracked instrument.

    Stocks/FX/metals get real-time Twelve Data prices overlaid on the daily-close
    base; indices/commodities/bonds come from the (yfinance) daily series.
    """
    out: dict[str, list[dict]] = {}
    for cls, syms in universe.UNIVERSE.items():
        closes = _batch_closes(syms, "5d", "1d")
        rtq = realtime_quotes(syms)
        items = []
        for s in syms:
            q = _quote_from_series(s, closes.get(s))
            r = rtq.get(s)
            if r and r.get("price") is not None:
                q["price"] = r["price"]
                if r.get("change_pct") is not None:
                    q["change"] = r.get("change")
                    q["change_pct"] = r["change_pct"]
            items.append(q)
        out[cls] = items
    return out


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

SCOPE_PERIOD: dict[str, tuple[str, str]] = {
    "day": ("5d", "1d"),
    "week": ("1mo", "1d"),
    "month": ("3mo", "1d"),
}

# How many trading bars back to look for each scope's starting point.
SCOPE_LOOKBACK = {"day": 1, "week": 5, "month": 21}


def get_summary(scope: str = "day", asset_class: str | None = None) -> dict[str, dict]:
    """For each asset class: average move, top gainers/losers over the scope."""
    classes = [asset_class] if asset_class else list(universe.UNIVERSE.keys())
    period, interval = SCOPE_PERIOD.get(scope, SCOPE_PERIOD["day"])
    lookback = SCOPE_LOOKBACK.get(scope, 1)

    result: dict[str, dict] = {}
    for cls in classes:
        syms = universe.UNIVERSE.get(cls, [])
        closes = _batch_closes(syms, period, interval)
        movers: list[dict] = []
        for s in syms:
            ser = closes.get(s)
            if ser is None or len(ser) < 2:
                continue
            last = _clean(ser.iloc[-1])
            start_idx = max(0, len(ser) - 1 - lookback)
            first = _clean(ser.iloc[start_idx])
            if last is None or first is None or first == 0:
                continue
            pct = (last - first) / first * 100
            movers.append(
                {
                    "symbol": s,
                    "name": universe.name_for(s),
                    "price": last,
                    "change_pct": pct,
                    "is_level": s in universe.LEVEL_SYMBOLS,
                    "is_fx": s in universe.FX_SYMBOLS,
                }
            )
        movers.sort(key=lambda m: m["change_pct"], reverse=True)
        avg = sum(m["change_pct"] for m in movers) / len(movers) if movers else None
        result[cls] = {
            "scope": scope,
            "label": universe.ASSET_CLASS_LABELS.get(cls, cls.title()),
            "average_pct": avg,
            "gainers": movers[:3],
            "losers": list(reversed(movers[-3:])) if movers else [],
            "all": movers,
        }
    return result


# ---------------------------------------------------------------------------
# Single-instrument detail
# ---------------------------------------------------------------------------

_mcap_cache: dict[str, tuple[float, float | None]] = {}


def _market_cap(symbol: str) -> float | None:
    """Market cap via yfinance (Twelve Data's /statistics is plan-gated)."""
    if (
        symbol.endswith("=X")
        or "=F" in symbol
        or "^" in symbol
        or symbol in universe.LEVEL_SYMBOLS
    ):
        return None
    hit = _mcap_cache.get(symbol)
    if hit and time.time() - hit[0] < (3600 if hit[1] is not None else 300):
        return hit[1]
    t = yf.Ticker(symbol)
    val: float | None = None
    try:
        val = _clean(dict(t.fast_info).get("market_cap"))
    except Exception:
        val = None
    if val is None:
        try:
            val = _clean(t.info.get("marketCap"))
        except Exception:
            val = None
    _mcap_cache[symbol] = (time.time(), val)
    return val


def get_quote(symbol: str) -> dict:
    """Rich snapshot for one instrument (used by its detail page)."""

    def fn() -> dict:
        # Identity stays the index; price data comes from its futures feed.
        fs = universe.feed_symbol(symbol)

        # Primary: Twelve Data real-time quote.
        if twelvedata.enabled():
            td = twelvedata.quote(fs)
            if td and td.get("price") is not None:
                return {
                    "symbol": symbol,
                    "name": resolve_name(symbol),
                    "asset_class": universe.class_for(symbol),
                    "is_level": symbol in universe.LEVEL_SYMBOLS,
                    "is_fx": symbol in universe.FX_SYMBOLS or symbol.endswith("=X"),
                    "market_cap": _market_cap(symbol),
                    **td,
                }

        t = yf.Ticker(fs)
        try:
            fi = dict(t.fast_info)
        except Exception:
            fi = {}

        def pick(*keys):
            for k in keys:
                if k in fi and fi[k] is not None:
                    return _clean(fi[k])
            return None

        last = pick("last_price", "lastPrice")
        prev = pick("previous_close", "previousClose")

        if last is None or prev is None:
            hist = get_history(symbol, "5d")
            closes = [r["close"] for r in hist if r["close"] is not None]
            if closes:
                last = last if last is not None else closes[-1]
                prev = prev if prev is not None else (
                    closes[-2] if len(closes) >= 2 else closes[-1]
                )

        change = (last - prev) if (last is not None and prev is not None) else None
        pct = (change / prev * 100) if (change is not None and prev) else None

        return {
            "symbol": symbol,
            "name": resolve_name(symbol),
            "asset_class": universe.class_for(symbol),
            "is_level": symbol in universe.LEVEL_SYMBOLS,
            "is_fx": symbol in universe.FX_SYMBOLS or symbol.endswith("=X"),
            "price": last,
            "previous_close": prev,
            "change": change,
            "change_pct": pct,
            "open": pick("open", "regularMarketOpen"),
            "day_high": pick("day_high", "dayHigh"),
            "day_low": pick("day_low", "dayLow"),
            "year_high": pick("year_high", "yearHigh"),
            "year_low": pick("year_low", "yearLow"),
            "market_cap": pick("market_cap", "marketCap"),
            "volume": pick("last_volume", "lastVolume", "volume"),
            "currency": fi.get("currency"),
        }

    mode = f":{universe.indices_mode()}" if symbol in universe.INDEX_FEED else ""
    return _cached(f"quote:{symbol}{mode}", 30, fn)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Currency conversion
# ---------------------------------------------------------------------------

CONVERT_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "CHF", "AUD", "CAD", "CNY",
    "INR", "MXN", "BRL", "HKD", "SGD", "NZD", "KRW", "SEK",
]


def get_fx_rate(base: str, quote: str) -> float | None:
    """Exchange rate: 1 unit of `base` in `quote` currency."""
    base, quote = base.upper(), quote.upper()
    if base == quote:
        return 1.0

    def fn() -> float | None:
        pair = f"{base}{quote}=X"
        s = _batch_closes([pair], "5d", "1d").get(pair)
        if s is not None and len(s):
            return _clean(s.iloc[-1])
        return None

    return _cached(f"fx:{base}{quote}", 60, fn)  # type: ignore[return-value]


def quotes_for(symbols: list[str]) -> list[dict]:
    """Snapshot quotes for an arbitrary list of symbols (used by watchlists)."""
    if not symbols:
        return []
    closes = _batch_closes(symbols, "5d", "1d")
    out: list[dict] = []
    for s in symbols:
        q = _quote_from_series(s, closes.get(s))
        if s not in universe.NAMES:
            q["name"] = resolve_name(s)
        if s.endswith("=X"):
            q["is_fx"] = True
        q["asset_class"] = universe.class_for(s)
        out.append(q)
    return out


def convert_currency(base: str, quote: str, amount: float) -> dict:
    rate = get_fx_rate(base, quote)
    return {
        "base": base.upper(),
        "quote": quote.upper(),
        "amount": amount,
        "rate": rate,
        "result": (amount * rate) if rate is not None else None,
    }
