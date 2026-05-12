"""
AgentSystem — Proactive scheduler.

Registers time-based pollers on the NotificationGateway so the assistant
proactively prompts for the morning briefing, end-of-day review, and upcoming
meetings — without the user having to remember to ask.

All pollers return ``list[Event]`` so they plug into the existing gateway and
audit pipeline. State is persisted under ``memory/scheduler_state.json`` to
avoid duplicate firings across a single local day.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tools.audit import log_action
from tools.graph_tools import graph_get_upcoming_events
from tools.notification import Event, NotificationGateway

logger = logging.getLogger(__name__)

SCHEDULER_STATE_PATH = (
    Path(__file__).resolve().parent.parent / "memory" / "scheduler_state.json"
)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        logger.warning("Invalid %s=%r; using default %s", name, raw, default)
        return default


def _timezone_offset() -> timedelta:
    """Local timezone offset in hours from UTC. Default: UTC."""
    return timedelta(hours=_env_int("SCHEDULER_TIMEZONE_OFFSET_HOURS", 0))


def _local_now() -> datetime:
    return datetime.now(timezone.utc) + _timezone_offset()


def _load_state() -> dict[str, Any]:
    if not SCHEDULER_STATE_PATH.exists():
        return {}
    try:
        return json.loads(SCHEDULER_STATE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Scheduler state unreadable (%s); starting fresh", exc)
        return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        SCHEDULER_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SCHEDULER_STATE_PATH.write_text(
            json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning("Failed to persist scheduler state: %s", exc)


def _already_fired_today(state: dict[str, Any], key: str, today_str: str) -> bool:
    return state.get(key) == today_str


def _mark_fired_today(state: dict[str, Any], key: str, today_str: str) -> None:
    state[key] = today_str
    _save_state(state)


async def poll_morning_briefing() -> list[Event]:
    """Fire once per local day at or after the configured morning hour."""
    briefing_hour = _env_int("SCHEDULER_BRIEFING_HOUR", 8)
    local_now = _local_now()
    if local_now.hour < briefing_hour:
        return []

    state = _load_state()
    today_str = local_now.date().isoformat()
    if _already_fired_today(state, "last_morning_briefing_date", today_str):
        return []

    _mark_fired_today(state, "last_morning_briefing_date", today_str)
    log_action(
        "Scheduler",
        "morning_briefing_trigger",
        f"hour={briefing_hour}",
        today_str,
        status="completed",
    )

    return [
        Event(
            source="scheduler",
            event_type="morning_briefing_due",
            summary=(
                "Run the morning briefing now. Use the generate_daily_briefing tool "
                "to produce today's start-of-day report (calendar, important unread "
                "mail with draft replies, follow-ups, routines)."
            ),
            data={"scheduled_hour": briefing_hour, "local_date": today_str},
            priority="high",
        )
    ]


async def poll_end_of_day() -> list[Event]:
    """Fire once per local day at or after the configured end-of-day hour."""
    eod_hour = _env_int("SCHEDULER_EOD_HOUR", 17)
    local_now = _local_now()
    if local_now.hour < eod_hour:
        return []

    state = _load_state()
    today_str = local_now.date().isoformat()
    if _already_fired_today(state, "last_eod_date", today_str):
        return []

    _mark_fired_today(state, "last_eod_date", today_str)
    log_action(
        "Scheduler",
        "end_of_day_trigger",
        f"hour={eod_hour}",
        today_str,
        status="completed",
    )

    return [
        Event(
            source="scheduler",
            event_type="end_of_day_due",
            summary=(
                "Run the end-of-day review now. Use the generate_eod_review tool to "
                "summarize today's accomplishments, unreplied important mail, "
                "tomorrow's calendar, pending follow-ups, and top 3 priorities for "
                "tomorrow."
            ),
            data={"scheduled_hour": eod_hour, "local_date": today_str},
            priority="high",
        )
    ]


async def poll_meeting_alerts() -> list[Event]:
    """Fire a one-time alert ahead of each upcoming calendar event."""
    lead_minutes = _env_int("SCHEDULER_MEETING_LEAD_MINUTES", 15)
    try:
        events = await graph_get_upcoming_events(days_ahead=1)
    except Exception as exc:
        logger.debug("Meeting alert poller skipped: %s", exc)
        return []

    state = _load_state()
    fired_ids: set[str] = set(state.get("meeting_alert_ids", []))
    today_str = _local_now().date().isoformat()
    last_prune = state.get("meeting_alert_prune_date")
    if last_prune != today_str:
        fired_ids = set()
        state["meeting_alert_prune_date"] = today_str

    now_utc = datetime.now(timezone.utc)
    window_end = now_utc + timedelta(minutes=lead_minutes)

    emitted: list[Event] = []

    for event in events:
        event_id = str(event.get("id", "")).strip()
        if not event_id or event_id in fired_ids:
            continue

        start_raw = event.get("start")
        if not start_raw:
            continue
        try:
            start_dt = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
        except ValueError:
            continue
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        if not (now_utc <= start_dt <= window_end):
            continue

        subject = event.get("subject") or "Untitled event"
        location = event.get("location") or "No location"
        minutes_out = max(0, int((start_dt - now_utc).total_seconds() // 60))

        fired_ids.add(event_id)
        emitted.append(
            Event(
                source="scheduler",
                event_type="meeting_soon",
                summary=(
                    f"Meeting '{subject}' starts in ~{minutes_out} minute(s) at "
                    f"{start_dt.isoformat()} ({location}). Prep quickly: pull any "
                    "relevant context from memory and recent emails, and remind me "
                    "of the key talking points."
                ),
                data={
                    "event_id": event_id,
                    "subject": subject,
                    "start": start_raw,
                    "location": location,
                    "minutes_until_start": minutes_out,
                },
                priority="urgent",
            )
        )
        log_action(
            "Scheduler",
            "meeting_alert",
            f"event_id={event_id}, minutes_out={minutes_out}",
            subject,
            status="completed",
        )

    if emitted or state.get("meeting_alert_prune_date") == today_str:
        state["meeting_alert_ids"] = list(fired_ids)[-200:]
        _save_state(state)

    return emitted


def register_scheduler_pollers(gateway: NotificationGateway) -> None:
    """Attach all scheduler pollers to the given gateway."""
    gateway.register_poller("morning_briefing", poll_morning_briefing, interval_seconds=300)
    gateway.register_poller("end_of_day", poll_end_of_day, interval_seconds=300)
    gateway.register_poller("meeting_alerts", poll_meeting_alerts, interval_seconds=120)
    logger.info("Scheduler pollers registered on notification gateway")


SCHEDULER_POLLERS = [poll_morning_briefing, poll_end_of_day, poll_meeting_alerts]
