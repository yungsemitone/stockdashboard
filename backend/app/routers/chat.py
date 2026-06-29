"""In-app Claude chat — an agentic assistant with tools.

Claude can call the dashboard's own data (watchlists, quotes, analyst consensus,
economy, calendar, news, search) and search the web, then reason over real data
to answer — instead of guessing from a static snapshot. The Anthropic key stays
server-side. Lightly guarded (rate limit + history/iteration caps).
"""

from __future__ import annotations

import json
import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import settings
from ..providers import analyst
from ..providers import calendar as econ_calendar
from ..providers import economy, market, news, search, watchlist

router = APIRouter()


class Msg(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Msg]


_hits: dict[str, list[float]] = defaultdict(list)
_RATE_N = 30
_RATE_WINDOW = 300


def _rate_ok(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _hits[ip] if now - t < _RATE_WINDOW]
    recent.append(now)
    _hits[ip] = recent
    return len(recent) <= _RATE_N


# --- Tools Claude can call -------------------------------------------------

TOOLS = [
    {
        "name": "get_watchlists",
        "description": "The user's saved watchlists (named lists of tickers) with each holding's current price and today's % change.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_market_overview",
        "description": "Current price and today's % change for every instrument the dashboard tracks, grouped by class (stocks, indices, commodities, bonds, currencies).",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_quote",
        "description": "Detailed current quote for one symbol: price, day range, 52-week range, volume, market cap.",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Ticker, e.g. AAPL or ^GSPC"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_analyst_consensus",
        "description": "Wall Street analyst view for a stock: buy/hold/sell breakdown, number of analysts, average/high/low 12-month price targets, implied upside, and the bull/hold/bear cases. USE THIS for questions about a stock's outlook, future projection, or price target.",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    },
    {
        "name": "get_economic_indicators",
        "description": "Latest US macro indicators (CPI/inflation, unemployment, Fed funds rate, GDP, yields, etc.) with values and what each means.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_economic_calendar",
        "description": "Upcoming US economic releases and events (CPI, jobs report, FOMC, etc.) with dates and implications.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_news",
        "description": "Recent market headlines, or headlines for a specific symbol if one is given.",
        "input_schema": {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "Optional ticker"}},
        },
    },
    {
        "name": "search_symbols",
        "description": "Look up ticker symbols by company name or partial ticker.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 5},
]


def _run_tool(name: str, inp: dict) -> dict:
    if name == "get_watchlists":
        lists = watchlist.get_all()
        syms = sorted({s for l in lists for s in l["symbols"]})
        q = {x["symbol"]: x for x in market.quotes_for(syms)}
        return {
            "lists": [
                {"name": l["name"], "quotes": [q.get(s) for s in l["symbols"] if s in q]}
                for l in lists
            ]
        }
    if name == "get_market_overview":
        return market.get_overview()
    if name == "get_quote":
        return market.get_quote(inp["symbol"])
    if name == "get_analyst_consensus":
        return analyst.consensus(inp["symbol"])
    if name == "get_economic_indicators":
        return {"indicators": economy.indicators()}
    if name == "get_economic_calendar":
        return {"events": econ_calendar.upcoming()}
    if name == "get_news":
        sym = (inp or {}).get("symbol")
        return {"articles": news.symbol_news(sym) if sym else news.market_news()}
    if name == "search_symbols":
        return {"results": search.search(inp["query"])}
    return {"error": f"unknown tool {name}"}


SYSTEM = (
    "You are Claude, embedded as a chat assistant inside the user's personal live "
    "markets dashboard. Talk naturally, like a sharp, friendly markets-savvy friend.\n\n"
    "You have TOOLS: call the dashboard's own data (watchlists, quotes, analyst "
    "consensus with price targets, economic indicators, the economic calendar, news, "
    "symbol search) AND search the web for anything the dashboard doesn't have. "
    "Be proactive — when asked about a stock's outlook or 'future projection', actually "
    "call get_analyst_consensus (and/or web_search for the latest), compare the numbers, "
    "and give a real answer. Never tell the user to go check another site themselves; "
    "look it up yourself with your tools. When comparing several watchlist holdings, "
    "fetch each one's data and compare.\n\n"
    "Reply in plain conversational text suitable for a small chat window — avoid markdown "
    "symbols like **, ##, or bullet characters. Be concise unless asked for depth. You are "
    "not a licensed financial advisor; for personalized buy/sell decisions, add a brief note."
)


@router.post("/chat")
def chat(req: ChatRequest, request: Request):
    if not settings.anthropic_api_key:
        raise HTTPException(503, "Chat isn't available — no API key is configured.")

    ip = request.headers.get("fly-client-ip") or (
        request.client.host if request.client else "anon"
    )
    if not _rate_ok(ip):
        raise HTTPException(429, "Whoa — too many messages. Give it a minute.")

    messages: list = [
        {"role": m.role, "content": m.content[:4000]}
        for m in req.messages[-20:]
        if m.role in ("user", "assistant") and m.content.strip()
    ]
    if not messages:
        raise HTTPException(400, "Nothing to send.")

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        final_text = ""

        for _ in range(6):  # agentic loop: tool calls until a final answer
            resp = client.messages.create(
                model=settings.chat_model,
                max_tokens=2048,
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
            )
            text = "".join(
                getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text"
            ).strip()
            if text:
                final_text = text

            if resp.stop_reason != "tool_use":
                break

            # Run the client-side tools Claude requested, feed results back.
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if getattr(block, "type", "") == "tool_use":
                    try:
                        out = _run_tool(block.name, block.input or {})
                    except Exception as e:  # surface to Claude, don't crash
                        out = {"error": str(e)}
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(out, default=str)[:9000],
                    })
            messages.append({"role": "user", "content": results})

        return {"reply": final_text or "(no response)"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Claude couldn't respond just now — try again in a moment.")
