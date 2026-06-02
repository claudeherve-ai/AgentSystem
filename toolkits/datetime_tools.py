"""
toolkits.datetime_tools — date/business-day/SLA math (stdlib only).

Computes durations between dates, adds business days (skipping weekends and
optional holidays), and derives SLA deadlines. Pure `datetime`; deterministic;
fail-soft; no LLM, no network, no credentials.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

_FORMATS = (
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
)


def _loads(raw: str, label: str) -> Any:
    if raw is None or str(raw).strip() == "":
        raise ValueError(f"{label} is empty")
    return json.loads(raw)


def _parse(value: str) -> datetime:
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+0000"
    for fmt in _FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    # last resort: ISO parser
    return datetime.fromisoformat(str(value).strip())


def date_diff(
    start: Annotated[str, "Start date/datetime, e.g. 2024-01-01 or 2024-01-01T09:00:00"],
    end: Annotated[str, "End date/datetime"],
    unit: Annotated[str, "Result unit: days (default), hours, minutes, seconds, or weeks"] = "days",
) -> str:
    """Compute the signed duration between two dates/datetimes in the requested unit.

    Accepts many common formats (ISO, ``YYYY-MM-DD``, ``MM/DD/YYYY``). Returns the
    difference plus a human-readable breakdown. Fails soft on unparseable input.
    """
    try:
        a = _parse(start)
        b = _parse(end)
        if a.tzinfo and not b.tzinfo:
            b = b.replace(tzinfo=a.tzinfo)
        elif b.tzinfo and not a.tzinfo:
            a = a.replace(tzinfo=b.tzinfo)
        delta = b - a
        secs = delta.total_seconds()
        u = unit.lower().strip()
        factor = {
            "seconds": 1, "minutes": 60, "hours": 3600,
            "days": 86400, "weeks": 604800,
        }.get(u, 86400)
        value = secs / factor
        total_days = secs / 86400
        return (f"# Date Difference\n\n"
                f"**From:** {a.isoformat()}\n**To:** {b.isoformat()}\n\n"
                f"**Result:** {value:.4g} {u if u in {'seconds','minutes','hours','days','weeks'} else 'days'}\n"
                f"**Breakdown:** {total_days:.2f} days ({secs:,.0f} seconds)")
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: could not parse dates — {e}"


def add_business_days(
    start: Annotated[str, "Start date, e.g. 2024-01-01"],
    days: Annotated[int, "Number of business days to add (can be negative)"],
    holidays_json: Annotated[
        str, 'Optional JSON array of holiday dates (YYYY-MM-DD) to skip, e.g. ["2024-01-15"]'
    ] = "[]",
) -> str:
    """Add (or subtract) business days to a date, skipping weekends and given holidays.

    Counts only Mon–Fri that are not in the holiday list. Returns the resulting date
    and weekday. Fails soft on bad input.
    """
    try:
        cur = _parse(start)
        holidays: set[str] = set()
        if str(holidays_json).strip():
            raw = _loads(holidays_json, "holidays_json")
            if isinstance(raw, list):
                holidays = {str(h).strip() for h in raw}
        n = int(days)
        step = 1 if n >= 0 else -1
        remaining = abs(n)
        guard = 0
        while remaining > 0 and guard < 100000:
            guard += 1
            cur = cur + timedelta(days=step)
            if cur.weekday() >= 5:
                continue
            if cur.strftime("%Y-%m-%d") in holidays:
                continue
            remaining -= 1
        return (f"# Business-Day Calculation\n\n"
                f"**Start:** {_parse(start).strftime('%Y-%m-%d (%A)')}\n"
                f"**Business days added:** {n}\n"
                f"**Holidays skipped:** {len(holidays)}\n\n"
                f"**Result:** {cur.strftime('%Y-%m-%d (%A)')}")
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


def sla_deadline(
    start: Annotated[str, "Ticket/start datetime, e.g. 2024-01-01T09:00:00"],
    hours: Annotated[float, "SLA budget in hours"],
    business_hours_json: Annotated[
        str,
        'Optional business-hours config, e.g. {"start_hour":9,"end_hour":17,"skip_weekends":true}. '
        "Omit for 24/7 calendar-hour SLA.",
    ] = "",
) -> str:
    """Compute an SLA deadline from a start time and an hour budget.

    By default uses calendar (24/7) hours. If a business-hours window is supplied,
    consumes the budget only within working hours on weekdays, rolling to the next
    working window as needed. Returns the deadline datetime. Fails soft.
    """
    try:
        start_dt = _parse(start)
        budget = float(hours)
        if budget < 0:
            return "❌ Error: hours must be non-negative"

        if not str(business_hours_json).strip():
            deadline = start_dt + timedelta(hours=budget)
            return (f"# SLA Deadline (24/7)\n\n"
                    f"**Start:** {start_dt.isoformat()}\n"
                    f"**Budget:** {budget:g} hours\n\n"
                    f"**Deadline:** {deadline.isoformat()}")

        cfg = _loads(business_hours_json, "business_hours_json")
        sh = int(cfg.get("start_hour", 9))
        eh = int(cfg.get("end_hour", 17))
        skip_weekends = bool(cfg.get("skip_weekends", True))
        if not (0 <= sh < eh <= 24):
            return "❌ Error: invalid business hours (need 0 ≤ start_hour < end_hour ≤ 24)"

        remaining = timedelta(hours=budget)
        cur = start_dt
        guard = 0
        while remaining.total_seconds() > 0 and guard < 100000:
            guard += 1
            if skip_weekends and cur.weekday() >= 5:
                cur = (cur + timedelta(days=1)).replace(hour=sh, minute=0, second=0, microsecond=0)
                continue
            day_start = cur.replace(hour=sh, minute=0, second=0, microsecond=0)
            day_end = cur.replace(hour=eh, minute=0, second=0, microsecond=0)
            if cur < day_start:
                cur = day_start
            if cur >= day_end:
                cur = (cur + timedelta(days=1)).replace(hour=sh, minute=0, second=0, microsecond=0)
                continue
            avail = day_end - cur
            if remaining <= avail:
                cur = cur + remaining
                remaining = timedelta(0)
            else:
                remaining -= avail
                cur = (cur + timedelta(days=1)).replace(hour=sh, minute=0, second=0, microsecond=0)
        return (f"# SLA Deadline (business hours {sh:02d}:00–{eh:02d}:00)\n\n"
                f"**Start:** {start_dt.isoformat()}\n"
                f"**Budget:** {budget:g} business hours\n"
                f"**Skip weekends:** {skip_weekends}\n\n"
                f"**Deadline:** {cur.isoformat()}")
    except Exception as e:  # noqa: BLE001
        return f"❌ Error: {e}"


DATETIME_TOOLS = [date_diff, add_business_days, sla_deadline]
