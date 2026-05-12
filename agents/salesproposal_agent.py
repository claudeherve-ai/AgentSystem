"""
AgentSystem — Sales Proposal Strategist Agent.

Strategic proposal architect for win theme development, competitive positioning,
executive summaries, and RFP response strategy.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)


async def develop_win_themes(
    opportunity_name: Annotated[str, "Name of the sales opportunity or RFP"],
    buyer_challenges: Annotated[str, "Key challenges the buyer faces"],
    our_strengths: Annotated[str, "Our relevant capabilities and differentiators"],
    competitor_landscape: Annotated[str, "Known competitors and their likely positioning"] = "",
) -> str:
    """Develop 3-5 win themes connecting our strengths to buyer needs with proof points."""
    log_action("SalesProposalAgent", "develop_win_themes", f"opp={opportunity_name[:60]}")

    return (
        f"WIN THEME MATRIX: {opportunity_name}\n{'=' * 60}\n\n"
        f"BUYER CHALLENGES\n  {buyer_challenges[:300]}\n\n"
        f"WIN THEMES\n{'─' * 60}\n\n"
        f"Theme 1: [Client-centric statement connecting challenge to capability]\n"
        f"  Buyer Need:       [Specific challenge]\n"
        f"  Our Differentiator: [Capability or methodology]\n"
        f"  Proof Point:      [Metric, case study, or evidence]\n"
        f"  Appears In:       Exec Summary, Technical Approach, Case Study\n\n"
        f"Theme 2: [Client-centric statement]\n"
        f"  [Same structure]\n\n"
        f"Theme 3: [Client-centric statement]\n"
        f"  [Same structure]\n\n"
        f"COMPETITIVE POSITIONING\n{'─' * 60}\n"
        f"  {'Dimension':<20} {'Our Position':<25} {'Competitor':<20}\n"
        f"  [Frame strengths as benefits, never name-attack competitors]\n\n"
        f"THEME QUALITY CHECK\n"
        f"  [ ] Each theme is specific to THIS buyer\n"
        f"  [ ] Each theme is provable with evidence\n"
        f"  [ ] Each theme differentiates without mentioning competitors\n"
        f"  [ ] Swapping the buyer's name would break the theme\n"
    )


async def write_executive_summary(
    opportunity_name: Annotated[str, "Opportunity or proposal name"],
    buyer_situation: Annotated[str, "The buyer's current situation in their own language"],
    central_tension: Annotated[str, "The cost of inaction or opportunity at risk"],
    solution_thesis: Annotated[str, "How our approach resolves the tension"],
    proof_point: Annotated[str, "One concrete evidence point (metric, case study, differentiator)"],
    transformed_state: Annotated[str, "What their organization looks like after implementation"],
) -> str:
    """Write a persuasive one-page executive summary following the five-part structure."""
    log_action("SalesProposalAgent", "exec_summary", f"opp={opportunity_name[:60]}")

    return (
        f"EXECUTIVE SUMMARY\n{'=' * 60}\n\n"
        f"[MIRROR THE BUYER]\n"
        f"  {buyer_situation}\n\n"
        f"[CENTRAL TENSION]\n"
        f"  {central_tension}\n\n"
        f"[SOLUTION THESIS]\n"
        f"  {solution_thesis}\n\n"
        f"[PROOF]\n"
        f"  {proof_point}\n\n"
        f"[TRANSFORMED STATE]\n"
        f"  {transformed_state}\n\n"
        f"{'─' * 60}\n"
        f"QUALITY CHECK\n"
        f"  [ ] Fits on one page\n"
        f"  [ ] Buyer's name and challenges are specific, not generic\n"
        f"  [ ] Win themes appear naturally\n"
        f"  [ ] Can stand alone as a persuasion document\n"
        f"  [ ] Every sentence earns its place\n"
    )


async def analyze_rfp(
    rfp_text: Annotated[str, "RFP text or key requirements to analyze"],
    evaluation_criteria: Annotated[str, "Known scoring criteria and weights"] = "",
    bid_decision: Annotated[str, "Considering: bid, no-bid, or already committed"] = "bid",
) -> str:
    """Analyze an RFP for requirements, scoring criteria, risks, and proposal strategy."""
    log_action("SalesProposalAgent", "analyze_rfp", f"decision={bid_decision}, len={len(rfp_text)}")

    return (
        f"RFP ANALYSIS\n{'=' * 60}\n\n"
        f"Decision Status: {bid_decision}\n"
        f"RFP Length:      {len(rfp_text):,} characters\n\n"
        f"REQUIREMENTS BREAKDOWN\n{'─' * 60}\n"
        f"  Mandatory:  [List must-have requirements]\n"
        f"  Evaluated:  [List scored requirements]\n"
        f"  Nice-to-have: [List optional/bonus items]\n\n"
        f"EVALUATION CRITERIA\n{'─' * 60}\n"
        f"  {evaluation_criteria or '[Extract from RFP or request from buyer]'}\n\n"
        f"RISK ASSESSMENT\n{'─' * 60}\n"
        f"  Compliance Risks:   [Requirements we may not fully meet]\n"
        f"  Competitive Risks:  [Where competitors have advantage]\n"
        f"  Execution Risks:    [Delivery challenges]\n\n"
        f"PROPOSAL STRATEGY\n{'─' * 60}\n"
        f"  Narrative Arc:      Understanding -> Solution -> Outcomes\n"
        f"  Key Differentiators: [Map to win themes]\n"
        f"  Compliance+Strategy: Answer every requirement, layer in themes\n\n"
        f"BID/NO-BID ASSESSMENT\n"
        f"  Win Probability: [Estimate based on fit and competition]\n"
        f"  Resource Investment: [Effort to produce competitive proposal]\n"
        f"  Strategic Value:     [Beyond this deal — reference, relationship]\n"
    )


SALESPROPOSAL_TOOLS = [develop_win_themes, write_executive_summary, analyze_rfp]
