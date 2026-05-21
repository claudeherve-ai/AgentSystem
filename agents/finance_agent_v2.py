"""FinanceAgent — Finance, tax, investment powerhouse.
Merges: FinanceAgent + TaxStrategist + InvestmentResearcher"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.finance_agent import (log_expense,set_budget,get_budget_report,create_invoice,list_invoices)
from agents.taxstrategist_agent import (analyze_tax_strategy,calculate_estimated_taxes,review_tax_position)
from agents.investmentresearcher_agent import (research_company,run_due_diligence,analyze_portfolio)
FINANCE_TOOLS_V2 = [log_expense,set_budget,get_budget_report,create_invoice,list_invoices,analyze_tax_strategy,calculate_estimated_taxes,review_tax_position,research_company,run_due_diligence,analyze_portfolio]
__all__=["FINANCE_TOOLS_V2"]
