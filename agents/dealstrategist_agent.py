"""
AgentSystem — Deal Strategist Agent.

Senior B2B deal strategist using MEDDPICC qualification, competitive
positioning, and pipeline risk assessment to drive predictable revenue.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


async def qualify_deal_meddpicc(
    opportunity_name: Annotated[str, "Name of the opportunity"],
    metrics: Annotated[str, "Quantifiable measures of success the buyer cares about"] = "",
    economic_buyer: Annotated[str, "Person with budget authority and their disposition"] = "",
    decision_criteria: Annotated[str, "Technical and business criteria for vendor selection"] = "",
    decision_process: Annotated[str, "Steps, timeline, and stakeholders in the decision"] = "",
    paper_process: Annotated[str, "Legal, procurement, and contract approval process"] = "",
    identify_pain: Annotated[str, "Critical business pain the buyer needs to solve"] = "",
    champion: Annotated[str, "Internal advocate with power and influence"] = "",
    competition: Annotated[str, "Known competitors and their positioning"] = "",
) -> str:
    """Score opportunity using full MEDDPICC framework with gap analysis."""
    logger.info(f"MEDDPICC qualification for: {opportunity_name}")

    elements = {
        "Metrics": metrics,
        "Economic Buyer": economic_buyer,
        "Decision Criteria": decision_criteria,
        "Decision Process": decision_process,
        "Paper Process": paper_process,
        "Identify Pain": identify_pain,
        "Champion": champion,
        "Competition": competition,
    }

    scores: dict[str, int] = {}
    gaps: list[str] = []
    actions: list[str] = []

    for element, value in elements.items():
        if not value or not value.strip():
            scores[element] = 0
            gaps.append(element)
            actions.append(f"Discover {element}: Schedule targeted conversation")
        elif len(value.strip()) < 20:
            scores[element] = 4
            gaps.append(f"{element} (incomplete)")
            actions.append(f"Deepen {element}: Validate and expand understanding")
        else:
            scores[element] = 8

    total_score = sum(scores.values())
    max_score = len(elements) * 10
    pct = (total_score / max_score * 100) if max_score > 0 else 0

    if pct >= 70:
        qualification = "STRONG — Ready to advance"
    elif pct >= 40:
        qualification = "DEVELOPING — Gaps require attention"
    else:
        qualification = "WEAK — Significant discovery needed"

    report = (
        f"🎯 MEDDPICC QUALIFICATION: {opportunity_name}\n"
        f"{'═' * 60}\n\n"
        f"📊 Element Scores (0-10):\n"
        f"  {'Element':<20} {'Score':>5}  {'Status'}\n"
        f"  {'─' * 50}\n"
    )

    for element, score in scores.items():
        bar = "█" * score + "░" * (10 - score)
        status = "✅ Strong" if score >= 7 else "⚠️ Partial" if score >= 4 else "❌ Gap"
        report += f"  {element:<20} {score:>5}  {bar} {status}\n"

    report += (
        f"  {'─' * 50}\n"
        f"  {'TOTAL':<20} {total_score:>5}/{max_score}  ({pct:.0f}%)\n\n"
        f"  📌 Qualification: {qualification}\n\n"
    )

    if gaps:
        report += f"🔍 Gap Analysis:\n"
        for gap in gaps:
            report += f"  ❌ {gap}\n"
        report += "\n"

    report += f"📋 Next Actions:\n"
    for i, action in enumerate(actions[:5], 1):
        report += f"  {i}. {action}\n"

    report += f"{'═' * 60}\n"

    log_action(
        "DealStrategistAgent",
        "qualify_deal_meddpicc",
        f"Opportunity: {opportunity_name}",
        f"Score: {total_score}/{max_score} ({pct:.0f}%), Gaps: {len(gaps)}",
    )
    return report


async def assess_pipeline_risk(
    deals_json: Annotated[str, "JSON array of deals with fields: name, stage, amount, close_date, probability"],
) -> str:
    """Analyze pipeline for risk. Returns risk-scored pipeline with forecast accuracy."""
    logger.info("Assessing pipeline risk")

    try:
        deals = json.loads(deals_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format for deals data."

    if not isinstance(deals, list):
        return "❌ Error: deals_json must be a JSON array of deal objects."

    total_pipeline = 0.0
    high_risk: list[dict] = []
    medium_risk: list[dict] = []
    low_risk: list[dict] = []

    for deal in deals:
        amount = float(deal.get("amount", 0))
        probability = float(deal.get("probability", 50))
        stage = deal.get("stage", "unknown").lower()
        total_pipeline += amount

        risk_score = 100 - probability
        if stage in ("prospecting", "qualification", "discovery"):
            risk_score += 20
        elif stage in ("proposal", "negotiation"):
            risk_score += 5

        deal["risk_score"] = min(risk_score, 100)

        if risk_score >= 60:
            high_risk.append(deal)
        elif risk_score >= 30:
            medium_risk.append(deal)
        else:
            low_risk.append(deal)

    weighted_pipeline = sum(
        float(d.get("amount", 0)) * float(d.get("probability", 50)) / 100
        for d in deals
    )

    report = (
        f"📊 PIPELINE RISK ASSESSMENT\n"
        f"{'═' * 65}\n\n"
        f"  Total Pipeline:    ${total_pipeline:>12,.2f}\n"
        f"  Weighted Pipeline: ${weighted_pipeline:>12,.2f}\n"
        f"  Deal Count:        {len(deals):>12}\n\n"
    )

    for label, risk_list, icon in [
        ("HIGH RISK", high_risk, "🔴"),
        ("MEDIUM RISK", medium_risk, "🟡"),
        ("LOW RISK", low_risk, "🟢"),
    ]:
        if risk_list:
            report += f"  {icon} {label} ({len(risk_list)} deals):\n"
            for deal in risk_list:
                name = deal.get("name", "Unnamed")
                amount = float(deal.get("amount", 0))
                stage = deal.get("stage", "N/A")
                report += f"    • {name:<25} ${amount:>10,.2f}  Stage: {stage}\n"
            report += "\n"

    coverage_ratio = total_pipeline / weighted_pipeline if weighted_pipeline > 0 else 0
    forecast_health = (
        "Healthy" if coverage_ratio >= 3 else "Adequate" if coverage_ratio >= 2 else "Insufficient"
    )

    report += (
        f"{'─' * 65}\n"
        f"  📈 Forecast Accuracy Assessment:\n"
        f"    Pipeline Coverage: {coverage_ratio:.1f}x\n"
        f"    Forecast Health:   {forecast_health}\n"
        f"    High Risk Deals:   {len(high_risk)} ({len(high_risk)/len(deals)*100:.0f}%)\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "DealStrategistAgent",
        "assess_pipeline_risk",
        f"Deals: {len(deals)}, Pipeline: ${total_pipeline:,.2f}",
        f"Weighted: ${weighted_pipeline:,.2f}, High risk: {len(high_risk)}",
    )
    return report


async def create_competitive_battle_card(
    competitor_name: Annotated[str, "Name of the competitor"],
    their_strengths: Annotated[str, "Comma-separated competitor strengths"],
    their_weaknesses: Annotated[str, "Comma-separated competitor weaknesses"],
    our_differentiators: Annotated[str, "Comma-separated unique differentiators we hold"],
) -> str:
    """Create competitive battle card with positioning guide and objection handling."""
    logger.info(f"Creating battle card vs: {competitor_name}")

    strengths = [s.strip() for s in their_strengths.split(",") if s.strip()]
    weaknesses = [w.strip() for w in their_weaknesses.split(",") if w.strip()]
    diffs = [d.strip() for d in our_differentiators.split(",") if d.strip()]

    report = (
        f"⚔️ COMPETITIVE BATTLE CARD: vs {competitor_name}\n"
        f"{'═' * 60}\n\n"
        f"🔴 Their Strengths (Neutralize):\n"
    )
    for s in strengths:
        report += f"  • {s}\n"
        report += f"    → Counter: Acknowledge, then redirect to our value\n"

    report += f"\n🟢 Their Weaknesses (Exploit):\n"
    for w in weaknesses:
        report += f"  • {w}\n"
        report += f"    → Strategy: Ask discovery questions that expose this gap\n"

    report += f"\n🏆 Our Differentiators (Amplify):\n"
    for d in diffs:
        report += f"  ✅ {d}\n"

    report += (
        f"\n{'─' * 60}\n"
        f"💬 Objection Handling:\n\n"
    )

    for s in strengths[:3]:
        report += (
            f"  Objection: \"{competitor_name} has {s.lower()}\"\n"
            f"  Response:  \"That's a valid point. What we've found with\n"
            f"    our customers is that {diffs[0].lower() if diffs else 'our approach'}\n"
            f"    delivers more measurable impact because...\"\n\n"
        )

    report += (
        f"{'─' * 60}\n"
        f"📌 Positioning Statement:\n"
        f"  While {competitor_name} competes on {strengths[0].lower() if strengths else 'features'},\n"
        f"  we win on {diffs[0].lower() if diffs else 'value'} — delivering outcomes\n"
        f"  that directly impact the buyer's business metrics.\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "DealStrategistAgent",
        "create_competitive_battle_card",
        f"Competitor: {competitor_name}",
        f"Strengths: {len(strengths)}, Weaknesses: {len(weaknesses)}, Diffs: {len(diffs)}",
    )
    return report


async def build_deal_strategy(
    opportunity_name: Annotated[str, "Name of the opportunity"],
    deal_size: Annotated[str, "Deal size/value in dollars"],
    stage: Annotated[str, "Current deal stage: prospecting, discovery, proposal, negotiation, closing"],
    key_stakeholders: Annotated[str, "Comma-separated key stakeholders and their roles"] = "",
    timeline: Annotated[str, "Expected close timeline or deadline"] = "",
) -> str:
    """Create stage-by-stage deal strategy with action plan."""
    logger.info(f"Building deal strategy for: {opportunity_name}")

    stakeholders = [s.strip() for s in key_stakeholders.split(",") if s.strip()] if key_stakeholders else []

    stage_playbook = {
        "prospecting": [
            ("Research", "Deep-dive on buyer's business, industry, and pain points"),
            ("Outreach", "Multi-channel engagement: email, LinkedIn, warm intro"),
            ("Qualify", "Confirm BANT basics before investing more time"),
        ],
        "discovery": [
            ("Pain Mapping", "Uncover and quantify business pain using MEDDPICC"),
            ("Stakeholder Map", "Identify economic buyer, champion, and blockers"),
            ("Vision Match", "Align solution vision with buyer's desired future state"),
        ],
        "proposal": [
            ("Win Themes", "Develop 3-5 win themes tied to buyer's priorities"),
            ("Solution Design", "Tailor proposal to decision criteria"),
            ("Executive Summary", "Craft compelling narrative; peer review before submit"),
        ],
        "negotiation": [
            ("Value Defense", "Anchor on ROI and business outcomes, not discounts"),
            ("Legal/Procurement", "Engage legal early; prepare redline strategy"),
            ("Champion Coaching", "Arm champion with internal selling tools"),
        ],
        "closing": [
            ("Paper Process", "Drive contract to signature; remove friction"),
            ("Implementation Plan", "Present go-live plan to build buyer confidence"),
            ("Executive Alignment", "CxO-to-CxO engagement to seal commitment"),
        ],
    }

    current_stage = stage.lower().strip()
    playbook = stage_playbook.get(current_stage, stage_playbook["discovery"])

    report = (
        f"🎯 DEAL STRATEGY: {opportunity_name}\n"
        f"{'═' * 60}\n"
        f"  Deal Size:  {deal_size}\n"
        f"  Stage:      {stage.title()}\n"
    )
    if timeline:
        report += f"  Timeline:   {timeline}\n"
    report += f"{'─' * 60}\n\n"

    report += f"📋 Stage Actions ({stage.title()}):\n"
    for i, (action, detail) in enumerate(playbook, 1):
        report += (
            f"  {i}. {action}\n"
            f"     → {detail}\n"
        )
    report += "\n"

    if stakeholders:
        report += f"👥 Stakeholder Strategy:\n"
        for stakeholder in stakeholders:
            report += f"  • {stakeholder} — Engage, align, confirm support\n"
        report += "\n"

    all_stages = list(stage_playbook.keys())
    current_idx = all_stages.index(current_stage) if current_stage in all_stages else 0

    report += f"📊 Deal Progression:\n"
    for i, stg in enumerate(all_stages):
        if i < current_idx:
            marker = "✅"
        elif i == current_idx:
            marker = "🔵"
        else:
            marker = "⚪"
        report += f"  {marker} {stg.title()}\n"

    report += (
        f"\n{'─' * 60}\n"
        f"  Exit Criteria for {stage.title()}:\n"
        f"  • All stage actions completed with evidence\n"
        f"  • Stakeholder alignment confirmed\n"
        f"  • Next-stage entry criteria validated\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "DealStrategistAgent",
        "build_deal_strategy",
        f"{opportunity_name} ({deal_size}, {stage})",
        f"Actions: {len(playbook)}, Stakeholders: {len(stakeholders)}",
    )
    return report


async def design_discovery_questions(
    industry: Annotated[str, "Buyer's industry vertical"],
    pain_hypothesis: Annotated[str, "Hypothesized business pain or challenge"],
    buyer_role: Annotated[str, "Role/title of the person being interviewed"],
) -> str:
    """Create discovery call question framework organized by MEDDPICC element."""
    logger.info(f"Designing discovery questions for {buyer_role} in {industry}")

    questions = {
        "Metrics": [
            f"What KPIs does your team track most closely in {industry}?",
            "How do you currently measure success for initiatives like this?",
            "What would a 'home run' outcome look like in quantifiable terms?",
        ],
        "Economic Buyer": [
            "Who ultimately signs off on investments of this nature?",
            "What does the budget approval process look like?",
            f"As a {buyer_role}, what's your role in the final decision?",
        ],
        "Decision Criteria": [
            "What are the must-have vs nice-to-have capabilities?",
            "How will you evaluate and compare different solutions?",
            "Are there technical or compliance requirements we should know about?",
        ],
        "Decision Process": [
            "Walk me through how decisions like this typically get made here.",
            "Who else needs to be involved, and what are their priorities?",
            "What's the expected timeline from evaluation to go-live?",
        ],
        "Paper Process": [
            "What does your procurement/legal review process look like?",
            "Are there standard contract terms or security reviews required?",
            "How long does the typical vendor approval cycle take?",
        ],
        "Identify Pain": [
            f"What's the biggest challenge you're facing with {pain_hypothesis.lower()}?",
            "What happens if this problem isn't solved in the next 6-12 months?",
            "How is this impacting your team's productivity or revenue today?",
        ],
        "Champion": [
            "Who on your team is most passionate about solving this?",
            "Is there someone internally who has been advocating for change?",
            "How can we best support you in building the internal case?",
        ],
        "Competition": [
            "Are you evaluating other solutions or approaches?",
            "What's worked or hasn't worked with previous vendors?",
            "What would make you confident you've chosen the right partner?",
        ],
    }

    report = (
        f"🔍 DISCOVERY QUESTION FRAMEWORK\n"
        f"{'═' * 60}\n"
        f"  Industry: {industry}\n"
        f"  Role:     {buyer_role}\n"
        f"  Pain:     {pain_hypothesis}\n"
        f"{'─' * 60}\n\n"
    )

    for element, q_list in questions.items():
        report += f"  📌 {element}:\n"
        for q in q_list:
            report += f"    → {q}\n"
        report += "\n"

    report += (
        f"{'─' * 60}\n"
        f"  💡 Tips:\n"
        f"  • Start broad (pain/metrics), then narrow (process/paper)\n"
        f"  • Listen for emotional language — it signals real pain\n"
        f"  • Confirm understanding before moving to next element\n"
        f"  • Adapt questions to {buyer_role}'s seniority and focus\n"
        f"{'═' * 60}\n"
    )

    total_questions = sum(len(q) for q in questions.values())
    log_action(
        "DealStrategistAgent",
        "design_discovery_questions",
        f"Industry: {industry}, Role: {buyer_role}",
        f"Questions: {total_questions} across {len(questions)} MEDDPICC elements",
    )
    return report


async def forecast_deal(
    deals_json: Annotated[str, "JSON array of deals with fields: name, amount, probability, stage, close_date"],
    methodology: Annotated[str, "Forecast method: weighted_pipeline, commit_based, historical"] = "weighted_pipeline",
) -> str:
    """Generate forecast from pipeline data with confidence levels and breakdown."""
    logger.info(f"Forecasting deals using {methodology} methodology")

    try:
        deals = json.loads(deals_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format for deals data."

    if not isinstance(deals, list):
        return "❌ Error: deals_json must be a JSON array of deal objects."

    commit: list[dict] = []
    upside: list[dict] = []
    pipeline: list[dict] = []

    for deal in deals:
        prob = float(deal.get("probability", 50))
        if prob >= 80:
            commit.append(deal)
        elif prob >= 50:
            upside.append(deal)
        else:
            pipeline.append(deal)

    commit_total = sum(float(d.get("amount", 0)) for d in commit)
    upside_total = sum(float(d.get("amount", 0)) for d in upside)
    pipeline_total = sum(float(d.get("amount", 0)) for d in pipeline)

    if methodology == "weighted_pipeline":
        forecast_value = sum(
            float(d.get("amount", 0)) * float(d.get("probability", 50)) / 100
            for d in deals
        )
    elif methodology == "commit_based":
        forecast_value = commit_total + (upside_total * 0.5)
    else:
        forecast_value = commit_total + (upside_total * 0.6) + (pipeline_total * 0.2)

    total_pipeline = commit_total + upside_total + pipeline_total
    confidence = "High" if commit_total / total_pipeline > 0.5 else "Medium" if commit_total / total_pipeline > 0.3 else "Low" if total_pipeline > 0 else "N/A"

    report = (
        f"📈 DEAL FORECAST ({methodology.replace('_', ' ').title()})\n"
        f"{'═' * 60}\n\n"
        f"  📊 Forecast Summary:\n"
        f"  {'─' * 45}\n"
        f"  Forecast Value:  ${forecast_value:>12,.2f}\n"
        f"  Confidence:      {confidence}\n"
        f"  Total Pipeline:  ${total_pipeline:>12,.2f}\n\n"
    )

    for label, deal_list, subtotal, icon in [
        ("COMMIT (≥80%)", commit, commit_total, "🟢"),
        ("UPSIDE (50-79%)", upside, upside_total, "🟡"),
        ("PIPELINE (<50%)", pipeline, pipeline_total, "🔴"),
    ]:
        report += f"  {icon} {label}: ${subtotal:>10,.2f} ({len(deal_list)} deals)\n"
        for deal in deal_list:
            name = deal.get("name", "Unnamed")
            amount = float(deal.get("amount", 0))
            prob = float(deal.get("probability", 50))
            report += f"    • {name:<25} ${amount:>10,.2f}  {prob:.0f}%\n"
        report += "\n"

    report += (
        f"{'─' * 60}\n"
        f"  📌 Methodology: {methodology.replace('_', ' ').title()}\n"
        f"  📌 Coverage Ratio: {total_pipeline / forecast_value:.1f}x\n" if forecast_value > 0 else ""
        f"{'═' * 60}\n"
    )

    log_action(
        "DealStrategistAgent",
        "forecast_deal",
        f"Deals: {len(deals)}, Method: {methodology}",
        f"Forecast: ${forecast_value:,.2f}, Confidence: {confidence}",
    )
    return report


DEALSTRATEGIST_TOOLS = [
    qualify_deal_meddpicc,
    assess_pipeline_risk,
    create_competitive_battle_card,
    build_deal_strategy,
    design_discovery_questions,
    forecast_deal,
]
