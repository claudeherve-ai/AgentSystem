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
from tools.compute import design_architecture, design_schema
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

    combined = requirements
    if expected_scale:
        combined = f"{requirements}\n\nExpected scale: {expected_scale}"
    pattern = "" if architecture_pattern.lower() == "hybrid" else architecture_pattern
    result = design_architecture(system_name, combined, pattern)
    return result.render()


async def design_database_schema(
    domain: Annotated[str, "Business domain or data model description"],
    entities: Annotated[
        str,
        (
            "Entity specification. Accepts a rich grammar (mix freely, comma- or "
            "newline-separated). "
            "Bare names: 'users, orders, products'. "
            "Typed fields: 'User(name:str, email:str unique, age:int?)' where "
            "':type' sets the column type, 'unique' adds a UNIQUE constraint, and a "
            "trailing '?' marks the column nullable (default NOT NULL). "
            "Foreign keys: a '<table>_id' field (e.g. 'Order(total:decimal, user_id)') "
            "becomes a real FK when the referenced table is present, and inherits the "
            "referenced primary key's type automatically. "
            "Types: int, bigint, str, text, bool, float, decimal, date, datetime, "
            "uuid, json. Every table auto-gets an 'id' primary key plus created_at / "
            "updated_at unless you supply your own 'id' or 'pk' column. "
            "Prefer the rich grammar to get FK-correct, multi-column DDL instead of "
            "id-only stub tables."
        ),
    ],
    database_type: Annotated[str, "DB type: postgresql, mysql, sqlite, mongodb, dynamodb, or multi"] = "postgresql",
) -> str:
    """Design a runnable database schema from an entity specification.

    Emits real CREATE TABLE DDL for the chosen SQL dialect plus a Mermaid
    erDiagram for SQL targets, or a document-model sketch for NoSQL targets
    (mongodb / dynamodb). Pass the full entity grammar — typed fields,
    'unique', nullable '?', and '<table>_id' foreign keys — to get rich,
    FK-correct schemas rather than id-only stub tables.

    Examples of the ``entities`` argument::

        users, orders, products
        User(name:str, email:str unique, age:int?), Order(total:decimal, status:str, user_id)
    """
    log_action("BackendArchitectAgent", "design_schema", f"domain={domain[:60]}, db={database_type}")
    result = design_schema(domain, entities, database_type)
    return result.render()


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
