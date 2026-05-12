"""
AgentSystem — Real Estate Agent.

Buyer and seller representation assistant for property analysis,
CMA preparation, offer strategy, and transaction coordination.
"""

import logging
import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.audit import log_action

logger = logging.getLogger(__name__)


async def prepare_cma(
    property_address: Annotated[str, "Subject property address"],
    property_type: Annotated[str, "Type: single-family, condo, townhome, multi-family"],
    beds: Annotated[int, "Number of bedrooms"],
    baths: Annotated[float, "Number of bathrooms"],
    sqft: Annotated[int, "Square footage"],
    purpose: Annotated[str, "Purpose: listing-price or offer-price"] = "listing-price",
) -> str:
    """Prepare a Comparative Market Analysis framework for pricing a property."""
    log_action("RealEstateAgent", "prepare_cma", f"addr={property_address[:60]}, purpose={purpose}")

    return (
        f"COMPARATIVE MARKET ANALYSIS\n{'=' * 60}\n\n"
        f"Subject:  {property_address}\n"
        f"Type:     {property_type}  |  {beds}bd / {baths}ba  |  {sqft:,} sqft\n"
        f"Purpose:  {purpose}\n\n"
        f"COMPARABLE SALES (template)\n{'─' * 60}\n"
        f"  {'Address':<25} {'Sale Price':<12} {'$/SqFt':<10} {'DOM':<5}\n"
        f"  {'─'*52}\n"
        f"  {'[Comp 1]':<25} {'$___,___':<12} {'$___':<10} {'__':<5}\n"
        f"  {'[Comp 2]':<25} {'$___,___':<12} {'$___':<10} {'__':<5}\n"
        f"  {'[Comp 3]':<25} {'$___,___':<12} {'$___':<10} {'__':<5}\n\n"
        f"MARKET CONDITIONS\n"
        f"  Months of Inventory: ___\n"
        f"  Avg DOM:             ___\n"
        f"  List-to-Sale Ratio:  ___%\n\n"
        f"PRICING RECOMMENDATION\n"
        f"  Suggested Range: $_______ to $_______\n"
        f"  Strategy: [Price at market / aggressive / conservative]\n"
    )


async def draft_offer_strategy(
    property_address: Annotated[str, "Target property address"],
    list_price: Annotated[float, "Current listing price"],
    buyer_max_budget: Annotated[float, "Buyer maximum budget (confidential)"],
    market_conditions: Annotated[str, "Market type: buyers-market, balanced, or sellers-market"],
    competing_offers: Annotated[int, "Known or estimated number of competing offers"] = 0,
) -> str:
    """Draft an offer strategy with pricing, contingencies, and negotiation approach."""
    log_action("RealEstateAgent", "draft_offer_strategy", f"addr={property_address[:60]}")

    return (
        f"OFFER STRATEGY\n{'=' * 60}\n\n"
        f"Property:     {property_address}\n"
        f"List Price:   ${list_price:,.0f}\n"
        f"Market:       {market_conditions}\n"
        f"Competition:  {competing_offers} known/estimated offers\n\n"
        f"RECOMMENDED APPROACH\n{'─' * 60}\n"
        f"  Initial Offer:    [Calculate based on comps and competition]\n"
        f"  Earnest Money:    [1-3% of offer price]\n"
        f"  Contingencies:    Inspection, financing, appraisal\n"
        f"  Escalation:       [Consider if multiple offers expected]\n"
        f"  Closing Timeline: [30-45 days typical]\n\n"
        f"NEGOTIATION NOTES\n"
        f"  - Lead with terms strength if budget is competitive\n"
        f"  - Personal letter to seller can differentiate in tight markets\n"
        f"  - Pre-approval letter should accompany offer\n"
    )


async def analyze_investment_property(
    property_address: Annotated[str, "Property address"],
    purchase_price: Annotated[float, "Expected purchase price"],
    monthly_rent: Annotated[float, "Expected monthly rental income"],
    annual_expenses: Annotated[float, "Estimated annual expenses (taxes, insurance, maintenance)"],
    down_payment_pct: Annotated[float, "Down payment percentage"] = 25.0,
    interest_rate: Annotated[float, "Mortgage interest rate percentage"] = 7.0,
) -> str:
    """Analyze a rental property investment with cap rate, cash-on-cash, and cash flow projections."""
    log_action("RealEstateAgent", "analyze_investment", f"addr={property_address[:60]}")

    annual_rent = monthly_rent * 12
    noi = annual_rent - annual_expenses
    cap_rate = (noi / purchase_price) * 100 if purchase_price > 0 else 0
    down_payment = purchase_price * (down_payment_pct / 100)

    return (
        f"INVESTMENT ANALYSIS\n{'=' * 60}\n\n"
        f"Property:       {property_address}\n"
        f"Purchase Price: ${purchase_price:,.0f}\n"
        f"Down Payment:   ${down_payment:,.0f} ({down_payment_pct}%)\n\n"
        f"INCOME\n{'─' * 60}\n"
        f"  Monthly Rent:     ${monthly_rent:,.0f}\n"
        f"  Annual Gross:     ${annual_rent:,.0f}\n"
        f"  Annual Expenses:  ${annual_expenses:,.0f}\n"
        f"  NOI:              ${noi:,.0f}\n\n"
        f"KEY METRICS\n{'─' * 60}\n"
        f"  Cap Rate:         {cap_rate:.1f}%\n"
        f"  GRM:              {purchase_price / annual_rent:.1f}x\n"
        f"  Interest Rate:    {interest_rate}%\n\n"
        f"NOTE: Run full cash-on-cash analysis with actual mortgage terms.\n"
    )


REALESTATE_TOOLS = [prepare_cma, draft_offer_strategy, analyze_investment_property]
