"""
AgentSystem — Growth Hacker Agent.

Growth hacker agent for rapid user acquisition and data-driven growth.
Covers viral loops, A/B testing, funnel analysis, growth dashboards,
channel strategy, and onboarding optimization.
"""

import json
import logging
import math
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


async def design_viral_loop(
    product_description: Annotated[str, "Description of the product"],
    target_audience: Annotated[str, "Target audience for the viral loop"],
    current_channels: Annotated[str, "Current distribution channels"] = "",
) -> str:
    """
    Design a viral referral/sharing mechanism. Returns loop diagram,
    incentive structure, and expected K-factor.
    """
    log_action(
        "GrowthHackerAgent",
        "design_viral_loop",
        f"product={product_description[:80]}, audience={target_audience[:80]}",
    )

    loop = (
        f"🔁 VIRAL LOOP DESIGN\n"
        f"{'═' * 50}\n\n"
        f"**Product:** {product_description}\n"
        f"**Target Audience:** {target_audience}\n"
    )

    if current_channels:
        loop += f"**Current Channels:** {current_channels}\n"

    loop += (
        f"\n**Loop Diagram:**\n\n"
        f"  User Signs Up\n"
        f"       │\n"
        f"       ▼\n"
        f"  Experiences Value (Aha Moment)\n"
        f"       │\n"
        f"       ▼\n"
        f"  Prompted to Share / Invite\n"
        f"       │\n"
        f"       ▼\n"
        f"  Friend Receives Invite + Incentive\n"
        f"       │\n"
        f"       ▼\n"
        f"  Friend Signs Up → Loop Repeats\n\n"
        f"**Incentive Structure:**\n"
        f"  • Referrer: Premium feature unlock or credit per referral.\n"
        f"  • Invitee: Extended trial or onboarding bonus.\n"
        f"  • Double-sided incentives increase conversion 2–3x.\n\n"
        f"**Expected K-Factor:**\n"
        f"  K = invites_per_user × conversion_rate\n"
        f"  Target: K ≥ 1.0 for organic growth (self-sustaining).\n"
        f"  Realistic starting point: K ≈ 0.3–0.5 (supplement with paid).\n\n"
        f"**Key Metrics to Track:**\n"
        f"  • Invites sent per user\n"
        f"  • Invite-to-signup conversion rate\n"
        f"  • Time from signup to first invite\n"
        f"  • Share channel breakdown (email, social, link)\n"
        f"{'═' * 50}"
    )

    return loop


async def create_ab_test(
    hypothesis: Annotated[str, "The hypothesis to test"],
    variants: Annotated[str, "Comma-separated list of variant names (e.g., 'control, variant_a, variant_b')"],
    success_metric: Annotated[str, "Primary metric to measure success"],
    sample_size: Annotated[int, "Sample size per variant"] = 1000,
) -> str:
    """
    Design an A/B test experiment. Returns test plan, statistical requirements,
    and duration estimate.
    """
    variant_list = [v.strip() for v in variants.split(",") if v.strip()]

    log_action(
        "GrowthHackerAgent",
        "create_ab_test",
        f"hypothesis={hypothesis[:80]}, variants={variant_list}, metric={success_metric}",
    )

    total_sample = sample_size * len(variant_list)
    # Rough duration estimate assuming 100 users/day
    est_days = max(1, math.ceil(total_sample / 100))

    test = (
        f"🧪 A/B TEST PLAN\n"
        f"{'═' * 50}\n\n"
        f"**Hypothesis:** {hypothesis}\n"
        f"**Success Metric:** {success_metric}\n"
        f"**Variants:** {', '.join(variant_list)} ({len(variant_list)} groups)\n\n"
        f"**Statistical Requirements:**\n"
        f"  • Sample size per variant: {sample_size:,}\n"
        f"  • Total sample needed: {total_sample:,}\n"
        f"  • Confidence level: 95%\n"
        f"  • Minimum detectable effect: 5%\n"
        f"  • Estimated duration: ~{est_days} days (at 100 users/day)\n\n"
        f"**Variant Definitions:**\n"
    )

    for i, variant in enumerate(variant_list):
        label = "Control" if i == 0 else f"Treatment {i}"
        test += f"  • {variant} ({label}): Define specific change here.\n"

    test += (
        f"\n**Guardrails:**\n"
        f"  • Monitor for sample ratio mismatch (SRM).\n"
        f"  • Check guardrail metrics (revenue, errors, latency).\n"
        f"  • Do not peek at results before reaching required sample size.\n\n"
        f"**Decision Framework:**\n"
        f"  • If p < 0.05 and effect > MDE → Ship winning variant.\n"
        f"  • If no significant difference → Keep control, iterate.\n"
        f"  • If guardrail metric regresses → Stop test immediately.\n"
        f"{'═' * 50}"
    )

    return test


async def analyze_funnel(
    funnel_stages_json: Annotated[str, "JSON string of funnel stages with conversion rates"],
) -> str:
    """
    Analyze funnel stages, identify biggest drop-offs, and suggest
    optimization opportunities. Expects a JSON array of objects with
    'stage' and 'conversion_rate' (0–1) fields.
    """
    log_action(
        "GrowthHackerAgent",
        "analyze_funnel",
        f"input_length={len(funnel_stages_json)}",
    )

    try:
        stages = json.loads(funnel_stages_json)
        if not isinstance(stages, list):
            return "Error: Expected a JSON array of funnel stage objects."
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON — {exc}"

    analysis = (
        f"📉 FUNNEL ANALYSIS\n"
        f"{'═' * 50}\n\n"
        f"**Stages analyzed:** {len(stages)}\n\n"
        f"**Funnel Breakdown:**\n"
    )

    biggest_drop = None
    biggest_drop_pct = 0.0

    for i, stage in enumerate(stages):
        name = stage.get("stage", f"Stage {i + 1}")
        rate = stage.get("conversion_rate", 0)
        bar_length = int(rate * 30)
        bar = "█" * bar_length + "░" * (30 - bar_length)

        analysis += f"  {name:<25} {bar} {rate * 100:.1f}%\n"

        if i > 0:
            prev_rate = stages[i - 1].get("conversion_rate", 0)
            drop = prev_rate - rate
            if drop > biggest_drop_pct:
                biggest_drop_pct = drop
                biggest_drop = name

    analysis += f"\n**Biggest Drop-off:** {biggest_drop or 'N/A'}"
    if biggest_drop:
        analysis += f" (−{biggest_drop_pct * 100:.1f}%)"

    analysis += (
        f"\n\n**Optimization Opportunities:**\n"
        f"  1. Focus on the biggest drop-off stage first.\n"
        f"  2. A/B test copy, layout, and friction reduction.\n"
        f"  3. Add social proof or urgency at high-drop stages.\n"
        f"  4. Simplify forms and reduce required fields.\n"
        f"  5. Implement exit-intent interventions.\n"
        f"{'═' * 50}"
    )

    return analysis


async def generate_growth_dashboard(
    metrics_json: Annotated[str, "JSON string of growth metrics with current values and trends"],
) -> str:
    """
    Generate a formatted dashboard summary from growth metrics.
    Expects a JSON array of objects with 'metric', 'value', and optionally
    'trend' (up/down/flat) and 'target' fields.
    """
    log_action(
        "GrowthHackerAgent",
        "generate_growth_dashboard",
        f"input_length={len(metrics_json)}",
    )

    try:
        metrics = json.loads(metrics_json)
        if not isinstance(metrics, list):
            return "Error: Expected a JSON array of metric objects."
    except json.JSONDecodeError as exc:
        return f"Error: Invalid JSON — {exc}"

    trend_icons = {"up": "📈", "down": "📉", "flat": "➡️"}

    dashboard = (
        f"📊 GROWTH DASHBOARD\n"
        f"{'═' * 55}\n\n"
    )

    alerts = []

    for m in metrics:
        name = m.get("metric", "Unknown")
        value = m.get("value", "—")
        trend = m.get("trend", "flat")
        target = m.get("target")
        icon = trend_icons.get(trend, "❓")

        line = f"  {icon} {name:<30} {str(value):>10}"
        if target is not None:
            line += f"  (target: {target})"
            try:
                if float(value) < float(target) * 0.8:
                    alerts.append(f"⚠️  {name} is significantly below target.")
            except (ValueError, TypeError):
                pass
        dashboard += line + "\n"

    dashboard += f"\n{'─' * 55}\n"

    if alerts:
        dashboard += "\n**Alerts:**\n"
        for alert in alerts:
            dashboard += f"  {alert}\n"
    else:
        dashboard += "\n  ✅ All metrics within acceptable range.\n"

    dashboard += f"\n{'═' * 55}"
    return dashboard


async def create_channel_strategy(
    budget: Annotated[str, "Total budget for acquisition (e.g., '$10,000/month')"],
    target_cac: Annotated[str, "Target customer acquisition cost (e.g., '$25')"],
    channels: Annotated[str, "Comma-separated channels to consider (or empty for auto)"] = "",
) -> str:
    """
    Create a multi-channel acquisition strategy. Returns channel allocation,
    expected ROI, and scaling plan.
    """
    channel_list = (
        [c.strip() for c in channels.split(",") if c.strip()]
        if channels
        else ["Paid Search", "Content/SEO", "Social Ads", "Email", "Referral"]
    )

    log_action(
        "GrowthHackerAgent",
        "create_channel_strategy",
        f"budget={budget}, target_cac={target_cac}, channels={channel_list}",
    )

    strategy = (
        f"💰 CHANNEL ACQUISITION STRATEGY\n"
        f"{'═' * 55}\n\n"
        f"**Budget:** {budget}\n"
        f"**Target CAC:** {target_cac}\n"
        f"**Channels:** {', '.join(channel_list)}\n\n"
        f"**Recommended Allocation:**\n\n"
    )

    # Simple allocation heuristic
    n = len(channel_list)
    for i, ch in enumerate(channel_list):
        pct = round(100 / n)
        strategy += f"  • {ch:<25} {pct}% of budget\n"

    strategy += (
        f"\n**Expected ROI by Channel:**\n"
        f"  [PLACEHOLDER] Actual ROI depends on historical performance data.\n"
        f"  • Run small tests ($500–$1,000) per channel before scaling.\n"
        f"  • Double down on channels with CAC below target.\n"
        f"  • Pause channels with CAC > 2x target after sufficient data.\n\n"
        f"**Scaling Plan:**\n"
        f"  Phase 1 (Month 1): Test all channels with equal budget split.\n"
        f"  Phase 2 (Month 2): Shift 60% budget to top 2 performers.\n"
        f"  Phase 3 (Month 3+): Optimize creatives and audiences; explore new.\n\n"
        f"**Key Metrics:**\n"
        f"  • CAC per channel\n"
        f"  • LTV:CAC ratio (target ≥ 3:1)\n"
        f"  • Payback period\n"
        f"  • Channel saturation signals\n"
        f"{'═' * 55}"
    )

    return strategy


async def design_onboarding_flow(
    product_type: Annotated[str, "Type of product (SaaS, mobile app, marketplace, etc.)"],
    target_activation_metric: Annotated[str, "The metric that indicates a user is 'activated'"],
    steps: Annotated[str, "Comma-separated list of current onboarding steps (or empty)"] = "",
) -> str:
    """
    Design a user onboarding flow optimized for activation.
    Returns flow diagram, copy suggestions, and measurement plan.
    """
    step_list = (
        [s.strip() for s in steps.split(",") if s.strip()]
        if steps
        else ["Sign Up", "Profile Setup", "First Action", "Aha Moment", "Activation"]
    )

    log_action(
        "GrowthHackerAgent",
        "design_onboarding_flow",
        f"product={product_type}, activation={target_activation_metric}, steps={len(step_list)}",
    )

    flow = (
        f"🚀 ONBOARDING FLOW DESIGN\n"
        f"{'═' * 50}\n\n"
        f"**Product Type:** {product_type}\n"
        f"**Activation Metric:** {target_activation_metric}\n\n"
        f"**Flow Diagram:**\n\n"
    )

    for i, step in enumerate(step_list):
        flow += f"  Step {i + 1}: {step}\n"
        if i < len(step_list) - 1:
            flow += "       │\n       ▼\n"

    flow += (
        f"\n**Copy Suggestions:**\n"
        f"  • Welcome screen: Focus on the value proposition, not features.\n"
        f"  • Progress indicator: Show completion percentage to motivate.\n"
        f"  • CTA buttons: Use action-oriented language ('Start building', not 'Next').\n"
        f"  • Skip option: Allow power users to skip, but track skip rates.\n\n"
        f"**Measurement Plan:**\n"
        f"  • Track completion rate at each step.\n"
        f"  • Measure time-to-activation (signup → {target_activation_metric}).\n"
        f"  • Segment by channel source and user persona.\n"
        f"  • A/B test each step with ≥ 1,000 users per variant.\n\n"
        f"**Optimization Targets:**\n"
        f"  • Reduce steps to minimize friction.\n"
        f"  • Get users to Aha Moment within first session.\n"
        f"  • Re-engage drop-offs with targeted emails within 24h.\n"
        f"{'═' * 50}"
    )

    return flow


# List of tools to register with the growth hacker agent
GROWTHHACKER_TOOLS = [
    design_viral_loop,
    create_ab_test,
    analyze_funnel,
    generate_growth_dashboard,
    create_channel_strategy,
    design_onboarding_flow,
]
