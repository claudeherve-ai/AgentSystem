"""
AgentSystem — Calendar Agent.

Manages calendar operations via Microsoft Graph API.
Supports reading upcoming events, creating events, and conflict detection.
"""

import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails import Guardrails
from guardrails.approval import HumanApproval
from tools.audit import log_action

logger = logging.getLogger(__name__)

_guardrails = Guardrails()
_approval = HumanApproval()


async def get_upcoming_events(
    days_ahead: Annotated[int, "Number of days to look ahead"] = 7,
) -> str:
    """
    Get upcoming calendar events for the next N days.

    NOTE: Placeholder — replace with Microsoft Graph Calendar API.
    """
    log_action("CalendarAgent", "get_upcoming_events", f"days_ahead={days_ahead}")

    try:
        from tools.graph_tools import graph_get_upcoming_events
        events = await graph_get_upcoming_events(days_ahead)

        if not events:
            return f"📅 No upcoming events in the next {days_ahead} days."

        result = f"📅 {len(events)} upcoming event(s):\n{'─' * 50}\n"
        for i, evt in enumerate(events, 1):
            online = " 🎥" if evt.get("is_online") else ""
            result += (
                f"\n{i}. {evt['subject']}{online}\n"
                f"   Start: {evt['start']}\n"
                f"   End: {evt['end']}\n"
                f"   Location: {evt.get('location') or 'N/A'}\n"
                f"   Organizer: {evt.get('organizer') or 'N/A'}\n"
            )
        return result
    except ValueError as e:
        return f"⚠️ Graph not configured: {e}\nSet GRAPH_CLIENT_ID in .env."
    except Exception as e:
        log_action("CalendarAgent", "get_upcoming_events", f"Error: {e}", status="error")
        return f"Error fetching events: {e}"


async def create_event(
    subject: Annotated[str, "Event title/subject"],
    start_time: Annotated[str, "Start time in ISO format (e.g., 2026-03-20T10:00:00)"],
    end_time: Annotated[str, "End time in ISO format (e.g., 2026-03-20T11:00:00)"],
    location: Annotated[str, "Event location or 'Online'"] = "Online",
    attendees: Annotated[str, "Comma-separated email addresses of attendees"] = "",
) -> str:
    """
    Create a new calendar event. REQUIRES human approval.
    """
    # Validate scheduling policy: no meetings before 9am or after 6pm
    try:
        start_dt = datetime.fromisoformat(start_time)
        if start_dt.hour < 9 or start_dt.hour >= 18:
            return (
                f"⚠️ Scheduling policy violation: No meetings before 9:00 AM or after 6:00 PM. "
                f"Requested start: {start_time}"
            )
    except ValueError:
        return f"Invalid start_time format: {start_time}. Use ISO format."

    details = (
        f"Subject: {subject}\n"
        f"Start: {start_time}\n"
        f"End: {end_time}\n"
        f"Location: {location}\n"
        f"Attendees: {attendees or 'None'}"
    )

    approved, feedback = await _approval.request_approval(
        agent_name="CalendarAgent",
        action="create_event",
        details=details,
    )

    if not approved:
        log_action("CalendarAgent", "create_event", details[:200], "Rejected", status="rejected")
        if feedback:
            return f"Event NOT created. Feedback: {feedback}"
        return "Event NOT created. Human rejected."

    # Create via Microsoft Graph
    try:
        from tools.graph_tools import graph_create_event
        attendee_list = [a.strip() for a in attendees.split(",") if a.strip()] if attendees else None
        result = await graph_create_event(subject, start_time, end_time, location, attendee_list)

        log_action(
            "CalendarAgent",
            "create_event",
            details[:200],
            f"Created: {result.get('id', 'N/A')}",
            approved_by="human",
            status="completed",
        )
        return (
            f"✅ Event created via Microsoft Graph:\n"
            f"  ID: {result.get('id', 'N/A')}\n"
            f"  Subject: {subject}\n"
            f"  Start: {start_time}\n"
            f"  End: {end_time}"
        )
    except ValueError as e:
        log_action("CalendarAgent", "create_event", details[:200], f"Graph not configured: {e}", status="error")
        return f"⚠️ Graph not configured: {e}\nSet GRAPH_CLIENT_ID in .env."
    except Exception as e:
        log_action("CalendarAgent", "create_event", details[:200], f"Error: {e}", status="error")
        return f"Error creating event: {e}"


async def check_conflicts(
    start_time: Annotated[str, "Start time in ISO format"],
    end_time: Annotated[str, "End time in ISO format"],
) -> str:
    """
    Check for scheduling conflicts in the given time window.

    NOTE: Placeholder — replace with Microsoft Graph Calendar API.
    """
    log_action("CalendarAgent", "check_conflicts", f"{start_time} → {end_time}")

    try:
        from tools.graph_tools import graph_check_conflicts
        conflicts = await graph_check_conflicts(start_time, end_time)

        if not conflicts:
            return f"✅ No conflicts found between {start_time} and {end_time}."

        result = f"⚠️ {len(conflicts)} conflict(s) found:\n{'─' * 50}\n"
        for i, c in enumerate(conflicts, 1):
            result += f"  {i}. {c['subject']} ({c['start']} → {c['end']})\n"
        return result
    except ValueError as e:
        return f"⚠️ Graph not configured: {e}\nSet GRAPH_CLIENT_ID in .env."
    except Exception as e:
        log_action("CalendarAgent", "check_conflicts", f"Error: {e}", status="error")
        return f"Error checking conflicts: {e}"


CALENDAR_TOOLS = [get_upcoming_events, create_event, check_conflicts]
