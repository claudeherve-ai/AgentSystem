"""
AgentSystem — Email Agent.

Manages email operations via Microsoft Graph API.
Auth tools: link_account/relink_account (start auth), finish_link (complete auth),
sign_out (logout). Email tools: read, search, draft, send, thread.
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from guardrails import Guardrails
from guardrails.approval import HumanApproval

logger = logging.getLogger(__name__)
_guardrails = Guardrails()
_approval = HumanApproval()


# ── AUTH TOOLS ───────────────────────────────────────────────────────

async def link_account() -> str:
    """Run this to get the Microsoft Device Code for linking your Email and Calendar.
    Starts a background poller so you don't have to wait for the token."""
    from tools.graph_tools import graph_login
    return await graph_login()


async def relink_account() -> str:
    """Run this tool whenever Microsoft connection is missing or failing.
    Initiates the device-code login flow — gives you a URL and code to enter."""
    from tools.graph_tools import graph_login
    return await graph_login()


async def finish_link() -> str:
    """Call this AFTER you have completed the browser login.
    Checks whether the background poller has acquired the token. Instant — no wait."""
    from tools.graph_tools import graph_finish_login
    return await graph_finish_login()


async def sign_out() -> str:
    """Remove cached Microsoft credentials so the next request re-authenticates."""
    from tools.graph_tools import graph_logout
    return await graph_logout()


# ── READ / CHECK INBOX ───────────────────────────────────────────────

async def read_inbox(count: int = 10) -> str:
    """Read the latest unread emails. Returns instructions if auth is missing."""
    log_action("EmailAgent", "read_inbox", f"count={count}")
    from tools.graph_tools import graph_read_inbox
    res = await graph_read_inbox(count=count, unread_only=True)
    if res == "ERR_AUTH_REQUIRED":
        return "Account not linked. Run 'link_account' to authenticate."
    if isinstance(res, str) and res.startswith("ERR"):
        return f"Session expired. Run 'link_account'."
    if isinstance(res, str):
        return res
    if not res:
        return "Mailbox clear — no unread messages."
    lines = ["Latest unread emails:"]
    for e in res:
        status = "[UNREAD]" if e["is_unread"] else "[READ]"
        lines.append(f"- {status} {e['subject']} (From: {e['from_name']})")
    return "\n".join(lines)


async def check_inbox(count: int = 10, unread_only: bool = True) -> str:
    """Reads latest unread emails. Convenience alias for read_inbox."""
    return await read_inbox(count=count)


# ── SEARCH INBOX ─────────────────────────────────────────────────────

async def search_inbox(query: str, count: int = 20) -> str:
    """Search inbox for emails matching a keyword query.

    Searches across subject, sender, and body preview.
    Use this to find specific threads or emails by topic.
    """
    log_action("EmailAgent", "search_inbox", f"query={query}, count={count}")
    try:
        from tools.graph_tools import graph_search_messages
        results = await graph_search_messages(query, count)
        if results == "ERR_AUTH_REQUIRED":
            return "Account not linked. Run 'link_account' to authenticate."
        if isinstance(results, str):
            return results
        if not results:
            return f"No emails found matching '{query}'."
        lines = [f"Search results for '{query}':"]
        for e in results:
            lines.append(
                f"- [{e['id'][:8]}...] {e['subject']} "
                f"(From: {e['from_name']}, {e.get('received_date', 'unknown date')})"
            )
        return "\n".join(lines)
    except Exception as e:
        log_action("EmailAgent", "search_inbox", f"Error: {e}", status="error")
        return f"Error searching inbox: {e}"


# ── GET THREAD ───────────────────────────────────────────────────────

async def get_thread(message_id: str) -> str:
    """Fetch the full conversation thread for a given message ID.

    Returns all messages in the thread with sender, date, and body preview.
    The message_id comes from read_inbox or search_inbox results.
    """
    log_action("EmailAgent", "get_thread", f"message_id={message_id}")
    try:
        from tools.graph_tools import graph_get_thread
        thread = await graph_get_thread(message_id)
        if thread == "ERR_AUTH_REQUIRED":
            return "Account not linked. Run 'link_account' to authenticate."
        if isinstance(thread, str):
            return thread
        if not thread:
            return f"Thread not found for message {message_id}."
        lines = [f"Conversation thread ({len(thread)} messages):", "─" * 50]
        for i, msg in enumerate(thread, 1):
            lines.append(
                f"\n{i}. From: {msg.get('from_name', 'Unknown')} "
                f"({msg.get('from_email', '')})\n"
                f"   Date: {msg.get('received_date', 'Unknown')}\n"
                f"   Subject: {msg.get('subject', '')}\n"
                f"   Preview: {msg.get('preview', '')}"
            )
        return "\n".join(lines)
    except Exception as e:
        log_action("EmailAgent", "get_thread", f"Error: {e}", status="error")
        return f"Error fetching thread: {e}"


# ── DRAFT REPLY ──────────────────────────────────────────────────────

async def draft_reply(message_id: str, body: str) -> str:
    """Create a draft reply to a specific email.

    The draft is saved to the Drafts folder in Outlook — it is NOT sent.
    You can review and send it manually from Outlook.

    Args:
        message_id: The ID of the email to reply to (from read_inbox/search_inbox)
        body: The full body text of your reply
    """
    log_action("EmailAgent", "draft_reply", f"message_id={message_id}")
    try:
        from tools.graph_tools import graph_create_draft_reply
        result = await graph_create_draft_reply(message_id, body)
        if result == "ERR_AUTH_REQUIRED":
            return "Account not linked. Run 'link_account' to authenticate."
        if isinstance(result, str) and result.startswith("ERR"):
            return f"Draft error: {result}"
        return (
            f"Draft reply saved to Outlook Drafts folder.\n"
            f"  Reply to: {message_id}\n"
            f"  Status: Draft saved (NOT sent)\n"
            f"  Review and send manually from Outlook."
        )
    except Exception as e:
        log_action("EmailAgent", "draft_reply", f"Error: {e}", status="error")
        return f"Error creating draft: {e}"


# ── SEND EMAIL ───────────────────────────────────────────────────────

async def send_email(
    to: str,
    subject: str,
    body: str,
    cc: str = "",
) -> str:
    """Draft and send an email via Microsoft Graph. REQUIRES human approval.

    Args:
        to: Recipient email address
        subject: Email subject line
        body: Full email body (plain text, supports line breaks)
        cc: Optional CC recipient(s), comma-separated
    """
    log_action("EmailAgent", "send_email", f"to={to}, subject={subject[:80]}")

    details = (
        f"To: {to}\n"
        f"CC: {cc or 'None'}\n"
        f"Subject: {subject}\n"
        f"Body: {body[:200]}{'...' if len(body) > 200 else ''}"
    )

    approved, feedback = await _approval.request_approval(
        agent_name="EmailAgent",
        action="send_email",
        details=details,
    )
    if not approved:
        log_action("EmailAgent", "send_email", "Rejected", status="rejected")
        return f"Send cancelled: {feedback}" if feedback else "Send cancelled."

    try:
        from tools.graph_tools import graph_send_mail
        result = await graph_send_mail(to, subject, body, cc)
        if result == "ERR_AUTH_REQUIRED":
            return "Account not linked. Run 'link_account' to authenticate."
        if isinstance(result, str) and result.startswith("ERR"):
            return f"Send error: {result}"
        return (
            f"Email sent via Microsoft Graph.\n"
            f"  To: {to}\n"
            f"  Subject: {subject}\n"
            f"  Status: Sent"
        )
    except Exception as e:
        log_action("EmailAgent", "send_email", f"Error: {e}", status="error")
        return f"Error sending email: {e}"


# ── TOOL EXPORT ──────────────────────────────────────────────────────

EMAIL_TOOLS = [
    link_account,
    relink_account,
    finish_link,
    sign_out,
    read_inbox,
    check_inbox,
    search_inbox,
    get_thread,
    draft_reply,
    send_email,
]
