import logging
from config import get_agent_configs
from agents.orchestrator import Orchestrator

# Import all agent toolsets
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

# Specialists
from agents.research_agent import RESEARCH_AGENT_NAME, RESEARCH_AGENT_TOOLS, RESEARCH_AGENT_DESCRIPTION, RESEARCH_AGENT_INSTRUCTIONS
from agents.codeexecutor_agent import CODEEXECUTOR_AGENT_NAME, CODEEXECUTOR_AGENT_TOOLS, CODEEXECUTOR_AGENT_DESCRIPTION, CODEEXECUTOR_AGENT_INSTRUCTIONS
from agents.documentanalyst_agent import DOCUMENTANALYST_AGENT_NAME, DOCUMENTANALYST_AGENT_TOOLS, DOCUMENTANALYST_AGENT_DESCRIPTION, DOCUMENTANALYST_AGENT_INSTRUCTIONS
from agents.critic_agent import CRITIC_AGENT_NAME, CRITIC_AGENT_TOOLS, CRITIC_AGENT_DESCRIPTION, CRITIC_AGENT_INSTRUCTIONS

def build_orchestrator() -> Orchestrator:
    agent_configs = get_agent_configs()
    orchestrator = Orchestrator()
    
    def register(key, name, tools, default_desc=""):
        cfg = agent_configs.get(key, {})
        orchestrator.register_agent(
            name=name,
            system_message=cfg.get("system_message", f"You are the {name}"),
            description=cfg.get("description", default_desc or name),
            tools=tools
        )

    # Core agents
    register("email_agent", "EmailAgent", EMAIL_TOOLS)
    register("calendar_agent", "CalendarAgent", CALENDAR_TOOLS)
    register("social_agent", "SocialAgent", SOCIAL_TOOLS)
    register("finance_agent", "FinanceAgent", FINANCE_TOOLS)
    register("business_agent", "BusinessAgent", BUSINESS_TOOLS)
    register("problemsolver_agent", "ProblemSolverAgent", PROBLEMSOLVER_TOOLS)
    register("aiengineer_agent", "AIEngineerAgent", AIENGINEER_TOOLS)
    register("enterprise_agent", "EnterpriseIntegrationAgent", ENTERPRISE_TOOLS)
    register("growthhacker_agent", "GrowthHackerAgent", GROWTHHACKER_TOOLS)
    register("legal_agent", "LegalAdvisorAgent", LEGAL_TOOLS)
    register("seniordev_agent", "SeniorDevAgent", SENIORDEV_TOOLS)
    register("softwarearchitect_agent", "SoftwareArchitectAgent", SOFTWAREARCHITECT_TOOLS)
    register("dataengineer_agent", "DataEngineerAgent", DATAENGINEER_TOOLS)
    register("azurearchitect_agent", "AzureSolutionArchitectAgent", AZUREARCHITECT_TOOLS)
    register("databricks_agent", "DatabricksSpecialistAgent", DATABRICKS_TOOLS)
    register("uxarchitect_agent", "UXArchitectAgent", UXARCHITECT_TOOLS)
    register("productmanager_agent", "ProductManagerAgent", PRODUCTMANAGER_TOOLS)
    register("projectmanager_agent", "ProjectManagerAgent", PROJECTMANAGER_TOOLS)
    register("proposalstrategist_agent", "ProposalStrategistAgent", PROPOSALSTRATEGIST_TOOLS)
    register("dealstrategist_agent", "DealStrategistAgent", DEALSTRATEGIST_TOOLS)
    register("optimizationarchitect_agent", "OptimizationArchitectAgent", OPTIMIZATIONARCHITECT_TOOLS)
    register("devopsautomator_agent", "DevOpsAutomatorAgent", DEVOPSAUTOMATOR_TOOLS)
    register("legaldocreview_agent", "LegalDocReviewAgent", LEGALDOCREVIEW_TOOLS)
    register("realestate_agent", "RealEstateAgent", REALESTATE_TOOLS)
    register("investmentresearcher_agent", "InvestmentResearcherAgent", INVESTMENTRESEARCHER_TOOLS)
    register("projectshepherd_agent", "ProjectShepherdAgent", PROJECTSHEPHERD_TOOLS)
    register("securityengineer_agent", "SecurityEngineerAgent", SECURITYENGINEER_TOOLS)
    register("frontenddev_agent", "FrontendDevAgent", FRONTENDDEV_TOOLS)
    register("backendarchitect_agent", "BackendArchitectAgent", BACKENDARCHITECT_TOOLS)
    register("taxstrategist_agent", "TaxStrategistAgent", TAXSTRATEGIST_TOOLS)
    register("emailintel_agent", "EmailIntelAgent", EMAILINTEL_TOOLS)
    register("salesproposal_agent", "SalesProposalAgent", SALESPROPOSAL_TOOLS)
    register("research_agent", RESEARCH_AGENT_NAME, RESEARCH_AGENT_TOOLS)
    register("codeexecutor_agent", CODEEXECUTOR_AGENT_NAME, CODEEXECUTOR_AGENT_TOOLS)
    register("documentanalyst_agent", DOCUMENTANALYST_AGENT_NAME, DOCUMENTANALYST_AGENT_TOOLS)
    register("critic_agent", CRITIC_AGENT_NAME, CRITIC_AGENT_TOOLS)

    return orchestrator
