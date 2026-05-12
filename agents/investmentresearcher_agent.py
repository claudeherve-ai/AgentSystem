"""
AgentSystem — Investment Researcher Agent.

Institutional-quality investment research: fundamental analysis, valuation,
due diligence, and portfolio assessment.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n---\nDISCLAIMER: This is AI-generated research for informational purposes only. "
    "It is NOT investment advice. Consult a qualified financial advisor before making decisions."
)


async def research_company(
    company_name: Annotated[str, "Company or ticker symbol to research"],
    research_focus: Annotated[str, "Focus: overview, fundamentals, valuation, risks, or full"],
    investment_horizon: Annotated[str, "Horizon: short-term (< 1yr), medium (1-3yr), or long-term (5+yr)"] = "medium",
) -> str:
    """Generate an investment research report framework for a company."""
    log_action("InvestmentResearcherAgent", "research_company", f"company={company_name}, focus={research_focus}")

    return (
        f"INVESTMENT RESEARCH: {company_name.upper()}\n{'=' * 60}\n\n"
        f"Focus:    {research_focus}\n"
        f"Horizon:  {investment_horizon}\n\n"
        f"EXECUTIVE SUMMARY\n{'─' * 60}\n"
        f"  [Thesis, key drivers, expected return range]\n\n"
        f"BULL CASE\n{'─' * 60}\n"
        f"  1. [Driver with quantified support]\n"
        f"  2. [Driver with quantified support]\n"
        f"  3. [Driver with quantified support]\n\n"
        f"BEAR CASE & RISKS\n{'─' * 60}\n"
        f"  1. [Risk with quantified downside impact]\n"
        f"  2. [Risk with quantified downside impact]\n\n"
        f"THESIS BREAKERS\n"
        f"  - If [metric] falls below [threshold], exit position\n"
        f"  - If [event] occurs, reassess immediately\n\n"
        f"VALUATION SUMMARY\n{'─' * 60}\n"
        f"  {'Scenario':<10} {'Revenue CAGR':<14} {'Implied Price':<14} {'Weight':<8}\n"
        f"  {'Bull':<10} {'__%':<14} {'$___':<14} {'25%':<8}\n"
        f"  {'Base':<10} {'__%':<14} {'$___':<14} {'50%':<8}\n"
        f"  {'Bear':<10} {'__%':<14} {'$___':<14} {'25%':<8}\n"
        + _DISCLAIMER
    )


async def run_due_diligence(
    target_name: Annotated[str, "Company or deal name"],
    dd_stage: Annotated[str, "Stage: initial, intermediate, or final"],
    focus_areas: Annotated[str, "Comma-separated areas: financial, operational, market, legal"] = "financial,operational",
) -> str:
    """Generate a due diligence checklist and findings framework."""
    log_action("InvestmentResearcherAgent", "due_diligence", f"target={target_name}, stage={dd_stage}")
    areas = [a.strip() for a in focus_areas.split(",")]

    result = (
        f"DUE DILIGENCE REPORT: {target_name}\n{'=' * 60}\n\n"
        f"Stage: {dd_stage}  |  Focus: {', '.join(areas)}\n\n"
    )
    checklists = {
        "financial": "  [ ] Revenue quality  [ ] Earnings sustainability  [ ] Balance sheet  [ ] Cash flow",
        "operational": "  [ ] Customer interviews  [ ] Supplier analysis  [ ] Tech assessment  [ ] Mgmt references",
        "market": "  [ ] TAM/SAM validation  [ ] Competitive positioning  [ ] Regulatory risk  [ ] Growth runway",
        "legal": "  [ ] IP portfolio  [ ] Litigation review  [ ] Contract review  [ ] Compliance",
    }
    for area in areas:
        result += f"{area.upper()} CHECKLIST\n{'─' * 60}\n{checklists.get(area, '  [Custom checklist]')}\n\n"

    result += (
        f"RED FLAGS\n{'─' * 60}\n"
        "  {'Finding':<30} {'Severity':<10} {'Recommendation'}\n"
        "  [Populate with investigation results]\n"
    )
    result += _DISCLAIMER
    return result


async def analyze_portfolio(
    holdings: Annotated[str, "JSON array or comma-separated list of holdings with allocations"],
    analysis_type: Annotated[str, "Type: concentration, risk, performance, or rebalance"] = "risk",
) -> str:
    """Analyze a portfolio for concentration, risk metrics, or rebalancing opportunities."""
    log_action("InvestmentResearcherAgent", "analyze_portfolio", f"type={analysis_type}")

    return (
        f"PORTFOLIO ANALYSIS\n{'=' * 60}\n\n"
        f"Analysis Type: {analysis_type}\n"
        f"Holdings: {holdings[:200]}\n\n"
        f"KEY METRICS\n{'─' * 60}\n"
        f"  Diversification Score: [Calculate]\n"
        f"  Top-5 Concentration:   [Calculate]\n"
        f"  Sector Exposure:       [Breakdown]\n"
        f"  Estimated Beta:        [Calculate]\n\n"
        f"RECOMMENDATIONS\n{'─' * 60}\n"
        f"  [Based on {analysis_type} analysis]\n"
        + _DISCLAIMER
    )


INVESTMENTRESEARCHER_TOOLS = [research_company, run_due_diligence, analyze_portfolio]
