"""RevenueAgent — Sales, deals, growth powerhouse.
Merges: DealStrategist + ProposalStrategist + SalesProposal + GrowthHacker"""
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.dealstrategist_agent import (qualify_deal_meddpicc,assess_pipeline_risk,create_competitive_battle_card,build_deal_strategy,design_discovery_questions,forecast_deal)
from agents.proposalstrategist_agent import (develop_win_themes as ps_win_themes,write_executive_summary as ps_exec_summary,create_proposal_architecture,analyze_rfp as ps_analyze_rfp,create_pricing_narrative)
from agents.salesproposal_agent import (develop_win_themes as sp_win_themes,write_executive_summary as sp_exec_summary,analyze_rfp as sp_analyze_rfp)
from agents.growthhacker_agent import (design_viral_loop,create_ab_test,analyze_funnel,generate_growth_dashboard,create_channel_strategy,design_onboarding_flow)
REVENUE_TOOLS = [qualify_deal_meddpicc,assess_pipeline_risk,create_competitive_battle_card,build_deal_strategy,design_discovery_questions,forecast_deal,ps_win_themes,ps_exec_summary,create_proposal_architecture,ps_analyze_rfp,create_pricing_narrative,sp_win_themes,sp_exec_summary,sp_analyze_rfp,design_viral_loop,create_ab_test,analyze_funnel,generate_growth_dashboard,create_channel_strategy,design_onboarding_flow]
__all__=["REVENUE_TOOLS"]
