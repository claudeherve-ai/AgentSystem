"""
AgentSystem — Project Shepherd Agent.

Cross-functional project coordination, timeline management,
stakeholder alignment, and risk mitigation.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)


async def create_project_charter(
    project_name: Annotated[str, "Name of the project"],
    problem_statement: Annotated[str, "Clear description of the problem or opportunity"],
    objectives: Annotated[str, "Specific, measurable project objectives"],
    stakeholders: Annotated[str, "Key stakeholders and their roles"],
    timeline_weeks: Annotated[int, "Estimated project duration in weeks"] = 12,
) -> str:
    """Create a project charter with objectives, stakeholders, scope, and governance."""
    log_action("ProjectShepherdAgent", "create_charter", f"project={project_name}")

    return (
        f"PROJECT CHARTER: {project_name}\n{'=' * 60}\n\n"
        f"PROBLEM STATEMENT\n  {problem_statement}\n\n"
        f"OBJECTIVES\n  {objectives}\n\n"
        f"STAKEHOLDERS\n  {stakeholders}\n\n"
        f"TIMELINE: {timeline_weeks} weeks\n\n"
        f"MILESTONES\n{'─' * 60}\n"
        f"  Phase 1 — Initiation & Planning    (Weeks 1-2)\n"
        f"  Phase 2 — Execution                (Weeks 3-{timeline_weeks-2})\n"
        f"  Phase 3 — QA & Delivery            (Weeks {timeline_weeks-1}-{timeline_weeks})\n\n"
        f"GOVERNANCE\n"
        f"  Decision Authority: [Executive Sponsor]\n"
        f"  Status Cadence:     Weekly\n"
        f"  Escalation Path:    PM -> Sponsor -> Steering Committee\n\n"
        f"RISKS\n"
        f"  [Identify top 3-5 risks with impact/probability]\n\n"
        f"SUCCESS CRITERIA\n"
        f"  [Quantifiable measures of project success]\n"
    )


async def generate_status_report(
    project_name: Annotated[str, "Project name"],
    overall_status: Annotated[str, "Status: green, yellow, or red"],
    completed_items: Annotated[str, "What was completed this period"],
    planned_items: Annotated[str, "What is planned for next period"],
    issues: Annotated[str, "Current issues or blockers"] = "None",
    risks: Annotated[str, "Active risks and mitigation status"] = "No new risks",
) -> str:
    """Generate a project status report for stakeholder communication."""
    log_action("ProjectShepherdAgent", "status_report", f"project={project_name}, status={overall_status}")

    icon = {"green": "[OK]", "yellow": "[!!]", "red": "[XX]"}.get(overall_status.lower(), "[??]")

    return (
        f"PROJECT STATUS REPORT\n{'=' * 60}\n\n"
        f"Project:  {project_name}\n"
        f"Status:   {icon} {overall_status.upper()}\n\n"
        f"COMPLETED THIS PERIOD\n{'─' * 60}\n  {completed_items}\n\n"
        f"PLANNED NEXT PERIOD\n{'─' * 60}\n  {planned_items}\n\n"
        f"ISSUES & BLOCKERS\n{'─' * 60}\n  {issues}\n\n"
        f"RISKS\n{'─' * 60}\n  {risks}\n\n"
        f"DECISIONS NEEDED\n"
        f"  [List any outstanding decisions required from stakeholders]\n"
    )


async def assess_project_risk(
    project_name: Annotated[str, "Project name"],
    risk_description: Annotated[str, "Description of the risk"],
    probability: Annotated[str, "Probability: low, medium, or high"],
    impact: Annotated[str, "Impact: low, medium, or high"],
    mitigation_plan: Annotated[str, "Proposed mitigation actions"] = "",
) -> str:
    """Assess a project risk with impact/probability scoring and mitigation plan."""
    log_action("ProjectShepherdAgent", "assess_risk", f"project={project_name}")

    score_map = {"low": 1, "medium": 2, "high": 3}
    p = score_map.get(probability.lower(), 2)
    i = score_map.get(impact.lower(), 2)
    overall = p * i
    rating = "LOW" if overall <= 2 else "MEDIUM" if overall <= 4 else "HIGH"

    return (
        f"RISK ASSESSMENT\n{'=' * 60}\n\n"
        f"Project:     {project_name}\n"
        f"Risk:        {risk_description}\n"
        f"Probability: {probability} ({p}/3)\n"
        f"Impact:      {impact} ({i}/3)\n"
        f"Overall:     {rating} (score {overall}/9)\n\n"
        f"MITIGATION PLAN\n{'─' * 60}\n"
        f"  {mitigation_plan or '[Define mitigation actions]'}\n\n"
        f"CONTINGENCY\n"
        f"  [Define fallback plan if risk materializes]\n"
    )


PROJECTSHEPHERD_TOOLS = [create_project_charter, generate_status_report, assess_project_risk]
