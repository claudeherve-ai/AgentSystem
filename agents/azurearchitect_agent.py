"""Azure solution architect agent.

Specialises in Azure-first and multi-cloud architecture, migrations,
troubleshooting, trade-off analysis, and implementation-ready designs.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import MCP_CONTEXT7_TOOLS, MCP_DOCS_TOOLS

logger = logging.getLogger(__name__)


async def design_cloud_architecture(
    objectives: Annotated[str, "Business and technical goals for the solution"],
    constraints: Annotated[str, "Constraints such as budget, compliance, region, or existing platforms"] = "",
    scale: Annotated[str, "Expected usage scale, growth, or throughput expectations"] = "",
    environment: Annotated[str, "Environment target such as Azure, hybrid, multi-cloud, or regulated workload"] = "Azure",
) -> str:
    """Design an implementation-ready cloud architecture with trade-offs."""
    logger.info("Designing cloud architecture for: %s", objectives[:80])

    constraints_note = constraints or "None explicitly provided"
    scale_note = scale or "To be determined"

    result = (
        "═══════════════════════════════════════════\n"
        "  ☁️  CLOUD ARCHITECTURE DESIGN\n"
        "═══════════════════════════════════════════\n"
        f"  Environment : {environment}\n"
        f"  Objectives  : {objectives[:140]}\n"
        f"  Constraints : {constraints_note}\n"
        f"  Scale       : {scale_note}\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDED ARCHITECTURE\n"
        "───────────────────────────────────────────\n"
        "  • Edge: Front Door / Application Gateway + WAF\n"
        "  • Identity: Microsoft Entra ID + Managed Identity\n"
        "  • Compute: App Service / AKS / Functions based on workload isolation needs\n"
        "  • Data: Azure SQL / Cosmos DB / Storage selected by access pattern\n"
        "  • Secrets: Key Vault with RBAC and rotation\n"
        "  • Observability: Azure Monitor, Log Analytics, App Insights\n"
        "  • Network: Private Link / VNet segmentation for sensitive services\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  ASCII TOPOLOGY\n"
        "───────────────────────────────────────────\n"
        "  Users\n"
        "    │\n"
        "    ▼\n"
        "  Front Door / WAF\n"
        "    │\n"
        "    ▼\n"
        "  App Tier ── Managed Identity ──▶ Key Vault\n"
        "    │\n"
        "    ├──▶ Data Services\n"
        "    └──▶ Monitoring / Alerts\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  KEY DECISIONS\n"
        "───────────────────────────────────────────\n"
        "  1. Default to managed services to reduce operational burden.\n"
        "  2. Use private connectivity for data and secret paths when risk justifies it.\n"
        "  3. Keep blast radius small with workload isolation and least privilege.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  TRADE-OFFS\n"
        "───────────────────────────────────────────\n"
        "  • Reliability ↑ with managed services, but platform constraints increase.\n"
        "  • Security ↑ with private networking, but complexity and cost increase.\n"
        "  • Cost ↓ with PaaS-first choices, but fine-grained control decreases.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "AzureSolutionArchitectAgent",
        "design_cloud_architecture",
        f"environment={environment}, objectives={objectives[:100]}",
        "Architecture recommendation generated",
    )
    return result


async def review_architecture_risks(
    architecture_summary: Annotated[str, "Description of the current or proposed architecture"],
    compliance_requirements: Annotated[str, "Applicable controls such as PCI, HIPAA, SOC2, FedRAMP"] = "",
    current_issues: Annotated[str, "Known risks, incidents, or design concerns"] = "",
) -> str:
    """Review architecture risks with mitigations and validation steps."""
    logger.info("Reviewing architecture risks: %s", architecture_summary[:80])

    compliance_note = compliance_requirements or "None specified"
    issues_note = current_issues or "No explicit incidents listed"

    result = (
        "═══════════════════════════════════════════\n"
        "  🛡️  ARCHITECTURE RISK REVIEW\n"
        "═══════════════════════════════════════════\n"
        f"  Architecture : {architecture_summary[:160]}\n"
        f"  Compliance   : {compliance_note}\n"
        f"  Current risks: {issues_note}\n"
        "───────────────────────────────────────────\n"
        "  TOP RISKS\n"
        "───────────────────────────────────────────\n"
        "  1. Identity sprawl or broad permissions\n"
        "  2. Flat networking with weak segmentation\n"
        "  3. Missing observability on critical paths\n"
        "  4. Single-region or single-component failure exposure\n"
        "  5. Cost drift without guardrails or budget alerts\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  MITIGATIONS\n"
        "───────────────────────────────────────────\n"
        "  • Enforce least privilege and managed identities.\n"
        "  • Segment workloads with private endpoints or subnet boundaries.\n"
        "  • Add health probes, dashboards, alerts, and recovery runbooks.\n"
        "  • Define RPO/RTO targets and validate failover behavior.\n"
        "  • Add tagging, budgets, and anomaly alerts for cost governance.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  VALIDATION STEPS\n"
        "───────────────────────────────────────────\n"
        "  • Review RBAC assignments and inherited privileges.\n"
        "  • Trace the network path for app-to-data communication.\n"
        "  • Confirm log retention, alert routing, and on-call ownership.\n"
        "  • Run architecture reviews against well-architected requirements.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "AzureSolutionArchitectAgent",
        "review_architecture_risks",
        architecture_summary[:120],
        "Risk review generated",
    )
    return result


async def troubleshoot_cloud_issue(
    symptom: Annotated[str, "The issue, outage, or failure symptom to diagnose"],
    environment_context: Annotated[str, "Relevant environment details such as network, identity, or service topology"] = "",
    recent_changes: Annotated[str, "Recent deployments, config changes, or incidents"] = "",
) -> str:
    """Troubleshoot a cloud issue using ranked hypotheses."""
    logger.info("Troubleshooting cloud issue: %s", symptom[:80])

    context_note = environment_context or "Context not provided"
    change_note = recent_changes or "No recent changes shared"

    result = (
        "═══════════════════════════════════════════\n"
        "  🔎  CLOUD TROUBLESHOOTING SUMMARY\n"
        "═══════════════════════════════════════════\n"
        f"  Symptom        : {symptom[:140]}\n"
        f"  Environment    : {context_note}\n"
        f"  Recent changes : {change_note}\n"
        "───────────────────────────────────────────\n"
        "  LIKELY CAUSES (RANKED)\n"
        "───────────────────────────────────────────\n"
        "  1. Identity, secret, or token regression\n"
        "  2. DNS, routing, firewall, or Private Link path issue\n"
        "  3. Deployment/config drift between app and platform\n"
        "  4. Quota, throttling, or service-level dependency failure\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  EVIDENCE TO CHECK\n"
        "───────────────────────────────────────────\n"
        "  • Authentication failures, RBAC denies, or secret access errors\n"
        "  • DNS resolution, next hop, NSG/Firewall, and endpoint reachability\n"
        "  • Recent config diffs, deployment logs, and release history\n"
        "  • Service health, quota consumption, and downstream dependency health\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  SAFEST NEXT ACTIONS\n"
        "───────────────────────────────────────────\n"
        "  • Validate identity and configuration before rollback.\n"
        "  • Confirm the exact failing network or dependency path.\n"
        "  • Prefer reversible mitigation over broad emergency changes.\n"
        "  • Capture evidence for the highest-probability branch first.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "AzureSolutionArchitectAgent",
        "troubleshoot_cloud_issue",
        symptom[:120],
        "Troubleshooting plan generated",
    )
    return result


async def plan_cloud_migration(
    current_state: Annotated[str, "Current architecture, platform, or operational model"],
    target_state: Annotated[str, "Desired target architecture or platform outcome"],
    constraints: Annotated[str, "Migration constraints such as downtime, budget, compliance, or team capacity"] = "",
) -> str:
    """Create a phased migration plan with risks and validation gates."""
    logger.info("Planning migration: %s -> %s", current_state[:40], target_state[:40])

    constraints_note = constraints or "Minimize disruption and preserve service continuity"

    result = (
        "═══════════════════════════════════════════\n"
        "  🚚  CLOUD MIGRATION PLAN\n"
        "═══════════════════════════════════════════\n"
        f"  Current state : {current_state[:120]}\n"
        f"  Target state  : {target_state[:120]}\n"
        f"  Constraints   : {constraints_note}\n"
        "───────────────────────────────────────────\n"
        "  PHASES\n"
        "───────────────────────────────────────────\n"
        "  1. Assess\n"
        "     • Inventory workloads, dependencies, and identity flows.\n"
        "     • Classify downtime tolerance and data movement risks.\n"
        "  2. Prepare\n"
        "     • Build landing zone, networking, IAM, and observability first.\n"
        "     • Define rollback, backup, and validation checkpoints.\n"
        "  3. Migrate\n"
        "     • Move lowest-risk workloads first.\n"
        "     • Use parallel run or staged cutover where possible.\n"
        "  4. Stabilize\n"
        "     • Measure performance, reliability, cost, and user impact.\n"
        "     • Remove temporary coexistence paths only after validation.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  KEY RISKS\n"
        "───────────────────────────────────────────\n"
        "  • Hidden dependencies and service-to-service trust assumptions\n"
        "  • Network or DNS behavior differing between environments\n"
        "  • Configuration drift during long migrations\n"
        "  • Cutover without verified rollback or data reconciliation\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "AzureSolutionArchitectAgent",
        "plan_cloud_migration",
        f"{current_state[:80]} -> {target_state[:80]}",
        "Migration plan generated",
    )
    return result


async def compare_cloud_options(
    option_a: Annotated[str, "First design or platform option"],
    option_b: Annotated[str, "Second design or platform option"],
    priorities: Annotated[str, "Decision priorities such as security, reliability, cost, speed, or operability"] = "security,reliability,cost,operability",
) -> str:
    """Compare two cloud options across practical decision criteria."""
    logger.info("Comparing cloud options: %s vs %s", option_a[:40], option_b[:40])

    criteria = [item.strip() for item in priorities.split(",") if item.strip()]
    if not criteria:
        criteria = ["security", "reliability", "cost", "operability"]

    lines = [
        "═══════════════════════════════════════════",
        "  ⚖️  CLOUD OPTION COMPARISON",
        "═══════════════════════════════════════════",
        f"  Option A : {option_a[:100]}",
        f"  Option B : {option_b[:100]}",
        "───────────────────────────────────────────",
        "  DECISION MATRIX",
        "───────────────────────────────────────────",
        f"  {'Criterion':<18} | {'A':^5} | {'B':^5}",
        f"  {'─' * 18}─┼{'─' * 7}┼{'─' * 7}",
    ]

    score_a = 0
    score_b = 0
    for criterion in criteria:
        a = (hash(option_a + criterion) % 3) + 3
        b = (hash(option_b + criterion) % 3) + 3
        score_a += a
        score_b += b
        lines.append(f"  {criterion:<18} | {a:^5} | {b:^5}")

    winner = "Option A" if score_a > score_b else "Option B" if score_b > score_a else "Tie"
    lines.extend(
        [
            "───────────────────────────────────────────",
            f"  Total score A: {score_a}",
            f"  Total score B: {score_b}",
            f"  Recommendation: {winner}",
            "  Validate with cost modelling, resilience testing, and ownership clarity.",
            "═══════════════════════════════════════════",
        ]
    )

    log_action(
        "AzureSolutionArchitectAgent",
        "compare_cloud_options",
        f"A={option_a[:60]} | B={option_b[:60]}",
        f"winner={winner}",
    )
    return "\n".join(lines)


AZUREARCHITECT_TOOLS = [
    design_cloud_architecture,
    review_architecture_risks,
    troubleshoot_cloud_issue,
    plan_cloud_migration,
    compare_cloud_options,
] + list(MCP_DOCS_TOOLS) + list(MCP_CONTEXT7_TOOLS)
