"""Completion Audit — Verify that a specialist completed the task, not just advised.

CITATION: Cloud agent self-assessment — "completion over commentary" and
"If execution is possible, do the execution" (session 2026-06-15).

Design: Scans the response for completion signals (code produced, files created,
actions taken) vs. commentary signals ("you could", "here's how", "I suggest").
High ratios of commentary to completion trigger an annotation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Completion signals ──────────────────────────────────────────────────
# Phrases that indicate the agent DID the work, not just talked about it.

COMPLETION_SIGNALS = [
    "i've created", "i created", "i have created",
    "i've written", "i wrote", "i have written",
    "i've generated", "i generated", "i have generated",
    "i've built", "i built", "i have built",
    "here is the", "here's the",
    "the result is", "the output is",
    "i've drafted", "i drafted",
    "i've scheduled", "i scheduled",
    "i've sent", "i sent",
    "i've analyzed", "i analyzed",
    "i've reviewed", "i reviewed",
    "task completed", "done", "all done",
    "```",  # code blocks = execution
    "i ran", "i've run",
    "i verified", "i've verified",
]

# ── Commentary signals ──────────────────────────────────────────────────
# Phrases that indicate the agent only ADVISED, didn't execute.

COMMENTARY_SIGNALS = [
    "you could", "you can",
    "here's how you could", "here is how you could",
    "here's how you can", "here is how you can",
    "here's how to", "here is how to",
    "i suggest", "i recommend",
    "you might want to", "you may want to",
    "consider", "you should consider",
    "one approach would be", "a possible approach",
    "you would need to", "you will need to",
    "first, you would", "first, you could",
    "i would recommend", "my recommendation is",
    "the best approach is to",
    "in general", "typically",
]

# ── Evidence of real tool use ───────────────────────────────────────────
TOOL_EVIDENCE_SIGNALS = [
    "based on",
    "according to",
    "from the",
    "web search returned",
    "the file contains",
    "the inbox shows",
    "the calendar has",
    "source:",
    "cited",
]


@dataclass(frozen=False, slots=True)
class CompletionAudit:
    """Result of auditing whether a task was completed vs. just advised."""

    completed: bool = True
    completion_signals_count: int = 0
    commentary_signals_count: int = 0
    ratio: float = 1.0  # completion / (completion + commentary)
    has_code: bool = False
    has_evidence: bool = False
    annotation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "completed": self.completed,
            "completion_signals_count": self.completion_signals_count,
            "commentary_signals_count": self.commentary_signals_count,
            "ratio": round(self.ratio, 2),
            "has_code": self.has_code,
            "has_evidence": self.has_evidence,
            "annotation": self.annotation,
        }


def audit_completion(response_text: str) -> CompletionAudit:
    """Audit a response for completion vs. commentary patterns.

    A response is "completed" if it demonstrates execution (code, files,
    data, actions) rather than just advice. High commentary ratio
    triggers a soft annotation advising re-execution.

    Args:
        response_text: The final response from the agent/specialist.

    Returns:
        CompletionAudit with pass/fail and details.
    """
    if not response_text:
        return CompletionAudit(
            completed=False,
            annotation="Empty response — nothing was completed.",
        )

    text_lower = response_text.lower()

    # Count signals
    completion_count = sum(1 for sig in COMPLETION_SIGNALS if sig in text_lower)
    commentary_count = sum(1 for sig in COMMENTARY_SIGNALS if sig in text_lower)

    total = completion_count + commentary_count or 1  # avoid div-by-zero
    ratio = completion_count / total

    has_code = "```" in response_text
    has_evidence = any(sig in text_lower for sig in TOOL_EVIDENCE_SIGNALS)

    # A response is "completed" if:
    # 1. More completion signals than commentary, OR
    # 2. Has code + evidence, OR
    # 3. Short response (< 200 chars — likely a direct answer)
    is_short = len(response_text) < 200
    completed = (
        ratio >= 0.5
        or (has_code and has_evidence)
        or is_short
    )

    # Build annotation
    if not completed:
        if commentary_count > 0 and completion_count == 0:
            annotation = (
                "⚠ Completion gap: response contains only advice with no "
                "execution. If tools exist, use them. Deliver finished work, "
                f"not instructions. ({commentary_count} advisory phrases detected)"
            )
        elif ratio < 0.5:
            annotation = (
                f"⚠ Completion gap: ratio {ratio:.1f} ({completion_count} completion "
                f"vs {commentary_count} commentary). Prefer execution over advice."
            )
        else:
            annotation = "⚠ Completion uncertain — verify task was fully executed."
    else:
        annotation = ""

    return CompletionAudit(
        completed=completed,
        completion_signals_count=completion_count,
        commentary_signals_count=commentary_count,
        ratio=round(ratio, 2),
        has_code=has_code,
        has_evidence=has_evidence,
        annotation=annotation,
    )
