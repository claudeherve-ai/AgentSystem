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
    """Get upcoming calendar events for the next N days."""
    log_action("CalendarAgent", "get_upcoming_events", f"days_ahead={days_ahead}")

    try:
        from tools.graph_tools import graph_get_upcoming_events

        events = await graph_get_upcoming_events(days_ahead)

        # Auth error handling
        if isinstance(events, str):
            if events == "ERR_AUTH_REQUIRED":
                return (
                    "Calendar not linked. Run 'link_account' to authenticate "
                    "— it covers both email and calendar."
                )
            return f"Calendar error: {events}"

        if not events:
            return f"No upcoming events in the next {days_ahead} days."

        result = f"{len(events)} upcoming event(s):\n{'─' * 50}\n"
        for i, evt in enumerate(events, 1):
            result += (
                f"\n{i}. {evt['subject']}\n"
                f"   Start: {evt['start']}\n"
                f"   End: {evt['end']}\n"
                f"   Location: {evt.get('location') or 'N/A'}\n"
            )
        return result
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
    """Create a new calendar event. REQUIRES human approval."""
    try:
        start_dt = datetime.fromisoformat(start_time)
        if start_dt.hour < 9 or start_dt.hour >= 18:
            return (
                f"Scheduling policy violation: No meetings before 9:00 AM "
                f"or after 6:00 PM. Requested start: {start_time}"
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

    try:
        from tools.graph_tools import graph_create_event

        result = await graph_create_event(subject, start_time, end_time, location)
        if isinstance(result, str) and result.startswith("ERR"):
            return (
                "Calendar not linked. Run 'link_account' to authenticate "
                "— it covers both email and calendar."
            )
        return (
            f"Event created via Microsoft Graph:\n"
            f"  Subject: {subject}\n"
            f"  Start: {start_time}\n"
            f"  End: {end_time}"
        )
    except Exception as e:
        log_action("CalendarAgent", "create_event", details[:200], f"Error: {e}", status="error")
        return f"Error creating event: {e}"


async def check_conflicts(
    start_time: Annotated[str, "Start time in ISO format"],
    end_time: Annotated[str, "End time in ISO format"],
) -> str:
    """Check for scheduling conflicts in the given time window."""
    log_action("CalendarAgent", "check_conflicts", f"{start_time} to {end_time}")

    try:
        from tools.graph_tools import graph_get_upcoming_events

        # Use get_upcoming_events to check the window
        events = await graph_get_upcoming_events(days_ahead=365)

        if isinstance(events, str):
            if events == "ERR_AUTH_REQUIRED":
                return "Calendar not linked. Run 'link_account' to authenticate."
            return f"Could not check conflicts: {events}"

        # Filter events in the requested window
        try:
            req_start = datetime.fromisoformat(start_time)
            req_end = datetime.fromisoformat(end_time)
        except ValueError:
            return f"Invalid date format. Use ISO format (e.g., 2026-03-20T10:00:00)."

        conflicts = []
        for evt in events:
            try:
                evt_start_str = evt["start"].split(" ")[0]
                evt_end_str = evt["end"].split(" ")[0]
                evt_start = datetime.fromisoformat(evt_start_str)
                evt_end = datetime.fromisoformat(evt_end_str)

                # Check overlap
                if evt_start < req_end and evt_end > req_start:
                    conflicts.append(evt)
            except (ValueError, KeyError):
                continue

        if not conflicts:
            return f"No conflicts found between {start_time} and {end_time}."

        result = f"{len(conflicts)} conflict(s) found:\n{'─' * 50}\n"
        for i, c in enumerate(conflicts[:5], 1):
            result += f"  {i}. {c['subject']} ({c['start']} to {c['end']})\n"
        return result

    except Exception as e:
        log_action("CalendarAgent", "check_conflicts", f"Error: {e}", status="error")
        return f"Error checking conflicts: {e}"


CALENDAR_TOOLS = [get_upcoming_events, create_event, check_conflicts]
