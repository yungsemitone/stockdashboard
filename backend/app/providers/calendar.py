"""Economic calendar: upcoming macro events + what they mean for markets.

Dates that are publicly fixed (FOMC) or follow a strict rule (jobs report =
first Friday, jobless claims = Thursdays) are exact. Other monthly releases
(CPI, PPI, PCE, retail sales) vary a few days month to month, so we place them
on their *typical* day and flag them `approximate`.
"""

from __future__ import annotations

import calendar as _cal
import time
from datetime import date, timedelta

# FOMC rate-decision dates for 2026 (announcement is the 2nd day of each meeting).
# Source: federalreserve.gov FOMC calendar.
FOMC_2026 = [
    date(2026, 1, 28),
    date(2026, 3, 18),
    date(2026, 4, 29),
    date(2026, 6, 17),
    date(2026, 7, 29),
    date(2026, 9, 16),
    date(2026, 10, 28),
    date(2026, 12, 9),
]

IMPLICATIONS = {
    "fomc": "Fed interest-rate decision + Chair press conference (2pm ET). The single biggest scheduled mover for rates, the dollar, stocks and bonds.",
    "nfp": "Monthly jobs report. Sets the tone for growth and Fed expectations — big surprises whip rates and equities.",
    "cpi": "Consumer Price Index — the headline inflation read. Hot CPI lifts yields and pressures stocks; soft CPI is risk-on.",
    "ppi": "Producer Price Index — wholesale inflation that often foreshadows CPI and feeds the Fed's PCE gauge.",
    "retail": "Retail Sales — a direct read on consumer demand. Strong sales support growth but can keep rates higher for longer.",
    "pce": "Core PCE, the Fed's preferred inflation gauge. Moves rate-cut odds more than any other inflation print.",
    "claims": "Weekly initial jobless claims — a timely pulse on the labor market.",
    "sentiment": "U. Michigan Consumer Sentiment — a leading gauge of household confidence and spending.",
}

_cache: tuple[float, list[dict]] | None = None
_TTL = 3600


def _first_friday(year: int, month: int) -> date:
    d = date(year, month, 1)
    return d + timedelta(days=(4 - d.weekday()) % 7)  # weekday: Fri == 4


def _approx(year: int, month: int, day: int) -> date:
    last = _cal.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _months_ahead(today: date, n: int):
    for i in range(n + 1):
        total = today.month - 1 + i
        yield today.year + total // 12, total % 12 + 1


def upcoming(days_ahead: int = 45) -> list[dict]:
    global _cache
    if _cache and time.time() - _cache[0] < _TTL:
        return _cache[1]

    today = date.today()
    horizon = today + timedelta(days=days_ahead)
    events: list[dict] = []

    def add(d: date, name: str, importance: str, key: str,
            approximate: bool = False, time_et: str | None = None) -> None:
        if today <= d <= horizon:
            events.append({
                "date": d.isoformat(),
                "name": name,
                "importance": importance,
                "approximate": approximate,
                "time_et": time_et,
                "implication": IMPLICATIONS[key],
            })

    for d in FOMC_2026:
        add(d, "FOMC Rate Decision", "high", "fomc", time_et="2:00 PM ET")

    for yy, mm in _months_ahead(today, 2):
        add(_first_friday(yy, mm), "Jobs Report (Nonfarm Payrolls)", "high", "nfp", time_et="8:30 AM ET")
        add(_approx(yy, mm, 12), "CPI Inflation", "high", "cpi", approximate=True, time_et="8:30 AM ET")
        add(_approx(yy, mm, 13), "PPI Inflation", "medium", "ppi", approximate=True, time_et="8:30 AM ET")
        add(_approx(yy, mm, 16), "Retail Sales", "medium", "retail", approximate=True, time_et="8:30 AM ET")
        add(_approx(yy, mm, 28), "Core PCE Price Index", "high", "pce", approximate=True, time_et="8:30 AM ET")
        add(_approx(yy, mm, 27), "Consumer Sentiment", "low", "sentiment", approximate=True)

    d = today
    while d <= horizon:
        if d.weekday() == 3:  # Thursday
            add(d, "Initial Jobless Claims", "low", "claims", time_et="8:30 AM ET")
        d += timedelta(days=1)

    rank = {"high": 0, "medium": 1, "low": 2}
    events.sort(key=lambda e: (e["date"], rank[e["importance"]]))

    _cache = (time.time(), events)
    return events
