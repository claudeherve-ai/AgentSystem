"""
AgentSystem — Enterprise Integration Agent.

Enterprise integration architect agent for designing system integrations,
API mappings, webhook handlers, data synchronization strategies, and
integration readiness checklists.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action
from tools.mcp_tools import (
    MCP_CONTEXT7_TOOLS,
    MCP_DOCS_TOOLS,
    MCP_FILESYSTEM_TOOLS,
    MCP_GITHUB_TOOLS,
)
from tools.rag_tools import RAG_TOOLS

logger = logging.getLogger(__name__)


async def design_integration(
    source_system: Annotated[str, "Name or description of the source system"],
    target_system: Annotated[str, "Name or description of the target system"],
    data_flow: Annotated[str, "Data flow direction: unidirectional, bidirectional"] = "bidirectional",
    pattern: Annotated[str, "Integration pattern: event-driven, batch, request-reply, streaming"] = "event-driven",
) -> str:
    """
    Design integration architecture between enterprise systems.
    Returns architecture diagram (ASCII), data mapping, and sync strategy.
    """
    log_action(
        "EnterpriseAgent",
        "design_integration",
        f"source={source_system}, target={target_system}, flow={data_flow}, pattern={pattern}",
    )

    flow_arrow = "⇄" if data_flow == "bidirectional" else "→"

    design = (
        f"🏢 INTEGRATION ARCHITECTURE\n"
        f"{'═' * 60}\n\n"
        f"**Source:** {source_system}\n"
        f"**Target:** {target_system}\n"
        f"**Data Flow:** {data_flow}\n"
        f"**Pattern:** {pattern}\n\n"
        f"**Architecture Diagram:**\n\n"
        f"  ┌────────────────┐     ┌──────────────┐     ┌────────────────┐\n"
        f"  │ {source_system[:14]:<14} │ {flow_arrow}   │  Integration │  {flow_arrow}  │ {target_system[:14]:<14} │\n"
        f"  │   (Source)     │     │    Layer     │     │   (Target)     │\n"
        f"  └────────────────┘     └──────────────┘     └────────────────┘\n"
        f"                          │            │\n"
        f"                     ┌────┘            └────┐\n"
        f"                     ▼                      ▼\n"
        f"              ┌─────────────┐      ┌──────────────┐\n"
        f"              │  Error Queue │      │  Audit Log   │\n"
        f"              └─────────────┘      └──────────────┘\n\n"
        f"**Data Mapping Strategy:**\n"
        f"  • Map source entities to target schema using a canonical model.\n"
        f"  • Apply transformations in the integration layer.\n"
        f"  • Store mapping rules in a versioned configuration.\n\n"
        f"**Sync Strategy ({pattern}):**\n"
    )

    if pattern == "event-driven":
        design += (
            f"  • Source publishes events to a message broker (e.g., Service Bus).\n"
            f"  • Integration layer subscribes, transforms, and pushes to target.\n"
            f"  • Dead-letter queue for failed messages with retry policy.\n"
        )
    elif pattern == "batch":
        design += (
            f"  • Scheduled extraction from source at defined intervals.\n"
            f"  • Batch transform and load into target system.\n"
            f"  • Reconciliation check after each batch run.\n"
        )
    elif pattern == "request-reply":
        design += (
            f"  • Synchronous API calls between systems.\n"
            f"  • Circuit breaker pattern for fault tolerance.\n"
            f"  • Response caching where appropriate.\n"
        )
    else:
        design += (
            f"  • Continuous streaming via change data capture (CDC).\n"
            f"  • Low-latency processing with ordering guarantees.\n"
            f"  • Checkpointing for exactly-once semantics.\n"
        )

    design += f"\n{'═' * 60}"
    return design


async def generate_api_mapping(
    source_api_description: Annotated[str, "Description or schema of the source API"],
    target_api_description: Annotated[str, "Description or schema of the target API"],
) -> str:
    """
    Map fields between two API schemas.
    Returns a field mapping table with transformations.
    """
    log_action(
        "EnterpriseAgent",
        "generate_api_mapping",
        f"source_len={len(source_api_description)}, target_len={len(target_api_description)}",
    )

    mapping = (
        f"🔗 API FIELD MAPPING\n"
        f"{'═' * 60}\n\n"
        f"**Source API:**\n  {source_api_description[:300]}\n\n"
        f"**Target API:**\n  {target_api_description[:300]}\n\n"
        f"**Mapping Table:**\n\n"
        f"  {'Source Field':<25} {'Target Field':<25} {'Transformation':<20}\n"
        f"  {'─' * 70}\n"
        f"  {'[field_1]':<25} {'[mapped_field_1]':<25} {'Direct copy':<20}\n"
        f"  {'[field_2]':<25} {'[mapped_field_2]':<25} {'Format conversion':<20}\n"
        f"  {'[field_3]':<25} {'[mapped_field_3]':<25} {'Lookup / enrich':<20}\n"
        f"  {'[field_4]':<25} {'—':<25} {'Dropped (N/A)':<20}\n"
        f"  {'—':<25} {'[mapped_field_5]':<25} {'Default value':<20}\n"
        f"  {'─' * 70}\n\n"
        f"**Notes:**\n"
        f"  [PLACEHOLDER] In production, this would parse the provided\n"
        f"  schemas and produce an actual field-by-field mapping.\n\n"
        f"  • Validate data types at each mapping boundary.\n"
        f"  • Handle nullable fields and missing data gracefully.\n"
        f"  • Version the mapping configuration for rollback support.\n"
        f"{'═' * 60}"
    )

    return mapping


async def create_webhook_handler(
    source_platform: Annotated[str, "Platform sending webhooks (e.g., Stripe, GitHub, Salesforce)"],
    event_types: Annotated[str, "Comma-separated list of event types to handle"],
    payload_format: Annotated[str, "Payload format: json, xml, form"] = "json",
) -> str:
    """
    Generate webhook handler design. Returns endpoint specification,
    payload schema, and retry strategy.
    """
    events = [e.strip() for e in event_types.split(",") if e.strip()]

    log_action(
        "EnterpriseAgent",
        "create_webhook_handler",
        f"platform={source_platform}, events={events}, format={payload_format}",
    )

    handler = (
        f"🪝 WEBHOOK HANDLER DESIGN\n"
        f"{'═' * 60}\n\n"
        f"**Source Platform:** {source_platform}\n"
        f"**Payload Format:** {payload_format}\n"
        f"**Events Handled:** {', '.join(events)}\n\n"
        f"**Endpoint Specification:**\n"
        f"  POST /webhooks/{source_platform.lower().replace(' ', '-')}\n"
        f"  Content-Type: application/{payload_format}\n"
        f"  Headers: X-Signature (HMAC verification)\n\n"
        f"**Processing Flow:**\n"
        f"  1. Receive → Verify signature → Respond 200 immediately.\n"
        f"  2. Enqueue payload for async processing.\n"
        f"  3. Route by event type:\n"
    )

    for event in events:
        handler += f"     • {event} → Handle and log.\n"

    handler += (
        f"\n**Payload Schema:**\n"
        f"  {{\n"
        f"    \"event\": \"<event_type>\",\n"
        f"    \"timestamp\": \"<ISO 8601>\",\n"
        f"    \"data\": {{ ... }}\n"
        f"  }}\n\n"
        f"**Retry Strategy:**\n"
        f"  • Idempotency key: Use event ID to deduplicate.\n"
        f"  • Retry: Exponential backoff (1s, 5s, 30s, 5m) up to 5 attempts.\n"
        f"  • Dead-letter after max retries for manual review.\n\n"
        f"**Security:**\n"
        f"  • HMAC signature verification on every request.\n"
        f"  • IP allowlisting for {source_platform} if supported.\n"
        f"  • TLS required; reject plain HTTP.\n"
        f"{'═' * 60}"
    )

    return handler


async def design_data_sync(
    systems: Annotated[str, "Comma-separated list of systems to synchronize"],
    sync_frequency: Annotated[str, "Sync frequency: real-time, hourly, daily"] = "real-time",
    conflict_resolution: Annotated[str, "Conflict strategy: last-write-wins, source-priority, manual-review"] = "last-write-wins",
) -> str:
    """
    Design multi-system data synchronization strategy.
    Returns sync topology, conflict handling, and error recovery.
    """
    system_list = [s.strip() for s in systems.split(",") if s.strip()]

    log_action(
        "EnterpriseAgent",
        "design_data_sync",
        f"systems={system_list}, freq={sync_frequency}, conflict={conflict_resolution}",
    )

    sync = (
        f"🔄 DATA SYNCHRONIZATION DESIGN\n"
        f"{'═' * 60}\n\n"
        f"**Systems:** {', '.join(system_list)}\n"
        f"**Frequency:** {sync_frequency}\n"
        f"**Conflict Resolution:** {conflict_resolution}\n\n"
        f"**Sync Topology:**\n"
        f"  Hub-and-spoke with a central canonical data store.\n\n"
    )

    for system in system_list:
        sync += f"    {system} ⇄ [Central Hub]\n"

    sync += (
        f"\n**Conflict Handling ({conflict_resolution}):**\n"
    )

    if conflict_resolution == "last-write-wins":
        sync += "  → Use timestamps to resolve conflicts; latest write takes precedence.\n"
    elif conflict_resolution == "source-priority":
        sync += "  → Designate a primary source of truth; other systems yield on conflict.\n"
    else:
        sync += "  → Flag conflicts for manual review; hold changes in quarantine queue.\n"

    sync += (
        f"\n**Error Recovery:**\n"
        f"  • Change data capture (CDC) logs for replay.\n"
        f"  • Checkpoint-based recovery to resume from last known good state.\n"
        f"  • Alerting on sync lag exceeding thresholds.\n"
        f"  • Reconciliation job runs daily to detect drift.\n\n"
        f"**Monitoring:**\n"
        f"  • Sync latency per system pair.\n"
        f"  • Conflict rate and resolution outcomes.\n"
        f"  • Error/retry counts with dead-letter metrics.\n"
        f"{'═' * 60}"
    )

    return sync


async def create_integration_checklist(
    integration_name: Annotated[str, "Name of the integration project"],
    systems_involved: Annotated[str, "Comma-separated list of systems involved"],
    compliance_requirements: Annotated[str, "Compliance standards to meet (e.g., SOC2, HIPAA)"] = "",
) -> str:
    """
    Create an enterprise integration readiness checklist.
    Returns a checklist covering security, performance, monitoring, and compliance.
    """
    systems = [s.strip() for s in systems_involved.split(",") if s.strip()]

    log_action(
        "EnterpriseAgent",
        "create_integration_checklist",
        f"name={integration_name}, systems={systems}, compliance={compliance_requirements}",
    )

    checklist = (
        f"✅ INTEGRATION READINESS CHECKLIST\n"
        f"{'═' * 60}\n\n"
        f"**Integration:** {integration_name}\n"
        f"**Systems:** {', '.join(systems)}\n"
    )

    if compliance_requirements:
        checklist += f"**Compliance:** {compliance_requirements}\n"

    checklist += (
        f"\n**Security:**\n"
        f"  [ ] Authentication configured (OAuth 2.0 / API keys / mTLS)\n"
        f"  [ ] Secrets stored in vault (Key Vault / Secrets Manager)\n"
        f"  [ ] Data encrypted in transit (TLS 1.2+)\n"
        f"  [ ] Data encrypted at rest where required\n"
        f"  [ ] Least-privilege access for service accounts\n"
        f"  [ ] Input validation and sanitization\n\n"
        f"**Performance:**\n"
        f"  [ ] Load tested at 2x expected peak volume\n"
        f"  [ ] Latency SLAs defined and achievable\n"
        f"  [ ] Rate limiting configured on both sides\n"
        f"  [ ] Connection pooling and timeout settings tuned\n"
        f"  [ ] Backpressure handling in place\n\n"
        f"**Reliability:**\n"
        f"  [ ] Retry logic with exponential backoff\n"
        f"  [ ] Dead-letter queue for unprocessable messages\n"
        f"  [ ] Circuit breaker for downstream failures\n"
        f"  [ ] Idempotent operations (safe to retry)\n"
        f"  [ ] Rollback / undo capability documented\n\n"
        f"**Monitoring & Observability:**\n"
        f"  [ ] Health check endpoint for each component\n"
        f"  [ ] Structured logging with correlation IDs\n"
        f"  [ ] Dashboard for throughput, latency, error rate\n"
        f"  [ ] Alerting on SLA breaches and error spikes\n"
        f"  [ ] Audit trail for all data exchanges\n\n"
        f"**Documentation:**\n"
        f"  [ ] API contracts versioned and published\n"
        f"  [ ] Runbook for common failure scenarios\n"
        f"  [ ] Data flow diagram reviewed and approved\n"
        f"  [ ] Disaster recovery procedure documented\n"
    )

    if compliance_requirements:
        checklist += (
            f"\n**Compliance ({compliance_requirements}):**\n"
            f"  [ ] Data handling meets regulatory requirements\n"
            f"  [ ] Consent and data subject rights supported\n"
            f"  [ ] Audit logs retained per policy\n"
            f"  [ ] Third-party vendor assessment completed\n"
        )

    checklist += f"\n{'═' * 60}"
    return checklist


# List of tools to register with the enterprise agent
ENTERPRISE_TOOLS = [
    design_integration,
    generate_api_mapping,
    create_webhook_handler,
    design_data_sync,
    create_integration_checklist,
] + list(MCP_DOCS_TOOLS) + list(MCP_GITHUB_TOOLS) + list(MCP_CONTEXT7_TOOLS) + list(MCP_FILESYSTEM_TOOLS) + list(RAG_TOOLS)
