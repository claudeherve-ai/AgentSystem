"""
AgentSystem — Backend Architect Agent.

Scalable system design, database architecture, API development,
and cloud infrastructure specialist.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action
from tools.mcp_tools import MCP_CONTEXT7_TOOLS, MCP_FILESYSTEM_TOOLS

logger = logging.getLogger(__name__)


async def design_system_architecture(
    system_name: Annotated[str, "Name of the system to design"],
    requirements: Annotated[str, "Functional and non-functional requirements"],
    architecture_pattern: Annotated[str, "Pattern: microservices, monolith, serverless, or hybrid"] = "microservices",
    expected_scale: Annotated[str, "Expected scale: requests/sec, users, data volume"] = "",
) -> str:
    """Design a system architecture with service decomposition, data flow, and infrastructure."""
    log_action("BackendArchitectAgent", "design_architecture", f"system={system_name}, pattern={architecture_pattern}")

    return (
        f"SYSTEM ARCHITECTURE: {system_name}\n{'=' * 60}\n\n"
        f"Pattern:  {architecture_pattern}\n"
        f"Scale:    {expected_scale or 'TBD'}\n\n"
        f"REQUIREMENTS\n{'─' * 60}\n  {requirements[:400]}\n\n"
        f"SERVICE DECOMPOSITION\n{'─' * 60}\n"
        f"  API Gateway      -> Auth, rate limiting, routing\n"
        f"  User Service     -> Authentication, profiles, RBAC\n"
        f"  Core Service     -> Business logic, domain operations\n"
        f"  Data Service     -> Persistence, caching, search\n"
        f"  Event Bus        -> Async messaging, event sourcing\n"
        f"  Notification Svc -> Email, push, webhooks\n\n"
        f"DATA FLOW\n{'─' * 60}\n"
        f"  Client -> API Gateway -> Service -> DB/Cache\n"
        f"  Service -> Event Bus -> Consumer Services\n\n"
        f"NON-FUNCTIONAL REQUIREMENTS\n{'─' * 60}\n"
        f"  Availability:  99.9% (8.76h downtime/year)\n"
        f"  Latency:       P95 < 200ms\n"
        f"  Throughput:    [Based on scale estimate]\n"
        f"  Security:      Zero-trust, encryption at rest/transit\n"
        f"  Observability: Structured logs, metrics, traces\n\n"
        f"TRADE-OFFS\n"
        f"  [Consistency vs. availability, cost vs. performance]\n"
    )


async def design_database_schema(
    domain: Annotated[str, "Business domain or data model description"],
    key_entities: Annotated[str, "Comma-separated list of key entities"],
    database_type: Annotated[str, "DB type: postgresql, mysql, mongodb, dynamodb, or multi"] = "postgresql",
) -> str:
    """Design a database schema with tables, indexes, and query patterns."""
    log_action("BackendArchitectAgent", "design_schema", f"domain={domain[:60]}, db={database_type}")
    entities = [e.strip() for e in key_entities.split(",")]

    result = (
        f"DATABASE SCHEMA DESIGN\n{'=' * 60}\n\n"
        f"Domain:   {domain}\n"
        f"Database: {database_type}\n"
        f"Entities: {', '.join(entities)}\n\n"
        f"ENTITY RELATIONSHIP\n{'─' * 60}\n"
    )
    for entity in entities:
        result += (
            f"\n  {entity.upper()}\n"
            f"    id          UUID PRIMARY KEY\n"
            f"    created_at  TIMESTAMP WITH TIME ZONE\n"
            f"    updated_at  TIMESTAMP WITH TIME ZONE\n"
            f"    [domain-specific columns]\n"
        )

    result += (
        f"\nINDEXING STRATEGY\n{'─' * 60}\n"
        f"  - Primary keys on all tables (UUID)\n"
        f"  - Covering indexes for frequent query patterns\n"
        f"  - Partial indexes for filtered queries\n"
        f"  - Full-text search indexes where needed\n\n"
        f"PERFORMANCE TARGETS\n"
        f"  - Query P95: < 100ms\n"
        f"  - Write P95: < 50ms\n"
        f"  - Connection pooling: pgbouncer or equivalent\n"
    )
    return result


async def design_api(
    api_name: Annotated[str, "API name or service name"],
    resources: Annotated[str, "Comma-separated list of API resources/endpoints"],
    api_style: Annotated[str, "Style: REST, GraphQL, gRPC, or hybrid"] = "REST",
    auth_method: Annotated[str, "Auth: JWT, OAuth2, API-key, or mTLS"] = "JWT",
) -> str:
    """Design an API architecture with endpoints, auth, rate limiting, and error handling."""
    log_action("BackendArchitectAgent", "design_api", f"api={api_name}, style={api_style}")

    return (
        f"API DESIGN: {api_name}\n{'=' * 60}\n\n"
        f"Style:  {api_style}\n"
        f"Auth:   {auth_method}\n\n"
        f"ENDPOINTS\n{'─' * 60}\n"
        f"  Resources: {resources}\n\n"
        f"  Each resource follows:\n"
        f"    GET    /api/v1/{{resource}}      - List (paginated)\n"
        f"    GET    /api/v1/{{resource}}/{{id}} - Get by ID\n"
        f"    POST   /api/v1/{{resource}}      - Create\n"
        f"    PUT    /api/v1/{{resource}}/{{id}} - Update\n"
        f"    DELETE /api/v1/{{resource}}/{{id}} - Delete\n\n"
        f"CROSS-CUTTING\n{'─' * 60}\n"
        f"  Rate Limiting:   100 req/min per client\n"
        f"  Pagination:      cursor-based (offset for simple cases)\n"
        f"  Error Format:    {{code, message, details, request_id}}\n"
        f"  Versioning:      URL path (/v1/, /v2/)\n"
        f"  CORS:            Whitelist-based\n"
        f"  Security Headers: Helmet defaults\n\n"
        f"OBSERVABILITY\n"
        f"  - Request ID on every response\n"
        f"  - Structured JSON logging\n"
        f"  - Metrics: latency, error rate, throughput\n"
    )


BACKENDARCHITECT_TOOLS = [design_system_architecture, design_database_schema, design_api] + list(MCP_CONTEXT7_TOOLS) + list(MCP_FILESYSTEM_TOOLS)
