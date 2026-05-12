"""
AgentSystem — Notification Gateway.

Polls and listens for inbound events (email, calendar, webhooks)
and routes them to the orchestrator for processing.

Supports:
- Periodic polling (email inbox, calendar)
- Webhook receiver (for Microsoft Graph push notifications)
- Scheduled tasks (recurring checks)
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_system_config
from tools.audit import log_action
from tools.graph_tools import graph_read_inbox
from tools.memory_tools import MEMORY_STORE

logger = logging.getLogger(__name__)
NOTIFICATION_STATE_PATH = Path(__file__).resolve().parent.parent / "memory" / "notification_state.json"


class Event:
    """Represents an inbound event to be processed by the orchestrator."""

    def __init__(
        self,
        source: str,
        event_type: str,
        summary: str,
        data: Optional[dict[str, Any]] = None,
        priority: str = "normal",
    ):
        self.source = source          # e.g., "email", "calendar", "webhook"
        self.event_type = event_type  # e.g., "new_email", "upcoming_meeting"
        self.summary = summary        # Human-readable summary
        self.data = data or {}        # Raw event data
        self.priority = priority      # "low", "normal", "high", "urgent"
        self.timestamp = datetime.now(timezone.utc)

    def to_prompt(self) -> str:
        """Convert event to a natural language prompt for the orchestrator."""
        priority_prefix = ""
        if self.priority == "urgent":
            priority_prefix = "🚨 URGENT: "
        elif self.priority == "high":
            priority_prefix = "⚡ HIGH PRIORITY: "

        return (
            f"{priority_prefix}[{self.source.upper()}] {self.event_type}: {self.summary}"
        )

    def __repr__(self) -> str:
        return f"Event({self.source}/{self.event_type}: {self.summary[:50]})"


class NotificationGateway:
    """
    Central notification gateway that collects events from multiple sources
    and feeds them to the orchestrator.
    """

    def __init__(self):
        self._config = get_system_config()
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()
        self._pollers: list[dict[str, Any]] = []
        self._running = False
        self._tasks: list[asyncio.Task] = []

    def register_poller(
        self,
        name: str,
        poll_fn: Callable[[], Coroutine[Any, Any, list[Event]]],
        interval_seconds: Optional[int] = None,
    ):
        """
        Register a polling function that periodically checks for new events.

        Args:
            name: Descriptive name (e.g., "email_poller")
            poll_fn: Async function that returns a list of Events
            interval_seconds: Override default polling interval
        """
        self._pollers.append({
            "name": name,
            "fn": poll_fn,
            "interval": interval_seconds or self._config.polling_interval_seconds,
        })
        logger.info(f"Registered poller: {name} (every {interval_seconds or self._config.polling_interval_seconds}s)")

    async def _run_poller(self, poller: dict[str, Any]):
        """Run a single poller in a loop."""
        name = poller["name"]
        fn = poller["fn"]
        interval = poller["interval"]

        while self._running:
            try:
                events = await fn()
                for event in events:
                    await self._event_queue.put(event)
                    logger.info(f"Poller [{name}] queued event: {event}")
                    log_action(
                        "NotificationGateway",
                        "event_queued",
                        f"source={event.source}, type={event.event_type}",
                        event.summary[:200],
                    )
            except Exception as e:
                logger.error(f"Poller [{name}] error: {e}", exc_info=True)
                log_action(
                    "NotificationGateway",
                    "poller_error",
                    name,
                    str(e),
                    status="error",
                )

            await asyncio.sleep(interval)

    async def get_next_event(self, timeout: float = 30.0) -> Optional[Event]:
        """
        Wait for the next event from the queue.
        Returns None if timeout expires with no events.
        """
        try:
            return await asyncio.wait_for(self._event_queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def start(self):
        """Start all registered pollers."""
        self._running = True
        for poller in self._pollers:
            task = asyncio.create_task(self._run_poller(poller))
            self._tasks.append(task)
        logger.info(f"Notification gateway started with {len(self._pollers)} pollers")
        log_action("NotificationGateway", "start", f"{len(self._pollers)} pollers")

    async def stop(self):
        """Stop all pollers gracefully."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        logger.info("Notification gateway stopped")
        log_action("NotificationGateway", "stop", "All pollers stopped")

    @property
    def queue_size(self) -> int:
        return self._event_queue.qsize()

    @property
    def is_running(self) -> bool:
        return self._running


def _load_notification_state() -> dict[str, list[str]]:
    if not NOTIFICATION_STATE_PATH.exists():
        return {}
    try:
        return json.loads(NOTIFICATION_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_notification_state(payload: dict[str, list[str]]) -> None:
    NOTIFICATION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    NOTIFICATION_STATE_PATH.write_text(
        json.dumps(payload, indent=2),
        encoding="utf-8",
    )


def _important_contact_markers() -> set[str]:
    markers: set[str] = set()
    for category in ("contact", "family"):
        for row in MEMORY_STORE.list_memories(category=category, limit=50):
            markers.add(row["key"].replace("_", " ").lower())
            markers.add(" ".join(row["value"].split()).lower())
    return {marker for marker in markers if len(marker) >= 4}


def _is_important_email(email: dict, important_contacts: set[str]) -> tuple[bool, str]:
    text = " ".join(
        [
            str(email.get("subject", "")),
            str(email.get("preview", "")),
            str(email.get("from_name", "")),
            str(email.get("from", "")),
        ]
    ).lower()

    if str(email.get("importance", "normal")).lower() == "high":
        return True, "marked high importance"

    if any(marker in text for marker in important_contacts):
        return True, "important contact"

    for keyword in ("urgent", "asap", "action required", "approval", "review", "deadline", "issue", "blocked"):
        if keyword in text:
            return True, f"contains '{keyword}'"

    return False, ""


# --- Built-in pollers ---

async def poll_email_inbox() -> list[Event]:
    """
    Poll for unread emails that are likely important.
    """
    try:
        emails = await graph_read_inbox(count=15, unread_only=True, hours_window=2)
    except Exception as exc:
        logger.debug("Email poller skipped: %s", exc)
        return []

    state = _load_notification_state()
    seen_ids = set(state.get("important_email_ids", []))
    important_contacts = _important_contact_markers()
    events: list[Event] = []

    for email in emails:
        message_id = str(email.get("id", "")).strip()
        if not message_id or message_id in seen_ids:
            continue

        is_important, reason = _is_important_email(email, important_contacts)
        if not is_important:
            continue

        sender = email.get("from_name") or email.get("from") or "Unknown sender"
        subject = email.get("subject") or "No subject"
        priority = "urgent" if "urgent" in reason else "high"
        events.append(
            Event(
                "email",
                "important_unread_email",
                f"{sender} — {subject} ({reason})",
                data={"message_id": message_id, "subject": subject, "from": sender},
                priority=priority,
            )
        )
        seen_ids.add(message_id)

    if events:
        state["important_email_ids"] = list(seen_ids)[-200:]
        _save_notification_state(state)

    logger.debug("Email poller: queued %d important email event(s)", len(events))
    return events


async def poll_calendar_upcoming() -> list[Event]:
    """
    Poll for upcoming calendar events that need attention.
    E.g., meetings starting in the next 15 minutes.
    """
    # TODO: Implement with Microsoft Graph:
    # GET /me/calendarView?startDateTime={now}&endDateTime={now+15min}

    logger.debug("Calendar poller: checking upcoming events (placeholder)")
    return []  # Return empty until Graph is connected


def create_default_gateway() -> NotificationGateway:
    """Create a gateway with the default set of pollers."""
    gw = NotificationGateway()
    gw.register_poller("email_inbox", poll_email_inbox, interval_seconds=7200)
    gw.register_poller("calendar_upcoming", poll_calendar_upcoming, interval_seconds=60)
    # Proactive time-based scheduler: morning briefing, end-of-day review,
    # and pre-meeting alerts. Imported lazily to avoid a circular import.
    try:
        from tools.scheduler import register_scheduler_pollers
        register_scheduler_pollers(gw)
    except Exception as exc:
        logger.warning("Scheduler pollers not registered: %s", exc)
    return gw
