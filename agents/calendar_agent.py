"""
AgentSystem — Calendar Agent.

Manages calendar operations via Microsoft Graph API.
Supports reading upcoming events, creating events, conflict detection,
and cognitive protection (focus hours, meeting density, optimal slots).
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
                f"   ID: {evt.get('id', 'N/A')}\n"
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

        events = await graph_get_upcoming_events(days_ahead=365)

        if isinstance(events, str):
            if events == "ERR_AUTH_REQUIRED":
                return "Calendar not linked. Run 'link_account' to authenticate."
            return f"Could not check conflicts: {events}"

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


async def update_event(
    event_id: Annotated[str, "The event ID (shown when listing events)"],
    subject: Annotated[str, "New event subject (optional)"] = "",
    start_time: Annotated[str, "New start time in ISO format (optional)"] = "",
    end_time: Annotated[str, "New end time in ISO format (optional)"] = "",
    location: Annotated[str, "New location (optional)"] = "",
) -> str:
    """Update an existing calendar event by ID. Only changed fields are modified. REQUIRES human approval."""
    log_action("CalendarAgent", "update_event", f"event_id={event_id}")

    details = (
        f"Event ID: {event_id}\n"
        f"Subject: {subject or '(unchanged)'}\n"
        f"Start: {start_time or '(unchanged)'}\n"
        f"End: {end_time or '(unchanged)'}\n"
        f"Location: {location or '(unchanged)'}"
    )

    approved, feedback = await _approval.request_approval(
        agent_name="CalendarAgent",
        action="update_event",
        details=details,
    )
    if not approved:
        return f"Event update cancelled: {feedback}" if feedback else "Event update cancelled."

    try:
        from tools.graph_tools import graph_update_event
        result = await graph_update_event(event_id, subject, start_time, end_time, location)
        if isinstance(result, str) and result.startswith("ERR"):
            return "Calendar not linked. Run 'link_account' to authenticate."
        return f"Event updated successfully."
    except Exception as e:
        log_action("CalendarAgent", "update_event", f"Error: {e}", status="error")
        return f"Error updating event: {e}"


async def delete_event(
    event_id: Annotated[str, "The event ID (shown when listing events)"],
) -> str:
    """Delete a calendar event by ID. REQUIRES human approval."""
    log_action("CalendarAgent", "delete_event", f"event_id={event_id}")

    approved, feedback = await _approval.request_approval(
        agent_name="CalendarAgent",
        action="delete_event",
        details=f"Event ID: {event_id}",
    )
    if not approved:
        return f"Event deletion cancelled: {feedback}" if feedback else "Event deletion cancelled."

    try:
        from tools.graph_tools import graph_delete_event
        result = await graph_delete_event(event_id)
        if isinstance(result, str) and result.startswith("ERR"):
            return "Calendar not linked. Run 'link_account' to authenticate."
        return f"Event deleted."
    except Exception as e:
        log_action("CalendarAgent", "delete_event", f"Error: {e}", status="error")
        return f"Error deleting event: {e}"


# ── COGNITIVE PROTECTION TOOLS ───────────────────────────────────────

async def get_focus_hours() -> str:
    """Return the protected focus-hour blocks (09:00-11:30 Pacific).

    These hours are hard-protected — meetings should not be scheduled here
    unless explicitly overridden by the user.
    """
    return (
        "PROTECTED FOCUS HOURS (Pacific Time):\n"
        "  Mon-Fri: 09:00 - 11:30 (deep work block)\n"
        "  Policy: No meetings during focus hours unless user explicitly overrides.\n"
        "  Available meeting windows: 11:30-12:30 (lunch-adjacent), 13:00-18:00 (afternoon).\n"
        "  Note: Cluster meetings in afternoon blocks to preserve morning cognition."
    )


async def check_meeting_density(day: str = "today") -> str:
    """Check meeting density and fragmentation for a given day.

    Returns: total meetings, total meeting hours, fragmentation score,
    and a cognitive load assessment.
    """
    log_action("CalendarAgent", "check_meeting_density", f"day={day}")
    from tools.graph_tools import graph_get_upcoming_events

    try:
        days = 1 if day == "today" else 7
        events = await graph_get_upcoming_events(days_ahead=days)
        if isinstance(events, str):
            if events == "ERR_AUTH_REQUIRED":
                return "Calendar not linked."
            return events
        if not events:
            return f"No meetings found for {day}. Excellent cognitive hygiene."

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        today_events = []
        for evt in events:
            if evt["start"].startswith(today_str):
                today_events.append(evt)

        if not today_events:
            return f"No meetings scheduled for today ({today_str}). Clear calendar — protect this."

        total_meetings = len(today_events)
        total_hours = 0.0
        for evt in today_events:
            try:
                start_str = evt["start"].split(" ")[0]
                end_str = evt["end"].split(" ")[0]
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                total_hours += (end_dt - start_dt).total_seconds() / 3600
            except (ValueError, KeyError):
                pass

        frag_score = min(total_meetings * 10, 100)

        if total_meetings >= 6:
            assessment = "🔴 HIGH COGNITIVE LOAD — Context switching will degrade decision quality."
        elif total_meetings >= 4:
            assessment = "🟡 MODERATE — Acceptable but block off remaining gaps for deep work."
        else:
            assessment = "🟢 GOOD — Low meeting density. Guard your remaining time."

        return (
            f"Meeting Density Report for {today_str}:\n"
            f"  Meetings: {total_meetings}\n"
            f"  Total hours in meetings: {total_hours:.1f}h\n"
            f"  Fragmentation score: {frag_score}/100\n"
            f"  Assessment: {assessment}"
        )
    except Exception as e:
        return f"Error checking meeting density: {e}"


async def suggest_optimal_slot(
    days_ahead: int = 5,
    duration_minutes: int = 30,
) -> str:
    """Find the least-disruptive meeting slot in the coming days.

    Prefers afternoon slots, avoids focus hours (09:00-11:30 Pacific),
    and avoids existing meetings.
    """
    log_action("CalendarAgent", "suggest_optimal_slot", f"days={days_ahead}, dur={duration_minutes}")
    from tools.graph_tools import graph_get_upcoming_events

    try:
        events = await graph_get_upcoming_events(days_ahead=days_ahead)
        if isinstance(events, str):
            if events == "ERR_AUTH_REQUIRED":
                return "Calendar not linked."
            return events

        occupied = {}
        for i in range(days_ahead):
            day = (datetime.now(timezone.utc) + timedelta(days=i)).strftime("%Y-%m-%d")
            occupied[day] = []

        for evt in events if not isinstance(events, str) else []:
            try:
                day_key = evt["start"][:10]
                if day_key in occupied:
                    start_s = evt["start"].split(" ")[0]
                    end_s = evt["end"].split(" ")[0]
                    occupied[day_key].append((start_s, end_s))
            except (ValueError, KeyError):
                continue

        best = None
        for day_key, booked in occupied.items():
            hour = 13.0
            while hour + duration_minutes / 60 <= 17:
                slot_start = f"{day_key}T{int(hour):02d}:00:00"
                slot_end = f"{day_key}T{int(hour + duration_minutes / 60):02d}:{duration_minutes % 60:02d}:00"

                conflict = False
                for bs, be in booked:
                    if slot_start < be and slot_end > bs:
                        conflict = True
                        break

                if not conflict:
                    best = {
                        "day": day_key,
                        "start": slot_start,
                        "end": slot_end,
                        "zone": "afternoon",
                    }
                    break
                hour += 0.5
            if best:
                break

        if best:
            return (
                f"Optimal meeting slot found:\n"
                f"  Day: {best['day']}\n"
                f"  Start: {best['start']}\n"
                f"  End: {best['end']}\n"
                f"  Zone: {best['zone']} (protected from focus hours)"
            )
        return "No clear slots found in the next few days. Consider rescheduling or shortening an existing meeting."
    except Exception as e:
        return f"Error finding optimal slot: {e}"


async def generate_pre_meeting_brief(event_id: str) -> str:
    """Generate a pre-meeting brief for a specific calendar event.

    Includes: attendees, objective suggestions, preparation checklist.
    """
    log_action("CalendarAgent", "generate_pre_meeting_brief", f"event_id={event_id}")
    from tools.graph_tools import graph_get_upcoming_events

    try:
        events = await graph_get_upcoming_events(days_ahead=14)
        if isinstance(events, str):
            return "Calendar not linked."

        target = None
        for evt in events if not isinstance(events, str) else []:
            if evt.get("id") == event_id:
                target = evt
                break

        if not target:
            return f"Event {event_id} not found in the next 14 days."

        return (
            f"PRE-MEETING BRIEF\n"
            f"{'─' * 40}\n"
            f"Meeting: {target['subject']}\n"
            f"When: {target['start']}\n"
            f"Location: {target.get('location', 'N/A')}\n\n"
            f"TO PREPARE:\n"
            f"  1. Review prior decisions and open questions for this topic.\n"
            f"  2. Check recent email threads from attendees.\n"
            f"  3. Identify your desired outcome for this meeting.\n"
            f"  4. Prepare any materials or questions you want to raise.\n\n"
            f"Suggested question: 'Should this meeting exist?'\n"
            f"If objective is unclear or could be async, consider declining."
        )
    except Exception as e:
        return f"Error generating brief: {e}"


CALENDAR_TOOLS = [
    get_upcoming_events,
    create_event,
    update_event,
    delete_event,
    check_conflicts,
    get_focus_hours,
    check_meeting_density,
    suggest_optimal_slot,
    generate_pre_meeting_brief,
]
