"""
AgentSystem — End-of-day review workflow.

Closes the productivity loop started by the daily briefing. Pulls today's
completed actions from the audit log, flags unread important mail, previews
tomorrow's calendar, reviews pending follow-ups, and proposes the top three
priorities for tomorrow.
"""

import logging
import sqlite3
from datetime import datetime, time, timedelta, timezone
from typing import Annotated

from agents.business_agent import get_pending_followups
from tools.audit import DB_PATH as AUDIT_DB_PATH, log_action
from tools.daily_briefing import (
    _build_email_summary,
    _clean_text,
    _format_routines,
    _important_contact_markers,
    _infer_sentiment,
    _memory_value,
    _parse_datetime,
    _score_email_importance,
)
from tools.graph_tools import graph_get_upcoming_events, graph_read_inbox

logger = logging.getLogger(__name__)

NON_SUBSTANTIVE_ACTIONS = {
    "startup",
    "shutdown",
    "error",
    "smoke_test_v2",
}


def _start_of_local_day(now_utc: datetime) -> datetime:
    """Midnight UTC today. Kept UTC to match audit log timestamps."""
    return datetime.combine(now_utc.date(), time.min, tzinfo=timezone.utc)


def _load_todays_actions(start_of_day: datetime) -> list[dict]:
    """Read completed actions from the audit DB for the current day."""
    if not AUDIT_DB_PATH.exists():
        return []

    conn = sqlite3.connect(str(AUDIT_DB_PATH))
    try:
        rows = conn.execute(
            """
            SELECT timestamp, agent_name, action, input_summary, output_summary, status
            FROM agent_actions
            WHERE timestamp >= ? AND status = 'completed'
            ORDER BY id ASC
            """,
            (start_of_day.isoformat(),),
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        logger.warning("End-of-day audit lookup failed: %s", exc)
        return []
    finally:
        conn.close()

    results: list[dict] = []
    for timestamp, agent_name, action, input_summary, output_summary, status in rows:
        if action in NON_SUBSTANTIVE_ACTIONS:
            continue
        results.append(
            {
                "timestamp": timestamp,
                "agent_name": agent_name,
                "action": action,
                "input_summary": input_summary or "",
                "output_summary": output_summary or "",
                "status": status,
            }
        )
    return results


def _summarize_accomplishments(actions: list[dict]) -> list[str]:
    if not actions:
        return ["- Nothing was logged to the audit trail today."]

    # Group by agent to show a compact rollup.
    by_agent: dict[str, list[dict]] = {}
    for entry in actions:
        by_agent.setdefault(entry["agent_name"], []).append(entry)

    lines: list[str] = []
    for agent_name in sorted(by_agent):
        entries = by_agent[agent_name]
        lines.append(f"- {agent_name} ({len(entries)} actions)")
        # Show up to 5 most recent actions per agent.
        for entry in entries[-5:]:
            action = entry["action"]
            input_hint = _clean_text(entry["input_summary"])[:120]
            if input_hint:
                lines.append(f"    • {action} — {input_hint}")
            else:
                lines.append(f"    • {action}")
    return lines


def _priorities_for_tomorrow(
    important_emails: list[tuple[int, list[str], dict]],
    events: list[dict],
    followups_text: str,
) -> list[str]:
    priorities: list[str] = []

    # 1. Unanswered important emails take the top slot.
    for score, reasons, email in important_emails[:2]:
        sender = _clean_text(email.get("from_name", "")) or email.get("from", "Unknown sender")
        subject = _clean_text(email.get("subject", "No subject"))
        priorities.append(
            f"Reply to {sender} — {subject} (importance {score}: {', '.join(reasons) or 'flagged'})"
        )

    # 2. First calendar event of tomorrow as a prep reminder.
    if events:
        first = events[0]
        subject = first.get("subject") or "Untitled event"
        start = first.get("start") or "unknown start"
        priorities.append(f"Prep for first meeting: {subject} at {start}")

    # 3. Add the first actionable follow-up if not already covered.
    followup_lines = [
        line.strip("- ").strip()
        for line in (followups_text or "").splitlines()
        if line.strip().startswith("-")
    ]
    if followup_lines:
        priorities.append(f"Close pending follow-up: {followup_lines[0][:140]}")

    if not priorities:
        priorities.append("No urgent signals detected — plan a deep-work block for your top goal.")

    # Cap at 3 priorities.
    return [f"{index}. {item}" for index, item in enumerate(priorities[:3], start=1)]


async def generate_eod_review(
    hours_window: Annotated[int, "How many hours of today's inbox to scan for unreplied important mail"] = 12,
) -> str:
    """Generate an end-of-day review covering today's work and tomorrow's priorities."""
    now = datetime.now(timezone.utc)
    start_of_day = _start_of_local_day(now)
    timezone_pref = _memory_value("timezone", "UTC")
    contact_markers = _important_contact_markers()

    # Section 1: accomplishments from the audit log.
    todays_actions = _load_todays_actions(start_of_day)
    accomplishment_lines = _summarize_accomplishments(todays_actions)

    # Section 2: unread important mail that still needs a reply today.
    important_emails: list[tuple[int, list[str], dict]] = []
    email_note = ""
    try:
        emails = await graph_read_inbox(
            count=25,
            unread_only=True,
            hours_window=hours_window,
        )
        for email in emails:
            score, reasons = _score_email_importance(email, contact_markers, now, hours_window)
            if score >= 2:
                important_emails.append((score, reasons, email))
        important_emails.sort(
            key=lambda item: (
                -item[0],
                _parse_datetime(item[2].get("received", "")) or datetime.min.replace(tzinfo=timezone.utc),
            ),
        )
    except Exception as exc:
        email_note = f"- Email unavailable: {exc}"
        logger.warning("End-of-day email lookup failed: %s", exc)

    # Section 3: tomorrow's calendar preview.
    events: list[dict] = []
    calendar_note = ""
    try:
        events = await graph_get_upcoming_events(days_ahead=1)
    except Exception as exc:
        calendar_note = f"- Calendar unavailable: {exc}"
        logger.warning("End-of-day calendar lookup failed: %s", exc)

    # Section 4: pending follow-ups.
    followups_text = await get_pending_followups()

    # Section 5: top 3 priorities for tomorrow.
    priorities = _priorities_for_tomorrow(important_emails, events, followups_text)

    lines: list[str] = [
        "🌆 END-OF-DAY REVIEW",
        f"Generated: {now.isoformat()}",
        f"Timezone preference: {timezone_pref}",
        "",
        "1. Today's accomplishments (from audit log)",
    ]
    lines.extend(accomplishment_lines)

    lines.extend(
        [
            "",
            f"2. Unreplied important email (last {hours_window} hours)",
        ]
    )
    if email_note:
        lines.append(email_note)
    elif important_emails:
        for index, (score, reasons, email) in enumerate(important_emails[:3], start=1):
            sender = _clean_text(email.get("from_name", "")) or email.get("from", "Unknown sender")
            lines.extend(
                [
                    f"- Email {index}: {sender}",
                    f"  Subject: {_clean_text(email.get('subject', 'No subject'))}",
                    f"  Received: {email.get('received') or 'unknown'}",
                    f"  Importance score: {score} ({', '.join(reasons) or 'flagged'})",
                    f"  Sentiment: {_infer_sentiment(email)}",
                    f"  Summary: {_build_email_summary(email)}",
                ]
            )
    else:
        lines.append("- Inbox is clear of unreplied important mail.")

    lines.extend(
        [
            "",
            "3. Tomorrow's calendar (next 24 hours)",
        ]
    )
    if calendar_note:
        lines.append(calendar_note)
    elif events:
        for event in events[:10]:
            lines.append(
                f"- {event.get('subject') or 'Untitled'} | "
                f"{event.get('start') or 'unknown start'} -> {event.get('end') or 'unknown end'} | "
                f"{event.get('location') or 'No location'}"
            )
    else:
        lines.append("- No events scheduled in the next 24 hours.")

    lines.extend(
        [
            "",
            "4. Pending follow-ups",
            followups_text,
            "",
            "5. Top 3 priorities for tomorrow",
            *priorities,
            "",
            "6. Personal routines reminder",
            *_format_routines(),
        ]
    )

    log_action(
        "EndOfDayReview",
        "generate_eod_review",
        f"hours_window={hours_window}",
        f"actions={len(todays_actions)}, emails={len(important_emails)}, events={len(events)}",
        status="completed",
    )

    return "\n".join(lines)


END_OF_DAY_TOOLS = [generate_eod_review]
