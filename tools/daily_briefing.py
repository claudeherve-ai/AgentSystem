"""
AgentSystem — Daily briefing workflow.

Builds a high-signal personal briefing from calendar, email, follow-ups,
and durable memory so the assistant can start the day with context.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from agents.business_agent import get_pending_followups
from tools.audit import log_action
from tools.graph_tools import graph_get_upcoming_events, graph_read_inbox
from tools.memory_tools import MEMORY_STORE

logger = logging.getLogger(__name__)

IMPORTANT_KEYWORDS = (
    "urgent",
    "asap",
    "action required",
    "approval",
    "approve",
    "review",
    "deadline",
    "follow up",
    "follow-up",
    "issue",
    "problem",
    "blocked",
    "failure",
    "incident",
    "invoice",
    "payment",
    "renewal",
    "meeting",
    "schedule",
    "today",
    "tomorrow",
)

NEGATIVE_KEYWORDS = (
    "blocked",
    "issue",
    "problem",
    "error",
    "failure",
    "concern",
    "delay",
    "late",
    "missed",
    "urgent",
)

POSITIVE_KEYWORDS = (
    "thanks",
    "thank you",
    "appreciate",
    "great",
    "excited",
    "happy",
    "congratulations",
)


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _memory_value(key: str, default: str = "") -> str:
    rows = MEMORY_STORE.search_memories(query=MEMORY_STORE.normalize_key(key), limit=5)
    for row in rows:
        if row["key"] == MEMORY_STORE.normalize_key(key):
            return row["value"]
    return default


def _important_contact_markers() -> set[str]:
    markers: set[str] = set()
    for category in ("contact", "family"):
        for row in MEMORY_STORE.list_memories(category=category, limit=50):
            markers.add(row["key"].replace("_", " ").lower())
            markers.add(_clean_text(row["value"]).lower())
    return {marker for marker in markers if len(marker) >= 4}


def _email_text(email: dict) -> str:
    parts = [
        email.get("subject", ""),
        email.get("preview", ""),
        email.get("from_name", ""),
        email.get("from", ""),
    ]
    return _clean_text(" ".join(parts)).lower()


def _score_email_importance(
    email: dict,
    contact_markers: set[str],
    now: datetime,
    hours_window: int,
) -> tuple[int, list[str]]:
    text = _email_text(email)
    score = 0
    reasons: list[str] = []

    importance = str(email.get("importance", "normal")).lower()
    if importance == "high":
        score += 3
        reasons.append("marked high importance")

    if any(marker in text for marker in contact_markers):
        score += 3
        reasons.append("important contact")

    keyword_hits = [keyword for keyword in IMPORTANT_KEYWORDS if keyword in text]
    if keyword_hits:
        score += 2
        reasons.append(f"priority language ({keyword_hits[0]})")

    received = _parse_datetime(email.get("received", ""))
    if received and now - received <= timedelta(hours=hours_window):
        score += 1
        reasons.append(f"arrived within {hours_window}h")

    return score, reasons


def _infer_sentiment(email: dict) -> str:
    text = _email_text(email)
    if any(keyword in text for keyword in NEGATIVE_KEYWORDS):
        if "urgent" in text or "asap" in text:
            return "urgent / negative"
        return "negative"
    if any(keyword in text for keyword in POSITIVE_KEYWORDS):
        return "positive"
    return "neutral"


def _build_email_summary(email: dict) -> str:
    subject = _clean_text(email.get("subject", "No subject"))
    preview = _clean_text(email.get("preview", ""))
    if not preview:
        return subject
    if preview.lower().startswith(subject.lower()):
        return preview[:220]
    return f"{subject} — {preview[:220]}"


def _draft_response(email: dict) -> str:
    sender_name = _clean_text(email.get("from_name", "")) or "there"
    subject = _clean_text(email.get("subject", "your message"))
    preview = _clean_text(email.get("preview", ""))[:120]
    text = _email_text(email)
    context = preview or subject.lower()

    if "meeting" in text or "schedule" in text or "calendar" in text or "availability" in text:
        return (
            f"Hi {sender_name},\n\n"
            f"Thanks for reaching out about {context}. I'm checking my calendar and will reply "
            f"with suitable times shortly.\n\n"
            "Best,\nClaude"
        )

    if "issue" in text or "problem" in text or "blocked" in text or "urgent" in text:
        return (
            f"Hi {sender_name},\n\n"
            f"Thanks for flagging this. I understand the urgency around {context}. "
            "I'm reviewing it now and will follow up with next steps as soon as possible.\n\n"
            "Best,\nClaude"
        )

    if "review" in text or "approve" in text or "proposal" in text or "document" in text:
        return (
            f"Hi {sender_name},\n\n"
            f"Thanks for sending this over regarding {context}. I’ve noted it and will review it "
            "carefully before replying with feedback.\n\n"
            "Best,\nClaude"
        )

    return (
        f"Hi {sender_name},\n\n"
        f"Thanks for your email about {context}. I’ve reviewed it and will get back to you shortly "
        "with the right next steps.\n\n"
        "Best,\nClaude"
    )


def _format_events(events: list[dict]) -> list[str]:
    if not events:
        return ["- No calendar events in the next 24 hours."]

    lines: list[str] = []
    for event in events[:10]:
        lines.append(
            f"- {event.get('subject') or 'Untitled'} | "
            f"{event.get('start') or 'unknown start'} -> {event.get('end') or 'unknown end'} | "
            f"{event.get('location') or 'No location'}"
        )
    return lines


def _format_routines() -> list[str]:
    routines = MEMORY_STORE.list_memories(category="routine", limit=10)
    if not routines:
        return ["- No stored routines yet."]

    return [
        f"- {row['key'].replace('_', ' ')}: {row['value']}"
        for row in routines
    ]


async def generate_daily_briefing(
    hours_window: Annotated[int, "How many recent hours of unread email to scan for important messages"] = 2,
) -> str:
    """Generate a daily briefing with calendar, important unread mail, follow-ups, and routines."""
    now = datetime.now(timezone.utc)
    timezone_pref = _memory_value("timezone", "UTC")
    briefing_format = _memory_value("briefing_format", "short bullets with urgent items first")
    contact_markers = _important_contact_markers()

    events: list[dict] = []
    important_emails: list[tuple[int, list[str], dict]] = []
    email_note = ""
    calendar_note = ""

    try:
        events = await graph_get_upcoming_events(days_ahead=1)
    except Exception as exc:
        calendar_note = f"- Calendar unavailable: {exc}"
        logger.warning("Daily briefing calendar lookup failed: %s", exc)

    try:
        emails = await graph_read_inbox(count=15, unread_only=True, hours_window=hours_window)
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
        logger.warning("Daily briefing email lookup failed: %s", exc)

    followups = await get_pending_followups()

    lines = [
        "🌅 DAILY BRIEFING",
        f"Generated: {now.isoformat()}",
        f"Timezone preference: {timezone_pref}",
        f"Format preference: {briefing_format}",
        "",
        f"1. Important unread emails (last {hours_window} hours)",
    ]

    if important_emails:
        for index, (score, reasons, email) in enumerate(important_emails[:3], start=1):
            sender = _clean_text(email.get("from_name", "")) or email.get("from", "Unknown sender")
            lines.extend(
                [
                    f"- Email {index}: {sender}",
                    f"  Subject: {_clean_text(email.get('subject', 'No subject'))}",
                    f"  Received: {email.get('received') or 'unknown'}",
                    f"  Importance score: {score} ({', '.join(reasons)})",
                    f"  Sentiment: {_infer_sentiment(email)}",
                    f"  Summary: {_build_email_summary(email)}",
                    "  Draft response:",
                    *[f"    {line}" for line in _draft_response(email).splitlines()],
                ]
            )
    elif email_note:
        lines.append(email_note)
    else:
        lines.append(f"- No important unread emails detected in the last {hours_window} hours.")

    lines.extend(
        [
            "",
            "2. Calendar snapshot (next 24 hours)",
        ]
    )
    if calendar_note:
        lines.append(calendar_note)
    else:
        lines.extend(_format_events(events))

    lines.extend(
        [
            "",
            "3. Pending follow-ups",
            followups,
            "",
            "4. Personal routines and reminders",
            *_format_routines(),
        ]
    )

    log_action(
        "DailyBriefing",
        "generate_daily_briefing",
        f"hours_window={hours_window}",
        f"emails={len(important_emails)}, events={len(events)}",
        status="completed",
    )
    return "\n".join(lines)


DAILY_BRIEFING_TOOLS = [generate_daily_briefing]
