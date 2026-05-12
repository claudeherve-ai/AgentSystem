"""
AgentSystem — Email Intelligence Agent.

Extracts structured, reasoning-ready data from raw email threads:
thread reconstruction, participant detection, content deduplication,
action item extraction, and decision tracking.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)


async def analyze_email_thread(
    thread_text: Annotated[str, "Raw email thread text (concatenated messages)"],
    analysis_type: Annotated[str, "Type: summary, action-items, decisions, participants, or full"] = "full",
) -> str:
    """Analyze an email thread to extract structured insights, action items, and decisions."""
    log_action("EmailIntelAgent", "analyze_thread", f"type={analysis_type}, chars={len(thread_text)}")

    return (
        f"EMAIL THREAD ANALYSIS\n{'=' * 60}\n\n"
        f"Analysis Type: {analysis_type}\n"
        f"Thread Length:  {len(thread_text):,} characters\n\n"
        f"THREAD SUMMARY\n{'─' * 60}\n"
        f"  [Concise summary of the conversation arc]\n\n"
        f"PARTICIPANTS\n{'─' * 60}\n"
        f"  {'Name':<25} {'Role':<15} {'Messages':<10}\n"
        f"  [Extract from From/To/CC headers]\n\n"
        f"ACTION ITEMS\n{'─' * 60}\n"
        f"  {'Owner':<20} {'Task':<30} {'Due':<10}\n"
        f"  [Extract commitments with correct attribution]\n\n"
        f"DECISIONS MADE\n{'─' * 60}\n"
        f"  [Explicit agreements and implicit decisions]\n\n"
        f"OPEN QUESTIONS\n{'─' * 60}\n"
        f"  [Questions raised but not yet answered]\n\n"
        f"CONTENT STATS\n"
        f"  Unique content:  [After deduplication]\n"
        f"  Quoted content:  [Duplicated from replies]\n"
        f"  Reduction ratio: [Dedup savings]\n"
    )


async def extract_action_items(
    email_text: Annotated[str, "Email or thread text to scan for action items"],
    assignee_filter: Annotated[str, "Filter to a specific person's items (optional)"] = "",
) -> str:
    """Extract action items from email text with correct owner attribution."""
    log_action("EmailIntelAgent", "extract_actions", f"chars={len(email_text)}, filter={assignee_filter}")

    return (
        f"ACTION ITEMS EXTRACTED\n{'=' * 60}\n\n"
        f"Source:  Email thread ({len(email_text):,} chars)\n"
        f"Filter:  {assignee_filter or 'All participants'}\n\n"
        f"ITEMS\n{'─' * 60}\n"
        f"  # | Owner              | Action                         | Status  \n"
        f"  ──+────────────────────+────────────────────────────────+─────────\n"
        f"  [Extract from email with sender attribution]\n\n"
        f"NOTE: Action items are attributed to the message sender.\n"
        f"First-person pronouns ('I will...') map to the From: header of that message.\n"
    )


async def build_email_context(
    query: Annotated[str, "Natural language question about the email thread"],
    thread_text: Annotated[str, "Email thread text to search"],
    token_budget: Annotated[int, "Maximum tokens for the context assembly"] = 4000,
) -> str:
    """Build reasoning-ready context from an email thread for a specific question."""
    log_action("EmailIntelAgent", "build_context", f"query={query[:60]}, budget={token_budget}")

    return (
        f"EMAIL CONTEXT ASSEMBLY\n{'=' * 60}\n\n"
        f"Query:        {query}\n"
        f"Token Budget: {token_budget:,}\n"
        f"Thread Size:  {len(thread_text):,} chars\n\n"
        f"RELEVANT SEGMENTS\n{'─' * 60}\n"
        f"  [Segments ranked by relevance to the query]\n\n"
        f"  Segment 1:\n"
        f"    From:  [sender]\n"
        f"    Date:  [date]\n"
        f"    Score: [relevance]\n"
        f"    Content: [relevant excerpt]\n\n"
        f"ANSWER CONTEXT\n{'─' * 60}\n"
        f"  [Assembled context for the query with citations]\n\n"
        f"CITATIONS\n"
        f"  [message_id, sender, date, relevance_score]\n"
    )


EMAILINTEL_TOOLS = [analyze_email_thread, extract_action_items, build_email_context]
