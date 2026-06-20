"""Macro / economic indicators from FRED (Federal Reserve Economic Data).

Uses FRED's public CSV download endpoint, which needs **no API key**. Each
indicator carries a plain-English "implication" describing what it means for
markets, satisfying the "explain how macro affects prices" goal.
"""

from __future__ import annotations

import time

import httpx

_cache: dict[str, list[dict]] = {}
_cache_ts: float = 0.0
_TTL = 6 * 3600  # econ data updates infrequently

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={id}"

# Curated indicators. transform: how to turn the raw series into a reading.
INDICATORS: list[dict] = [
    {
        "id": "CPIAUCSL", "label": "Inflation — CPI (YoY)", "transform": "yoy",
        "unit": "%", "good_when": "low",
        "implication": "Headline consumer inflation. Hot prints push the Fed toward higher-for-longer rates — a drag on stocks and bonds; cooling inflation is risk-on.",
    },
    {
        "id": "CPILFESL", "label": "Core CPI (YoY)", "transform": "yoy",
        "unit": "%", "good_when": "low",
        "implication": "CPI excluding food & energy — the underlying trend. Sticky core inflation keeps rate cuts on hold.",
    },
    {
        "id": "PCEPILFE", "label": "Core PCE (YoY)", "transform": "yoy",
        "unit": "%", "good_when": "low",
        "implication": "The Fed's preferred inflation gauge, targeted at 2%. Moves here shift rate-cut expectations most directly.",
    },
    {
        "id": "UNRATE", "label": "Unemployment Rate", "transform": "level",
        "unit": "%", "good_when": "low",
        "implication": "A rising jobless rate signals a slowing economy — bad for earnings, but it can pull forward rate cuts and rally bonds.",
    },
    {
        "id": "PAYEMS", "label": "Nonfarm Payrolls (MoM)", "transform": "mom_diff",
        "unit": "K", "good_when": "high",
        "implication": "Monthly job creation. Strong jobs mean a resilient economy but fewer cuts; weak jobs raise recession worries.",
    },
    {
        "id": "FEDFUNDS", "label": "Fed Funds Rate", "transform": "level",
        "unit": "%", "good_when": "neutral",
        "implication": "The Fed's policy rate — the anchor for all other rates. Its direction of travel drives nearly every asset class.",
    },
    {
        "id": "DGS10", "label": "10-Year Treasury Yield", "transform": "level",
        "unit": "%", "good_when": "neutral",
        "implication": "The benchmark long rate. Rising yields lift discount rates and pressure growth stocks; falling yields lift them.",
    },
    {
        "id": "T10Y2Y", "label": "10Y–2Y Yield Spread", "transform": "level",
        "unit": "%", "good_when": "high",
        "implication": "Yield-curve slope. A negative (inverted) spread has historically preceded recessions; re-steepening is watched closely.",
    },
    {
        "id": "GDPC1", "label": "Real GDP (YoY)", "transform": "yoy_q",
        "unit": "%", "good_when": "high",
        "implication": "Inflation-adjusted output growth. Above-trend growth supports earnings; contraction signals recession.",
    },
    {
        "id": "UMCSENT", "label": "Consumer Sentiment", "transform": "level",
        "unit": "index", "good_when": "high",
        "implication": "University of Michigan survey. Confident consumers spend more — a leading read on demand.",
    },
]


def _fetch_series(series_id: str) -> list[tuple[str, float]]:
    url = FRED_CSV.format(id=series_id)
    r = httpx.get(url, timeout=20, follow_redirects=True)
    r.raise_for_status()
    rows: list[tuple[str, float]] = []
    for line in r.text.strip().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        date, val = parts[0].strip(), parts[1].strip()
        if val in (".", ""):
            continue
        try:
            rows.append((date, float(val)))
        except ValueError:
            continue
    return rows


def _compute(ind: dict, rows: list[tuple[str, float]]) -> dict | None:
    if not rows:
        return None
    date, last = rows[-1]
    t = ind["transform"]
    value: float | None = None
    prev: float | None = None

    if t == "level":
        value = last
        prev = rows[-2][1] if len(rows) >= 2 else None
    elif t == "mom_diff":
        # PAYEMS is already in thousands of persons, so the diff is "K jobs".
        if len(rows) >= 2:
            value = last - rows[-2][1]
            prev = (rows[-2][1] - rows[-3][1]) if len(rows) >= 3 else None
    elif t in ("yoy", "yoy_q"):
        lag = 12 if t == "yoy" else 4
        if len(rows) > lag:
            base = rows[-1 - lag][1]
            if base:
                value = (last - base) / base * 100
            if len(rows) > lag + 1:
                base2 = rows[-2 - lag][1]
                if base2:
                    prev = (rows[-2][1] - base2) / base2 * 100

    if value is None:
        return None
    change = (value - prev) if (prev is not None) else None
    return {
        "id": ind["id"],
        "label": ind["label"],
        "unit": ind["unit"],
        "value": value,
        "prev": prev,
        "change": change,
        "as_of": date,
        "good_when": ind["good_when"],
        "implication": ind["implication"],
    }


def indicators() -> list[dict]:
    global _cache_ts
    if _cache.get("all") and time.time() - _cache_ts < _TTL:
        return _cache["all"]

    out: list[dict] = []
    for ind in INDICATORS:
        try:
            rows = _fetch_series(ind["id"])
            computed = _compute(ind, rows)
            if computed:
                out.append(computed)
        except Exception:
            continue

    if out:
        _cache["all"] = out
        _cache_ts = time.time()
    return out


def headline_context() -> str:
    """A compact text block of the latest readings, for the AI narrative."""
    lines = []
    for ind in indicators():
        v = ind["value"]
        unit = ind["unit"]
        if unit == "K":
            vs = f"{v:+,.0f}K"
        elif unit == "%":
            vs = f"{v:.2f}%"
        else:
            vs = f"{v:.1f}"
        lines.append(f"{ind['label']}: {vs} (as of {ind['as_of']})")
    return "\n".join(lines)
