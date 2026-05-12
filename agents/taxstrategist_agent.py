"""
AgentSystem — Tax Strategist Agent.

Tax optimization, multi-jurisdictional compliance, entity structuring,
and strategic tax planning.

DISCLAIMER: All outputs are AI-generated and do NOT constitute tax or legal advice.
Consult a qualified tax professional for all tax matters.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n---\nDISCLAIMER: This is AI-generated tax analysis, NOT professional tax advice. "
    "Consult a qualified CPA or tax attorney before making tax decisions."
)


async def analyze_tax_strategy(
    entity_type: Annotated[str, "Entity type: C-Corp, S-Corp, LLC, partnership, sole-prop, or trust"],
    annual_revenue: Annotated[str, "Approximate annual revenue range"],
    jurisdictions: Annotated[str, "Comma-separated jurisdictions (states/countries)"],
    focus: Annotated[str, "Focus: deductions, entity-structure, credits, international, or comprehensive"] = "comprehensive",
) -> str:
    """Analyze tax optimization opportunities for a given entity and structure."""
    log_action("TaxStrategistAgent", "analyze_strategy", f"entity={entity_type}, focus={focus}")

    return (
        f"TAX STRATEGY ANALYSIS\n{'=' * 60}\n\n"
        f"Entity:       {entity_type}\n"
        f"Revenue:      {annual_revenue}\n"
        f"Jurisdictions: {jurisdictions}\n"
        f"Focus:        {focus}\n\n"
        f"OPTIMIZATION OPPORTUNITIES\n{'─' * 60}\n"
        f"  1. R&D Tax Credits — Qualify activities, document expenses\n"
        f"  2. Section 179 / Bonus Depreciation — Accelerate deductions\n"
        f"  3. QBI Deduction — 20% pass-through deduction (if eligible)\n"
        f"  4. Retirement Plans — Solo 401(k), SEP IRA, defined benefit\n"
        f"  5. Health Insurance — HSA contributions, employer plans\n"
        f"  6. Charitable Giving — Donor-advised funds, appreciated stock\n\n"
        f"ENTITY STRUCTURE REVIEW\n{'─' * 60}\n"
        f"  Current: {entity_type}\n"
        f"  Consider: [Evaluate based on revenue and growth trajectory]\n"
        f"  S-Corp election savings: [Calculate SE tax savings vs. compliance cost]\n\n"
        f"STATE & LOCAL TAX (SALT)\n{'─' * 60}\n"
        f"  Nexus analysis for: {jurisdictions}\n"
        f"  Apportionment optimization opportunities: [Evaluate]\n"
        f"  Credits and incentives by state: [Research]\n\n"
        f"ESTIMATED SAVINGS RANGE\n"
        f"  [Calculate based on specific facts and circumstances]\n\n"
        f"NEXT STEPS\n"
        f"  1. Engage qualified CPA for implementation\n"
        f"  2. Document all tax positions\n"
        f"  3. Set calendar reminders for filing deadlines\n"
        + _DISCLAIMER
    )


async def calculate_estimated_taxes(
    gross_income: Annotated[float, "Total gross income"],
    deductions: Annotated[float, "Total deductions and adjustments"],
    filing_status: Annotated[str, "Status: single, married-joint, married-separate, or head-of-household"],
    state: Annotated[str, "Primary state for state tax calculation"] = "N/A",
    self_employment_income: Annotated[float, "Self-employment income (if applicable)"] = 0,
) -> str:
    """Calculate estimated federal and state tax liability with quarterly payment schedule."""
    log_action("TaxStrategistAgent", "estimate_taxes", f"gross={gross_income}, status={filing_status}")

    taxable = max(0, gross_income - deductions)
    se_tax = self_employment_income * 0.153 * 0.9235 if self_employment_income > 0 else 0
    quarterly = taxable * 0.24 / 4  # Rough estimate using 24% marginal

    return (
        f"ESTIMATED TAX CALCULATION\n{'=' * 60}\n\n"
        f"Filing Status:       {filing_status}\n"
        f"Gross Income:        ${gross_income:,.0f}\n"
        f"Deductions:          ${deductions:,.0f}\n"
        f"Taxable Income:      ${taxable:,.0f}\n"
        f"SE Income:           ${self_employment_income:,.0f}\n"
        f"State:               {state}\n\n"
        f"ESTIMATED LIABILITY\n{'─' * 60}\n"
        f"  Federal Income Tax:  [Calculate using actual brackets]\n"
        f"  Self-Employment Tax: ${se_tax:,.0f} (estimated)\n"
        f"  State Tax ({state}):  [Apply state rates]\n\n"
        f"QUARTERLY PAYMENTS (estimated)\n{'─' * 60}\n"
        f"  Q1 (Apr 15):  ${quarterly:,.0f}\n"
        f"  Q2 (Jun 15):  ${quarterly:,.0f}\n"
        f"  Q3 (Sep 15):  ${quarterly:,.0f}\n"
        f"  Q4 (Jan 15):  ${quarterly:,.0f}\n\n"
        f"NOTE: Use IRS Form 1040-ES for accurate calculations.\n"
        + _DISCLAIMER
    )


async def review_tax_position(
    position_description: Annotated[str, "Description of the tax position or transaction"],
    authority_level: Annotated[str, "Authority: substantial, reasonable-basis, or more-likely-than-not"],
    estimated_savings: Annotated[float, "Estimated tax savings from this position"],
    risk_factors: Annotated[str, "Known risk factors or concerns"] = "",
) -> str:
    """Review a tax position for strength, risk, and documentation requirements."""
    log_action("TaxStrategistAgent", "review_position", f"authority={authority_level}")

    return (
        f"TAX POSITION REVIEW\n{'=' * 60}\n\n"
        f"Position:  {position_description}\n"
        f"Authority: {authority_level}\n"
        f"Savings:   ${estimated_savings:,.0f}\n"
        f"Risks:     {risk_factors or 'None identified'}\n\n"
        f"ASSESSMENT\n{'─' * 60}\n"
        f"  Strength:     [{authority_level} authority — evaluate specific citations]\n"
        f"  Audit Risk:   [Low/Medium/High based on position aggressiveness]\n"
        f"  Exposure:     [Potential tax, interest, and penalties]\n\n"
        f"DOCUMENTATION REQUIREMENTS\n{'─' * 60}\n"
        f"  [ ] Written tax memorandum with citations\n"
        f"  [ ] Supporting calculations and workpapers\n"
        f"  [ ] Business purpose documentation\n"
        f"  [ ] Contemporaneous records\n\n"
        f"RECOMMENDATION\n"
        f"  [Accept/modify/abandon based on risk-reward analysis]\n"
        + _DISCLAIMER
    )


TAXSTRATEGIST_TOOLS = [analyze_tax_strategy, calculate_estimated_taxes, review_tax_position]
