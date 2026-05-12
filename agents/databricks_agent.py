"""Databricks specialist agent.

Specialises in Databricks platform architecture, Spark/SQL performance,
governance, delivery patterns, Apps, Jobs, Lakeflow Pipelines, and
production troubleshooting.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import MCP_CONTEXT7_TOOLS, MCP_DOCS_TOOLS

logger = logging.getLogger(__name__)


async def design_databricks_platform(
    workload_summary: Annotated[str, "Business and technical goals for the Databricks platform"],
    data_domains: Annotated[str, "Primary data domains, products, or workload types"] = "",
    governance_requirements: Annotated[str, "Governance, security, or compliance requirements"] = "",
    operating_model: Annotated[str, "Desired operating model such as central platform team, federated, or hybrid"] = "central platform team",
) -> str:
    """Design a Databricks platform architecture with governance and delivery guidance."""
    logger.info("Designing Databricks platform for: %s", workload_summary[:80])

    domains_note = data_domains or "To be defined"
    governance_note = governance_requirements or "Standard enterprise governance"

    result = (
        "═══════════════════════════════════════════\n"
        "  🧱  DATABRICKS PLATFORM DESIGN\n"
        "═══════════════════════════════════════════\n"
        f"  Workload      : {workload_summary[:140]}\n"
        f"  Data domains  : {domains_note}\n"
        f"  Governance    : {governance_note}\n"
        f"  Operating mode: {operating_model}\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDED PLATFORM SHAPE\n"
        "───────────────────────────────────────────\n"
        "  • Unity Catalog for data, AI, and governance boundaries\n"
        "  • Lakehouse medallion flow for analytics and ML workloads\n"
        "  • Lakeflow Pipelines / Jobs for managed production delivery\n"
        "  • SQL Warehouses for BI and app-facing analytical reads\n"
        "  • Lakebase for transactional app patterns when OLTP is needed\n"
        "  • Asset Bundles for repeatable deployment across environments\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  ASCII TOPOLOGY\n"
        "───────────────────────────────────────────\n"
        "  Sources / SaaS / Files / Streams\n"
        "                │\n"
        "                ▼\n"
        "       Ingestion + Bronze Landing\n"
        "                │\n"
        "                ▼\n"
        "      Silver / Gold Delta Tables\n"
        "                │\n"
        "      ┌─────────┼─────────┐\n"
        "      ▼         ▼         ▼\n"
        "  Jobs     SQL Warehouse  ML / Serving\n"
        "      │         │         │\n"
        "      └──────▶ Apps / APIs ◀──────┘\n"
        "                │\n"
        "                ▼\n"
        "         Unity Catalog + Audit\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  KEY DECISIONS\n"
        "───────────────────────────────────────────\n"
        "  1. Govern once in Unity Catalog instead of per-workspace policies.\n"
        "  2. Default to bundle-based delivery for Jobs, Pipelines, and Apps.\n"
        "  3. Separate analytics reads from engineering compute where concurrency differs.\n"
        "  4. Use Lakebase only when app writes and transactional semantics justify it.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  TRADE-OFFS\n"
        "───────────────────────────────────────────\n"
        "  • Central governance improves control, but federated teams need enablement.\n"
        "  • More environment isolation reduces blast radius, but increases cost and ops.\n"
        "  • SQL Warehouse serving simplifies analytics access, but adds concurrency cost.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DatabricksSpecialistAgent",
        "design_databricks_platform",
        f"workload={workload_summary[:100]}",
        "Platform architecture recommendation generated",
    )
    return result


async def troubleshoot_databricks_issue(
    symptom: Annotated[str, "The Databricks issue, outage, or failure symptom"],
    workload_surface: Annotated[str, "Surface area such as Jobs, SQL Warehouse, Pipeline, App, cluster, or CLI"] = "",
    environment_context: Annotated[str, "Relevant workspace, network, identity, or governance context"] = "",
    recent_changes: Annotated[str, "Recent deployments, policy changes, auth changes, or config drift"] = "",
) -> str:
    """Troubleshoot Databricks issues using a ranked root-cause approach."""
    logger.info("Troubleshooting Databricks issue: %s", symptom[:80])

    surface_note = workload_surface or "Not specified"
    context_note = environment_context or "Context not provided"
    changes_note = recent_changes or "No recent changes shared"

    result = (
        "═══════════════════════════════════════════\n"
        "  🔎  DATABRICKS TROUBLESHOOTING\n"
        "═══════════════════════════════════════════\n"
        f"  Symptom        : {symptom[:140]}\n"
        f"  Surface        : {surface_note}\n"
        f"  Context        : {context_note}\n"
        f"  Recent changes : {changes_note}\n"
        "───────────────────────────────────────────\n"
        "  LIKELY CAUSES (RANKED)\n"
        "───────────────────────────────────────────\n"
        "  1. Identity, entitlement, or Unity Catalog permission regression\n"
        "  2. Networking or DNS path issue (Private Link, SCC, egress, firewall)\n"
        "  3. Bundle/deployment drift between code, workspace state, and config\n"
        "  4. Compute sizing, concurrency, or Spark execution bottlenecks\n"
        "  5. Dependency outage on storage, metastore, or downstream service\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  EVIDENCE TO CHECK\n"
        "───────────────────────────────────────────\n"
        "  • Job, pipeline, SQL Warehouse, or app event logs\n"
        "  • Workspace auth profile, SCIM, entitlements, and UC grants\n"
        "  • Storage reachability, DNS, route path, and firewall/NSG rules\n"
        "  • Recent bundle validation/deploy results and config diffs\n"
        "  • Query history, Spark UI, skew, shuffle, spill, and cluster metrics\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  SAFEST NEXT ACTIONS\n"
        "───────────────────────────────────────────\n"
        "  • Validate auth and governance before changing runtime settings.\n"
        "  • Confirm the exact failing surface: control plane, planner, or data plane.\n"
        "  • Prefer reversible mitigations over broad workspace changes.\n"
        "  • Capture the smallest reproducible failing command or job run.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DatabricksSpecialistAgent",
        "troubleshoot_databricks_issue",
        symptom[:120],
        "Troubleshooting summary generated",
    )
    return result


async def optimize_spark_workload(
    workload_summary: Annotated[str, "Description of the Spark, SQL, or Delta workload"],
    pain_points: Annotated[str, "Observed performance issues such as skew, shuffle, small files, or latency"] = "",
    data_layout: Annotated[str, "Current table format, partitioning, clustering, or file layout"] = "",
    execution_context: Annotated[str, "Execution context such as job cluster, all-purpose cluster, or SQL Warehouse"] = "",
) -> str:
    """Recommend practical Databricks and Spark performance improvements."""
    logger.info("Optimizing Spark workload: %s", workload_summary[:80])

    pain_note = pain_points or "General throughput and latency improvement"
    layout_note = data_layout or "Layout details not provided"
    context_note = execution_context or "Execution context not specified"

    result = (
        "═══════════════════════════════════════════\n"
        "  ⚡  SPARK / SQL OPTIMIZATION REVIEW\n"
        "═══════════════════════════════════════════\n"
        f"  Workload  : {workload_summary[:140]}\n"
        f"  Pain      : {pain_note}\n"
        f"  Layout    : {layout_note}\n"
        f"  Context   : {context_note}\n"
        "───────────────────────────────────────────\n"
        "  HIGHEST-IMPACT OPTIMIZATIONS\n"
        "───────────────────────────────────────────\n"
        "  1. Fix data layout first: compaction, clustering, partition strategy.\n"
        "  2. Reduce shuffle pain: join strategy, skew handling, AQE, broadcast where safe.\n"
        "  3. Remove Python/UDF hotspots if SQL or built-ins can replace them.\n"
        "  4. Right-size compute for concurrency, memory pressure, and I/O profile.\n"
        "  5. Separate ETL and BI workloads if they compete for the same resources.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  CHECKLIST\n"
        "───────────────────────────────────────────\n"
        "  • Inspect Spark UI for skew, spill, stage retries, and long tails.\n"
        "  • Review Delta file counts, table maintenance cadence, and vacuum policy.\n"
        "  • Confirm Photon, AQE, and warehouse type match the workload shape.\n"
        "  • Track query history and warehouse saturation for interactive workloads.\n"
        "  • Re-test after each change to isolate the actual performance driver.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DatabricksSpecialistAgent",
        "optimize_spark_workload",
        workload_summary[:120],
        "Optimization guidance generated",
    )
    return result


async def review_databricks_governance(
    catalog_strategy: Annotated[str, "Current or proposed Unity Catalog / workspace governance strategy"],
    identity_model: Annotated[str, "Identity, group, and entitlement model"] = "",
    compliance_requirements: Annotated[str, "Applicable controls such as PCI, HIPAA, SOC2, or internal policies"] = "",
    security_concerns: Annotated[str, "Known security or governance concerns"] = "",
) -> str:
    """Review Databricks governance, permissions, and platform controls."""
    logger.info("Reviewing Databricks governance: %s", catalog_strategy[:80])

    identity_note = identity_model or "Identity model not specified"
    compliance_note = compliance_requirements or "Standard enterprise controls"
    concerns_note = security_concerns or "No explicit concerns listed"

    result = (
        "═══════════════════════════════════════════\n"
        "  🛡️  DATABRICKS GOVERNANCE REVIEW\n"
        "═══════════════════════════════════════════\n"
        f"  Catalog strategy : {catalog_strategy[:140]}\n"
        f"  Identity model   : {identity_note}\n"
        f"  Compliance       : {compliance_note}\n"
        f"  Current concerns : {concerns_note}\n"
        "───────────────────────────────────────────\n"
        "  PRIORITY CONTROLS\n"
        "───────────────────────────────────────────\n"
        "  • Unity Catalog as the system of governance truth\n"
        "  • Group-based permissions instead of user-by-user grants\n"
        "  • Least privilege for compute, data, and external locations\n"
        "  • Audit logging, lineage, and query access review\n"
        "  • Network isolation and private connectivity for sensitive paths\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  COMMON GAPS\n"
        "───────────────────────────────────────────\n"
        "  1. Workspace-local assumptions surviving after UC rollout\n"
        "  2. Broad all-users or admin group access to critical data\n"
        "  3. External location or credential sharing without ownership clarity\n"
        "  4. Missing separation between developer, platform, and consumer roles\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  VALIDATION STEPS\n"
        "───────────────────────────────────────────\n"
        "  • Review grants at catalog, schema, table, and volume levels.\n"
        "  • Validate SCIM groups, SSO, break-glass access, and service identities.\n"
        "  • Confirm audit export, retention, and monitoring coverage.\n"
        "  • Test the data path from the least-privileged persona viewpoint.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DatabricksSpecialistAgent",
        "review_databricks_governance",
        catalog_strategy[:120],
        "Governance review generated",
    )
    return result


async def plan_databricks_delivery(
    target_capability: Annotated[str, "Capability to deliver such as app, job, pipeline, serving endpoint, or platform baseline"],
    delivery_model: Annotated[str, "Preferred delivery model such as asset bundles, appkit, notebooks, or mixed"] = "asset bundles",
    environments: Annotated[str, "Target environments such as dev,test,prod"] = "dev,test,prod",
    validation_requirements: Annotated[str, "Required validation steps, smoke tests, policy checks, or approvals"] = "",
) -> str:
    """Create a Databricks delivery plan focused on safe, repeatable deployment."""
    logger.info("Planning Databricks delivery for: %s", target_capability[:80])

    validation_note = validation_requirements or "validate -> deploy -> verify with smoke checks"

    result = (
        "═══════════════════════════════════════════\n"
        "  🚀  DATABRICKS DELIVERY PLAN\n"
        "═══════════════════════════════════════════\n"
        f"  Capability   : {target_capability[:140]}\n"
        f"  Delivery     : {delivery_model}\n"
        f"  Environments : {environments}\n"
        f"  Validation   : {validation_note}\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDED FLOW\n"
        "───────────────────────────────────────────\n"
        "  1. Define resources and config in version control.\n"
        "  2. Validate locally or in CI before any deploy.\n"
        "  3. Deploy to dev first and run smoke checks.\n"
        "  4. Promote the same artifact/config pattern to higher environments.\n"
        "  5. Verify logs, permissions, and rollback posture after release.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  DEFAULTS BY SURFACE\n"
        "───────────────────────────────────────────\n"
        "  • Jobs / Pipelines / Apps: Asset Bundles as the default path\n"
        "  • Apps: schema/query design before UI work, then typed integration\n"
        "  • Pipelines: choose Streaming Table vs Materialized View deliberately\n"
        "  • Serving / APIs: add quota, auth, observability, and rollback gates\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "DatabricksSpecialistAgent",
        "plan_databricks_delivery",
        target_capability[:120],
        "Delivery plan generated",
    )
    return result


DATABRICKS_TOOLS = [
    design_databricks_platform,
    troubleshoot_databricks_issue,
    optimize_spark_workload,
    review_databricks_governance,
    plan_databricks_delivery,
] + list(MCP_DOCS_TOOLS) + list(MCP_CONTEXT7_TOOLS)
