"""
AgentSystem — Draft reply generator for inbox triage.

Scans the inbox for important unread emails, generates professional draft
replies using the same template/memory signals as the daily briefing, and
optionally saves them to the user's Outlook Drafts folder so they can be
reviewed and sent manually. Never sends email directly — drafts only.
"""

import logging
from datetime import datetime, timezone
from typing import Annotated

from tools.audit import log_action
from tools.daily_briefing import (
    _build_email_summary,
    _clean_text,
    _draft_response,
    _important_contact_markers,
    _memory_value,
    _parse_datetime,
    _score_email_importance,
)
from tools.graph_tools import (
    graph_create_reply_draft,
    graph_read_inbox,
)

logger = logging.getLogger(__name__)


def _as_html(body: str) -> str:
    """Convert the plain-text draft into minimal HTML for Outlook."""
    if not body:
        return ""
    escaped = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    paragraphs = [
        f"<p>{segment.strip().replace(chr(10), '<br />')}</p>"
        for segment in escaped.split("\n\n")
        if segment.strip()
    ]
    return "".join(paragraphs) or f"<p>{escaped}</p>"


async def generate_draft_replies(
    hours_window: Annotated[
        int, "How many recent hours of unread mail to scan for draftable messages"
    ] = 24,
    max_drafts: Annotated[int, "Maximum number of draft replies to produce"] = 5,
    save_to_outlook: Annotated[
        bool, "When true, also save each draft to the Outlook Drafts folder"
    ] = True,
) -> str:
    """Generate draft replies for important unread emails.

    Pulls important unread messages from the inbox, produces a template-based
    professional reply seeded with memory signals (user name, tone, voice),
    and optionally saves each draft to the Outlook Drafts folder via Microsoft
    Graph. Returns a human-readable summary of what was drafted.
    """
    now = datetime.now(timezone.utc)
    contact_markers = _important_contact_markers()
    user_name = _memory_value("name", "Claude")

    try:
        emails = await graph_read_inbox(
            count=30,
            unread_only=True,
            hours_window=hours_window,
        )
    except Exception as exc:
        logger.warning("Draft replies email lookup failed: %s", exc)
        log_action(
            "DraftReplies",
            "generate_draft_replies",
            f"hours_window={hours_window}",
            f"email lookup failed: {exc}",
            status="error",
        )
        return f"✏️  DRAFT REPLIES\n- Email unavailable: {exc}"

    scored: list[tuple[int, list[str], dict]] = []
    for email in emails:
        score, reasons = _score_email_importance(email, contact_markers, now, hours_window)
        if score >= 2:
            scored.append((score, reasons, email))

    scored.sort(
        key=lambda item: (
            -item[0],
            _parse_datetime(item[2].get("received", ""))
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
    )

    lines: list[str] = [
        "✏️  DRAFT REPLIES",
        f"Generated: {now.isoformat()}",
        f"Window: last {hours_window} hours | Author voice: {user_name}",
        "",
    ]

    if not scored:
        lines.append("- No important unread emails found in the window. Inbox is clear.")
        log_action(
            "DraftReplies",
            "generate_draft_replies",
            f"hours_window={hours_window}",
            "no candidates",
            status="completed",
        )
        return "\n".join(lines)

    saved_count = 0
    errors: list[str] = []

    for index, (score, reasons, email) in enumerate(scored[:max_drafts], start=1):
        message_id = str(email.get("id", "")).strip()
        sender = _clean_text(email.get("from_name", "")) or email.get("from", "Unknown sender")
        subject = _clean_text(email.get("subject", "No subject"))
        draft_body = _draft_response(email)

        lines.extend(
            [
                f"- Draft {index}: {sender}",
                f"  Subject: {subject}",
                f"  Importance score: {score} ({', '.join(reasons) or 'flagged'})",
                f"  Context: {_build_email_summary(email)}",
                "  Proposed reply:",
                *[f"    {line}" for line in draft_body.splitlines()],
            ]
        )

        if save_to_outlook and message_id:
            try:
                draft_id = await graph_create_reply_draft(message_id, _as_html(draft_body))
                if draft_id:
                    lines.append(f"  ✅ Saved to Outlook Drafts (draft id: {draft_id})")
                else:
                    lines.append("  ✅ Saved to Outlook Drafts")
                saved_count += 1
            except Exception as exc:
                logger.warning("Failed to save draft for message %s: %s", message_id, exc)
                errors.append(f"{sender}: {exc}")
                lines.append(f"  ⚠️  Could not save draft to Outlook: {exc}")
        elif save_to_outlook and not message_id:
            lines.append("  ⚠️  Missing message id — draft shown inline only.")

        lines.append("")

    lines.append(
        f"Summary: {len(scored[:max_drafts])} draft(s) generated"
        + (f", {saved_count} saved to Outlook" if save_to_outlook else "")
        + (f", {len(errors)} save error(s)" if errors else "")
        + "."
    )
    lines.append(
        "Review each draft in your Outlook Drafts folder, edit as needed, and send manually."
    )

    log_action(
        "DraftReplies",
        "generate_draft_replies",
        f"hours_window={hours_window}, max_drafts={max_drafts}, save={save_to_outlook}",
        f"drafted={len(scored[:max_drafts])}, saved={saved_count}, errors={len(errors)}",
        status="completed",
    )

    return "\n".join(lines)


DRAFT_REPLY_TOOLS = [generate_draft_replies]
