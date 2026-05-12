"""
AgentSystem — Optimization Architect Agent.

Autonomous optimization architect — intelligent system governor for API
performance shadow-testing, cost optimization, circuit breakers, and
financial guardrails.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


async def design_optimization_strategy(
    system_description: Annotated[str, "Description of the system to optimize"],
    current_costs: Annotated[str, "Current monthly/annual cost breakdown"] = "",
    performance_baseline: Annotated[str, "Current performance metrics (latency, throughput, error rate)"] = "",
    budget_limit: Annotated[str, "Maximum budget for optimization initiatives"] = "",
) -> str:
    """Design optimization strategy with A/B testing, shadow traffic, and cost analysis."""
    logger.info("Designing optimization strategy")

    report = (
        f"🚀 OPTIMIZATION STRATEGY\n"
        f"{'═' * 65}\n\n"
        f"📋 System Overview:\n"
        f"  {system_description}\n\n"
    )

    if current_costs:
        report += f"💰 Current Cost Baseline:\n  {current_costs}\n\n"
    if performance_baseline:
        report += f"📈 Performance Baseline:\n  {performance_baseline}\n\n"
    if budget_limit:
        report += f"💳 Budget Limit: {budget_limit}\n\n"

    report += (
        f"🎯 Optimization Phases:\n"
        f"{'─' * 55}\n\n"
        f"  Phase 1: Measure & Baseline (Week 1-2)\n"
        f"  ─────────────────────────────────────\n"
        f"  • Instrument all API endpoints with latency tracking\n"
        f"  • Establish P50/P95/P99 latency baselines\n"
        f"  • Map cost-per-request for each service\n"
        f"  • Identify top-5 cost and latency hotspots\n\n"
        f"  Phase 2: Shadow Testing (Week 3-4)\n"
        f"  ─────────────────────────────────────\n"
        f"  • Deploy candidate optimizations behind feature flags\n"
        f"  • Route 5% shadow traffic to optimized paths\n"
        f"  • Compare latency, error rates, and resource usage\n"
        f"  • Grade candidates on cost, performance, reliability\n\n"
        f"  Phase 3: A/B Rollout (Week 5-6)\n"
        f"  ─────────────────────────────────────\n"
        f"  • Promote passing candidates to 50/50 A/B test\n"
        f"  • Monitor for regressions with automated rollback\n"
        f"  • Validate cost savings match projections\n\n"
        f"  Phase 4: Full Deployment (Week 7-8)\n"
        f"  ─────────────────────────────────────\n"
        f"  • Roll out winning optimizations to 100% traffic\n"
        f"  • Update circuit breaker thresholds\n"
        f"  • Document changes and update runbooks\n\n"
    )

    report += (
        f"📊 Expected Outcomes:\n"
        f"  • Latency reduction: 15-30% (P95)\n"
        f"  • Cost savings: 20-40% on compute/API spend\n"
        f"  • Reliability improvement: 99.9% → 99.95% SLA\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "OptimizationArchitectAgent",
        "design_optimization_strategy",
        f"System: {system_description[:80]}",
        "Strategy with 4 phases created",
    )
    return report


async def create_circuit_breaker(
    service_name: Annotated[str, "Name of the service to protect"],
    failure_threshold: Annotated[int, "Number of failures before circuit opens"] = 5,
    timeout_seconds: Annotated[int, "Seconds before attempting to close circuit"] = 30,
    fallback_service: Annotated[str, "Alternative service to use when circuit is open"] = "",
) -> str:
    """Design circuit breaker configuration with states, transitions, and alerting."""
    logger.info(f"Creating circuit breaker for: {service_name}")

    report = (
        f"🔌 CIRCUIT BREAKER SPECIFICATION: {service_name}\n"
        f"{'═' * 60}\n\n"
        f"⚙️ Configuration:\n"
        f"  Service:           {service_name}\n"
        f"  Failure Threshold: {failure_threshold} consecutive failures\n"
        f"  Timeout:           {timeout_seconds} seconds\n"
        f"  Fallback:          {fallback_service or 'Graceful degradation (cached response)'}\n\n"
        f"📊 State Machine:\n"
        f"  ┌─────────┐    {failure_threshold} failures    ┌──────┐\n"
        f"  │ CLOSED  │ ──────────────────→ │ OPEN │\n"
        f"  │ (normal)│ ←────────────────── │(fail)│\n"
        f"  └─────────┘    success          └──────┘\n"
        f"       ↑                              │\n"
        f"       │          {timeout_seconds}s timeout          │\n"
        f"       │         ┌───────────┐        │\n"
        f"       └──────── │ HALF-OPEN │ ←──────┘\n"
        f"     success     │  (probe)  │\n"
        f"                 └───────────┘\n\n"
        f"🔄 State Transitions:\n"
        f"  CLOSED → OPEN:\n"
        f"    Trigger: {failure_threshold} consecutive failures detected\n"
        f"    Action:  Route traffic to fallback; fire alert\n\n"
        f"  OPEN → HALF-OPEN:\n"
        f"    Trigger: {timeout_seconds}s timeout elapsed\n"
        f"    Action:  Allow single probe request through\n\n"
        f"  HALF-OPEN → CLOSED:\n"
        f"    Trigger: Probe request succeeds\n"
        f"    Action:  Resume normal traffic; clear alert\n\n"
        f"  HALF-OPEN → OPEN:\n"
        f"    Trigger: Probe request fails\n"
        f"    Action:  Reset timeout; maintain fallback\n\n"
    )

    report += (
        f"🚨 Alerting Rules:\n"
        f"  • Circuit OPEN:      P1 alert to on-call (PagerDuty/Slack)\n"
        f"  • Circuit HALF-OPEN: P3 informational notification\n"
        f"  • Circuit CLOSED:    Resolution notification\n"
        f"  • Flapping (>3 opens/hour): P2 escalation to engineering lead\n\n"
    )

    if fallback_service:
        report += (
            f"🔀 Fallback Strategy:\n"
            f"  Primary:   {service_name}\n"
            f"  Fallback:  {fallback_service}\n"
            f"  Behavior:  Transparent failover; client sees degraded but functional response\n\n"
        )

    report += f"{'═' * 60}\n"

    log_action(
        "OptimizationArchitectAgent",
        "create_circuit_breaker",
        f"Service: {service_name}",
        f"Threshold: {failure_threshold}, Timeout: {timeout_seconds}s, Fallback: {fallback_service or 'default'}",
    )
    return report


async def analyze_api_costs(
    api_usage_json: Annotated[str, "JSON array of API endpoints with fields: endpoint, calls_per_day, cost_per_call"],
    cost_per_call: Annotated[str, "Default cost per API call if not specified per endpoint"] = "",
    monthly_budget: Annotated[str, "Monthly budget limit for API costs"] = "",
) -> str:
    """Analyze API usage costs and identify optimization opportunities."""
    logger.info("Analyzing API costs")

    try:
        endpoints = json.loads(api_usage_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format for API usage data."

    if not isinstance(endpoints, list):
        return "❌ Error: api_usage_json must be a JSON array."

    default_cost = float(cost_per_call) if cost_per_call else 0.001
    budget = float(monthly_budget) if monthly_budget else 0

    report = (
        f"💰 API COST ANALYSIS\n"
        f"{'═' * 70}\n\n"
        f"  {'Endpoint':<30} {'Calls/Day':>10} {'$/Call':>8} {'$/Month':>10}\n"
        f"  {'─' * 66}\n"
    )

    total_monthly = 0.0
    endpoint_costs: list[tuple[str, float]] = []

    for ep in endpoints:
        name = ep.get("endpoint", "unknown")
        calls = int(ep.get("calls_per_day", 0))
        cpc = float(ep.get("cost_per_call", default_cost))
        monthly = calls * cpc * 30
        total_monthly += monthly
        endpoint_costs.append((name, monthly))
        report += f"  {name:<30} {calls:>10,} ${cpc:>7.4f} ${monthly:>9,.2f}\n"

    report += (
        f"  {'─' * 66}\n"
        f"  {'TOTAL':<30} {'':>10} {'':>8} ${total_monthly:>9,.2f}\n\n"
    )

    if budget:
        utilization = (total_monthly / budget * 100) if budget > 0 else 0
        status = "🟢 Under budget" if utilization < 80 else "🟡 Approaching limit" if utilization < 100 else "🔴 Over budget"
        report += (
            f"  📊 Budget Analysis:\n"
            f"    Monthly Budget:  ${budget:>10,.2f}\n"
            f"    Current Spend:   ${total_monthly:>10,.2f}\n"
            f"    Utilization:     {utilization:.1f}%\n"
            f"    Status:          {status}\n\n"
        )

    endpoint_costs.sort(key=lambda x: x[1], reverse=True)
    report += f"  🎯 Optimization Recommendations:\n"
    for name, cost in endpoint_costs[:3]:
        report += (
            f"    • {name} (${cost:,.2f}/mo)\n"
            f"      → Consider caching, batching, or rate limiting\n"
        )

    report += (
        f"\n  💡 General Savings Strategies:\n"
        f"    • Implement response caching (est. 20-30% reduction)\n"
        f"    • Batch API calls where possible (est. 15-25% reduction)\n"
        f"    • Add request deduplication (est. 5-10% reduction)\n"
        f"    • Negotiate volume pricing with providers\n"
        f"{'═' * 70}\n"
    )

    log_action(
        "OptimizationArchitectAgent",
        "analyze_api_costs",
        f"Endpoints: {len(endpoints)}",
        f"Total monthly: ${total_monthly:,.2f}, Budget: {monthly_budget or 'not set'}",
    )
    return report


async def design_shadow_test(
    production_service: Annotated[str, "Name or URL of the production service"],
    candidate_service: Annotated[str, "Name or URL of the candidate/optimized service"],
    evaluation_criteria: Annotated[str, "Criteria to evaluate: latency, accuracy, cost, error_rate"],
    traffic_percentage: Annotated[int, "Percentage of traffic to mirror to candidate"] = 5,
) -> str:
    """Design shadow testing configuration with routing rules and grading criteria."""
    logger.info(f"Designing shadow test: {production_service} vs {candidate_service}")

    criteria_list = [c.strip().lower() for c in evaluation_criteria.split(",") if c.strip()]

    report = (
        f"🔬 SHADOW TEST PLAN\n"
        f"{'═' * 60}\n\n"
        f"  Production Service:  {production_service}\n"
        f"  Candidate Service:   {candidate_service}\n"
        f"  Traffic Percentage:  {traffic_percentage}%\n\n"
        f"🔀 Traffic Routing:\n"
        f"  ┌──────────┐\n"
        f"  │ Incoming  │\n"
        f"  │ Traffic   │\n"
        f"  └─────┬────┘\n"
        f"        │\n"
        f"  ┌─────┴─────┐\n"
        f"  │  Splitter  │\n"
        f"  └──┬────┬───┘\n"
        f"     │    │\n"
        f"  {100 - traffic_percentage}% │    │ {traffic_percentage}% (mirror)\n"
        f"     │    │\n"
        f"  ┌──┴──┐ ┌─┴────────┐\n"
        f"  │Prod │ │Candidate │\n"
        f"  │(live)│ │(shadow)  │\n"
        f"  └──┬──┘ └─┬────────┘\n"
        f"     │      │\n"
        f"  Response   Discard (log only)\n\n"
    )

    report += f"📊 Evaluation Criteria & Thresholds:\n"
    criteria_thresholds = {
        "latency": ("P95 latency ≤ production P95", "Candidate must match or beat production latency"),
        "accuracy": ("Response match ≥ 99.5%", "Compare response bodies for semantic equivalence"),
        "cost": ("Cost per request ≤ 80% of production", "Minimum 20% cost reduction to justify switch"),
        "error_rate": ("Error rate ≤ production error rate", "No increase in 4xx/5xx responses"),
    }
    for criterion in criteria_list:
        threshold, description = criteria_thresholds.get(
            criterion,
            ("Custom threshold TBD", "Define acceptance criteria before test"),
        )
        report += (
            f"  • {criterion.title()}\n"
            f"    Threshold:   {threshold}\n"
            f"    Description: {description}\n"
        )
    report += "\n"

    report += (
        f"🏁 Promotion Thresholds:\n"
        f"  • Minimum test duration:  72 hours\n"
        f"  • Minimum sample size:    10,000 requests\n"
        f"  • All criteria must PASS for promotion\n"
        f"  • Any criterion FAIL triggers automatic halt\n\n"
        f"📋 Test Stages:\n"
        f"  Stage 1: {traffic_percentage}% shadow traffic (72h)\n"
        f"  Stage 2: {min(traffic_percentage * 5, 50)}% canary (48h) — if Stage 1 passes\n"
        f"  Stage 3: 100% rollout — if Stage 2 passes\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "OptimizationArchitectAgent",
        "design_shadow_test",
        f"{production_service} vs {candidate_service}",
        f"Traffic: {traffic_percentage}%, Criteria: {len(criteria_list)}",
    )
    return report


async def create_finops_dashboard(
    services_json: Annotated[str, "JSON array of services with fields: name, monthly_cost, category"],
    budget_alerts: Annotated[str, "Comma-separated budget alert thresholds in percent (e.g., 50,80,95)"] = "",
    cost_allocation: Annotated[str, "Cost allocation tags/dimensions (e.g., team, environment, project)"] = "",
) -> str:
    """Create FinOps dashboard specification with metrics, alerts, and anomaly detection."""
    logger.info("Creating FinOps dashboard specification")

    try:
        services = json.loads(services_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format for services data."

    if not isinstance(services, list):
        return "❌ Error: services_json must be a JSON array."

    alert_thresholds = [int(a.strip()) for a in budget_alerts.split(",") if a.strip()] if budget_alerts else [50, 80, 95]
    allocation_dims = [d.strip() for d in cost_allocation.split(",") if d.strip()] if cost_allocation else ["team", "environment"]

    total_cost = sum(float(s.get("monthly_cost", 0)) for s in services)
    categories: dict[str, float] = {}
    for s in services:
        cat = s.get("category", "Other")
        categories[cat] = categories.get(cat, 0) + float(s.get("monthly_cost", 0))

    report = (
        f"📊 FINOPS DASHBOARD SPECIFICATION\n"
        f"{'═' * 65}\n\n"
        f"💰 Cost Overview Panel:\n"
        f"  ┌───────────────────────────────────┐\n"
        f"  │ Total Monthly Spend: ${total_cost:>10,.2f} │\n"
        f"  └───────────────────────────────────┘\n\n"
        f"  By Category:\n"
    )

    for cat, cost in sorted(categories.items(), key=lambda x: x[1], reverse=True):
        pct = (cost / total_cost * 100) if total_cost > 0 else 0
        bar = "█" * int(pct / 5)
        report += f"    {cat:<20} ${cost:>10,.2f}  {pct:>5.1f}%  {bar}\n"

    report += (
        f"\n📈 Dashboard Panels:\n"
        f"  {'─' * 55}\n"
        f"  Panel 1: Cost Trend (30/60/90 day line chart)\n"
        f"  Panel 2: Cost by Service (top-10 bar chart)\n"
        f"  Panel 3: Cost by {' / '.join(allocation_dims)} (pie chart)\n"
        f"  Panel 4: Daily Spend vs Budget (gauge + sparkline)\n"
        f"  Panel 5: Cost Anomaly Detection (z-score alerts)\n"
        f"  Panel 6: Resource Utilization vs Cost (scatter plot)\n\n"
    )

    report += f"🚨 Budget Alerts:\n"
    for threshold in sorted(alert_thresholds):
        severity = "INFO" if threshold < 70 else "WARNING" if threshold < 90 else "CRITICAL"
        report += f"  • {threshold}% utilization → {severity} alert\n"

    report += (
        f"\n🔍 Anomaly Detection Rules:\n"
        f"  • Daily spend > 2σ above 30-day mean → WARNING\n"
        f"  • Daily spend > 3σ above 30-day mean → CRITICAL\n"
        f"  • New service appears with >$100/day → INFO\n"
        f"  • Service cost increases >50% week-over-week → WARNING\n\n"
        f"🏷️ Cost Allocation Dimensions:\n"
    )
    for dim in allocation_dims:
        report += f"  • {dim.title()}\n"

    report += f"{'═' * 65}\n"

    log_action(
        "OptimizationArchitectAgent",
        "create_finops_dashboard",
        f"Services: {len(services)}, Total: ${total_cost:,.2f}",
        f"Alerts: {alert_thresholds}, Dimensions: {allocation_dims}",
    )
    return report


OPTIMIZATIONARCHITECT_TOOLS = [
    design_optimization_strategy,
    create_circuit_breaker,
    analyze_api_costs,
    design_shadow_test,
    create_finops_dashboard,
]
