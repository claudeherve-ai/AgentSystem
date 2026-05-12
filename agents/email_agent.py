"""
AgentSystem — Email Agent.

Manages email operations via Microsoft Graph API.
Supports reading inbox, drafting replies, and sending emails (with human approval).
"""

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails import ApprovalRequired, Guardrails
from guardrails.approval import HumanApproval
from tools.audit import log_action

logger = logging.getLogger(__name__)

# --- Tool functions that the email agent can call ---

_guardrails = Guardrails()
_approval = HumanApproval()


async def read_inbox(
    count: Annotated[int, "Number of recent emails to fetch"] = 10,
    unread_only: Annotated[bool, "Only fetch unread emails"] = True,
) -> str:
    """
    Read recent emails from the inbox via Microsoft Graph.
    Falls back to placeholder if Graph is not configured.
    """
    log_action("EmailAgent", "read_inbox", f"count={count}, unread_only={unread_only}")

    try:
        from tools.graph_tools import graph_read_inbox
        emails = await graph_read_inbox(count, unread_only)

        if not emails:
            return "📭 No unread emails in your inbox."

        result = f"📬 {len(emails)} email(s):\n{'─' * 50}\n"
        for i, email in enumerate(emails, 1):
            result += (
                f"\n{i}. From: {email['from_name']} <{email['from']}>\n"
                f"   Subject: {email['subject']}\n"
                f"   Received: {email['received']}\n"
                f"   Preview: {email['preview'][:100]}...\n"
            )
        return result
    except ValueError as e:
        return f"⚠️ Graph not configured: {e}\nSet GRAPH_CLIENT_ID in .env."
    except Exception as e:
        log_action("EmailAgent", "read_inbox", f"Error: {e}", status="error")
        return f"Error reading inbox: {e}"


async def draft_reply(
    original_subject: Annotated[str, "Subject of the email being replied to"],
    original_sender: Annotated[str, "Email address of the original sender"],
    reply_body: Annotated[str, "The reply message body"],
) -> str:
    """
    Draft a reply to an email. Does NOT send — just prepares the draft.
    """
    if not _guardrails.check_content_length(reply_body):
        return "Error: Reply is too long. Please shorten it."

    draft = (
        f"📧 DRAFT REPLY\n"
        f"To: {original_sender}\n"
        f"Subject: Re: {original_subject}\n"
        f"{'─' * 40}\n"
        f"{reply_body}\n"
        f"{'─' * 40}\n"
        f"Status: DRAFT (not sent)"
    )

    log_action(
        "EmailAgent",
        "draft_reply",
        f"Re: {original_subject} → {original_sender}",
        f"Draft: {reply_body[:100]}...",
        status="drafted",
    )

    return draft


async def send_email(
    to: Annotated[str, "Recipient email address"],
    subject: Annotated[str, "Email subject line"],
    body: Annotated[str, "Email body text"],
) -> str:
    """
    Send an email. REQUIRES human approval before sending.
    """
    # Enforce rate limits
    try:
        _guardrails.check_email_rate()
    except Exception as e:
        return f"Rate limit exceeded: {e}"

    # Content length check
    if not _guardrails.check_content_length(body):
        return "Error: Email body is too long. Please shorten it."

    # Request human approval
    approved, feedback = await _approval.request_approval(
        agent_name="EmailAgent",
        action="send_email",
        details=f"To: {to}\nSubject: {subject}\n\n{body}",
    )

    if not approved:
        if feedback:
            log_action("EmailAgent", "send_email", f"To: {to}", f"Rejected with feedback: {feedback}", status="rejected")
            return f"Email NOT sent. Human feedback: {feedback}"
        log_action("EmailAgent", "send_email", f"To: {to}", "Rejected", status="rejected")
        return "Email NOT sent. Human rejected the action."

    # Send via Microsoft Graph
    try:
        from tools.graph_tools import graph_send_email
        await graph_send_email(to, subject, body)

        log_action(
            "EmailAgent",
            "send_email",
            f"To: {to}, Subject: {subject}",
            "Sent via Microsoft Graph",
            approved_by="human",
            status="completed",
        )
        return f"✅ Email sent successfully via Microsoft Graph:\n  To: {to}\n  Subject: {subject}"
    except ValueError as e:
        log_action("EmailAgent", "send_email", f"To: {to}", f"Graph not configured: {e}", status="error")
        return f"⚠️ Graph not configured: {e}\nSet GRAPH_CLIENT_ID in .env."
    except Exception as e:
        log_action("EmailAgent", "send_email", f"To: {to}", f"Error: {e}", status="error")
        return f"Error sending email: {e}"


# List of tools to register with the email agent
EMAIL_TOOLS = [read_inbox, draft_reply, send_email]
