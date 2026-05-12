"""
AgentSystem — Project Manager Agent.

Senior project manager specializing in cross-functional coordination,
timeline management, stakeholder alignment, and risk mitigation.
Focused on realistic scope and exact spec requirements.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


async def create_project_plan(
    project_name: Annotated[str, "Name of the project"],
    objectives: Annotated[str, "Key project objectives and goals"],
    deliverables: Annotated[str, "Expected deliverables and outputs"],
    team_members: Annotated[str, "Comma-separated list of team members and roles"] = "",
    deadline: Annotated[str, "Target deadline in YYYY-MM-DD format"] = "",
) -> str:
    """Create a comprehensive project plan with WBS, timeline, and milestones."""
    logger.info(f"Creating project plan for: {project_name}")

    objectives_list = [o.strip() for o in objectives.split(",") if o.strip()]
    deliverables_list = [d.strip() for d in deliverables.split(",") if d.strip()]
    team_list = [t.strip() for t in team_members.split(",") if t.strip()] if team_members else []

    plan = (
        f"📋 PROJECT CHARTER: {project_name}\n"
        f"{'═' * 60}\n\n"
        f"🎯 Objectives:\n"
    )
    for i, obj in enumerate(objectives_list, 1):
        plan += f"  {i}. {obj}\n"

    plan += f"\n📦 Deliverables (WBS):\n"
    for i, deliv in enumerate(deliverables_list, 1):
        plan += f"  {i}.0 {deliv}\n"
        plan += f"    {i}.1 Requirements & Design\n"
        plan += f"    {i}.2 Implementation\n"
        plan += f"    {i}.3 Testing & Validation\n"
        plan += f"    {i}.4 Delivery & Sign-off\n"

    if team_list:
        plan += f"\n👥 Team:\n"
        for member in team_list:
            plan += f"  • {member}\n"

    plan += f"\n📅 Gantt-Style Timeline:\n"
    plan += f"  {'Phase':<30} {'Duration':<15} {'Status':<10}\n"
    plan += f"  {'─' * 55}\n"
    phases = [
        ("Initiation & Planning", "1-2 weeks", "🔵 Ready"),
        ("Requirements Gathering", "1-2 weeks", "⚪ Pending"),
        ("Design & Architecture", "2-3 weeks", "⚪ Pending"),
        ("Implementation", "4-6 weeks", "⚪ Pending"),
        ("Testing & QA", "2-3 weeks", "⚪ Pending"),
        ("Deployment & Launch", "1 week", "⚪ Pending"),
        ("Post-Launch Review", "1 week", "⚪ Pending"),
    ]
    for phase, duration, status in phases:
        plan += f"  {phase:<30} {duration:<15} {status}\n"

    if deadline:
        plan += f"\n  🏁 Target Deadline: {deadline}\n"

    plan += (
        f"\n🏆 Milestones:\n"
        f"  M1: Project kickoff complete\n"
        f"  M2: Requirements signed off\n"
        f"  M3: Design review passed\n"
        f"  M4: Feature-complete build\n"
        f"  M5: UAT sign-off\n"
        f"  M6: Production launch\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "ProjectManagerAgent",
        "create_project_plan",
        f"Project: {project_name}",
        f"Objectives: {len(objectives_list)}, Deliverables: {len(deliverables_list)}",
    )
    return plan


async def track_tasks(
    tasks_json: Annotated[str, "JSON array of tasks with fields: name, status, assignee, priority"],
    sprint: Annotated[str, "Sprint identifier"] = "current",
) -> str:
    """Track task status, blockers, and progress. Returns progress report with burndown analysis."""
    logger.info(f"Tracking tasks for sprint: {sprint}")

    try:
        tasks = json.loads(tasks_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format. Expected an array of task objects."

    if not isinstance(tasks, list):
        return "❌ Error: tasks_json must be a JSON array of task objects."

    total = len(tasks)
    status_counts: dict[str, int] = {}
    blocked_tasks: list[dict] = []
    for task in tasks:
        status = task.get("status", "unknown").lower()
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "blocked":
            blocked_tasks.append(task)

    done = status_counts.get("done", 0) + status_counts.get("completed", 0)
    in_progress = status_counts.get("in_progress", 0) + status_counts.get("in progress", 0)
    completion_pct = (done / total * 100) if total > 0 else 0

    report = (
        f"📊 SPRINT PROGRESS REPORT — {sprint}\n"
        f"{'═' * 55}\n\n"
        f"  Total Tasks: {total}\n"
    )
    for status, count in sorted(status_counts.items()):
        bar = "█" * int(count / total * 20) if total > 0 else ""
        report += f"  {status.title():<15} {count:>3}  {bar}\n"

    report += (
        f"\n📈 Burndown Analysis:\n"
        f"  Completion: {completion_pct:.1f}%\n"
        f"  Velocity:   {'On track' if completion_pct >= 50 else 'At risk — consider scope adjustment'}\n"
    )

    if blocked_tasks:
        report += f"\n🚫 Blocked Tasks ({len(blocked_tasks)}):\n"
        for task in blocked_tasks:
            report += f"  • {task.get('name', 'Unnamed')} — {task.get('blocker', 'No blocker details')}\n"

    report += f"{'═' * 55}\n"

    log_action(
        "ProjectManagerAgent",
        "track_tasks",
        f"Sprint: {sprint}, Tasks: {total}",
        f"Done: {done}, In Progress: {in_progress}, Blocked: {len(blocked_tasks)}",
    )
    return report


async def assess_risks(
    project_description: Annotated[str, "Description of the project for risk assessment"],
    known_risks: Annotated[str, "Comma-separated list of already-identified risks"] = "",
    severity_threshold: Annotated[str, "Minimum severity to include: low, medium, high, critical"] = "medium",
) -> str:
    """Identify and assess project risks. Returns risk register with impact/probability matrix."""
    logger.info(f"Assessing risks for project, threshold: {severity_threshold}")

    threshold_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    threshold_val = threshold_order.get(severity_threshold.lower(), 1)

    standard_risks = [
        ("Scope creep", "high", "high", "Implement change control board; freeze scope after sign-off"),
        ("Resource unavailability", "medium", "medium", "Cross-train team; maintain resource buffer"),
        ("Technical debt accumulation", "high", "medium", "Allocate 20% sprint capacity for tech debt"),
        ("Stakeholder misalignment", "medium", "high", "Weekly steering committee; RACI matrix"),
        ("Integration failures", "medium", "high", "Early integration testing; contract-first APIs"),
        ("Timeline slippage", "high", "medium", "Buffer 15-20% on estimates; track velocity"),
        ("Security vulnerabilities", "low", "critical", "Security reviews at each phase; automated scanning"),
        ("Vendor/dependency risk", "medium", "medium", "Evaluate alternatives; contractual SLAs"),
    ]

    known_list = [r.strip() for r in known_risks.split(",") if r.strip()] if known_risks else []

    report = (
        f"⚠️ RISK REGISTER\n"
        f"{'═' * 70}\n"
        f"  Severity threshold: {severity_threshold}\n\n"
        f"  {'Risk':<30} {'Probability':<13} {'Impact':<10} {'Action'}\n"
        f"  {'─' * 66}\n"
    )

    risk_count = 0
    for risk_name, prob, impact, mitigation in standard_risks:
        impact_val = threshold_order.get(impact.lower(), 1)
        if impact_val >= threshold_val:
            report += f"  {risk_name:<30} {prob:<13} {impact:<10} {mitigation}\n"
            risk_count += 1

    if known_list:
        report += f"\n  📌 Customer-Identified Risks:\n"
        for risk in known_list:
            report += f"  • {risk} — Requires detailed assessment\n"
            risk_count += 1

    report += (
        f"\n{'─' * 70}\n"
        f"  Impact/Probability Matrix:\n"
        f"              Low Prob    Med Prob    High Prob\n"
        f"  Critical    Monitor     Mitigate    Escalate\n"
        f"  High        Monitor     Mitigate    Mitigate\n"
        f"  Medium      Accept      Monitor     Monitor\n"
        f"  Low         Accept      Accept      Monitor\n"
        f"{'═' * 70}\n"
        f"  Total risks identified: {risk_count}\n"
    )

    log_action(
        "ProjectManagerAgent",
        "assess_risks",
        f"Threshold: {severity_threshold}",
        f"Risks found: {risk_count}",
    )
    return report


async def create_status_report(
    project_name: Annotated[str, "Name of the project"],
    period: Annotated[str, "Reporting period: daily, weekly, monthly"] = "weekly",
    accomplishments: Annotated[str, "Key accomplishments for this period"] = "",
    blockers: Annotated[str, "Current blockers and impediments"] = "",
    next_steps: Annotated[str, "Planned next steps and upcoming work"] = "",
) -> str:
    """Generate a stakeholder status report. Returns formatted executive summary."""
    logger.info(f"Creating {period} status report for: {project_name}")

    accomplishments_list = [a.strip() for a in accomplishments.split(",") if a.strip()] if accomplishments else []
    blockers_list = [b.strip() for b in blockers.split(",") if b.strip()] if blockers else []
    next_steps_list = [n.strip() for n in next_steps.split(",") if n.strip()] if next_steps else []

    health = "🟢 On Track"
    if blockers_list:
        health = "🟡 At Risk" if len(blockers_list) <= 2 else "🔴 Off Track"

    report = (
        f"📊 EXECUTIVE STATUS REPORT\n"
        f"{'═' * 55}\n"
        f"  Project: {project_name}\n"
        f"  Period:  {period.title()}\n"
        f"  Health:  {health}\n"
        f"{'─' * 55}\n\n"
    )

    report += f"✅ Accomplishments:\n"
    if accomplishments_list:
        for item in accomplishments_list:
            report += f"  • {item}\n"
    else:
        report += f"  (No accomplishments reported)\n"

    report += f"\n🚫 Blockers:\n"
    if blockers_list:
        for item in blockers_list:
            report += f"  ⚠️ {item}\n"
    else:
        report += f"  ✅ No blockers\n"

    report += f"\n🔜 Next Steps:\n"
    if next_steps_list:
        for item in next_steps_list:
            report += f"  → {item}\n"
    else:
        report += f"  (No next steps defined)\n"

    report += (
        f"\n{'─' * 55}\n"
        f"  Prepared by: ProjectManagerAgent\n"
        f"  Distribution: Stakeholders, Leadership\n"
        f"{'═' * 55}\n"
    )

    log_action(
        "ProjectManagerAgent",
        "create_status_report",
        f"{project_name} ({period})",
        f"Health: {health}, Blockers: {len(blockers_list)}",
    )
    return report


async def manage_scope_change(
    change_description: Annotated[str, "Description of the proposed scope change"],
    impact_areas: Annotated[str, "Comma-separated areas impacted: timeline, budget, resources, quality"] = "",
    original_scope: Annotated[str, "Summary of the original agreed scope"] = "",
) -> str:
    """Evaluate scope change requests. Returns impact analysis with recommendation."""
    logger.info(f"Evaluating scope change request")

    impact_list = [a.strip().lower() for a in impact_areas.split(",") if a.strip()] if impact_areas else []
    impact_score = len(impact_list)

    if impact_score == 0:
        recommendation = "ACCEPT"
        rationale = "No significant impact areas identified."
    elif impact_score <= 2:
        recommendation = "ACCEPT WITH CONDITIONS"
        rationale = "Manageable impact; requires timeline/resource adjustment."
    elif impact_score <= 3:
        recommendation = "DEFER"
        rationale = "Significant impact across multiple areas; recommend deferring to next phase."
    else:
        recommendation = "REJECT"
        rationale = "Broad impact threatens project success; recommend separate initiative."

    report = (
        f"🔄 SCOPE CHANGE ANALYSIS\n"
        f"{'═' * 60}\n\n"
        f"📝 Change Request:\n"
        f"  {change_description}\n\n"
    )

    if original_scope:
        report += (
            f"📐 Original Scope:\n"
            f"  {original_scope}\n\n"
        )

    report += f"💥 Impact Analysis:\n"
    impact_details = {
        "timeline": "Schedule extension likely; milestone dates shift",
        "budget": "Additional funding required; cost overrun risk",
        "resources": "Team reallocation needed; potential bottlenecks",
        "quality": "Testing scope increases; regression risk",
    }
    if impact_list:
        for area in impact_list:
            detail = impact_details.get(area, "Requires further analysis")
            report += f"  ⚠️ {area.title()}: {detail}\n"
    else:
        report += f"  ℹ️ No impact areas specified — needs further analysis\n"

    report += (
        f"\n{'─' * 60}\n"
        f"  📌 Recommendation: {recommendation}\n"
        f"  📝 Rationale: {rationale}\n"
        f"  📊 Impact Score: {impact_score}/4\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "ProjectManagerAgent",
        "manage_scope_change",
        change_description[:100],
        f"Recommendation: {recommendation}, Impact: {impact_score}/4",
    )
    return report


async def create_retrospective(
    sprint_name: Annotated[str, "Name or identifier of the sprint/project phase"],
    what_went_well: Annotated[str, "Comma-separated items that went well"] = "",
    what_didnt: Annotated[str, "Comma-separated items that did not go well"] = "",
    action_items: Annotated[str, "Comma-separated action items for improvement"] = "",
) -> str:
    """Facilitate sprint/project retrospective. Returns structured retro document."""
    logger.info(f"Creating retrospective for: {sprint_name}")

    well_list = [w.strip() for w in what_went_well.split(",") if w.strip()] if what_went_well else []
    bad_list = [b.strip() for b in what_didnt.split(",") if b.strip()] if what_didnt else []
    action_list = [a.strip() for a in action_items.split(",") if a.strip()] if action_items else []

    report = (
        f"🔍 RETROSPECTIVE: {sprint_name}\n"
        f"{'═' * 55}\n\n"
        f"😊 What Went Well:\n"
    )
    if well_list:
        for item in well_list:
            report += f"  ✅ {item}\n"
    else:
        report += f"  (No items reported — solicit feedback from team)\n"

    report += f"\n😟 What Didn't Go Well:\n"
    if bad_list:
        for item in bad_list:
            report += f"  ❌ {item}\n"
    else:
        report += f"  (No items reported — solicit feedback from team)\n"

    report += f"\n🎯 Action Items:\n"
    if action_list:
        for i, item in enumerate(action_list, 1):
            report += f"  {i}. {item}\n"
    else:
        suggested = [
            "Schedule team feedback session",
            "Review and update process documentation",
            "Identify top 3 improvement areas for next sprint",
        ]
        report += f"  Suggested actions:\n"
        for i, item in enumerate(suggested, 1):
            report += f"  {i}. {item}\n"

    sentiment = "Positive" if len(well_list) > len(bad_list) else "Needs attention"
    report += (
        f"\n{'─' * 55}\n"
        f"  📊 Overall Sentiment: {sentiment}\n"
        f"  ✅ Positives: {len(well_list)}  |  ❌ Issues: {len(bad_list)}  |  🎯 Actions: {len(action_list)}\n"
        f"{'═' * 55}\n"
    )

    log_action(
        "ProjectManagerAgent",
        "create_retrospective",
        f"Sprint: {sprint_name}",
        f"Well: {len(well_list)}, Issues: {len(bad_list)}, Actions: {len(action_list)}",
    )
    return report


PROJECTMANAGER_TOOLS = [
    create_project_plan,
    track_tasks,
    assess_risks,
    create_status_report,
    manage_scope_change,
    create_retrospective,
]
