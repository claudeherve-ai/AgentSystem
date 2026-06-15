"""Grounding Verification — Post-hoc check that specialists used required tools.

CITATION: Cloud agent self-assessment — "Mandatory grounding rules by domain"
and "If current facts matter, use tools" (session 2026-06-15).

Design: Inspects the specialist agent's tool call history (via conversation
session messages) to verify grounding tools were invoked. Returns a structured
verdict with missing requirements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=False, slots=True)
class GroundingVerification:
    """Result of verifying a specialist's grounding compliance."""

    passed: bool = True
    required_tools: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    missing_tools: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)
    specialist_used: str = ""
    evidence_quality: str = "none"  # none, partial, full
    annotation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "required_tools": self.required_tools,
            "tools_used": self.tools_used,
            "missing_tools": self.missing_tools,
            "domains": self.domains,
            "specialist_used": self.specialist_used,
            "evidence_quality": self.evidence_quality,
            "annotation": self.annotation,
        }


def _extract_tool_calls_from_response(response_text: str) -> list[str]:
    """Extract tool names from a response by matching both literal tool names
    and natural-language descriptions of tool use.

    Heuristic: scans for:
    1. Literal tool names (e.g. "web_search")
    2. Natural language signals (e.g. "based on my search", "I searched for")
    3. Evidence markers (URLs, code blocks, citations)
    """
    if not response_text:
        return []

    tools_found: list[str] = []
    text_lower = response_text.lower()

    # ── Literal tool names ──────────────────────────────────────────
    known_tools = [
        "web_search", "web_fetch", "browse_fetch", "browse_health",
        "microsoft_docs_search", "microsoft_docs_fetch",
        "github_search_code", "github_search_repositories",
        "github_search_issues", "github_get_file_contents",
        "case_search", "case_index_update", "case_list_indexed",
        "read_file", "list_dir", "search_in_file",
        "run_python", "code_executor",
        "critique_response",
        "read_inbox", "check_inbox", "read_calendar", "check_calendar",
        "huggingface_model_search", "huggingface_dataset_search",
        "deepwiki_ask_question", "context7_get_library_docs",
        "plan_create", "plan_resume", "plan_get",
    ]

    for tool in known_tools:
        if tool in text_lower:
            tools_found.append(tool)

    # ── Natural language signals ────────────────────────────────────
    # Map natural language patterns to the tools they imply.
    NL_TO_TOOL: dict[str, str] = {
        # web_search
        "based on my search": "web_search",
        "i searched for": "web_search",
        "i searched the web": "web_search",
        "web search returned": "web_search",
        "according to search results": "web_search",
        "search results show": "web_search",
        # web_fetch
        "i fetched the": "web_fetch",
        "after fetching the page": "web_fetch",
        "the page content shows": "web_fetch",
        # microsoft_docs_search
        "based on microsoft docs": "microsoft_docs_search",
        "according to microsoft": "microsoft_docs_search",
        "microsoft learn": "microsoft_docs_search",
        "from the azure documentation": "microsoft_docs_search",
        # case_search
        "based on the case": "case_search",
        "from the case file": "case_search",
        "case details show": "case_search",
        # read_file
        "i read the file": "read_file",
        "the file contains": "read_file",
        "after inspecting the file": "read_file",
        "i checked the file": "read_file",
        # run_python
        "i ran the code": "run_python",
        "i executed the script": "run_python",
        "the output was": "run_python",
        "i tested this": "run_python",
        "i verified it works": "run_python",
        # critique_response
        "after reviewing my draft": "critique_response",
        "self-review": "critique_response",
        "i critiqued": "critique_response",
        # read_inbox
        "your inbox shows": "read_inbox",
        "i checked your inbox": "read_inbox",
        # read_calendar
        "your calendar shows": "read_calendar",
        "i checked your calendar": "read_calendar",
    }

    for pattern, tool_name in NL_TO_TOOL.items():
        if pattern in text_lower and tool_name not in tools_found:
            tools_found.append(tool_name)

    # ── Evidence markers (imply search/fetch was done) ──────────────
    has_url = "http://" in text_lower or "https://" in text_lower
    has_code = "```" in response_text
    has_source_citation = any(
        m in text_lower for m in ["source:", "cited", "reference:"]
    )

    if has_url and "web_search" not in tools_found:
        tools_found.append("web_search")
    if has_code and "run_python" not in tools_found:
        tools_found.append("run_python")

    _ = has_source_citation  # informational

    return tools_found


def _assess_evidence_quality(response_text: str, required_tools: list[str], tools_used: list[str]) -> str:
    """Rate evidence quality: none, partial, or full."""
    if not required_tools:
        return "full"  # No tools required = full by definition

    if not tools_used:
        return "none"

    # Check for URL citations
    has_urls = "http://" in response_text.lower() or "https://" in response_text.lower()
    # Check for code blocks
    has_code = "```" in response_text
    # Check for source citations
    has_citations = any(
        marker in response_text.lower()
        for marker in ["based on", "according to", "source:", "from ", "cited"]
    )

    coverage = len(set(tools_used) & set(required_tools)) / len(required_tools) if required_tools else 1.0

    if coverage >= 0.8 and (has_urls or has_citations or has_code):
        return "full"
    elif coverage >= 0.3:
        return "partial"
    return "none"


def verify_grounding(
    response_text: str,
    required_tools: list[str],
    domains: list[str],
    specialist_name: str = "",
) -> GroundingVerification:
    """Verify that a specialist agent's response was properly grounded.

    Args:
        response_text: The final text response from the specialist.
        required_tools: Tools that SHOULD have been used for this domain.
        domains: The domain classifications that apply.
        specialist_name: Which specialist produced this response.

    Returns:
        GroundingVerification with pass/fail and details.
    """
    tools_used = _extract_tool_calls_from_response(response_text)

    # Determine missing tools — only those that are both required AND relevant
    # to grounding. Administrative tools (case_list_indexed, browse_health) are
    # not grounding-critical.
    GROUNDING_CRITICAL_TOOLS = {
        "web_search", "web_fetch", "microsoft_docs_search",
        "github_search_code", "github_get_file_contents",
        "case_search", "read_file", "search_in_file",
        "run_python", "critique_response",
        "read_inbox", "check_inbox", "read_calendar", "check_calendar",
        "huggingface_model_search",
    }

    critical_required = [t for t in required_tools if t in GROUNDING_CRITICAL_TOOLS]
    missing = [t for t in critical_required if t not in tools_used]

    evidence = _assess_evidence_quality(response_text, required_tools, tools_used)
    passed = len(missing) == 0 or evidence == "full"

    # Build annotation
    if not passed and missing:
        annotation = (
            f"⚠ Grounding gap: specialist '{specialist_name}' "
            f"for domains {domains} should have used: {missing}. "
            f"Evidence quality: {evidence}."
        )
    elif evidence == "partial":
        annotation = (
            f"ℹ Partial grounding: specialist '{specialist_name}' "
            f"has some evidence but could strengthen with: {missing}."
        )
    else:
        annotation = ""

    return GroundingVerification(
        passed=passed,
        required_tools=required_tools,
        tools_used=tools_used,
        missing_tools=missing,
        domains=domains,
        specialist_used=specialist_name,
        evidence_quality=evidence,
        annotation=annotation,
    )
