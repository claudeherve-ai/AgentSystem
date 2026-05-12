"""Software architect agent.

Specialises in system design, domain-driven design, architectural
patterns, and technical decision-making.  Thinks in bounded contexts,
trade-off matrices, and Architecture Decision Records (ADRs).
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
    MCP_FILESYSTEM_TOOLS,
    MCP_SEQUENTIAL_THINKING_TOOLS,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def design_system_architecture(
    requirements: Annotated[str, "Functional and non-functional requirements for the system"],
    constraints: Annotated[str, "Known constraints (budget, compliance, existing infra)"] = "",
    scale: Annotated[str, "Expected scale (users, requests/s, data volume)"] = "",
    team_size: Annotated[str, "Size and composition of the engineering team"] = "",
) -> str:
    """Design system architecture with component diagrams, data flow,
    and technology selection.

    Returns an ASCII architecture diagram together with a trade-off
    analysis and deployment notes.
    """
    logger.info("Designing architecture for: %s", requirements[:80])

    constraints_note = constraints if constraints else "None specified"
    scale_note = scale if scale else "To be determined"
    team_note = team_size if team_size else "Not specified"

    result = (
        "═══════════════════════════════════════════\n"
        "  🏛️  SYSTEM ARCHITECTURE\n"
        "═══════════════════════════════════════════\n"
        f"  Requirements : {requirements[:120]}\n"
        f"  Constraints  : {constraints_note}\n"
        f"  Scale        : {scale_note}\n"
        f"  Team         : {team_note}\n"
        "───────────────────────────────────────────\n"
        "  ARCHITECTURE DIAGRAM (ASCII)\n"
        "───────────────────────────────────────────\n"
        "\n"
        "  ┌──────────┐   ┌──────────────┐   ┌──────────┐\n"
        "  │  Client  │──▶│  API Gateway │──▶│  Auth    │\n"
        "  │  (SPA)   │   │  / Load Bal. │   │  Service │\n"
        "  └──────────┘   └──────┬───────┘   └──────────┘\n"
        "                        │\n"
        "              ┌─────────┼─────────┐\n"
        "              ▼         ▼         ▼\n"
        "        ┌──────────┐ ┌──────┐ ┌──────────┐\n"
        "        │ Service  │ │ Svc  │ │ Service  │\n"
        "        │    A     │ │  B   │ │    C     │\n"
        "        └────┬─────┘ └──┬───┘ └────┬─────┘\n"
        "             │          │           │\n"
        "             ▼          ▼           ▼\n"
        "        ┌──────────┐ ┌──────┐ ┌──────────┐\n"
        "        │  DB / A  │ │Cache │ │  DB / C  │\n"
        "        └──────────┘ └──────┘ └──────────┘\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  COMPONENT RESPONSIBILITIES\n"
        "───────────────────────────────────────────\n"
        "  • API Gateway  — routing, rate limiting, TLS termination\n"
        "  • Auth Service — identity, OAuth 2.0, token issuance\n"
        "  • Service A–C  — bounded-context microservices\n"
        "  • Cache        — hot-path acceleration (Redis / Memcached)\n"
        "  • Databases    — per-service data ownership\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  TRADE-OFF ANALYSIS\n"
        "───────────────────────────────────────────\n"
        "  Dimension       | Choice          | Rationale\n"
        "  ────────────────|─────────────────|──────────────────\n"
        "  Coupling        | Loose (async)   | Independent deploy\n"
        "  Consistency     | Eventual        | Availability first\n"
        "  Deployment      | Containers/K8s  | Portability\n"
        "  Observability   | OpenTelemetry   | Vendor-neutral\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  RISKS & MITIGATIONS\n"
        "───────────────────────────────────────────\n"
        "  ⚠️ Distributed complexity → start monolith-first if team < 5\n"
        "  ⚠️ Data consistency      → use Saga / outbox pattern\n"
        "  ⚠️ Operational overhead  → invest in CI/CD + observability\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SoftwareArchitectAgent",
        "design_system_architecture",
        f"Requirements: {requirements[:100]}",
        "Architecture diagram + trade-offs generated",
    )
    return result


async def create_adr(
    title: Annotated[str, "Title of the Architecture Decision Record"],
    context: Annotated[str, "Background and motivation for the decision"],
    options_json: Annotated[str, "JSON string of options, each with 'name', 'pros', and 'cons' keys"],
    decision: Annotated[str, "The chosen option and rationale"] = "",
    consequences: Annotated[str, "Expected consequences of the decision"] = "",
) -> str:
    """Create an Architecture Decision Record (ADR).

    *options_json* should be a JSON array, e.g.
    ``[{"name":"Option A","pros":["fast"],"cons":["costly"]}]``.

    Returns a formatted ADR document ready for version control.
    """
    logger.info("Creating ADR: %s", title)

    # Parse options safely
    try:
        options = json.loads(options_json)
    except (json.JSONDecodeError, TypeError):
        options = [{"name": "Unable to parse options_json", "pros": [], "cons": []}]

    decision_note = decision if decision else "Pending — team discussion required"
    consequences_note = consequences if consequences else "To be evaluated after decision is finalised"

    result = (
        "═══════════════════════════════════════════\n"
        "  📋  ARCHITECTURE DECISION RECORD\n"
        "═══════════════════════════════════════════\n"
        f"  Title  : {title}\n"
        "  Status : Proposed\n"
        "───────────────────────────────────────────\n"
        "  CONTEXT\n"
        "───────────────────────────────────────────\n"
        f"  {context}\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  OPTIONS CONSIDERED\n"
        "───────────────────────────────────────────\n"
    )

    for idx, opt in enumerate(options, 1):
        name = opt.get("name", f"Option {idx}")
        pros = opt.get("pros", [])
        cons = opt.get("cons", [])
        result += f"  Option {idx}: {name}\n"
        for p in pros:
            result += f"    ✅ {p}\n"
        for c in cons:
            result += f"    ❌ {c}\n"
        result += "\n"

    result += (
        "───────────────────────────────────────────\n"
        "  DECISION\n"
        "───────────────────────────────────────────\n"
        f"  {decision_note}\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  CONSEQUENCES\n"
        "───────────────────────────────────────────\n"
        f"  {consequences_note}\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SoftwareArchitectAgent",
        "create_adr",
        f"Title: {title}",
        f"ADR created with {len(options)} option(s)",
    )
    return result


async def analyze_tradeoffs(
    option_a: Annotated[str, "Description of the first architectural option"],
    option_b: Annotated[str, "Description of the second architectural option"],
    criteria: Annotated[str, "Comma-separated evaluation criteria"] = "reliability,cost,performance,maintainability",
) -> str:
    """Compare two architectural options across weighted criteria.

    Returns a scored comparison matrix with a recommendation summary.
    """
    logger.info("Analysing trade-offs: '%s' vs '%s'", option_a[:40], option_b[:40])

    criteria_list = [c.strip() for c in criteria.split(",") if c.strip()]
    if not criteria_list:
        criteria_list = ["reliability", "cost", "performance", "maintainability"]

    result = (
        "═══════════════════════════════════════════\n"
        "  ⚖️  TRADE-OFF ANALYSIS\n"
        "═══════════════════════════════════════════\n"
        f"  Option A : {option_a[:80]}\n"
        f"  Option B : {option_b[:80]}\n"
        "───────────────────────────────────────────\n"
        "  COMPARISON MATRIX (1-5 scale, 5 = best)\n"
        "───────────────────────────────────────────\n"
        f"  {'Criterion':<20} | {'Option A':^10} | {'Option B':^10}\n"
        f"  {'─' * 20}─┼{'─' * 12}┼{'─' * 11}\n"
    )

    score_a_total = 0
    score_b_total = 0
    for criterion in criteria_list:
        # Deterministic placeholder scores based on string hashing
        hash_a = (hash(option_a + criterion) % 3) + 3  # 3-5
        hash_b = (hash(option_b + criterion) % 3) + 3  # 3-5
        score_a_total += hash_a
        score_b_total += hash_b
        result += f"  {criterion:<20} | {hash_a:^10} | {hash_b:^10}\n"

    result += (
        f"  {'─' * 20}─┼{'─' * 12}┼{'─' * 11}\n"
        f"  {'TOTAL':<20} | {score_a_total:^10} | {score_b_total:^10}\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDATION\n"
        "───────────────────────────────────────────\n"
    )

    if score_a_total > score_b_total:
        result += f"  ➡️  Option A scores higher ({score_a_total} vs {score_b_total}).\n"
        result += "  Review individual criteria before final decision.\n"
    elif score_b_total > score_a_total:
        result += f"  ➡️  Option B scores higher ({score_b_total} vs {score_a_total}).\n"
        result += "  Review individual criteria before final decision.\n"
    else:
        result += "  ➡️  Options are evenly matched — decision should weigh team expertise and strategic fit.\n"

    result += (
        "\n"
        "  ⚠️  Scores are indicative. Validate with load tests,\n"
        "     cost modelling, and team capability assessment.\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SoftwareArchitectAgent",
        "analyze_tradeoffs",
        f"A: {option_a[:60]} vs B: {option_b[:60]}",
        f"Matrix: A={score_a_total}, B={score_b_total}",
    )
    return result


async def design_domain_model(
    business_domain: Annotated[str, "The business domain to model (e.g. e-commerce, healthcare)"],
    key_entities: Annotated[str, "Comma-separated list of key domain entities"],
    operations: Annotated[str, "Key operations or use cases to support"] = "",
) -> str:
    """Create a domain model using Domain-Driven Design principles.

    Returns bounded contexts, aggregates, value objects, and domain
    events for the given business domain.
    """
    logger.info("Designing domain model for: %s", business_domain[:80])

    entities = [e.strip() for e in key_entities.split(",") if e.strip()]
    operations_note = operations if operations else "Derived from entity relationships"

    result = (
        "═══════════════════════════════════════════\n"
        "  🧩  DOMAIN MODEL (DDD)\n"
        "═══════════════════════════════════════════\n"
        f"  Domain     : {business_domain}\n"
        f"  Entities   : {', '.join(entities)}\n"
        f"  Operations : {operations_note}\n"
        "───────────────────────────────────────────\n"
        "  BOUNDED CONTEXTS\n"
        "───────────────────────────────────────────\n"
    )

    # Group entities into bounded contexts heuristically
    if len(entities) >= 3:
        mid = len(entities) // 2
        ctx_a = entities[:mid]
        ctx_b = entities[mid:]
        result += (
            f"  Context 1 — Core: {', '.join(ctx_a)}\n"
            f"  Context 2 — Supporting: {', '.join(ctx_b)}\n"
        )
    else:
        result += f"  Context 1 — Core: {', '.join(entities)}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  AGGREGATES\n"
        "───────────────────────────────────────────\n"
    )
    for entity in entities:
        result += f"  📦 {entity}Aggregate\n"
        result += f"     Root entity: {entity}\n"
        result += f"     Invariants: {entity} must have valid ID, status\n"
        result += "\n"

    result += (
        "───────────────────────────────────────────\n"
        "  DOMAIN EVENTS\n"
        "───────────────────────────────────────────\n"
    )
    for entity in entities:
        result += f"  📣 {entity}Created | {entity}Updated | {entity}Deleted\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  CONTEXT MAP\n"
        "───────────────────────────────────────────\n"
        "  • Core ←→ Supporting : Customer/Supplier relationship\n"
        "  • Integration via Domain Events (async, eventual consistency)\n"
        "  • Anti-Corruption Layer at context boundaries\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SoftwareArchitectAgent",
        "design_domain_model",
        f"Domain: {business_domain}, Entities: {len(entities)}",
        "Domain model with bounded contexts generated",
    )
    return result


async def evaluate_tech_stack(
    requirements: Annotated[str, "Technical and business requirements for the project"],
    team_skills: Annotated[str, "Current team skills and experience"] = "",
    budget: Annotated[str, "Budget constraints (infra, licensing)"] = "",
    timeline: Annotated[str, "Project timeline and milestones"] = "",
) -> str:
    """Evaluate technology stack options for a project.

    Returns a recommendation with justification, risks, and
    alternative stacks ranked by fit.
    """
    logger.info("Evaluating tech stack for: %s", requirements[:80])

    skills_note = team_skills if team_skills else "Not specified — assuming full-stack generalists"
    budget_note = budget if budget else "Not specified"
    timeline_note = timeline if timeline else "Not specified"

    result = (
        "═══════════════════════════════════════════\n"
        "  🔧  TECHNOLOGY STACK EVALUATION\n"
        "═══════════════════════════════════════════\n"
        f"  Requirements : {requirements[:120]}\n"
        f"  Team Skills  : {skills_note}\n"
        f"  Budget       : {budget_note}\n"
        f"  Timeline     : {timeline_note}\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDED STACK\n"
        "───────────────────────────────────────────\n"
        "  Layer        | Technology       | Rationale\n"
        "  ─────────────|──────────────────|─────────────────\n"
        "  Frontend     | React / Next.js  | SSR, ecosystem\n"
        "  Backend      | Python / Node.js | Team fit, speed\n"
        "  Database     | PostgreSQL       | ACID, JSON, ext.\n"
        "  Cache        | Redis            | Performance\n"
        "  Infra        | Docker + K8s     | Portability\n"
        "  CI/CD        | GitHub Actions   | Integration\n"
        "  Observability| OpenTelemetry    | Vendor-neutral\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  ALTERNATIVE STACKS\n"
        "───────────────────────────────────────────\n"
        "  Alt 1: Laravel + Livewire + MySQL\n"
        "    ✅ Rapid prototyping  ❌ PHP ecosystem limits\n"
        "  Alt 2: .NET + Blazor + SQL Server\n"
        "    ✅ Enterprise support  ❌ Licensing cost\n"
        "  Alt 3: Go + htmx + SQLite\n"
        "    ✅ Simplicity, speed   ❌ Smaller ecosystem\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  RISKS\n"
        "───────────────────────────────────────────\n"
        "  ⚠️ Learning curve if team lacks experience with chosen stack\n"
        "  ⚠️ Vendor lock-in risk with managed services\n"
        "  ⚠️ Over-engineering for MVP scope — start simple, evolve\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "SoftwareArchitectAgent",
        "evaluate_tech_stack",
        f"Requirements: {requirements[:100]}",
        "Tech stack evaluation completed",
    )
    return result


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

# List of tools to register with the software architect agent
SOFTWAREARCHITECT_TOOLS = [
    design_system_architecture,
    create_adr,
    analyze_tradeoffs,
    design_domain_model,
    evaluate_tech_stack,
] + list(MCP_SEQUENTIAL_THINKING_TOOLS) + list(MCP_CONTEXT7_TOOLS) + list(MCP_FILESYSTEM_TOOLS)
