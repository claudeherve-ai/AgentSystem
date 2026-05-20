"""
AgentSystem — Agent Factory.

Unified build orchestrator that registers all 38 specialist agents.
Used by both the local CLI (main.py) and the cloud dashboard (dashboard.py).

Boil-the-Ocean commitment: every agent gets full tools, full instructions,
and is ready to deliver enterprise-grade results from the moment of registration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_agent_configs, get_system_config
from agents.orchestrator import Orchestrator
from agents.email_agent import EMAIL_TOOLS
from agents.calendar_agent import CALENDAR_TOOLS
from agents.social_agent import SOCIAL_TOOLS
from agents.finance_agent import FINANCE_TOOLS
from agents.business_agent import BUSINESS_TOOLS
from agents.problemsolver_agent import PROBLEMSOLVER_TOOLS
from agents.aiengineer_agent import AIENGINEER_TOOLS
from agents.enterprise_agent import ENTERPRISE_TOOLS
from agents.growthhacker_agent import GROWTHHACKER_TOOLS
from agents.legal_agent import LEGAL_TOOLS
from agents.seniordev_agent import SENIORDEV_TOOLS
from agents.softwarearchitect_agent import SOFTWAREARCHITECT_TOOLS
from agents.dataengineer_agent import DATAENGINEER_TOOLS
from agents.azurearchitect_agent import AZUREARCHITECT_TOOLS
from agents.databricks_agent import DATABRICKS_TOOLS
from agents.uxarchitect_agent import UXARCHITECT_TOOLS
from agents.productmanager_agent import PRODUCTMANAGER_TOOLS
from agents.projectmanager_agent import PROJECTMANAGER_TOOLS
from agents.proposalstrategist_agent import PROPOSALSTRATEGIST_TOOLS
from agents.dealstrategist_agent import DEALSTRATEGIST_TOOLS
from agents.optimizationarchitect_agent import OPTIMIZATIONARCHITECT_TOOLS
from agents.devopsautomator_agent import DEVOPSAUTOMATOR_TOOLS
from agents.legaldocreview_agent import LEGALDOCREVIEW_TOOLS
from agents.realestate_agent import REALESTATE_TOOLS
from agents.investmentresearcher_agent import INVESTMENTRESEARCHER_TOOLS
from agents.projectshepherd_agent import PROJECTSHEPHERD_TOOLS
from agents.securityengineer_agent import SECURITYENGINEER_TOOLS
from agents.frontenddev_agent import FRONTENDDEV_TOOLS
from agents.backendarchitect_agent import BACKENDARCHITECT_TOOLS
from agents.taxstrategist_agent import TAXSTRATEGIST_TOOLS
from agents.emailintel_agent import EMAILINTEL_TOOLS
from agents.salesproposal_agent import SALESPROPOSAL_TOOLS
from agents.research_agent import (
    RESEARCH_AGENT_DESCRIPTION,
    RESEARCH_AGENT_INSTRUCTIONS,
    RESEARCH_AGENT_NAME,
    RESEARCH_AGENT_TOOLS,
)
from agents.codeexecutor_agent import (
    CODEEXECUTOR_AGENT_DESCRIPTION,
    CODEEXECUTOR_AGENT_INSTRUCTIONS,
    CODEEXECUTOR_AGENT_NAME,
    CODEEXECUTOR_AGENT_TOOLS,
)
from agents.documentanalyst_agent import (
    DOCUMENTANALYST_AGENT_DESCRIPTION,
    DOCUMENTANALYST_AGENT_INSTRUCTIONS,
    DOCUMENTANALYST_AGENT_NAME,
    DOCUMENTANALYST_AGENT_TOOLS,
)
from agents.critic_agent import (
    CRITIC_AGENT_DESCRIPTION,
    CRITIC_AGENT_INSTRUCTIONS,
    CRITIC_AGENT_NAME,
    CRITIC_AGENT_TOOLS,
)


def build_orchestrator() -> Orchestrator:
    """Build and configure the orchestrator with all 38 specialist agents."""
    agent_configs = get_agent_configs()
    orchestrator = Orchestrator()

    # ── Communication & Productivity ─────────────────────────────────
    email_cfg = agent_configs.get("email_agent", {})
    orchestrator.register_agent(
        name="EmailAgent",
        system_message=email_cfg.get("system_message", "You are an email management agent."),
        description=email_cfg.get("description", "Reads, drafts, and sends emails"),
        tools=EMAIL_TOOLS,
    )

    cal_cfg = agent_configs.get("calendar_agent", {})
    orchestrator.register_agent(
        name="CalendarAgent",
        system_message=cal_cfg.get("system_message", "You are a calendar management agent."),
        description=cal_cfg.get("description", "Manages appointments and scheduling"),
        tools=CALENDAR_TOOLS,
    )

    social_cfg = agent_configs.get("social_agent", {})
    orchestrator.register_agent(
        name="SocialAgent",
        system_message=social_cfg.get("system_message", "You are a social media management agent."),
        description=social_cfg.get("description", "Manages social media posting"),
        tools=SOCIAL_TOOLS,
    )

    ei_cfg = agent_configs.get("emailintel_agent", {})
    orchestrator.register_agent(
        name="EmailIntelAgent",
        system_message=ei_cfg.get("system_message", "You are an email intelligence specialist."),
        description=ei_cfg.get("description", "Email thread analysis, action items, decision tracking"),
        tools=EMAILINTEL_TOOLS,
    )

    # ── Business & Finance ──────────────────────────────────────────
    finance_cfg = agent_configs.get("finance_agent", {})
    orchestrator.register_agent(
        name="FinanceAgent",
        system_message=finance_cfg.get("system_message", "You are a finance management agent."),
        description=finance_cfg.get("description", "Tracks expenses, budgets, and invoices"),
        tools=FINANCE_TOOLS,
    )

    business_cfg = agent_configs.get("business_agent", {})
    orchestrator.register_agent(
        name="BusinessAgent",
        system_message=business_cfg.get("system_message", "You are a business operations agent."),
        description=business_cfg.get("description", "Manages customers, proposals, and CRM"),
        tools=BUSINESS_TOOLS,
    )

    tax_cfg = agent_configs.get("taxstrategist_agent", {})
    orchestrator.register_agent(
        name="TaxStrategistAgent",
        system_message=tax_cfg.get("system_message", "You are a veteran tax strategist."),
        description=tax_cfg.get("description", "Tax optimization, entity structuring, compliance"),
        tools=TAXSTRATEGIST_TOOLS,
    )

    # ── Sales & Growth ──────────────────────────────────────────────
    gh_cfg = agent_configs.get("growthhacker_agent", {})
    orchestrator.register_agent(
        name="GrowthHackerAgent",
        system_message=gh_cfg.get("system_message", "You are a growth hacking specialist."),
        description=gh_cfg.get("description", "Growth experiments and user acquisition"),
        tools=GROWTHHACKER_TOOLS,
    )

    ds_cfg = agent_configs.get("dealstrategist_agent", {})
    orchestrator.register_agent(
        name="DealStrategistAgent",
        system_message=ds_cfg.get("system_message", "You are a senior deal strategist."),
        description=ds_cfg.get("description", "MEDDPICC qualification and pipeline risk"),
        tools=DEALSTRATEGIST_TOOLS,
    )

    ps_cfg = agent_configs.get("proposalstrategist_agent", {})
    orchestrator.register_agent(
        name="ProposalStrategistAgent",
        system_message=ps_cfg.get("system_message", "You are a senior proposal strategist."),
        description=ps_cfg.get("description", "Win themes, RFP analysis, executive summaries"),
        tools=PROPOSALSTRATEGIST_TOOLS,
    )

    sp_cfg = agent_configs.get("salesproposal_agent", {})
    orchestrator.register_agent(
        name="SalesProposalAgent",
        system_message=sp_cfg.get("system_message", "You are a senior sales proposal strategist."),
        description=sp_cfg.get("description", "Win themes, executive summaries, RFP analysis"),
        tools=SALESPROPOSAL_TOOLS,
    )

    # ── Engineering & Architecture ──────────────────────────────────
    sd_cfg = agent_configs.get("seniordev_agent", {})
    orchestrator.register_agent(
        name="SeniorDevAgent",
        system_message=sd_cfg.get("system_message", "You are a senior full-stack developer."),
        description=sd_cfg.get("description", "Premium code implementation and review"),
        tools=SENIORDEV_TOOLS,
    )

    sa_cfg = agent_configs.get("softwarearchitect_agent", {})
    orchestrator.register_agent(
        name="SoftwareArchitectAgent",
        system_message=sa_cfg.get("system_message", "You are an expert software architect."),
        description=sa_cfg.get("description", "System design and architecture decisions"),
        tools=SOFTWAREARCHITECT_TOOLS,
    )

    bea_cfg = agent_configs.get("backendarchitect_agent", {})
    orchestrator.register_agent(
        name="BackendArchitectAgent",
        system_message=bea_cfg.get("system_message", "You are a senior backend architect."),
        description=bea_cfg.get("description", "System design, database architecture, API design"),
        tools=BACKENDARCHITECT_TOOLS,
    )

    fed_cfg = agent_configs.get("frontenddev_agent", {})
    orchestrator.register_agent(
        name="FrontendDevAgent",
        system_message=fed_cfg.get("system_message", "You are an expert frontend developer."),
        description=fed_cfg.get("description", "React/Vue/Angular, accessibility, performance optimization"),
        tools=FRONTENDDEV_TOOLS,
    )

    ux_cfg = agent_configs.get("uxarchitect_agent", {})
    orchestrator.register_agent(
        name="UXArchitectAgent",
        system_message=ux_cfg.get("system_message", "You are a UX architecture specialist."),
        description=ux_cfg.get("description", "CSS systems, layouts, and accessibility"),
        tools=UXARCHITECT_TOOLS,
    )

    # ── Cloud & Data ────────────────────────────────────────────────
    de_cfg = agent_configs.get("dataengineer_agent", {})
    orchestrator.register_agent(
        name="DataEngineerAgent",
        system_message=de_cfg.get("system_message", "You are an expert data engineer."),
        description=de_cfg.get("description", "Data pipelines, lakehouse, and data quality"),
        tools=DATAENGINEER_TOOLS,
    )

    az_cfg = agent_configs.get("azurearchitect_agent", {})
    orchestrator.register_agent(
        name="AzureSolutionArchitectAgent",
        system_message=az_cfg.get("system_message", "You are an elite senior cloud solution architect."),
        description=az_cfg.get("description", "Azure, hybrid, and multi-cloud architecture plus migration and troubleshooting"),
        tools=AZUREARCHITECT_TOOLS,
    )

    dbx_cfg = agent_configs.get("databricks_agent", {})
    orchestrator.register_agent(
        name="DatabricksSpecialistAgent",
        system_message=dbx_cfg.get("system_message", "You are a Databricks platform specialist."),
        description=dbx_cfg.get("description", "Databricks architecture, governance, Spark optimization, delivery, and troubleshooting"),
        tools=DATABRICKS_TOOLS,
    )

    do_cfg = agent_configs.get("devopsautomator_agent", {})
    orchestrator.register_agent(
        name="DevOpsAutomatorAgent",
        system_message=do_cfg.get("system_message", "You are an expert DevOps engineer."),
        description=do_cfg.get("description", "CI/CD, IaC, containers, monitoring, DR"),
        tools=DEVOPSAUTOMATOR_TOOLS,
    )

    oa_cfg = agent_configs.get("optimizationarchitect_agent", {})
    orchestrator.register_agent(
        name="OptimizationArchitectAgent",
        system_message=oa_cfg.get("system_message", "You are an optimization architect."),
        description=oa_cfg.get("description", "API performance, cost optimization, circuit breakers"),
        tools=OPTIMIZATIONARCHITECT_TOOLS,
    )

    # ── AI & Intelligence ───────────────────────────────────────────
    ai_cfg = agent_configs.get("aiengineer_agent", {})
    orchestrator.register_agent(
        name="AIEngineerAgent",
        system_message=ai_cfg.get("system_message", "You are an AI/ML engineering specialist."),
        description=ai_cfg.get("description", "AI/ML implementation and LLM integration"),
        tools=AIENGINEER_TOOLS,
    )

    ps_cfg_2 = agent_configs.get("problemsolver_agent", {})
    orchestrator.register_agent(
        name="ProblemSolverAgent",
        system_message=ps_cfg_2.get("system_message", "You are a universal problem-solving specialist."),
        description=ps_cfg_2.get("description", "Complex debugging and investigation"),
        tools=PROBLEMSOLVER_TOOLS,
    )

    # ── Legal & Compliance ──────────────────────────────────────────
    legal_cfg = agent_configs.get("legal_agent", {})
    orchestrator.register_agent(
        name="LegalAdvisorAgent",
        system_message=legal_cfg.get("system_message", "You are a legal advisory agent."),
        description=legal_cfg.get("description", "Legal docs, compliance, and contracts"),
        tools=LEGAL_TOOLS,
    )

    ldr_cfg = agent_configs.get("legaldocreview_agent", {})
    orchestrator.register_agent(
        name="LegalDocReviewAgent",
        system_message=ldr_cfg.get("system_message", "You are a legal document review specialist."),
        description=ldr_cfg.get("description", "Contract analysis, risk clauses, version comparison"),
        tools=LEGALDOCREVIEW_TOOLS,
    )

    # ── Enterprise & Strategy ───────────────────────────────────────
    ent_cfg = agent_configs.get("enterprise_agent", {})
    orchestrator.register_agent(
        name="EnterpriseIntegrationAgent",
        system_message=ent_cfg.get("system_message", "You are an enterprise integration architect."),
        description=ent_cfg.get("description", "Enterprise system integrations"),
        tools=ENTERPRISE_TOOLS,
    )

    pm_cfg = agent_configs.get("productmanager_agent", {})
    orchestrator.register_agent(
        name="ProductManagerAgent",
        system_message=pm_cfg.get("system_message", "You are a seasoned product manager."),
        description=pm_cfg.get("description", "PRDs, roadmaps, and go-to-market"),
        tools=PRODUCTMANAGER_TOOLS,
    )

    pjm_cfg = agent_configs.get("projectmanager_agent", {})
    orchestrator.register_agent(
        name="ProjectManagerAgent",
        system_message=pjm_cfg.get("system_message", "You are an expert project manager."),
        description=pjm_cfg.get("description", "Project plans, risks, and stakeholder reports"),
        tools=PROJECTMANAGER_TOOLS,
    )

    psh_cfg = agent_configs.get("projectshepherd_agent", {})
    orchestrator.register_agent(
        name="ProjectShepherdAgent",
        system_message=psh_cfg.get("system_message", "You are an expert project coordinator."),
        description=psh_cfg.get("description", "Cross-functional project coordination and stakeholder alignment"),
        tools=PROJECTSHEPHERD_TOOLS,
    )

    re_cfg = agent_configs.get("realestate_agent", {})
    orchestrator.register_agent(
        name="RealEstateAgent",
        system_message=re_cfg.get("system_message", "You are a real estate specialist."),
        description=re_cfg.get("description", "Property analysis, CMA, offer strategy, investment analysis"),
        tools=REALESTATE_TOOLS,
    )

    ir_cfg = agent_configs.get("investmentresearcher_agent", {})
    orchestrator.register_agent(
        name="InvestmentResearcherAgent",
        system_message=ir_cfg.get("system_message", "You are a veteran investment researcher."),
        description=ir_cfg.get("description", "Investment research, due diligence, portfolio analysis"),
        tools=INVESTMENTRESEARCHER_TOOLS,
    )

    # ── Security ────────────────────────────────────────────────────
    sec_cfg = agent_configs.get("securityengineer_agent", {})
    orchestrator.register_agent(
        name="SecurityEngineerAgent",
        system_message=sec_cfg.get("system_message", "You are an application security engineer."),
        description=sec_cfg.get("description", "Threat modeling, vulnerability assessment, secure code review"),
        tools=SECURITYENGINEER_TOOLS,
    )

    # ── Boil-the-Ocean Specialist Agents ────────────────────────────
    research_cfg = agent_configs.get("research_agent", {})
    orchestrator.register_agent(
        name=RESEARCH_AGENT_NAME,
        system_message=research_cfg.get("system_message", RESEARCH_AGENT_INSTRUCTIONS),
        description=research_cfg.get("description", RESEARCH_AGENT_DESCRIPTION),
        tools=RESEARCH_AGENT_TOOLS,
    )

    codeexec_cfg = agent_configs.get("codeexecutor_agent", {})
    orchestrator.register_agent(
        name=CODEEXECUTOR_AGENT_NAME,
        system_message=codeexec_cfg.get("system_message", CODEEXECUTOR_AGENT_INSTRUCTIONS),
        description=codeexec_cfg.get("description", CODEEXECUTOR_AGENT_DESCRIPTION),
        tools=CODEEXECUTOR_AGENT_TOOLS,
    )

    docanalyst_cfg = agent_configs.get("documentanalyst_agent", {})
    orchestrator.register_agent(
        name=DOCUMENTANALYST_AGENT_NAME,
        system_message=docanalyst_cfg.get("system_message", DOCUMENTANALYST_AGENT_INSTRUCTIONS),
        description=docanalyst_cfg.get("description", DOCUMENTANALYST_AGENT_DESCRIPTION),
        tools=DOCUMENTANALYST_AGENT_TOOLS,
    )

    critic_cfg = agent_configs.get("critic_agent", {})
    orchestrator.register_agent(
        name=CRITIC_AGENT_NAME,
        system_message=critic_cfg.get("system_message", CRITIC_AGENT_INSTRUCTIONS),
        description=critic_cfg.get("description", CRITIC_AGENT_DESCRIPTION),
        tools=CRITIC_AGENT_TOOLS,
    )

    return orchestrator


__all__ = ["build_orchestrator"]
