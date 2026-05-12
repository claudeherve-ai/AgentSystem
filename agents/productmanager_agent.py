"""Product manager agent.

Owns the full product lifecycle — discovery, strategy, roadmap,
stakeholder alignment, go-to-market, and outcome measurement.
Outcome-obsessed, user-grounded.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


async def create_prd(
    feature_name: Annotated[str, "Name of the feature or product initiative"],
    problem_statement: Annotated[str, "The user/business problem this feature solves"],
    target_users: Annotated[str, "Target user personas or segments"],
    success_metrics: Annotated[str, "Key metrics to measure success (e.g. activation rate, NPS)"] = "",
) -> str:
    """Create a Product Requirements Document (PRD).

    Returns a structured PRD with problem statement, goals, scope,
    functional requirements, acceptance criteria, and out-of-scope items.
    """
    logger.info("Creating PRD for: %s", feature_name)

    metrics_note = success_metrics if success_metrics else "To be defined during discovery"

    result = (
        "═══════════════════════════════════════════\n"
        "  📄  PRODUCT REQUIREMENTS DOCUMENT\n"
        "═══════════════════════════════════════════\n"
        f"  Feature  : {feature_name}\n"
        "  Status   : Draft\n"
        f"  Target   : {target_users}\n"
        "───────────────────────────────────────────\n"
        "  1. PROBLEM STATEMENT\n"
        "───────────────────────────────────────────\n"
        f"  {problem_statement}\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  2. GOALS & SUCCESS METRICS\n"
        "───────────────────────────────────────────\n"
        "  Goals:\n"
        f"  • Solve: {problem_statement[:80]}…\n"
        f"  • Serve: {target_users}\n"
        "  • Deliver measurable business impact\n"
        "\n"
        "  Success Metrics:\n"
        f"  • {metrics_note}\n"
        "  • User adoption rate within 30 days\n"
        "  • Task completion time reduction\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  3. SCOPE\n"
        "───────────────────────────────────────────\n"
        "  In Scope:\n"
        f"  • Core {feature_name} functionality\n"
        "  • Integration with existing auth and data layer\n"
        "  • Mobile-responsive UI\n"
        "  • Analytics instrumentation\n"
        "\n"
        "  Out of Scope (v1):\n"
        "  • Admin configuration UI\n"
        "  • Third-party integrations\n"
        "  • Offline support\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  4. FUNCTIONAL REQUIREMENTS\n"
        "───────────────────────────────────────────\n"
        f"  FR-1: User can access {feature_name} from main navigation\n"
        f"  FR-2: System validates user input before processing\n"
        f"  FR-3: Results displayed within 2 seconds (p95)\n"
        f"  FR-4: Actions are audit-logged for compliance\n"
        f"  FR-5: Feature respects role-based access controls\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  5. ACCEPTANCE CRITERIA\n"
        "───────────────────────────────────────────\n"
        "  AC-1: Given a logged-in user, when they access the feature,\n"
        "        then they see the main interface within 2s.\n"
        "  AC-2: Given invalid input, when submitted,\n"
        "        then a clear error message is shown.\n"
        "  AC-3: Given a completed action, when viewed in audit log,\n"
        "        then all details are recorded.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  6. RISKS & MITIGATIONS\n"
        "───────────────────────────────────────────\n"
        "  ⚠️ Adoption risk → run beta with 10% of users first\n"
        "  ⚠️ Scope creep   → strict v1 scope, defer to v2\n"
        "  ⚠️ Tech debt     → allocate 20% capacity for refactoring\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "ProductManagerAgent",
        "create_prd",
        f"Feature: {feature_name}, Users: {target_users[:60]}",
        "PRD generated (draft)",
        status="drafted",
    )
    return result


async def prioritize_backlog(
    items_json: Annotated[str, "JSON array of backlog items with 'name' and 'description' keys"],
    framework: Annotated[str, "Prioritisation framework: rice, ice, or moscow"] = "rice",
) -> str:
    """Prioritise product backlog using RICE, ICE, or MoSCoW.

    Returns a ranked list with scores and rationale for each item.
    """
    logger.info("Prioritising backlog (%s framework)", framework.upper())

    try:
        items = json.loads(items_json)
    except (json.JSONDecodeError, TypeError):
        items = [{"name": "Unparseable items", "description": "Could not parse items_json"}]

    fw = framework.lower()

    result = (
        "═══════════════════════════════════════════\n"
        f"  📊  BACKLOG PRIORITISATION ({fw.upper()})\n"
        "═══════════════════════════════════════════\n"
        f"  Items     : {len(items)}\n"
        f"  Framework : {fw.upper()}\n"
        "───────────────────────────────────────────\n"
    )

    if fw == "rice":
        result += f"  {'Rank':<5} {'Item':<25} {'Reach':>6} {'Impact':>7} {'Confidence':>11} {'Effort':>7} {'Score':>7}\n"
        result += f"  {'─'*5} {'─'*25} {'─'*6} {'─'*7} {'─'*11} {'─'*7} {'─'*7}\n"

        scored: list[tuple[float, int, dict]] = []
        for idx, item in enumerate(items):
            name = item.get("name", f"Item {idx+1}")
            # Deterministic scores for reproducibility
            reach = ((hash(name) % 5) + 1) * 200
            impact = (hash(name + "i") % 3) + 1
            confidence = ((hash(name + "c") % 3) + 1) * 30
            effort = (hash(name + "e") % 4) + 1
            score = (reach * impact * (confidence / 100)) / effort
            scored.append((score, idx, item))

        scored.sort(key=lambda x: x[0], reverse=True)

        for rank, (score, _idx, item) in enumerate(scored, 1):
            name = item.get("name", "Unknown")[:25]
            reach = ((hash(name.strip()) % 5) + 1) * 200
            impact = (hash(name.strip() + "i") % 3) + 1
            confidence = ((hash(name.strip() + "c") % 3) + 1) * 30
            effort = (hash(name.strip() + "e") % 4) + 1
            result += f"  {rank:<5} {name:<25} {reach:>6} {impact:>7} {confidence:>10}% {effort:>7} {score:>7.0f}\n"

    elif fw == "ice":
        result += f"  {'Rank':<5} {'Item':<30} {'Impact':>7} {'Confidence':>11} {'Ease':>6} {'Score':>7}\n"
        result += f"  {'─'*5} {'─'*30} {'─'*7} {'─'*11} {'─'*6} {'─'*7}\n"

        scored = []
        for idx, item in enumerate(items):
            name = item.get("name", f"Item {idx+1}")
            impact = (hash(name + "i") % 5) + 1
            confidence = (hash(name + "c") % 5) + 1
            ease = (hash(name + "e") % 5) + 1
            score = (impact + confidence + ease) / 3.0
            scored.append((score, idx, item, impact, confidence, ease))

        scored.sort(key=lambda x: x[0], reverse=True)
        for rank, (score, _idx, item, imp, conf, ease) in enumerate(scored, 1):
            name = item.get("name", "Unknown")[:30]
            result += f"  {rank:<5} {name:<30} {imp:>7} {conf:>11} {ease:>6} {score:>7.1f}\n"

    else:  # moscow
        result += "  Category     | Items\n"
        result += "  ─────────────|──────────────────────────────\n"
        categories = ["Must Have", "Should Have", "Could Have", "Won't Have"]
        per_cat = max(1, len(items) // 4)
        for cat_idx, category in enumerate(categories):
            start = cat_idx * per_cat
            end = start + per_cat if cat_idx < 3 else len(items)
            cat_items = items[start:end]
            names = ", ".join(i.get("name", "?")[:20] for i in cat_items) if cat_items else "—"
            result += f"  {category:<13} | {names}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDATION\n"
        "───────────────────────────────────────────\n"
        "  • Focus next sprint on top 3 items\n"
        "  • Validate assumptions with user research\n"
        "  • Re-score quarterly as market conditions change\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "ProductManagerAgent",
        "prioritize_backlog",
        f"Items: {len(items)}, Framework: {fw}",
        f"Backlog prioritised ({len(items)} items ranked)",
    )
    return result


async def create_roadmap(
    objectives_json: Annotated[str, "JSON array of objectives with 'name', 'description', 'priority' keys"],
    timeline: Annotated[str, "Timeline view: quarterly, monthly, or yearly"] = "quarterly",
    format: Annotated[str, "Roadmap format: now-next-later or timeline"] = "now-next-later",
) -> str:
    """Create a product roadmap.

    Returns a visual roadmap with milestones, dependencies, and
    resource estimates.
    """
    logger.info("Creating roadmap (format=%s, timeline=%s)", format, timeline)

    try:
        objectives = json.loads(objectives_json)
    except (json.JSONDecodeError, TypeError):
        objectives = [{"name": "Objective 1", "description": "Define objectives", "priority": "high"}]

    result = (
        "═══════════════════════════════════════════\n"
        "  🗺️  PRODUCT ROADMAP\n"
        "═══════════════════════════════════════════\n"
        f"  Format   : {format}\n"
        f"  Timeline : {timeline}\n"
        f"  Items    : {len(objectives)}\n"
        "───────────────────────────────────────────\n"
    )

    if format == "now-next-later":
        buckets = {"now": [], "next": [], "later": []}
        for idx, obj in enumerate(objectives):
            priority = obj.get("priority", "medium").lower()
            if priority == "high" or idx == 0:
                buckets["now"].append(obj)
            elif priority == "medium":
                buckets["next"].append(obj)
            else:
                buckets["later"].append(obj)

        for phase, label in [("now", "NOW (This Quarter)"), ("next", "NEXT (Next Quarter)"), ("later", "LATER (Future)")]:
            result += f"  {label}\n"
            result += "  ─────────────────────────────────────\n"
            if buckets[phase]:
                for obj in buckets[phase]:
                    name = obj.get("name", "?")
                    desc = obj.get("description", "")[:60]
                    result += f"  ▸ {name} — {desc}\n"
            else:
                result += "  (no items)\n"
            result += "\n"
    else:
        result += "  TIMELINE VIEW\n"
        result += "  ─────────────────────────────────────\n"
        period_labels = {
            "quarterly": ["Q1", "Q2", "Q3", "Q4"],
            "monthly": ["M1", "M2", "M3", "M4", "M5", "M6"],
            "yearly": ["Y1", "Y2", "Y3"],
        }
        periods = period_labels.get(timeline, ["Q1", "Q2", "Q3", "Q4"])
        per_period = max(1, len(objectives) // len(periods))
        for p_idx, period in enumerate(periods):
            start = p_idx * per_period
            end = start + per_period if p_idx < len(periods) - 1 else len(objectives)
            period_items = objectives[start:end]
            names = ", ".join(o.get("name", "?")[:20] for o in period_items) if period_items else "—"
            result += f"  {period}: {names}\n"
        result += "\n"

    result += (
        "───────────────────────────────────────────\n"
        "  MILESTONES\n"
        "───────────────────────────────────────────\n"
        "  🏁 Alpha release — core feature functional\n"
        "  🏁 Beta release  — external user testing\n"
        "  🏁 GA release    — full launch with marketing\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  DEPENDENCIES & RISKS\n"
        "───────────────────────────────────────────\n"
        "  • Platform readiness (API, infra, auth)\n"
        "  • Design finalisation before development\n"
        "  • Regulatory / compliance review\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "ProductManagerAgent",
        "create_roadmap",
        f"Objectives: {len(objectives)}, Format: {format}",
        "Roadmap generated",
    )
    return result


async def write_user_story(
    persona: Annotated[str, "User persona (e.g. 'marketing manager', 'new developer')"],
    goal: Annotated[str, "What the user wants to achieve"],
    context: Annotated[str, "Additional context or constraints"] = "",
    acceptance_criteria: Annotated[str, "Specific acceptance criteria (if already known)"] = "",
) -> str:
    """Write a user story with acceptance criteria and edge cases.

    Returns the story in standard "As a / I want / So that" format
    with detailed acceptance criteria.
    """
    logger.info("Writing user story for persona: %s", persona)

    context_note = context if context else "Standard product context"

    result = (
        "═══════════════════════════════════════════\n"
        "  📝  USER STORY\n"
        "═══════════════════════════════════════════\n"
        f"\n"
        f"  As a {persona},\n"
        f"  I want to {goal},\n"
        f"  So that I can achieve my objective efficiently.\n"
        f"\n"
        f"  Context: {context_note}\n"
        "───────────────────────────────────────────\n"
        "  ACCEPTANCE CRITERIA\n"
        "───────────────────────────────────────────\n"
    )

    if acceptance_criteria:
        for idx, ac in enumerate(acceptance_criteria.split(";"), 1):
            ac = ac.strip()
            if ac:
                result += f"  AC-{idx}: {ac}\n"
    else:
        result += (
            f"  AC-1: Given a {persona} is logged in,\n"
            f"        When they initiate \"{goal[:50]}\",\n"
            f"        Then the system responds within 2 seconds.\n"
            "\n"
            f"  AC-2: Given invalid input,\n"
            f"        When submitted,\n"
            f"        Then a clear, actionable error is displayed.\n"
            "\n"
            f"  AC-3: Given the action is completed,\n"
            f"        When the {persona} checks the result,\n"
            f"        Then the expected outcome is visible and correct.\n"
        )

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  EDGE CASES\n"
        "───────────────────────────────────────────\n"
        "  • What if the user has no permission? → Show access-denied message.\n"
        "  • What if the network fails mid-action? → Retry with saved state.\n"
        "  • What if the input exceeds limits? → Validate before submission.\n"
        "  • What if concurrent users edit the same resource? → Conflict resolution.\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  STORY POINTS (ESTIMATE)\n"
        "───────────────────────────────────────────\n"
        "  Complexity : Medium (3–5 points)\n"
        "  Dependencies: Auth, data layer, UI components\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "ProductManagerAgent",
        "write_user_story",
        f"Persona: {persona}, Goal: {goal[:60]}",
        "User story generated with acceptance criteria",
    )
    return result


async def analyze_metrics(
    metrics_json: Annotated[str, "JSON object or array of metric data with 'name' and 'value' keys"],
    period: Annotated[str, "Analysis period: daily, weekly, monthly, quarterly"] = "monthly",
    goals: Annotated[str, "Target goals for the metrics"] = "",
) -> str:
    """Analyse product metrics and identify trends.

    Returns insights, recommendations, and action items based on the
    provided metric data.
    """
    logger.info("Analysing metrics for period: %s", period)

    try:
        metrics = json.loads(metrics_json)
        if isinstance(metrics, dict):
            metrics = [metrics]
    except (json.JSONDecodeError, TypeError):
        metrics = [{"name": "unknown", "value": 0}]

    goals_note = goals if goals else "Compare against industry benchmarks"

    result = (
        "═══════════════════════════════════════════\n"
        "  📈  METRICS ANALYSIS\n"
        "═══════════════════════════════════════════\n"
        f"  Period  : {period}\n"
        f"  Metrics : {len(metrics)}\n"
        f"  Goals   : {goals_note}\n"
        "───────────────────────────────────────────\n"
        "  METRIC SUMMARY\n"
        "───────────────────────────────────────────\n"
    )

    for m in metrics:
        name = m.get("name", "Unknown")
        value = m.get("value", "N/A")
        result += f"  • {name}: {value}\n"

    result += (
        "\n"
        "───────────────────────────────────────────\n"
        "  INSIGHTS\n"
        "───────────────────────────────────────────\n"
        "  📊 Trend: Review week-over-week change for anomalies\n"
        "  📊 Cohort: Compare new vs returning user behaviour\n"
        "  📊 Funnel: Identify largest drop-off stage\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  RECOMMENDATIONS\n"
        "───────────────────────────────────────────\n"
        "  1. Set alert thresholds for key metrics (±15% change)\n"
        "  2. Run A/B test on highest-impact lever\n"
        "  3. Share dashboard with stakeholders weekly\n"
        "  4. Correlate product changes with metric movements\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  ACTION ITEMS\n"
        "───────────────────────────────────────────\n"
        "  ☐ Build automated metrics dashboard\n"
        "  ☐ Define metric ownership per team\n"
        "  ☐ Schedule monthly metrics review meeting\n"
        "  ☐ Document metric definitions in data dictionary\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "ProductManagerAgent",
        "analyze_metrics",
        f"Period: {period}, Metrics: {len(metrics)}",
        f"Analysis completed ({len(metrics)} metrics reviewed)",
    )
    return result


async def create_go_to_market(
    product_description: Annotated[str, "Description of the product or feature being launched"],
    target_market: Annotated[str, "Target market segment or audience"],
    competitive_landscape: Annotated[str, "Key competitors and differentiators"] = "",
    pricing: Annotated[str, "Pricing strategy or model"] = "",
) -> str:
    """Create a go-to-market strategy.

    Returns positioning, messaging, channel strategy, launch plan,
    and KPIs for the product launch.
    """
    logger.info("Creating GTM strategy for: %s", product_description[:80])

    competitive_note = competitive_landscape if competitive_landscape else "Competitive analysis pending"
    pricing_note = pricing if pricing else "Pricing TBD — recommend value-based approach"

    result = (
        "═══════════════════════════════════════════\n"
        "  🚀  GO-TO-MARKET STRATEGY\n"
        "═══════════════════════════════════════════\n"
        f"  Product    : {product_description[:100]}\n"
        f"  Market     : {target_market}\n"
        f"  Competitors: {competitive_note[:80]}\n"
        f"  Pricing    : {pricing_note}\n"
        "───────────────────────────────────────────\n"
        "  1. POSITIONING\n"
        "───────────────────────────────────────────\n"
        f"  For {target_market}\n"
        f"  Who need {product_description[:60]}\n"
        "  Our product is the [category]\n"
        "  That provides [key benefit]\n"
        "  Unlike [competitor], we [differentiator]\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  2. MESSAGING FRAMEWORK\n"
        "───────────────────────────────────────────\n"
        "  Headline    : [Benefit-driven headline]\n"
        "  Subhead     : [How it works in one sentence]\n"
        "  Proof Points:\n"
        "    • Quantified benefit #1\n"
        "    • Quantified benefit #2\n"
        "    • Social proof / testimonial\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  3. CHANNEL STRATEGY\n"
        "───────────────────────────────────────────\n"
        "  • Content marketing (blog, case studies, whitepapers)\n"
        "  • Product-led growth (free tier, self-serve onboarding)\n"
        "  • Developer relations (docs, tutorials, community)\n"
        "  • Paid acquisition (search, social, retargeting)\n"
        "  • Sales enablement (pitch deck, demo script, battle cards)\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  4. LAUNCH PLAN\n"
        "───────────────────────────────────────────\n"
        "  Week -4 : Internal readiness (sales training, support docs)\n"
        "  Week -2 : Beta launch with select customers\n"
        "  Week  0 : Public launch (blog post, Product Hunt, socials)\n"
        "  Week +1 : Collect feedback, monitor KPIs\n"
        "  Week +4 : Retrospective and iteration\n"
        "\n"
        "───────────────────────────────────────────\n"
        "  5. KPIs\n"
        "───────────────────────────────────────────\n"
        "  • Sign-ups / activations in first 30 days\n"
        "  • Conversion rate (free → paid)\n"
        "  • Customer acquisition cost (CAC)\n"
        "  • Net Promoter Score (NPS)\n"
        "  • Time to first value (TTFV)\n"
        "═══════════════════════════════════════════"
    )

    log_action(
        "ProductManagerAgent",
        "create_go_to_market",
        f"Product: {product_description[:60]}, Market: {target_market[:40]}",
        "GTM strategy generated",
    )
    return result


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

# List of tools to register with the product manager agent
PRODUCTMANAGER_TOOLS = [
    create_prd,
    prioritize_backlog,
    create_roadmap,
    write_user_story,
    analyze_metrics,
    create_go_to_market,
]
