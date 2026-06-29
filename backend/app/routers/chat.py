"""In-app Claude chat — a small assistant aware of the live dashboard data.

The Anthropic key stays server-side. Lightly guarded (token caps, history limit,
per-IP rate limit) since the endpoint is public.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import settings
from ..providers import market

router = APIRouter()


class Msg(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Msg]


_hits: dict[str, list[float]] = defaultdict(list)
_RATE_N = 40  # max messages per IP...
_RATE_WINDOW = 300  # ...per 5 minutes


def _rate_ok(ip: str) -> bool:
    now = time.time()
    recent = [t for t in _hits[ip] if now - t < _RATE_WINDOW]
    recent.append(now)
    _hits[ip] = recent
    return len(recent) <= _RATE_N


def _market_context() -> str:
    try:
        summary = market.get_summary("day")
    except Exception:
        return ""
    lines: list[str] = []
    for cls, d in summary.items():
        avg = d.get("average_pct")
        if avg is None:
            continue
        g = (d.get("gainers") or [{}])[0]
        l = (d.get("losers") or [{}])[0]
        bit = f"{d.get('label', cls)}: avg {avg:+.2f}% today"
        if g.get("name"):
            bit += f" (best {g['name']} {g['change_pct']:+.1f}%"
            if l.get("name"):
                bit += f", worst {l['name']} {l['change_pct']:+.1f}%"
            bit += ")"
        lines.append(bit)
    return "\n".join(lines)


@router.post("/chat")
def chat(req: ChatRequest, request: Request):
    if not settings.anthropic_api_key:
        raise HTTPException(503, "Chat isn't available — no API key is configured.")

    ip = request.headers.get("fly-client-ip") or (
        request.client.host if request.client else "anon"
    )
    if not _rate_ok(ip):
        raise HTTPException(429, "Whoa — too many messages. Give it a minute.")

    api_messages = [
        {"role": m.role, "content": m.content[:4000]}
        for m in req.messages[-20:]
        if m.role in ("user", "assistant") and m.content.strip()
    ]
    if not api_messages:
        raise HTTPException(400, "Nothing to send.")

    ctx = _market_context()
    system = (
        "You are Claude, a helpful assistant embedded as a small chat panel inside the "
        "user's personal live markets dashboard. Help with markets, finance, the economy, "
        "or anything else they ask. Be concise, clear, and friendly; use plain language and "
        "explain jargon. You are not a licensed financial advisor — for personalized "
        "investment decisions, say so briefly. Reply in plain conversational text "
        "for a small chat window — avoid markdown symbols like **, ##, or bullet "
        "characters; keep it short unless asked for detail.\n\n"
        + (f"The user's live dashboard right now:\n{ctx}\n" if ctx else "")
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model=settings.chat_model,
            max_tokens=1024,
            system=system,
            messages=api_messages,
        )
        text = "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        return {"reply": text or "(no response)"}
    except Exception:
        raise HTTPException(502, "Claude couldn't respond just now — try again in a moment.")
