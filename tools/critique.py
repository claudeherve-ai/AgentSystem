"""
Critique / rubber-duck tool — review a draft response and surface improvements.

This is the "second pair of eyes" pattern: take a question + a draft answer
and return a structured critique with severity-ranked findings. The orchestrator
can call it on its own draft before responding to the user when stakes are high.

Implementation note: this tool builds an ephemeral specialist agent on demand
using the same model client the orchestrator uses, so it inherits Azure config,
timeouts, etc. It does NOT register as a long-lived agent — it's a tool.
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from pydantic import Field

from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient

from .audit import audit_log

logger = logging.getLogger(__name__)

_REVIEWER_NAME = "RubberDuckReviewer"
_REVIEWER_INSTRUCTIONS = (
    "You are a senior principal engineer doing rubber-duck review. "
    "Given a USER QUESTION and a DRAFT RESPONSE, do NOT rewrite the answer. "
    "Instead, return a critique in this exact Markdown format:\n\n"
    "## Verdict\n"
    "(one of: Ship it / Ship with minor fixes / Needs material revision / Reject)\n\n"
    "## Critical findings\n"
    "- (only items that would cause a wrong answer, customer-impacting risk, or factual error)\n\n"
    "## Important findings\n"
    "- (items that would meaningfully improve correctness, clarity, or completeness)\n\n"
    "## Nice-to-haves\n"
    "- (style / phrasing only)\n\n"
    "## Confidence\n"
    "(0-1 score with one-line rationale)\n\n"
    "Be concise. Skip empty sections. Never invent issues to look thorough."
)

_reviewer_client: Optional[OpenAIChatCompletionClient] = None
_reviewer_agent: Optional[Agent] = None


def _get_reviewer() -> Agent:
    global _reviewer_client, _reviewer_agent
    if _reviewer_client is None:
        # Lazy import to avoid circular dependency: orchestrator imports this module.
        from agents.orchestrator import create_model_client

        _reviewer_client = create_model_client()
    if _reviewer_agent is None:
        _reviewer_agent = Agent(
            name=_REVIEWER_NAME,
            description="Rubber-duck reviewer that critiques draft responses.",
            client=_reviewer_client,
            instructions=_REVIEWER_INSTRUCTIONS,
        )
    return _reviewer_agent


async def critique_response(
    question: Annotated[str, Field(description="The original user question or task")],
    draft_response: Annotated[str, Field(description="The draft response to review")],
    severity: Annotated[
        str, Field(description="Lowest severity to surface: 'critical', 'important', or 'all'")
    ] = "important",
) -> str:
    """
    Have a senior reviewer critique a draft response. Returns a structured Markdown report.

    Use this when the question is non-trivial: architecture decisions, customer-facing
    outputs, code that will be merged, anything irreversible. Skip for chit-chat.
    """
    audit_id = audit_log(
        "Critique.review",
        "started",
        {"question_chars": len(question), "draft_chars": len(draft_response)},
    )
    severity = (severity or "important").lower()
    if severity not in {"critical", "important", "all"}:
        severity = "important"

    prompt = (
        f"USER QUESTION:\n{question}\n\n"
        f"DRAFT RESPONSE:\n{draft_response}\n\n"
        f"Provide your rubber-duck critique. Surface findings of severity '{severity}' or higher."
    )
    try:
        reviewer = _get_reviewer()
        result = await reviewer.run(prompt)
        text = (result.text or "").strip() if hasattr(result, "text") else str(result).strip()
        audit_log(
            "Critique.review",
            "completed",
            {"response_chars": len(text)},
            parent_id=audit_id,
        )
        return text or "Critique returned no content."
    except Exception as exc:  # noqa: BLE001
        logger.exception("Critique failed")
        audit_log("Critique.review", "error", {"error": str(exc)}, parent_id=audit_id)
        return f"Critique unavailable: {exc!s}"


CRITIQUE_TOOLS = [critique_response]


# ---------------------------------------------------------------------------
# Auto-critique helpers (used by the orchestrator for opt-out self-review)
# ---------------------------------------------------------------------------

import os
import re

# Substrings that mark a task as high-stakes enough to auto-review.
_HIGH_STAKES_MARKERS = (
    "architect", "architecture", "design", "schema", "database", "ddl",
    "migration", "security", "secure", "auth", "review", "code", "deploy",
    "production", "infrastructure", "terraform", "bicep", "pipeline",
    "cost", "finops", "budget", "incident", "root cause", "rca",
    "compliance", "audit", "threat", "vulnerability", "strategy",
)

# A draft this short is almost certainly chit-chat / a clarifying question.
_MIN_DRAFT_CHARS_FOR_CRITIQUE = 400


def auto_critique_enabled() -> bool:
    """Auto-critique is on unless explicitly disabled via env."""
    return os.getenv("AUTO_CRITIQUE_ENABLED", "true").strip().lower() not in (
        "false", "0", "no", "off",
    )


def auto_critique_mode() -> str:
    """Currently only 'annotate' is supported (append a note, never re-run)."""
    return os.getenv("AUTO_CRITIQUE_MODE", "annotate").strip().lower() or "annotate"


def should_auto_critique(question: str, draft_response: str) -> bool:
    """Decide whether a draft is worth a self-review pass.

    Conservative on purpose: only fires on substantial drafts for tasks whose
    wording signals real stakes. Avoids burning a model call on small talk.
    """
    if not auto_critique_enabled():
        return False
    q = (question or "").lower()
    draft = draft_response or ""
    if len(draft) < _MIN_DRAFT_CHARS_FOR_CRITIQUE:
        return False
    return any(marker in q for marker in _HIGH_STAKES_MARKERS)


def has_material_findings(critique_text: str) -> bool:
    """True if the critique reports anything beyond 'ship it'.

    Parses the structured verdict/sections produced by ``critique_response``.
    Returns False for empty critiques, errors, or a clean bill of health so the
    orchestrator only annotates when there is real signal.
    """
    if not critique_text:
        return False
    text = critique_text.strip()
    low = text.lower()
    if low.startswith("critique unavailable") or low.startswith("critique returned no content"):
        return False

    # Verdict gate: a clean "ship it" with no qualifier means no material issue.
    verdict_match = re.search(r"##\s*verdict\s*\n+([^\n]+)", text, re.IGNORECASE)
    if verdict_match:
        verdict = verdict_match.group(1).strip().lower()
        if verdict.startswith("ship it"):
            # still check for non-empty critical/important sections below
            pass
        elif any(k in verdict for k in ("needs material", "reject", "minor fix", "ship with")):
            return True

    # Section gate: any non-empty Critical/Important section is material.
    for header in ("critical findings", "important findings"):
        section = _extract_section(text, header)
        if _section_has_bullets(section):
            return True
    return False


def _extract_section(text: str, header: str) -> str:
    pattern = re.compile(
        rf"##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else ""


def _section_has_bullets(section: str) -> bool:
    for line in section.splitlines():
        stripped = line.strip().lstrip("-*• ").strip()
        if not stripped:
            continue
        # ignore explicit "none" placeholders
        if stripped.lower() in ("none", "n/a", "(none)", "none.", "no issues"):
            continue
        if line.lstrip().startswith(("-", "*", "•")):
            return True
    return False
