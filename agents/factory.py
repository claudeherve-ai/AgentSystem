"""
AgentSystem — Agent Factory v3.0
19 powerhouse agents with inter-agent handoff. Each agent has:
- Base capability tools (web search, code execution, KB, critique)
- Domain-specific tools from merged specialist agents
- Claude-skills context injection
- Handoff to peer agents for cross-domain tasks
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_agent_configs
from agents.orchestrator import Orchestrator
from agents.email_agent import EMAIL_TOOLS
from agents.calendar_agent import CALENDAR_TOOLS
from agents.social_agent import SOCIAL_TOOLS
from agents.enterprise_agent import ENTERPRISE_TOOLS
from agents.business_agent import BUSINESS_TOOLS
from agents.aiengineer_agent import AIENGINEER_TOOLS
from agents.securityengineer_agent import SECURITYENGINEER_TOOLS
from agents.productmanager_agent import PRODUCTMANAGER_TOOLS
from agents.projectmanager_agent import PROJECTMANAGER_TOOLS
from agents.projectshepherd_agent import PROJECTSHEPHERD_TOOLS
from agents.realestate_agent import REALESTATE_TOOLS
from agents.emailintel_agent import EMAILINTEL_TOOLS

# Merged agent tools
from agents.engineering_agent import ENGINEERING_TOOLS
from agents.cloud_data_agent import CLOUDDATA_TOOLS
from agents.revenue_agent import REVENUE_TOOLS
from agents.legal_agent_v2 import LEGAL_TOOLS_V2
from agents.finance_agent_v2 import FINANCE_TOOLS_V2
from agents.execution_agent import EXECUTION_TOOLS
from agents.codeexecutor_agent import (
    CODEEXECUTOR_AGENT_DESCRIPTION,
    CODEEXECUTOR_AGENT_INSTRUCTIONS,
    CODEEXECUTOR_AGENT_TOOLS,
)
from toolkits import FINANCE_TOOLS


def build_orchestrator() -> Orchestrator:
    agent_configs = get_agent_configs()
    orch = Orchestrator()

    # ── Communication ────────────────────────────────────────────────────
    orch.register_agent(
        name="EmailAgent",
        system_message=agent_configs.get("email_agent", {}).get("system_message", ""),
        description="Read, draft, send emails via Microsoft Graph. Auth with link_account.",
        tools=EMAIL_TOOLS,
        handoff_agents=["EmailIntelAgent", "CalendarAgent"],
    )
    orch.register_agent(
        name="CalendarAgent",
        system_message=agent_configs.get("calendar_agent", {}).get("system_message", ""),
        description="Manage appointments, scheduling, conflicts via Microsoft Graph",
        tools=CALENDAR_TOOLS,
        handoff_agents=["EmailAgent"],
    )
    orch.register_agent(
        name="SocialAgent",
        system_message=agent_configs.get("social_agent", {}).get("system_message", ""),
        description="Social media posting, engagement across platforms",
        tools=SOCIAL_TOOLS,
        handoff_agents=["RevenueAgent"],
    )
    orch.register_agent(
        name="EmailIntelAgent",
        system_message=agent_configs.get("emailintel_agent", {}).get("system_message", ""),
        description="Email thread analysis, action items, decision tracking",
        tools=EMAILINTEL_TOOLS,
        handoff_agents=["EmailAgent"],
    )

    # ── ENGINEERING HUB (6→1) ───────────────────────────────────────────
    orch.register_agent(
        name="EngineeringAgent",
        system_message=(
            "You are a world-class full-stack engineering lead covering software architecture, "
            "senior development, backend systems, frontend UX, and performance optimization.\n\n"
            "CAPABILITIES:\n"
            "- Design system architectures with trade-off analysis, ADRs, domain models\n"
            "- Review code for quality, security, and performance\n"
            "- Generate production-ready implementations across the full stack\n"
            "- Design database schemas, APIs, component architectures\n"
            "- Create design systems, layouts, accessibility audits\n"
            "- Optimize performance, API costs, circuit breakers, FinOps\n"
            "- Debug complex issues across frontend, backend, and infrastructure\n\n"
            "CRITICAL RULES:\n"
            "1. Always use your tools — never give generic advice when you can design, review, or generate real output.\n"
            "2. Search the web for current best practices before making architecture recommendations (use web_search + web_fetch).\n"
            "3. Generate runnable code with run_python when demonstrating solutions.\n"
            "4. Critique your own architecture decisions before presenting them.\n"
            "5. Handoff to CloudDataAgent for cloud/infra questions, ExecutionAgent for research/debugging loops.\n"
            "6. Every pixel intentional. 60fps animations. WCAG 2.1 AA compliance. Sub-1.5s loads."
        ),
        description="Full-stack engineering: architecture, code, review, performance, UX, optimization (25+ tools)",
        tools=ENGINEERING_TOOLS,
        handoff_agents=["CloudDataAgent", "ExecutionAgent", "SecurityEngineerAgent"],
    )

    # ── CLOUD & DATA HUB (4→1) ──────────────────────────────────────────
    orch.register_agent(
        name="CloudDataAgent",
        system_message=(
            "You are an elite cloud and data engineering specialist covering Azure architecture, "
            "Databricks, data pipelines, DevOps, and infrastructure.\n\n"
            "CAPABILITIES:\n"
            "- Design cloud architectures on Azure with migration planning\n"
            "- Build data pipelines following medallion architecture (Bronze→Silver→Gold)\n"
            "- Design Databricks platforms, optimize Spark, governance review\n"
            "- Create CI/CD pipelines, container setups, monitoring stacks\n"
            "- Design disaster recovery, deployment strategies, infrastructure-as-code\n"
            "- Troubleshoot cloud and data platform issues\n\n"
            "CRITICAL RULES:\n"
            "1. Always use your tools — design real architectures, not generic advice.\n"
            "2. Search Microsoft Docs (microsoft_docs_search) before making Azure recommendations.\n"
            "3. Generate IaC templates (Bicep/Terraform) via run_python.\n"
            "4. Handoff to EngineeringAgent for application architecture, ExecutionAgent for research.\n"
            "5. Idempotent, observable, self-healing — every design must meet these standards."
        ),
        description="Cloud architecture, data pipelines, Databricks, DevOps, CI/CD, IaC (22+ tools)",
        tools=CLOUDDATA_TOOLS,
        handoff_agents=["EngineeringAgent", "ExecutionAgent", "SecurityEngineerAgent"],
    )

    # ── REVENUE HUB (4→1) ───────────────────────────────────────────────
    orch.register_agent(
        name="RevenueAgent",
        system_message=(
            "You are a revenue powerhouse covering deal strategy, proposals, sales, and growth.\n\n"
            "CAPABILITIES:\n"
            "- Qualify deals with MEDDPICC, assess pipeline risk, forecast revenue\n"
            "- Develop win themes, executive summaries, proposal architectures\n"
            "- Analyze RFPs, create pricing narratives, competitive battle cards\n"
            "- Design viral loops, A/B tests, funnel optimization, growth dashboards\n"
            "- Create channel strategies, onboarding flows, growth experiments\n\n"
            "CRITICAL RULES:\n"
            "1. Always back recommendations with data — use web_search for market context.\n"
            "2. Run financial calculations with run_python, not mental math.\n"
            "3. Handoff to FinanceAgent for pricing/budget questions, LegalAgent for contract review.\n"
            "4. Every deal strategy must cite MEDDPICC criteria explicitly.\n"
            "5. Growth experiments must include success metrics and statistical significance thresholds."
        ),
        description="Deals, proposals, sales strategy, growth hacking, funnel optimization (20+ tools)",
        tools=[*REVENUE_TOOLS, *FINANCE_TOOLS],
        handoff_agents=["FinanceAgent", "LegalAgent", "BusinessAgent"],
    )

    # ── LEGAL HUB (2→1) ─────────────────────────────────────────────────
    orch.register_agent(
        name="LegalAgent",
        system_message=(
            "You are a legal advisory and compliance specialist.\n\n"
            "CAPABILITIES:\n"
            "- Draft legal documents (NDA, ToS, DPA, contracts, privacy policies)\n"
            "- Analyze compliance requirements (GDPR, HIPAA, SOC2, CCPA)\n"
            "- Review contracts for risks and unfavorable terms\n"
            "- Compare document versions, check regulatory compliance\n"
            "- Create RFP response frameworks, legal research\n\n"
            "CRITICAL RULES:\n"
            "1. ALWAYS include a disclaimer: output is AI-generated legal information, NOT legal advice.\n"
            "2. Recommend consulting a qualified attorney for all legal matters.\n"
            "3. Search current regulations via web_search before making compliance claims.\n"
            "4. Handoff to RevenueAgent for deal-related legal review.\n"
            "5. Laws vary by jurisdiction — always note jurisdictional context."
        ),
        description="Legal docs, contracts, compliance (GDPR/SOC2/HIPAA), document review (8 tools)",
        tools=LEGAL_TOOLS_V2,
        handoff_agents=["RevenueAgent", "SecurityEngineerAgent"],
    )

    # ── FINANCE HUB (3→1) ───────────────────────────────────────────────
    orch.register_agent(
        name="FinanceAgent",
        system_message=(
            "You are a comprehensive finance specialist covering FP&A, tax, and investments.\n\n"
            "CAPABILITIES:\n"
            "- Track expenses, create budgets, generate financial reports\n"
            "- Analyze tax strategies, calculate estimated taxes, review tax positions\n"
            "- Research companies, run due diligence, analyze portfolios\n"
            "- Create invoices, track budget vs actuals\n\n"
            "CRITICAL RULES:\n"
            "1. Validate all calculations with run_python — never estimate numbers mentally.\n"
            "2. Search current market data via web_search for investment decisions.\n"
            "3. Handoff to RevenueAgent for deal economics, LegalAgent for tax law interpretation.\n"
            "4. All financial advice must include risk disclaimers.\n"
            "5. Use claude-skills financial tools for DCF, ratios, SaaS metrics when applicable."
        ),
        description="Financial planning, tax strategy, investment research, budgeting (11 tools)",
        tools=[*FINANCE_TOOLS_V2, *FINANCE_TOOLS],
        handoff_agents=["RevenueAgent", "LegalAgent"],
    )

    # ── EXECUTION HUB (4→1) ─────────────────────────────────────────────
    orch.register_agent(
        name="ExecutionAgent",
        system_message=(
            "You are the execution engine — research, code, debug, and critique in a tight loop.\n\n"
            "WORKFLOW:\n"
            "1. SEARCH: Use web_search + web_fetch to find current, grounded information\n"
            "2. CODE: Use run_python to compute, transform, and generate output\n"
            "3. REVIEW: Use critique_response to self-review before presenting\n"
            "4. ITERATE: If the first approach fails, research again and retry\n\n"
            "CAPABILITIES:\n"
            "- Multi-step web research with citations\n"
            "- Code execution and data transformation\n"
            "- Systematic problem solving and debugging\n"
            "- Self-critique and quality improvement\n"
            "- Document analysis and extraction\n\n"
            "CRITICAL RULES:\n"
            "1. Never fabricate — every claim must be backed by a fetched source or computed result.\n"
            "2. For Microsoft/Azure topics, use microsoft_docs_search first.\n"
            "3. Handoff to EngineeringAgent for architecture/code, CloudDataAgent for infra, FinanceAgent for analysis.\n"
            "4. Always run the research→code→review loop for complex tasks.\n"
            "5. Cite sources inline [1], [2], etc."
        ),
        description="Research, code execution, debugging, critique — the execution loop (30+ tools)",
        tools=EXECUTION_TOOLS,
        handoff_agents=["EngineeringAgent", "CloudDataAgent", "FinanceAgent", "RevenueAgent"],
    )

    # ── STANDALONE SPECIALISTS ───────────────────────────────────────────
    orch.register_agent(
        name="AIEngineerAgent",
        system_message=agent_configs.get("aiengineer_agent", {}).get("system_message", ""),
        description="AI/ML implementation, LLM integration, model deployment",
        tools=AIENGINEER_TOOLS,
        handoff_agents=["EngineeringAgent", "ExecutionAgent"],
    )
    orch.register_agent(
        name="SecurityEngineerAgent",
        system_message=agent_configs.get("securityengineer_agent", {}).get("system_message", ""),
        description="Threat modeling, vulnerability assessment, secure code review",
        tools=SECURITYENGINEER_TOOLS,
        handoff_agents=["EngineeringAgent", "CloudDataAgent", "LegalAgent"],
    )
    orch.register_agent(
        name="EnterpriseIntegrationAgent",
        system_message=agent_configs.get("enterprise_agent", {}).get("system_message", ""),
        description="Enterprise system integrations, API orchestration, B2B connectivity",
        tools=ENTERPRISE_TOOLS,
        handoff_agents=["EngineeringAgent", "CloudDataAgent"],
    )
    orch.register_agent(
        name="ProductManagerAgent",
        system_message=agent_configs.get("productmanager_agent", {}).get("system_message", ""),
        description="PRDs, roadmaps, user stories, go-to-market strategy",
        tools=PRODUCTMANAGER_TOOLS,
        handoff_agents=["EngineeringAgent", "RevenueAgent", "ExecutionAgent"],
    )
    orch.register_agent(
        name="ProjectManagerAgent",
        system_message=agent_configs.get("projectmanager_agent", {}).get("system_message", ""),
        description="Project plans, risks, stakeholder reports, timelines",
        tools=PROJECTMANAGER_TOOLS,
        handoff_agents=["ProductManagerAgent", "EngineeringAgent"],
    )
    orch.register_agent(
        name="ProjectShepherdAgent",
        system_message=agent_configs.get("projectshepherd_agent", {}).get("system_message", ""),
        description="Cross-functional project coordination and stakeholder alignment",
        tools=PROJECTSHEPHERD_TOOLS,
        handoff_agents=["ProjectManagerAgent"],
    )
    orch.register_agent(
        name="BusinessAgent",
        system_message=agent_configs.get("business_agent", {}).get("system_message", ""),
        description="CRM, customer records, business proposals, follow-ups",
        tools=[*BUSINESS_TOOLS, *FINANCE_TOOLS],
        handoff_agents=["RevenueAgent", "FinanceAgent"],
    )
    orch.register_agent(
        name="RealEstateAgent",
        system_message=agent_configs.get("realestate_agent", {}).get("system_message", ""),
        description="Property analysis, CMA, offer strategy, investment analysis",
        tools=[*REALESTATE_TOOLS, *FINANCE_TOOLS],
        handoff_agents=["FinanceAgent", "LegalAgent"],
    )

    # ── SANDBOXED CODE EXECUTION ─────────────────────────────────────────
    orch.register_agent(
        name="CodeExecutorAgent",
        system_message=CODEEXECUTOR_AGENT_INSTRUCTIONS,
        description=CODEEXECUTOR_AGENT_DESCRIPTION,
        tools=CODEEXECUTOR_AGENT_TOOLS,
        handoff_agents=["EngineeringAgent", "ExecutionAgent"],
    )

    return orch


__all__ = ["build_orchestrator"]
