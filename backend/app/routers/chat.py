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
from fastapi.responses import StreamingResponse
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
    web_search: bool = True
    model: str = "fast"  # "fast" | "deep"


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

DASHBOARD_TOOLS = [
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
]

# Web search is an Anthropic server tool; kept separate so Settings can toggle it.
WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 5}
TOOLS = DASHBOARD_TOOLS + [WEB_SEARCH_TOOL]

# "fast" is the everyday model; "deep" trades latency for a stronger model.
CHAT_MODELS = {"fast": settings.chat_model, "deep": "claude-opus-4-8"}


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


def _status_for(name: str, inp: dict) -> str:
    sym = (inp or {}).get("symbol")
    return {
        "get_watchlists": "Checking your watchlist…",
        "get_market_overview": "Scanning the markets…",
        "get_quote": f"Getting {sym} quote…" if sym else "Getting a quote…",
        "get_analyst_consensus": f"Pulling analyst targets for {sym}…" if sym else "Pulling analyst targets…",
        "get_economic_indicators": "Reading the economic data…",
        "get_economic_calendar": "Checking the calendar…",
        "get_news": "Reading the news…",
        "search_symbols": "Searching tickers…",
    }.get(name, "Working…")


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
    "not a licensed financial advisor; for personalized buy/sell decisions, add a brief note. "
    "Don't narrate that you're about to use a tool — just use it, then give the answer."
)


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


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

    tools = DASHBOARD_TOOLS + ([WEB_SEARCH_TOOL] if req.web_search else [])
    model_id = CHAT_MODELS.get(req.model, settings.chat_model)

    def stream():
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            for _ in range(6):  # agentic loop until a final answer
                with client.messages.stream(
                    model=model_id,
                    max_tokens=2048,
                    system=SYSTEM,
                    tools=tools,
                    messages=messages,
                ) as s:
                    for event in s:
                        et = getattr(event, "type", "")
                        if et == "content_block_start":
                            if getattr(getattr(event, "content_block", None), "name", "") == "web_search":
                                yield _sse({"type": "status", "text": "Searching the web…"})
                        elif et == "content_block_delta":
                            d = getattr(event, "delta", None)
                            if getattr(d, "type", "") == "text_delta":
                                yield _sse({"type": "delta", "text": d.text})
                    final = s.get_final_message()

                if final.stop_reason != "tool_use":
                    break

                messages.append({"role": "assistant", "content": final.content})
                results = []
                for block in final.content:
                    if getattr(block, "type", "") == "tool_use":
                        yield _sse({"type": "status", "text": _status_for(block.name, block.input or {})})
                        try:
                            out = _run_tool(block.name, block.input or {})
                        except Exception as e:
                            out = {"error": str(e)}
                        results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(out, default=str)[:9000],
                        })
                messages.append({"role": "user", "content": results})
        except Exception:
            yield _sse({"type": "error", "text": "Claude couldn't respond just now — try again."})
        yield _sse({"type": "done"})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
