"""
CriticAgent — second-pair-of-eyes reviewer for any specialist output.

This specialist takes a question and a draft answer, then rubber-ducks the draft:
  - Verdict (ship it / minor fixes / material revision / reject)
  - Critical findings (bugs, factual errors, customer-impacting risk)
  - Important findings (clarity, completeness, correctness)
  - Confidence score with rationale

Use it before sending high-stakes responses (architecture, customer-facing, code merges,
financial advice). It is intentionally conservative: it does NOT rewrite the answer —
it surfaces what to fix.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action  # noqa: E402
from tools.critique import CRITIQUE_TOOLS  # noqa: E402

logger = logging.getLogger(__name__)


CRITIC_AGENT_NAME = "CriticAgent"
CRITIC_AGENT_DESCRIPTION = (
    "Rubber-duck reviewer: takes a question + draft answer and returns a structured "
    "critique with verdict, critical findings, and confidence. Use before sending "
    "high-stakes responses — architecture, customer-facing, code merges, financial."
)

CRITIC_AGENT_INSTRUCTIONS = (
    "You are a senior principal engineer doing rubber-duck review.\n\n"
    "WORKFLOW:\n"
    "1. Take the user's QUESTION and the DRAFT response they want reviewed.\n"
    "2. Call `critique_response(question, draft_response)` to get the structured review.\n"
    "3. Return the critique exactly as produced — do not rewrite the draft for them.\n\n"
    "RULES:\n"
    "- You are the reviewer, not the author. Never silently fix the draft.\n"
    "- Surface only real issues. Do not invent problems to look thorough.\n"
    "- If the draft is genuinely solid, say 'Ship it' with a one-line rationale.\n"
    "- Be ruthless about correctness, security, and customer safety.\n"
    "- Be relaxed about style and phrasing unless it harms clarity."
)


CRITIC_AGENT_TOOLS = list(CRITIQUE_TOOLS)


log_action(
    agent_name=CRITIC_AGENT_NAME,
    action="module_loaded",
    output_summary=f"{len(CRITIC_AGENT_TOOLS)} tools available",
)
