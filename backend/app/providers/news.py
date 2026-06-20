"""News headlines via Yahoo Finance (free, through yfinance).

Also keeps an in-memory index of fetched articles (by id) so the app can render
its own article page — a readable summary plus links to the assets it mentions —
before sending the user out to the original source.
"""

from __future__ import annotations

import hashlib
import json
import time

import yfinance as yf

from ..config import settings
from . import market


def _aid(natural: str) -> str:
    """A short, URL-safe, stable id derived from a natural article identifier."""
    return hashlib.md5(natural.encode("utf-8")).hexdigest()[:16]

_cache: dict[str, tuple[float, list[dict]]] = {}
_TTL = 300

# id -> raw article, so /article/{id} can look it up later.
_index: dict[str, dict] = {}
_INDEX_CAP = 800
# id -> enriched article (AI summary + linked assets), cached longer.
_enriched: dict[str, dict] = {}


def _remember(articles: list[dict]) -> None:
    for a in articles:
        if a and a.get("id"):
            _index[a["id"]] = a
    if len(_index) > _INDEX_CAP:
        for k in list(_index)[: len(_index) - _INDEX_CAP]:
            _index.pop(k, None)


def _from_content(item: dict) -> dict | None:
    c = item.get("content") or item
    title = c.get("title")
    if not title:
        return None
    url = ""
    for key in ("clickThroughUrl", "canonicalUrl"):
        node = c.get(key)
        if isinstance(node, dict) and node.get("url"):
            url = node["url"]
            break
    provider = c.get("provider") or {}
    return {
        "id": _aid(str(item.get("id") or c.get("id") or url or title)),
        "title": title,
        "summary": c.get("summary") or c.get("description") or "",
        "url": url,
        "publisher": provider.get("displayName") if isinstance(provider, dict) else "",
        "published": c.get("pubDate") or c.get("displayTime") or "",
        "tickers": [],
    }


def _from_search(item: dict) -> dict | None:
    title = item.get("title")
    if not title:
        return None
    ts = item.get("providerPublishTime")
    published = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else ""
    return {
        "id": _aid(str(item.get("uuid") or item.get("link") or title)),
        "title": title,
        "summary": "",
        "url": item.get("link") or "",
        "publisher": item.get("publisher") or "",
        "published": published,
        "tickers": item.get("relatedTickers") or [],
    }


def _dedupe(items: list[dict], limit: int) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for it in items:
        if not it or it["title"] in seen:
            continue
        seen.add(it["title"])
        out.append(it)
        if len(out) >= limit:
            break
    return out


def market_news(limit: int = 12) -> list[dict]:
    key = f"market:{limit}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    try:
        results = yf.Search("stock market", news_count=limit * 2, max_results=1).news
        items = [_from_search(x) for x in results]
    except Exception:
        items = []
    out = _dedupe(items, limit)
    _remember(out)
    _cache[key] = (time.time(), out)
    return out


def symbol_news(symbol: str, limit: int = 8) -> list[dict]:
    key = f"sym:{symbol}:{limit}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    try:
        results = yf.Ticker(symbol).news or []
        items = [_from_content(x) for x in results]
    except Exception:
        items = []
    out = _dedupe(items, limit)
    if not out:
        try:
            results = yf.Search(market.resolve_name(symbol), news_count=limit * 2, max_results=1).news
            out = _dedupe([_from_search(x) for x in results], limit)
        except Exception:
            out = []
    # Tag with the symbol we looked up so the article page can link back to it.
    for a in out:
        if symbol not in a["tickers"]:
            a["tickers"] = [symbol] + a["tickers"]
    _remember(out)
    _cache[key] = (time.time(), out)
    return out


def top_headline(symbol: str) -> dict | None:
    arts = symbol_news(symbol, 1)
    return arts[0] if arts else None


# ---------------------------------------------------------------------------
# Single-article view (summary + linked assets)
# ---------------------------------------------------------------------------


def _ai_summary(article: dict) -> tuple[str | None, list[str]]:
    if not settings.anthropic_api_key:
        return None, []
    try:
        import anthropic

        provided = article.get("summary") or ""
        prompt = (
            "You are summarizing a financial news headline for a smart beginner in "
            "plain English.\n\n"
            f'Headline: "{article["title"]}"\n'
            f"Publisher: {article.get('publisher') or 'n/a'}\n"
            + (f"Provided summary: {provided}\n" if provided else "")
            + "\nRespond with ONLY a JSON object:\n"
            '  "summary": a clear, easy-to-read 2-4 sentence summary of what the story '
            "is about and why it matters for markets. Explain any jargon simply.\n"
            '  "tickers": array of Yahoo Finance ticker symbols for specific public '
            'companies, indices, or commodities the headline is about (e.g. ["AAPL","^GSPC"]). '
            "Use [] if none are clearly identifiable.\n"
            "JSON only, no markdown."
        )
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.narrative_model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        data = json.loads(text[text.find("{") : text.rfind("}") + 1])
        tickers = [str(t).upper().strip() for t in (data.get("tickers") or [])]
        return data.get("summary"), tickers
    except Exception:
        return None, []


def get_article(article_id: str) -> dict | None:
    raw = _index.get(article_id)
    if raw is None:
        return None
    if article_id in _enriched:
        return _enriched[article_id]

    ai_summary, ai_tickers = _ai_summary(raw)

    # Authoritative related tickers first, then AI-identified ones (validated).
    candidates = list(dict.fromkeys((raw.get("tickers") or []) + ai_tickers))
    related = set(raw.get("tickers") or [])
    assets: list[dict] = []
    seen: set[str] = set()
    for tk in candidates:
        tk = tk.upper().strip()
        if not tk or tk in seen:
            continue
        name = market.resolve_name(tk)
        if name != tk or tk in related:
            assets.append({"symbol": tk, "name": name})
            seen.add(tk)
        if len(assets) >= 8:
            break

    enriched = {
        "id": article_id,
        "title": raw["title"],
        "publisher": raw.get("publisher", ""),
        "published": raw.get("published", ""),
        "url": raw.get("url", ""),
        "summary": ai_summary or raw.get("summary") or "",
        "ai_summary": bool(ai_summary),
        "assets": assets,
    }
    _enriched[article_id] = enriched
    return enriched
