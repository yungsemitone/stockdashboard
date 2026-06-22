"""The default set of instruments the app tracks, grouped by asset class.

Symbols are Yahoo Finance tickers:
  - "^" prefix  -> an index or rate (e.g. ^GSPC = S&P 500, ^TNX = 10y yield)
  - "=F" suffix -> a futures contract (e.g. GC=F = gold, CL=F = WTI crude)
  - plain        -> an equity or ETF (e.g. AAPL, TLT)

This is just the starting watchlist. It will become user-editable later.
"""

UNIVERSE: dict[str, list[str]] = {
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


def feed_symbol(symbol: str) -> str:
    """Always fetch mapped indices from their 24h futures feed (per user pref)."""
    return INDEX_FEED.get(symbol, symbol)


def name_for(symbol: str) -> str:
    return NAMES.get(symbol, symbol)


def class_for(symbol: str) -> str | None:
    for cls, syms in UNIVERSE.items():
        if symbol in syms:
            return cls
    return None
