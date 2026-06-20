"""Macro narrative: turn the day's market moves into a plain-English 'why'.

Works with zero configuration (returns a templated summary). If an
ANTHROPIC_API_KEY is set, it asks Claude to write a richer explanation that
ties the moves to macro themes.
"""

from __future__ import annotations

import time

from ..config import settings
from . import economy, market

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 600  # narratives are expensive; refresh every 10 min


def _describe_moves(summary: dict[str, dict]) -> str:
    lines: list[str] = []
    for cls, data in summary.items():
        movers = data.get("all", [])
        if not movers:
            continue
        avg = data.get("average_pct")
        avg_txt = f"{avg:+.2f}%" if avg is not None else "n/a"
        detail = ", ".join(f"{m['name']} {m['change_pct']:+.2f}%" for m in movers)
        lines.append(f"{data.get('label', cls)} (avg {avg_txt}): {detail}")
    return "\n".join(lines)


def _fallback(summary: dict[str, dict]) -> str:
    parts: list[str] = []
    for cls, data in summary.items():
        avg = data.get("average_pct")
        if avg is None:
            continue
        direction = "up" if avg > 0.05 else "down" if avg < -0.05 else "roughly flat"
        label = data.get("label", cls)
        lead = data.get("gainers", [{}])[0]
        lag = data.get("losers", [{}])[0]
        bits = f"{label} are {direction}"
        if avg is not None and direction != "roughly flat":
            bits += f" {abs(avg):.2f}% on average"
        if lead.get("name") and lag.get("name"):
            bits += (
                f" (best: {lead['name']} {lead['change_pct']:+.1f}%, "
                f"worst: {lag['name']} {lag['change_pct']:+.1f}%)"
            )
        parts.append(bits + ".")
    return " ".join(parts) or "No market data available yet."


def market_narrative(scope: str = "day") -> dict:
    hit = _cache.get(scope)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]

    summary = market.get_summary(scope)
    fallback = _fallback(summary)

    if not settings.anthropic_api_key:
        result = {"scope": scope, "narrative": fallback, "ai": False}
        _cache[scope] = (time.time(), result)
        return result

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        moves = _describe_moves(summary)
        try:
            econ = economy.headline_context()
        except Exception:
            econ = ""
        econ_block = f"\n\nLatest economic readings:\n{econ}\n" if econ else "\n"
        period_word = {"day": "today", "week": "this week", "month": "this month"}.get(
            scope, "recently"
        )
        prompt = (
            f"You are a markets commentator. Here is how tracked instruments moved "
            f"{period_word}:\n\n{moves}\n{econ_block}\n"
            "Write a concise 2-3 paragraph explanation of what the market did and the "
            "likely macro drivers (rates, inflation, growth, geopolitics, the dollar, "
            "risk appetite). Tie the price action to the economic readings above where "
            "relevant. Connect cross-asset moves where it makes sense (e.g. yields vs. "
            "equities, oil vs. inflation). Be specific and grounded in the numbers above; "
            "do not invent precise data points you weren't given. Plain English, no "
            "disclaimers."
        )
        msg = client.messages.create(
            model=settings.narrative_model,
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ).strip()
        result = {"scope": scope, "narrative": text or fallback, "ai": bool(text)}
    except Exception as e:  # network, auth, quota — degrade gracefully
        result = {"scope": scope, "narrative": fallback, "ai": False, "error": str(e)}

    _cache[scope] = (time.time(), result)
    return result
