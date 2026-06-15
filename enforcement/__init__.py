"""AgentSystem — Enforcement Layer

Transforms the orchestrator from "encouragement-based" to "enforcement-based" 
operational discipline. Three gates run in sequence during route_task:

1. DOMAIN CLASSIFICATION — what type of task is this?
2. GROUNDING VERIFICATION — did the specialist use required tools?
3. COMPLETION AUDIT — was the task completed, or just advised about?

Each gate produces a structured assessment. The orchestrator can use these
to decide whether to re-route, annotate, or return the response as-is.

Design: non-blocking by default. Gates annotate, never block, unless
ENFORCEMENT_MODE=strict is set (for CI/testing). Failures are logged
to the audit trail for weekly review (Phase 5 instrumentation).

CITATION: User prompt "improve cloud environment capabilities" + 
cloud agent self-assessment feedback (session 2026-06-15).
"""

from __future__ import annotations

from enforcement.domain_classifier import (
    DomainClassification,
    classify_domain,
)
from enforcement.grounding_check import (
    GroundingVerification,
    verify_grounding,
)
from enforcement.completion_audit import (
    CompletionAudit,
    audit_completion,
)

__all__ = [
    "DomainClassification",
    "classify_domain",
    "GroundingVerification",
    "verify_grounding",
    "CompletionAudit",
    "audit_completion",
]
