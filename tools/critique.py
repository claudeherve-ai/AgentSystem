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
