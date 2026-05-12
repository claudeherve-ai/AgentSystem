"""
Microsoft Graph SDK module for email and calendar API integration.

Uses azure-identity DeviceCodeCredential for authentication and
msgraph-sdk for Microsoft Graph API calls (mail, calendar, user).
"""

import os
import sys
import logging
from datetime import datetime, timedelta, timezone

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from azure.identity import DeviceCodeCredential, TokenCachePersistenceOptions
from msgraph import GraphServiceClient
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
from msgraph.generated.models.message import Message
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.event import Event
from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone
from msgraph.generated.models.attendee import Attendee
from msgraph.generated.models.attendee_type import AttendeeType
from msgraph.generated.users.item.calendar_view.calendar_view_request_builder import CalendarViewRequestBuilder

logger = logging.getLogger(__name__)

GRAPH_SCOPES = [
    "Mail.Read",
    "Mail.ReadWrite",
    "Mail.Send",
    "Calendars.Read",
    "Calendars.ReadWrite",
    "User.Read",
]

_graph_client = None
_graph_credential = None


def _to_graph_timestamp(value: datetime) -> str:
    """Render a UTC timestamp in the format expected by Microsoft Graph filters."""
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def get_graph_client() -> GraphServiceClient:
    """Create an authenticated GraphServiceClient using DeviceCodeCredential.

    Reads GRAPH_CLIENT_ID and GRAPH_TENANT_ID from environment variables.
    GRAPH_TENANT_ID defaults to 'consumers' for personal Microsoft accounts.
    """
    global _graph_client, _graph_credential

    if _graph_client is not None:
        return _graph_client

    client_id = os.environ.get("GRAPH_CLIENT_ID")
    if not client_id:
        raise EnvironmentError("GRAPH_CLIENT_ID environment variable is not set.")

    tenant_id = os.environ.get("GRAPH_TENANT_ID", "consumers")
    cache_options = TokenCachePersistenceOptions(name="AgentSystemGraph")

    _graph_credential = DeviceCodeCredential(
        client_id=client_id,
        tenant_id=tenant_id,
        cache_persistence_options=cache_options,
    )

    _graph_client = GraphServiceClient(credentials=_graph_credential, scopes=GRAPH_SCOPES)
    logger.info("GraphServiceClient created (tenant=%s)", tenant_id)
    return _graph_client


async def graph_read_inbox(
    count: int = 10,
    unread_only: bool = True,
    hours_window: int | None = None,
) -> list[dict]:
    """Read messages from the authenticated user's inbox.

    Args:
        count: Maximum number of messages to return.
        unread_only: If True, only return unread messages.

    Returns:
        List of dicts with id, subject, from, from_name, received, preview, is_read.
    """
    try:
        client = get_graph_client()

        filters: list[str] = []
        if unread_only:
            filters.append("isRead eq false")
        if hours_window is not None and hours_window > 0:
            since = datetime.now(timezone.utc) - timedelta(hours=hours_window)
            filters.append(f"receivedDateTime ge {_to_graph_timestamp(since)}")

        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            top=count,
            select=["id", "subject", "from", "receivedDateTime", "bodyPreview", "isRead", "importance"],
            orderby=["receivedDateTime DESC"],
            filter=" and ".join(filters) if filters else None,
        )
        config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )

        messages = await client.me.messages.get(request_configuration=config)

        results = []
        for msg in messages.value or []:
            from_addr = ""
            from_name = ""
            if msg.from_ and msg.from_.email_address:
                from_addr = msg.from_.email_address.address or ""
                from_name = msg.from_.email_address.name or ""

            results.append({
                "id": msg.id,
                "subject": msg.subject or "",
                "from": from_addr,
                "from_name": from_name,
                "received": msg.received_date_time.isoformat() if msg.received_date_time else "",
                "preview": msg.body_preview or "",
                "is_read": msg.is_read or False,
                "importance": getattr(msg.importance, "value", str(msg.importance or "normal")).lower(),
            })

        logger.info("Retrieved %d messages from inbox", len(results))
        return results

    except Exception as e:
        logger.error("Failed to read inbox: %s", e)
        raise


async def graph_send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via Microsoft Graph.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: HTML body content.

    Returns:
        True if the email was sent successfully.
    """
    try:
        client = get_graph_client()

        recipient = Recipient()
        recipient.email_address = EmailAddress()
        recipient.email_address.address = to

        message = Message()
        message.subject = subject
        message.body = ItemBody()
        message.body.content_type = BodyType.Html
        message.body.content = body
        message.to_recipients = [recipient]

        request_body = SendMailPostRequestBody()
        request_body.message = message
        request_body.save_to_sent_items = True

        await client.me.send_mail.post(body=request_body)

        logger.info("Email sent to %s: %s", to, subject)
        return True

    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)
        raise


async def graph_reply_to_email(message_id: str, reply_body: str) -> bool:
    """Reply to a specific email message.

    Args:
        message_id: The Graph message ID to reply to.
        reply_body: HTML body content for the reply.

    Returns:
        True if the reply was sent successfully.
    """
    try:
        client = get_graph_client()

        from msgraph.generated.users.item.messages.item.reply.reply_post_request_body import (
            ReplyPostRequestBody,
        )

        reply_message = Message()
        reply_message.body = ItemBody()
        reply_message.body.content_type = BodyType.Html
        reply_message.body.content = reply_body

        request_body = ReplyPostRequestBody()
        request_body.message = reply_message

        await client.me.messages.by_message_id(message_id).reply.post(body=request_body)

        logger.info("Replied to message %s", message_id)
        return True

    except Exception as e:
        logger.error("Failed to reply to message %s: %s", message_id, e)
        raise


async def graph_create_reply_draft(message_id: str, reply_body: str) -> str:
    """Create a draft reply to a specific email message without sending it.

    The draft is saved to the Outlook Drafts folder so the user can review,
    edit, and send it manually. This is safer than graph_reply_to_email which
    sends immediately.

    Args:
        message_id: The Graph message ID to create a draft reply for.
        reply_body: HTML body content seeded into the draft.

    Returns:
        The draft message ID (or empty string if the ID could not be parsed).
    """
    try:
        client = get_graph_client()

        from msgraph.generated.users.item.messages.item.create_reply.create_reply_post_request_body import (
            CreateReplyPostRequestBody,
        )

        reply_message = Message()
        reply_message.body = ItemBody()
        reply_message.body.content_type = BodyType.Html
        reply_message.body.content = reply_body

        request_body = CreateReplyPostRequestBody()
        request_body.message = reply_message

        result = await client.me.messages.by_message_id(message_id).create_reply.post(
            body=request_body
        )

        draft_id = getattr(result, "id", "") or ""
        logger.info("Created draft reply for message %s (draft=%s)", message_id, draft_id)
        return draft_id

    except Exception as e:
        logger.error("Failed to create draft reply for %s: %s", message_id, e)
        raise


async def graph_get_upcoming_events(days_ahead: int = 7) -> list[dict]:
    """Get upcoming calendar events within the specified number of days.

    Args:
        days_ahead: Number of days ahead to look for events.

    Returns:
        List of dicts with id, subject, start, end, location, organizer, is_online.
    """
    try:
        client = get_graph_client()

        now = datetime.now(timezone.utc)
        end_date = now + timedelta(days=days_ahead)

        query_params = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetQueryParameters(
            start_date_time=now.isoformat(),
            end_date_time=end_date.isoformat(),
            select=["id", "subject", "start", "end", "location", "organizer", "isOnlineMeeting"],
            orderby=["start/dateTime ASC"],
            top=50,
        )
        config = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )

        events = await client.me.calendar_view.get(request_configuration=config)

        results = []
        for event in events.value or []:
            location_name = ""
            if event.location and event.location.display_name:
                location_name = event.location.display_name

            organizer_name = ""
            if event.organizer and event.organizer.email_address:
                organizer_name = event.organizer.email_address.name or ""

            results.append({
                "id": event.id,
                "subject": event.subject or "",
                "start": event.start.date_time if event.start else "",
                "end": event.end.date_time if event.end else "",
                "location": location_name,
                "organizer": organizer_name,
                "is_online": event.is_online_meeting or False,
            })

        logger.info("Retrieved %d upcoming events", len(results))
        return results

    except Exception as e:
        logger.error("Failed to get upcoming events: %s", e)
        raise


async def graph_create_event(
    subject: str,
    start_time: str,
    end_time: str,
    location: str = "",
    attendees: list[str] | None = None,
    body: str = "",
) -> dict:
    """Create a new calendar event.

    Args:
        subject: Event title.
        start_time: ISO 8601 start datetime string.
        end_time: ISO 8601 end datetime string.
        location: Optional location display name.
        attendees: Optional list of attendee email addresses.
        body: Optional HTML body/description.

    Returns:
        Dict with id, subject, start, end of the created event.
    """
    try:
        client = get_graph_client()

        event = Event()
        event.subject = subject

        event.start = DateTimeTimeZone()
        event.start.date_time = start_time
        event.start.time_zone = "UTC"

        event.end = DateTimeTimeZone()
        event.end.date_time = end_time
        event.end.time_zone = "UTC"

        if body:
            event.body = ItemBody()
            event.body.content_type = BodyType.Html
            event.body.content = body

        if location:
            from msgraph.generated.models.location import Location
            event.location = Location()
            event.location.display_name = location

        if attendees:
            event.attendees = []
            for email in attendees:
                attendee = Attendee()
                attendee.email_address = EmailAddress()
                attendee.email_address.address = email
                attendee.type = AttendeeType.Required
                event.attendees.append(attendee)

        created = await client.me.events.post(body=event)

        result = {
            "id": created.id,
            "subject": created.subject or "",
            "start": created.start.date_time if created.start else "",
            "end": created.end.date_time if created.end else "",
        }

        logger.info("Created event: %s", subject)
        return result

    except Exception as e:
        logger.error("Failed to create event '%s': %s", subject, e)
        raise


async def graph_check_conflicts(start_time: str, end_time: str) -> list[dict]:
    """Check for calendar events that conflict with the given time range.

    Args:
        start_time: ISO 8601 start datetime string.
        end_time: ISO 8601 end datetime string.

    Returns:
        List of dicts for each conflicting event (id, subject, start, end).
    """
    try:
        client = get_graph_client()

        query_params = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetQueryParameters(
            start_date_time=start_time,
            end_date_time=end_time,
            select=["id", "subject", "start", "end"],
            orderby=["start/dateTime ASC"],
        )
        config = CalendarViewRequestBuilder.CalendarViewRequestBuilderGetRequestConfiguration(
            query_parameters=query_params,
        )

        events = await client.me.calendar_view.get(request_configuration=config)

        conflicts = []
        for event in events.value or []:
            conflicts.append({
                "id": event.id,
                "subject": event.subject or "",
                "start": event.start.date_time if event.start else "",
                "end": event.end.date_time if event.end else "",
            })

        logger.info("Found %d conflicting events for %s – %s", len(conflicts), start_time, end_time)
        return conflicts

    except Exception as e:
        logger.error("Failed to check conflicts: %s", e)
        raise
