"""
AgentSystem — Proposal Strategist Agent.

Strategic proposal architect who transforms RFPs into compelling win
narratives. Specializes in win theme development, competitive positioning,
and executive summary craft.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action

logger = logging.getLogger(__name__)


async def develop_win_themes(
    opportunity_name: Annotated[str, "Name of the opportunity or deal"],
    buyer_challenges: Annotated[str, "Key challenges the buyer faces"],
    differentiators: Annotated[str, "Our unique differentiators and strengths"],
    competitors: Annotated[str, "Comma-separated list of known competitors"] = "",
) -> str:
    """Create 3-5 win themes with proof points and competitive positioning."""
    logger.info(f"Developing win themes for: {opportunity_name}")

    challenges = [c.strip() for c in buyer_challenges.split(",") if c.strip()]
    diffs = [d.strip() for d in differentiators.split(",") if d.strip()]
    competitor_list = [c.strip() for c in competitors.split(",") if c.strip()] if competitors else []

    themes = []
    if challenges and diffs:
        for i, (challenge, diff) in enumerate(zip(challenges, diffs), 1):
            themes.append((
                f"Theme {i}: {diff}",
                challenge,
                diff,
                f"Proven track record delivering {diff.lower()} for similar engagements",
            ))

    while len(themes) < 3:
        idx = len(themes) + 1
        themes.append((
            f"Theme {idx}: Trusted Partnership",
            "Need for reliable, long-term partner",
            "Deep domain expertise and customer success focus",
            "High customer retention and satisfaction scores",
        ))

    report = (
        f"🏆 WIN THEME MATRIX: {opportunity_name}\n"
        f"{'═' * 65}\n\n"
    )

    for theme_name, challenge, diff, proof in themes[:5]:
        report += (
            f"  {theme_name}\n"
            f"  {'─' * 55}\n"
            f"  Buyer Challenge: {challenge}\n"
            f"  Differentiator:  {diff}\n"
            f"  Proof Point:     {proof}\n\n"
        )

    if competitor_list:
        report += f"⚔️ Competitive Positioning:\n"
        for comp in competitor_list:
            report += (
                f"  vs {comp}:\n"
                f"    Advantage: Our solution offers superior integration and support\n"
                f"    Counter:   Emphasize total cost of ownership and proven ROI\n"
            )
        report += "\n"

    report += (
        f"{'─' * 65}\n"
        f"  📌 Strategy: Lead with themes in executive summary; reinforce\n"
        f"     throughout proposal with proof points at each mention.\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "ProposalStrategistAgent",
        "develop_win_themes",
        f"Opportunity: {opportunity_name}",
        f"Themes: {len(themes[:5])}, Competitors: {len(competitor_list)}",
    )
    return report


async def write_executive_summary(
    buyer_name: Annotated[str, "Name of the buyer/customer organization"],
    challenge: Annotated[str, "Core challenge or need the buyer faces"],
    solution_thesis: Annotated[str, "Our proposed solution approach and thesis"],
    proof_points: Annotated[str, "Comma-separated evidence, case studies, or metrics"] = "",
    outcomes: Annotated[str, "Expected outcomes and business impact"] = "",
) -> str:
    """Craft a persuasive one-page executive summary using three-act narrative."""
    logger.info(f"Writing executive summary for: {buyer_name}")

    proofs = [p.strip() for p in proof_points.split(",") if p.strip()] if proof_points else []
    outcome_list = [o.strip() for o in outcomes.split(",") if o.strip()] if outcomes else []

    summary = (
        f"📄 EXECUTIVE SUMMARY\n"
        f"{'═' * 60}\n"
        f"  Prepared for: {buyer_name}\n"
        f"{'─' * 60}\n\n"
        f"  ACT I — THE CHALLENGE\n"
        f"  {'─' * 40}\n"
        f"  {buyer_name} faces a critical challenge: {challenge}\n\n"
        f"  In today's rapidly evolving landscape, organizations that fail\n"
        f"  to address this challenge risk falling behind competitors and\n"
        f"  missing strategic opportunities for growth.\n\n"
        f"  ACT II — THE SOLUTION\n"
        f"  {'─' * 40}\n"
        f"  {solution_thesis}\n\n"
        f"  Our approach is purpose-built to address {buyer_name}'s specific\n"
        f"  requirements, combining proven methodology with innovative\n"
        f"  technology to deliver measurable results.\n\n"
    )

    if proofs:
        summary += f"  Evidence & Proof Points:\n"
        for proof in proofs:
            summary += f"    ✓ {proof}\n"
        summary += "\n"

    summary += f"  ACT III — THE OUTCOME\n  {'─' * 40}\n"
    if outcome_list:
        summary += f"  By partnering with us, {buyer_name} will achieve:\n"
        for outcome in outcome_list:
            summary += f"    → {outcome}\n"
    else:
        summary += (
            f"  By partnering with us, {buyer_name} will achieve accelerated\n"
            f"  time-to-value, reduced operational risk, and a sustainable\n"
            f"  competitive advantage.\n"
        )

    summary += (
        f"\n{'─' * 60}\n"
        f"  We are committed to {buyer_name}'s success and look forward\n"
        f"  to demonstrating how our partnership will drive transformative\n"
        f"  outcomes.\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "ProposalStrategistAgent",
        "write_executive_summary",
        f"Buyer: {buyer_name}",
        f"Proof points: {len(proofs)}, Outcomes: {len(outcome_list)}",
    )
    return summary


async def create_proposal_architecture(
    rfp_requirements: Annotated[str, "Key RFP requirements and sections to address"],
    win_themes: Annotated[str, "Comma-separated win themes to weave through the proposal"],
    solution_components: Annotated[str, "Comma-separated solution components or modules"] = "",
) -> str:
    """Design proposal structure mapping sections to win themes. Returns section outline."""
    logger.info("Creating proposal architecture")

    requirements = [r.strip() for r in rfp_requirements.split(",") if r.strip()]
    themes = [t.strip() for t in win_themes.split(",") if t.strip()]
    components = [c.strip() for c in solution_components.split(",") if c.strip()] if solution_components else []

    sections = [
        ("1. Executive Summary", "Set the narrative; address buyer pain"),
        ("2. Understanding of Requirements", "Mirror buyer's language; show empathy"),
        ("3. Technical Approach", "Detail solution; map to requirements"),
        ("4. Management Approach", "Team, timeline, governance"),
        ("5. Past Performance", "Case studies and references"),
        ("6. Pricing & Value", "ROI-anchored pricing narrative"),
        ("7. Risk Mitigation", "Proactive risk handling"),
        ("8. Implementation Plan", "Phased rollout with milestones"),
    ]

    report = (
        f"🏗️ PROPOSAL ARCHITECTURE\n"
        f"{'═' * 65}\n\n"
        f"📋 Narrative Flow:\n"
    )

    for section_name, purpose in sections:
        theme_tag = themes[hash(section_name) % len(themes)] if themes else "N/A"
        report += (
            f"\n  {section_name}\n"
            f"  {'─' * 50}\n"
            f"  Purpose:   {purpose}\n"
            f"  Win Theme: {theme_tag}\n"
        )

    report += f"\n🎯 Requirements Traceability:\n"
    for i, req in enumerate(requirements, 1):
        section_ref = sections[min(i, len(sections) - 1)][0]
        report += f"  R{i}: {req} → {section_ref}\n"

    if components:
        report += f"\n🧩 Solution Component Mapping:\n"
        for comp in components:
            report += f"  • {comp} → Section 3: Technical Approach\n"

    report += (
        f"\n{'─' * 65}\n"
        f"  📌 Strategy: Each section reinforces win themes.\n"
        f"     Open and close every section with buyer-centric language.\n"
        f"{'═' * 65}\n"
    )

    log_action(
        "ProposalStrategistAgent",
        "create_proposal_architecture",
        f"Requirements: {len(requirements)}, Themes: {len(themes)}",
        f"Sections: {len(sections)}, Components: {len(components)}",
    )
    return report


async def analyze_rfp(
    rfp_text: Annotated[str, "Full text or key excerpts from the RFP"],
    evaluation_criteria: Annotated[str, "Known evaluation/scoring criteria"] = "",
    submission_deadline: Annotated[str, "Submission deadline in YYYY-MM-DD format"] = "",
) -> str:
    """Analyze RFP requirements, scoring criteria, and compliance. Returns go/no-go recommendation."""
    logger.info("Analyzing RFP")

    criteria_list = [c.strip() for c in evaluation_criteria.split(",") if c.strip()] if evaluation_criteria else []
    text_length = len(rfp_text)

    keywords = {
        "mandatory": rfp_text.lower().count("mandatory") + rfp_text.lower().count("required") + rfp_text.lower().count("must"),
        "preferred": rfp_text.lower().count("preferred") + rfp_text.lower().count("desired") + rfp_text.lower().count("should"),
        "compliance": rfp_text.lower().count("compliance") + rfp_text.lower().count("certif"),
        "experience": rfp_text.lower().count("experience") + rfp_text.lower().count("past performance"),
    }

    risk_flags = []
    if keywords["mandatory"] > 10:
        risk_flags.append("High number of mandatory requirements — compliance risk")
    if keywords["compliance"] > 5:
        risk_flags.append("Heavy compliance/certification requirements")
    if text_length < 100:
        risk_flags.append("Limited RFP information provided — request full document")

    go_score = 7
    if len(risk_flags) >= 2:
        go_score -= 2
    if keywords["mandatory"] > 15:
        go_score -= 1

    recommendation = "GO" if go_score >= 6 else "CONDITIONAL GO" if go_score >= 4 else "NO-GO"

    report = (
        f"🔎 RFP ANALYSIS\n"
        f"{'═' * 60}\n\n"
        f"📊 Keyword Analysis:\n"
    )
    for category, count in keywords.items():
        report += f"  {category.title():<15} {count:>3} mentions\n"

    if criteria_list:
        report += f"\n📋 Evaluation Criteria:\n"
        for i, criterion in enumerate(criteria_list, 1):
            report += f"  {i}. {criterion}\n"

    if submission_deadline:
        report += f"\n📅 Submission Deadline: {submission_deadline}\n"

    report += f"\n⚠️ Risk Flags:\n"
    if risk_flags:
        for flag in risk_flags:
            report += f"  🚩 {flag}\n"
    else:
        report += f"  ✅ No critical risk flags identified\n"

    report += (
        f"\n{'─' * 60}\n"
        f"  📌 GO/NO-GO Score: {go_score}/10\n"
        f"  📌 Recommendation: {recommendation}\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "ProposalStrategistAgent",
        "analyze_rfp",
        f"Text length: {text_length}, Criteria: {len(criteria_list)}",
        f"Recommendation: {recommendation}, Score: {go_score}/10",
    )
    return report


async def create_pricing_narrative(
    solution_components_json: Annotated[str, "JSON array of components with fields: name, cost, description"],
    value_proposition: Annotated[str, "Overall value proposition anchoring the pricing"],
    competitor_pricing: Annotated[str, "Known competitor pricing or positioning"] = "",
) -> str:
    """Build pricing rationale anchored on value, not cost. Returns pricing narrative with ROI."""
    logger.info("Creating pricing narrative")

    try:
        components = json.loads(solution_components_json)
    except json.JSONDecodeError:
        return "❌ Error: Invalid JSON format for solution components."

    if not isinstance(components, list):
        return "❌ Error: solution_components_json must be a JSON array."

    total_cost = sum(float(c.get("cost", 0)) for c in components)

    report = (
        f"💰 PRICING NARRATIVE\n"
        f"{'═' * 60}\n\n"
        f"📌 Value Anchor:\n"
        f"  {value_proposition}\n\n"
        f"📋 Investment Breakdown:\n"
        f"  {'Component':<25} {'Investment':>12}  Description\n"
        f"  {'─' * 56}\n"
    )

    for comp in components:
        name = comp.get("name", "Unnamed")
        cost = float(comp.get("cost", 0))
        desc = comp.get("description", "")
        report += f"  {name:<25} ${cost:>10,.2f}  {desc}\n"

    report += (
        f"  {'─' * 56}\n"
        f"  {'TOTAL INVESTMENT':<25} ${total_cost:>10,.2f}\n\n"
    )

    roi_conservative = total_cost * 2.5
    roi_expected = total_cost * 4.0
    report += (
        f"📈 ROI Justification:\n"
        f"  Conservative (12mo): ${roi_conservative:,.2f} ({2.5:.1f}x return)\n"
        f"  Expected (12mo):     ${roi_expected:,.2f} ({4.0:.1f}x return)\n"
        f"  Payback Period:      3-6 months (estimated)\n\n"
    )

    if competitor_pricing:
        report += (
            f"⚔️ Competitive Context:\n"
            f"  {competitor_pricing}\n\n"
            f"  Our Positioning: We compete on value delivered, not price.\n"
            f"  Total cost of ownership favors our solution when factoring\n"
            f"  in implementation speed, support quality, and long-term ROI.\n\n"
        )

    report += (
        f"{'─' * 60}\n"
        f"  💡 Framing: Present as 'investment' not 'cost'.\n"
        f"     Lead with outcomes, follow with components.\n"
        f"{'═' * 60}\n"
    )

    log_action(
        "ProposalStrategistAgent",
        "create_pricing_narrative",
        f"Components: {len(components)}, Total: ${total_cost:,.2f}",
        f"ROI range: ${roi_conservative:,.2f}-${roi_expected:,.2f}",
    )
    return report


PROPOSALSTRATEGIST_TOOLS = [
    develop_win_themes,
    write_executive_summary,
    create_proposal_architecture,
    analyze_rfp,
    create_pricing_narrative,
]
