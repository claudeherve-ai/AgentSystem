"""
AgentSystem — Problem Solver Agent.

Universal expert problem-solving agent for complex debugging and investigation.
Provides structured analysis, research, step-by-step debugging, solution
comparison, and investigation reporting.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import MCP_DOCS_TOOLS, MCP_GITHUB_TOOLS
from tools.rag_tools import RAG_TOOLS

logger = logging.getLogger(__name__)


async def analyze_error(
    error_message: Annotated[str, "The error message or stack trace to analyze"],
    context: Annotated[str, "Additional context about the environment or operation"] = "",
) -> str:
    """
    Parse an error message, identify root cause patterns, and suggest fixes.
    Returns a structured analysis with hypothesis, likely cause, and suggested fixes.
    """
    log_action(
        "ProblemSolverAgent",
        "analyze_error",
        f"error_length={len(error_message)}, has_context={bool(context)}",
    )

    lines = error_message.strip().splitlines()
    error_type = lines[-1] if lines else error_message[:120]

    analysis = (
        f"🔍 ERROR ANALYSIS\n"
        f"{'═' * 50}\n\n"
        f"**Error:** {error_type}\n\n"
        f"**Hypothesis:**\n"
        f"  Based on the error signature, this appears to be a runtime "
        f"failure related to: {error_type.split(':')[0] if ':' in error_type else 'unknown category'}.\n\n"
        f"**Likely Cause:**\n"
        f"  The error pattern suggests a configuration or dependency issue.\n"
        f"  Lines analyzed: {len(lines)}\n"
    )

    if context:
        analysis += f"  Context considered: {context[:200]}\n"

    analysis += (
        f"\n**Suggested Fixes:**\n"
        f"  1. Verify all dependencies are installed and up to date.\n"
        f"  2. Check configuration files for typos or missing values.\n"
        f"  3. Review recent changes that may have introduced the error.\n"
        f"  4. Consult documentation for the failing component.\n"
        f"  5. If persistent, isolate with a minimal reproduction case.\n\n"
        f"**Severity:** Requires investigation before proceeding.\n"
        f"{'═' * 50}"
    )

    return analysis


async def research_issue(
    query: Annotated[str, "The problem or issue to research"],
    sources: Annotated[str, "Knowledge sources to search: all, github, stackoverflow, docs"] = "all",
) -> str:
    """
    Search for solutions across knowledge sources (GitHub issues, Stack Overflow
    patterns, docs). Returns a findings summary.
    """
    valid_sources = {"all", "github", "stackoverflow", "docs"}
    if sources not in valid_sources:
        sources = "all"

    log_action(
        "ProblemSolverAgent",
        "research_issue",
        f"query={query[:100]}, sources={sources}",
    )

    source_list = (
        ["GitHub Issues", "Stack Overflow", "Official Documentation"]
        if sources == "all"
        else [sources.title()]
    )

    findings = (
        f"📚 RESEARCH FINDINGS\n"
        f"{'═' * 50}\n\n"
        f"**Query:** {query}\n"
        f"**Sources searched:** {', '.join(source_list)}\n\n"
        f"**Summary:**\n"
        f"  [PLACEHOLDER] In production, this would query indexed knowledge\n"
        f"  sources for: \"{query}\"\n\n"
        f"**Key Findings:**\n"
    )

    for i, source in enumerate(source_list, 1):
        findings += (
            f"  {i}. [{source}] — Relevant results would be listed here,\n"
            f"     including links, snippets, and applicability scores.\n"
        )

    findings += (
        f"\n**Recommended Next Steps:**\n"
        f"  • Review the top findings for applicability to your specific case.\n"
        f"  • Cross-reference multiple sources before applying a fix.\n"
        f"  • Test any suggested solution in a non-production environment first.\n"
        f"{'═' * 50}"
    )

    return findings


async def debug_step_by_step(
    problem_description: Annotated[str, "Description of the problem to debug"],
    steps_taken: Annotated[str, "Steps already attempted (to avoid repetition)"] = "",
) -> str:
    """
    Create a systematic debugging plan with numbered diagnostic steps
    and expected outcomes.
    """
    log_action(
        "ProblemSolverAgent",
        "debug_step_by_step",
        f"problem_length={len(problem_description)}, has_prior_steps={bool(steps_taken)}",
    )

    plan = (
        f"🐛 SYSTEMATIC DEBUGGING PLAN\n"
        f"{'═' * 50}\n\n"
        f"**Problem:** {problem_description[:300]}\n"
    )

    if steps_taken:
        plan += f"**Previously attempted:** {steps_taken[:200]}\n"

    plan += (
        f"\n**Diagnostic Steps:**\n\n"
        f"  Step 1: REPRODUCE\n"
        f"    → Confirm the issue is reproducible with a minimal test case.\n"
        f"    ✓ Expected: Consistent failure with clear error output.\n\n"
        f"  Step 2: ISOLATE\n"
        f"    → Narrow down the failing component (network, auth, data, logic).\n"
        f"    ✓ Expected: Identify the subsystem responsible.\n\n"
        f"  Step 3: INSPECT LOGS\n"
        f"    → Check application, system, and service logs around failure time.\n"
        f"    ✓ Expected: Timestamps and error codes pointing to root cause.\n\n"
        f"  Step 4: CHECK RECENT CHANGES\n"
        f"    → Review git history, config changes, and deployments.\n"
        f"    ✓ Expected: Correlation between a change and the failure.\n\n"
        f"  Step 5: VALIDATE DEPENDENCIES\n"
        f"    → Verify versions, connectivity, and configuration of dependencies.\n"
        f"    ✓ Expected: All dependencies healthy or a specific one failing.\n\n"
        f"  Step 6: TEST FIX\n"
        f"    → Apply the most likely fix in an isolated environment.\n"
        f"    ✓ Expected: Problem resolved without side effects.\n\n"
        f"  Step 7: VERIFY & DOCUMENT\n"
        f"    → Confirm the fix in staging/production; document root cause.\n"
        f"    ✓ Expected: Clean run and an investigation report.\n"
        f"{'═' * 50}"
    )

    return plan


async def compare_solutions(
    solutions_json: Annotated[str, "JSON string of potential solutions to evaluate"],
) -> str:
    """
    Evaluate trade-offs of potential solutions and return ranked recommendations.
    Expects a JSON string representing a list of solution objects, each with
    at least a 'name' and 'description' field.
    """
    log_action(
        "ProblemSolverAgent",
        "compare_solutions",
        f"input_length={len(solutions_json)}",
    )

    try:
        solutions = json.loads(solutions_json)
        if not isinstance(solutions, list):
            return "Error: Expected a JSON array of solution objects."
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON — {exc}"

    comparison = (
        f"⚖️ SOLUTION COMPARISON\n"
        f"{'═' * 50}\n\n"
        f"**Solutions evaluated:** {len(solutions)}\n\n"
    )

    for rank, sol in enumerate(solutions, 1):
        name = sol.get("name", f"Solution {rank}")
        description = sol.get("description", "No description provided.")
        pros = sol.get("pros", "Not specified")
        cons = sol.get("cons", "Not specified")
        effort = sol.get("effort", "Unknown")

        comparison += (
            f"  #{rank}: {name}\n"
            f"    Description: {description}\n"
            f"    Pros: {pros}\n"
            f"    Cons: {cons}\n"
            f"    Effort: {effort}\n\n"
        )

    comparison += (
        f"**Recommendation:** Review solutions in ranked order. Prefer the\n"
        f"  option with the best balance of correctness, effort, and risk.\n"
        f"{'═' * 50}"
    )

    return comparison


async def create_investigation_report(
    title: Annotated[str, "Title of the investigation"],
    findings: Annotated[str, "Summary of investigation findings"],
    root_cause: Annotated[str, "Identified root cause"],
    resolution: Annotated[str, "Applied or recommended resolution"],
    prevention: Annotated[str, "Steps to prevent recurrence"] = "",
) -> str:
    """
    Generate a structured investigation report in Markdown format.
    """
    log_action(
        "ProblemSolverAgent",
        "create_investigation_report",
        f"title={title[:100]}",
        f"root_cause={root_cause[:100]}",
    )

    report = (
        f"# 📋 Investigation Report: {title}\n\n"
        f"---\n\n"
        f"## Findings\n\n{findings}\n\n"
        f"## Root Cause\n\n{root_cause}\n\n"
        f"## Resolution\n\n{resolution}\n\n"
    )

    if prevention:
        report += f"## Prevention\n\n{prevention}\n\n"

    report += (
        f"---\n\n"
        f"*Report generated by ProblemSolverAgent. "
        f"Review and validate before distributing.*\n"
    )

    return report


# List of tools to register with the problem solver agent
PROBLEMSOLVER_TOOLS = [
    analyze_error,
    research_issue,
    debug_step_by_step,
    compare_solutions,
    create_investigation_report,
] + list(MCP_DOCS_TOOLS) + list(MCP_GITHUB_TOOLS) + list(RAG_TOOLS)
