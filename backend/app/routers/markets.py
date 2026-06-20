from fastapi import APIRouter, HTTPException

from .. import universe
from ..providers import analyst
from ..providers import calendar as econ_calendar
from ..providers import economy, market, narrative, news, search

router = APIRouter()


@router.get("/universe")
def get_universe():
    """The tracked instruments grouped by asset class, with display labels."""
    return {
        "classes": [
            {
                "key": cls,
                "label": universe.ASSET_CLASS_LABELS.get(cls, cls.title()),
                "symbols": [
                    {"symbol": s, "name": universe.name_for(s)} for s in syms
                ],
            }
            for cls, syms in universe.UNIVERSE.items()
        ]
    }


@router.get("/overview")
def overview():
    """Snapshot of every instrument (price + today's change), by class."""
    return market.get_overview()


@router.get("/summary")
def summary(scope: str = "day", asset_class: str | None = None):
    if scope not in ("day", "week", "month"):
        raise HTTPException(400, "scope must be one of: day, week, month")
    return market.get_summary(scope, asset_class)


@router.get("/macro")
def macro(scope: str = "day"):
    """Plain-English explanation of what drove the moves (AI when configured)."""
    if scope not in ("day", "week", "month"):
        raise HTTPException(400, "scope must be one of: day, week, month")
    return narrative.market_narrative(scope)


@router.get("/search")
def search_symbols(q: str = "", limit: int = 8):
    return {"query": q, "results": search.search(q, limit)}


@router.get("/news")
def market_news(limit: int = 12):
    return {"articles": news.market_news(limit)}


@router.get("/article/{article_id}")
def article(article_id: str):
    data = news.get_article(article_id)
    if data is None:
        raise HTTPException(404, "Article not found or no longer cached")
    return data


@router.get("/movers")
def movers(scope: str = "day", limit: int = 6):
    if scope not in ("day", "week", "month"):
        raise HTTPException(400, "scope must be one of: day, week, month")
    summary = market.get_summary(scope)
    flat: list[dict] = []
    for cls, data in summary.items():
        for m in data.get("all", []):
            flat.append({**m, "asset_class": cls})
    flat.sort(key=lambda m: abs(m["change_pct"]), reverse=True)
    out = []
    for m in flat[:limit]:
        out.append({**m, "headline": news.top_headline(m["symbol"])})
    return {"scope": scope, "movers": out}


@router.get("/economy")
def economy_indicators():
    return {"indicators": economy.indicators()}


@router.get("/calendar")
def economic_calendar(days: int = 45):
    return {"events": econ_calendar.upcoming(days)}


@router.get("/currencies")
def currencies():
    return {"currencies": market.CONVERT_CURRENCIES}


@router.get("/convert")
def convert(base: str, quote: str, amount: float = 1.0):
    return market.convert_currency(base, quote, amount)


@router.get("/quote/{symbol:path}")
def quote(symbol: str):
    return market.get_quote(symbol)


@router.get("/analysis/{symbol:path}")
def analysis(symbol: str):
    return analyst.consensus(symbol)


@router.get("/news/{symbol:path}")
def symbol_news(symbol: str, limit: int = 8):
    return {"symbol": symbol, "articles": news.symbol_news(symbol, limit)}


@router.get("/history/{symbol:path}")
def history(symbol: str, range: str = "6mo"):
    if range not in market.RANGE_MAP:
        raise HTTPException(
            400, f"range must be one of: {', '.join(market.RANGE_MAP)}"
        )
    return {"symbol": symbol, "range": range, "candles": market.get_history(symbol, range)}
