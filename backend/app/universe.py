"""The default set of instruments the app tracks, grouped by asset class.

Symbols are Yahoo Finance tickers:
  - "^" prefix  -> an index or rate (e.g. ^GSPC = S&P 500, ^TNX = 10y yield)
  - "=F" suffix -> a futures contract (e.g. GC=F = gold, CL=F = WTI crude)
  - plain        -> an equity or ETF (e.g. AAPL, TLT)

The defaults below are the starting set; the user can customize per-class
symbols and hide whole classes (persisted via the customization block at the
bottom of this file). `UNIVERSE` is the *live* universe every feature reads.
"""

DEFAULT_UNIVERSE: dict[str, list[str]] = {
    "stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"],
    "indices": ["^GSPC", "^DJI", "^NDX", "^RUT", "^VIX", "^FTSE", "^N225", "^GDAXI"],
    "commodities": ["GC=F", "SI=F", "CL=F", "BZ=F", "NG=F", "HG=F", "ZC=F", "ZW=F"],
    "bonds": ["^TNX", "^FVX", "^TYX", "^IRX", "TLT", "IEF", "SHY", "LQD"],
    "currencies": [
        "DX-Y.NYB",
        "EURUSD=X",
        "GBPUSD=X",
        "USDJPY=X",
        "USDCHF=X",
        "AUDUSD=X",
        "USDCAD=X",
        "USDCNY=X",
    ],
}

# The live universe: defaults overlaid with the user's saved customization
# (rebuilt in place so overview/summary/movers/narrative/chat all follow).
# Hidden classes are absent entirely.
UNIVERSE: dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_UNIVERSE.items()}

# Human-friendly names for display.
NAMES: dict[str, str] = {
    # Stocks
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "GOOGL": "Alphabet (Google)",
    "AMZN": "Amazon",
    "NVDA": "NVIDIA",
    "META": "Meta Platforms",
    "TSLA": "Tesla",
    "JPM": "JPMorgan Chase",
    # Indices
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones Industrial Average",
    "^IXIC": "Nasdaq Composite",
    "^NDX": "Nasdaq 100",
    "^RUT": "Russell 2000",
    "^VIX": "CBOE Volatility Index (VIX)",
    "^FTSE": "FTSE 100 (UK)",
    "^N225": "Nikkei 225 (Japan)",
    "^GDAXI": "DAX (Germany)",
    # Commodities
    "GC=F": "Gold",
    "SI=F": "Silver",
    "CL=F": "Crude Oil (WTI)",
    "BZ=F": "Crude Oil (Brent)",
    "NG=F": "Natural Gas",
    "HG=F": "Copper",
    "ZC=F": "Corn",
    "ZW=F": "Wheat",
    # Bonds / rates
    "^TNX": "US 10-Year Treasury Yield",
    "^FVX": "US 5-Year Treasury Yield",
    "^TYX": "US 30-Year Treasury Yield",
    "^IRX": "US 13-Week T-Bill Yield",
    "TLT": "iShares 20+ Year Treasury Bond ETF",
    "IEF": "iShares 7-10 Year Treasury Bond ETF",
    "SHY": "iShares 1-3 Year Treasury Bond ETF",
    "LQD": "iShares Investment Grade Corporate Bond ETF",
    # Currencies
    "DX-Y.NYB": "US Dollar Index (DXY)",
    "EURUSD=X": "Euro / US Dollar",
    "GBPUSD=X": "British Pound / US Dollar",
    "USDJPY=X": "US Dollar / Japanese Yen",
    "USDCHF=X": "US Dollar / Swiss Franc",
    "AUDUSD=X": "Australian Dollar / US Dollar",
    "USDCAD=X": "US Dollar / Canadian Dollar",
    "USDCNY=X": "US Dollar / Chinese Yuan",
}

# A few asset classes (rates, the VIX) are quoted as levels, not prices in $.
LEVEL_SYMBOLS = {"^TNX", "^FVX", "^TYX", "^IRX", "^VIX", "DX-Y.NYB"}

# FX pairs are shown with more decimal places.
FX_SYMBOLS = {s for syms in [["EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X",
                              "AUDUSD=X", "USDCAD=X", "USDCNY=X"]] for s in syms}

ASSET_CLASS_LABELS = {
    "stocks": "Stocks",
    "indices": "Indices",
    "commodities": "Commodities",
    "bonds": "Bonds & Rates",
    "currencies": "Currencies",
}

# Price/chart data for these indices is pulled from their E-mini FUTURES, which
# trade nearly 24 hours (Sun evening–Fri evening) — so the value reflects
# overnight/weekend moves instead of being frozen at the last cash-session close.
# The instrument keeps its index identity (name, symbol); only the feed changes.
INDEX_FEED = {
    "^GSPC": "ES=F",  # S&P 500 E-mini
    "^DJI": "YM=F",  # Dow E-mini
    "^NDX": "NQ=F",  # Nasdaq-100 E-mini
    "^RUT": "RTY=F",  # Russell 2000 E-mini
}


def _et_now():
    """Current US Eastern time (handles EDT/EST without a tz database)."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    def first_sunday(month: int) -> datetime:
        d = datetime(now.year, month, 1, tzinfo=timezone.utc)
        return d + timedelta(days=(6 - d.weekday()) % 7)

    # US DST: 2nd Sunday of March → 1st Sunday of November (≈2am ET).
    dst_start = (first_sunday(3) + timedelta(weeks=1)).replace(hour=7)
    dst_end = first_sunday(11).replace(hour=6)
    offset = -4 if dst_start <= now < dst_end else -5
    return now + timedelta(hours=offset)


def us_cash_market_open() -> bool:
    et = _et_now()
    if et.weekday() >= 5:  # Sat/Sun
        return False
    minutes = et.hour * 60 + et.minute
    return 9 * 60 + 30 <= minutes < 16 * 60  # 9:30am–4:00pm ET


import contextvars

# Per-request indices feed mode: "futures" (24h), "cash" (matches investing.com),
# or "auto" (cash during US market hours, futures when closed). Endpoints set it
# from the ?indices= query param.
_indices_mode: contextvars.ContextVar[str] = contextvars.ContextVar(
    "indices_mode", default="futures"
)


def set_indices_mode(mode: str) -> None:
    _indices_mode.set(mode if mode in ("futures", "cash", "auto") else "futures")


def indices_mode() -> str:
    return _indices_mode.get()


def feed_symbol(symbol: str) -> str:
    """Where to fetch a mapped index's price data, per the indices-mode setting."""
    if symbol not in INDEX_FEED:
        return symbol
    mode = _indices_mode.get()
    if mode == "cash":
        return symbol
    if mode == "auto":
        return symbol if us_cash_market_open() else INDEX_FEED[symbol]
    return INDEX_FEED[symbol]  # "futures" (default)


def name_for(symbol: str) -> str:
    return _custom_names.get(symbol) or NAMES.get(symbol, symbol)


def is_fx(symbol: str) -> bool:
    """FX pairs get extra decimal places; covers custom-added Yahoo pairs too."""
    return symbol in FX_SYMBOLS or symbol.endswith("=X")


def class_for(symbol: str) -> str | None:
    # Checked against the full config (not just UNIVERSE) so instruments in a
    # hidden class still classify correctly on their asset pages.
    for cls, syms in _class_symbols.items():
        if symbol in syms:
            return cls
    return None


# ---------------------------------------------------------------------------
# User customization (Customize dashboard) — persisted like the watchlists.
# ---------------------------------------------------------------------------

import json
import threading
from pathlib import Path

from .config import settings

_CFG_BASE = (
    Path(settings.data_dir)
    if settings.data_dir
    else Path(__file__).resolve().parent.parent / "data"
)
_CFG_PATH = _CFG_BASE / "universe.json"
_cfg_lock = threading.Lock()

MAX_SYMBOLS_PER_CLASS = 20

# Full per-class setup, *including* hidden classes (hiding is reversible).
_class_symbols: dict[str, list[str]] = {k: list(v) for k, v in DEFAULT_UNIVERSE.items()}
_hidden_classes: set[str] = set()
_custom_names: dict[str, str] = {}  # display names for user-added symbols


def _rebuild_universe() -> None:
    UNIVERSE.clear()
    UNIVERSE.update(
        {
            cls: list(syms)
            for cls, syms in _class_symbols.items()
            if cls not in _hidden_classes
        }
    )


def is_default_config() -> bool:
    return not _hidden_classes and _class_symbols == DEFAULT_UNIVERSE


def get_config() -> dict:
    """The full instrument setup, shaped for the Customize editor."""
    return {
        "classes": [
            {
                "key": cls,
                "label": ASSET_CLASS_LABELS.get(cls, cls.title()),
                "visible": cls not in _hidden_classes,
                "symbols": [
                    {"symbol": s, "name": name_for(s)} for s in _class_symbols[cls]
                ],
            }
            for cls in DEFAULT_UNIVERSE
        ],
        "is_default": is_default_config(),
        "max_per_class": MAX_SYMBOLS_PER_CLASS,
    }


def apply_config(classes: list[dict]) -> dict:
    """Sanitize + apply a customization, persist it, and return the new config.

    Unknown classes are ignored; classes missing from the payload keep their
    current setup. Per class: dedupe, drop blanks, cap the count.
    """
    with _cfg_lock:
        for cls_cfg in classes:
            key = cls_cfg.get("key")
            if key not in DEFAULT_UNIVERSE:
                continue
            seen: set[str] = set()
            symbols: list[str] = []
            for item in cls_cfg.get("symbols", []):
                sym = str(item.get("symbol", "")).strip()
                if not sym or sym in seen or len(sym) > 20:
                    continue
                seen.add(sym)
                symbols.append(sym)
                name = str(item.get("name") or "").strip()
                if name and sym not in NAMES:
                    _custom_names[sym] = name
                if len(symbols) >= MAX_SYMBOLS_PER_CLASS:
                    break
            _class_symbols[key] = symbols
            if cls_cfg.get("visible", True):
                _hidden_classes.discard(key)
            else:
                _hidden_classes.add(key)
        # Drop custom names that no longer point at a tracked symbol.
        in_use = {s for syms in _class_symbols.values() for s in syms}
        for sym in list(_custom_names):
            if sym not in in_use:
                del _custom_names[sym]
        _rebuild_universe()
        _save_cfg()
    return get_config()


def reset_config() -> dict:
    with _cfg_lock:
        _class_symbols.clear()
        _class_symbols.update({k: list(v) for k, v in DEFAULT_UNIVERSE.items()})
        _hidden_classes.clear()
        _custom_names.clear()
        _rebuild_universe()
        try:
            _CFG_PATH.unlink(missing_ok=True)
        except Exception:
            pass
    return get_config()


def _save_cfg() -> None:
    try:
        _CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CFG_PATH.write_text(
            json.dumps(
                {
                    "classes": {
                        cls: {
                            "visible": cls not in _hidden_classes,
                            "symbols": syms,
                        }
                        for cls, syms in _class_symbols.items()
                    },
                    "names": _custom_names,
                },
                indent=2,
            )
        )
    except Exception:
        pass  # persistence is best-effort; the in-memory config still applies


def _load_cfg() -> None:
    try:
        data = json.loads(_CFG_PATH.read_text())
    except Exception:
        return
    classes = data.get("classes")
    if not isinstance(classes, dict):
        return
    for cls, cfg in classes.items():
        if cls not in DEFAULT_UNIVERSE or not isinstance(cfg, dict):
            continue
        syms = [
            s.strip()
            for s in cfg.get("symbols", [])
            if isinstance(s, str) and s.strip()
        ]
        _class_symbols[cls] = syms[:MAX_SYMBOLS_PER_CLASS]
        if cfg.get("visible", True):
            _hidden_classes.discard(cls)
        else:
            _hidden_classes.add(cls)
    names = data.get("names")
    if isinstance(names, dict):
        _custom_names.update({str(k): str(v) for k, v in names.items()})
    _rebuild_universe()


_load_cfg()
