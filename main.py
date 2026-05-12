"""
AgentSystem — Main entry point.

Registers all agents with the orchestrator and starts the interactive loop.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))

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
from tools.code_interpreter import run_python
from tools.critique import critique_response
from tools.file_reader import read_file
from tools.knowledge_base import kb_index, kb_list_sources, kb_search
from tools.rag_tools import (
    case_index_rebuild,
    case_index_update,
    case_list_indexed,
    case_search,
)
from tools.plans_tools import (
    plan_add_step,
    plan_cancel,
    plan_create,
    plan_events,
    plan_get,
    plan_list,
    plan_resume,
    plan_step_update,
)
from tools.screen_context import (
    clear_active_case,
    detect_active_case,
    get_active_case,
    get_active_window_title,
    paste_to_clipboard,
    read_clipboard,
    set_active_case,
)
from tools.project_workspace import (
    project_archive,
    project_create,
    project_list,
    project_note,
    project_open,
    project_status,
)
from tools.web_fetch import web_fetch
from tools.web_search import web_search
from tools.daily_briefing import generate_daily_briefing
from tools.draft_replies import generate_draft_replies
from tools.end_of_day import generate_eod_review
from tools.notification import NotificationGateway, create_default_gateway
from tools.audit import log_action
from tools.mcp_tools import print_mcp_banner


def setup_logging():
    """Configure logging for the agent system."""
    config = get_system_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level, logging.INFO),
        format="%(asctime)s [%(name)-20s] %(levelname)-7s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                Path(__file__).parent / "memory" / "agent_system.log",
                encoding="utf-8",
            ),
        ],
    )


def build_orchestrator() -> Orchestrator:
    """Build and configure the orchestrator with all agents."""
    agent_configs = get_agent_configs()
    orchestrator = Orchestrator()

    # Register Email Agent
    email_cfg = agent_configs.get("email_agent", {})
    orchestrator.register_agent(
        name="EmailAgent",
        system_message=email_cfg.get("system_message", "You are an email management agent."),
        description=email_cfg.get("description", "Reads, drafts, and sends emails"),
        tools=EMAIL_TOOLS,
    )

    # Register Calendar Agent
    cal_cfg = agent_configs.get("calendar_agent", {})
    orchestrator.register_agent(
        name="CalendarAgent",
        system_message=cal_cfg.get("system_message", "You are a calendar management agent."),
        description=cal_cfg.get("description", "Manages appointments and scheduling"),
        tools=CALENDAR_TOOLS,
    )

    # Register Social Media Agent
    social_cfg = agent_configs.get("social_agent", {})
    orchestrator.register_agent(
        name="SocialAgent",
        system_message=social_cfg.get("system_message", "You are a social media management agent."),
        description=social_cfg.get("description", "Manages social media posting"),
        tools=SOCIAL_TOOLS,
    )

    # Register Finance Agent
    finance_cfg = agent_configs.get("finance_agent", {})
    orchestrator.register_agent(
        name="FinanceAgent",
        system_message=finance_cfg.get("system_message", "You are a finance management agent."),
        description=finance_cfg.get("description", "Tracks expenses, budgets, and invoices"),
        tools=FINANCE_TOOLS,
    )

    # Register Business Operations Agent
    business_cfg = agent_configs.get("business_agent", {})
    orchestrator.register_agent(
        name="BusinessAgent",
        system_message=business_cfg.get("system_message", "You are a business operations agent."),
        description=business_cfg.get("description", "Manages customers, proposals, and CRM"),
        tools=BUSINESS_TOOLS,
    )

    # Register Problem Solver Agent
    ps_cfg = agent_configs.get("problemsolver_agent", {})
    orchestrator.register_agent(
        name="ProblemSolverAgent",
        system_message=ps_cfg.get("system_message", "You are a universal problem-solving specialist."),
        description=ps_cfg.get("description", "Complex debugging and investigation"),
        tools=PROBLEMSOLVER_TOOLS,
    )

    # Register AI Engineer Agent
    ai_cfg = agent_configs.get("aiengineer_agent", {})
    orchestrator.register_agent(
        name="AIEngineerAgent",
        system_message=ai_cfg.get("system_message", "You are an AI/ML engineering specialist."),
        description=ai_cfg.get("description", "AI/ML implementation and LLM integration"),
        tools=AIENGINEER_TOOLS,
    )

    # Register Enterprise Integration Agent
    ent_cfg = agent_configs.get("enterprise_agent", {})
    orchestrator.register_agent(
        name="EnterpriseIntegrationAgent",
        system_message=ent_cfg.get("system_message", "You are an enterprise integration architect."),
        description=ent_cfg.get("description", "Enterprise system integrations"),
        tools=ENTERPRISE_TOOLS,
    )

    # Register Growth Hacker Agent
    gh_cfg = agent_configs.get("growthhacker_agent", {})
    orchestrator.register_agent(
        name="GrowthHackerAgent",
        system_message=gh_cfg.get("system_message", "You are a growth hacking specialist."),
        description=gh_cfg.get("description", "Growth experiments and user acquisition"),
        tools=GROWTHHACKER_TOOLS,
    )

    # Register Legal Advisor Agent
    legal_cfg = agent_configs.get("legal_agent", {})
    orchestrator.register_agent(
        name="LegalAdvisorAgent",
        system_message=legal_cfg.get("system_message", "You are a legal advisory agent."),
        description=legal_cfg.get("description", "Legal docs, compliance, and contracts"),
        tools=LEGAL_TOOLS,
    )

    # Register Senior Developer Agent
    sd_cfg = agent_configs.get("seniordev_agent", {})
    orchestrator.register_agent(
        name="SeniorDevAgent",
        system_message=sd_cfg.get("system_message", "You are a senior full-stack developer."),
        description=sd_cfg.get("description", "Premium code implementation and review"),
        tools=SENIORDEV_TOOLS,
    )

    # Register Software Architect Agent
    sa_cfg = agent_configs.get("softwarearchitect_agent", {})
    orchestrator.register_agent(
        name="SoftwareArchitectAgent",
        system_message=sa_cfg.get("system_message", "You are an expert software architect."),
        description=sa_cfg.get("description", "System design and architecture decisions"),
        tools=SOFTWAREARCHITECT_TOOLS,
    )

    # Register Data Engineer Agent
    de_cfg = agent_configs.get("dataengineer_agent", {})
    orchestrator.register_agent(
        name="DataEngineerAgent",
        system_message=de_cfg.get("system_message", "You are an expert data engineer."),
        description=de_cfg.get("description", "Data pipelines, lakehouse, and data quality"),
        tools=DATAENGINEER_TOOLS,
    )

    # Register Azure Solution Architect Agent
    az_cfg = agent_configs.get("azurearchitect_agent", {})
    orchestrator.register_agent(
        name="AzureSolutionArchitectAgent",
        system_message=az_cfg.get("system_message", "You are an elite senior cloud solution architect."),
        description=az_cfg.get("description", "Azure, hybrid, and multi-cloud architecture plus migration and troubleshooting"),
        tools=AZUREARCHITECT_TOOLS,
    )

    # Register Databricks Specialist Agent
    dbx_cfg = agent_configs.get("databricks_agent", {})
    orchestrator.register_agent(
        name="DatabricksSpecialistAgent",
        system_message=dbx_cfg.get("system_message", "You are a Databricks platform specialist."),
        description=dbx_cfg.get("description", "Databricks architecture, governance, Spark optimization, delivery, and troubleshooting"),
        tools=DATABRICKS_TOOLS,
    )

    # Register UX Architect Agent
    ux_cfg = agent_configs.get("uxarchitect_agent", {})
    orchestrator.register_agent(
        name="UXArchitectAgent",
        system_message=ux_cfg.get("system_message", "You are a UX architecture specialist."),
        description=ux_cfg.get("description", "CSS systems, layouts, and accessibility"),
        tools=UXARCHITECT_TOOLS,
    )

    # Register Product Manager Agent
    pm_cfg = agent_configs.get("productmanager_agent", {})
    orchestrator.register_agent(
        name="ProductManagerAgent",
        system_message=pm_cfg.get("system_message", "You are a seasoned product manager."),
        description=pm_cfg.get("description", "PRDs, roadmaps, and go-to-market"),
        tools=PRODUCTMANAGER_TOOLS,
    )

    # Register Project Manager Agent
    pjm_cfg = agent_configs.get("projectmanager_agent", {})
    orchestrator.register_agent(
        name="ProjectManagerAgent",
        system_message=pjm_cfg.get("system_message", "You are an expert project manager."),
        description=pjm_cfg.get("description", "Project plans, risks, and stakeholder reports"),
        tools=PROJECTMANAGER_TOOLS,
    )

    # Register Proposal Strategist Agent
    ps_cfg = agent_configs.get("proposalstrategist_agent", {})
    orchestrator.register_agent(
        name="ProposalStrategistAgent",
        system_message=ps_cfg.get("system_message", "You are a senior proposal strategist."),
        description=ps_cfg.get("description", "Win themes, RFP analysis, executive summaries"),
        tools=PROPOSALSTRATEGIST_TOOLS,
    )

    # Register Deal Strategist Agent
    ds_cfg = agent_configs.get("dealstrategist_agent", {})
    orchestrator.register_agent(
        name="DealStrategistAgent",
        system_message=ds_cfg.get("system_message", "You are a senior deal strategist."),
        description=ds_cfg.get("description", "MEDDPICC qualification and pipeline risk"),
        tools=DEALSTRATEGIST_TOOLS,
    )

    # Register Optimization Architect Agent
    oa_cfg = agent_configs.get("optimizationarchitect_agent", {})
    orchestrator.register_agent(
        name="OptimizationArchitectAgent",
        system_message=oa_cfg.get("system_message", "You are an optimization architect."),
        description=oa_cfg.get("description", "API performance, cost optimization, circuit breakers"),
        tools=OPTIMIZATIONARCHITECT_TOOLS,
    )

    # Register DevOps Automator Agent
    do_cfg = agent_configs.get("devopsautomator_agent", {})
    orchestrator.register_agent(
        name="DevOpsAutomatorAgent",
        system_message=do_cfg.get("system_message", "You are an expert DevOps engineer."),
        description=do_cfg.get("description", "CI/CD, IaC, containers, monitoring, DR"),
        tools=DEVOPSAUTOMATOR_TOOLS,
    )

    # Register Legal Document Review Agent
    ldr_cfg = agent_configs.get("legaldocreview_agent", {})
    orchestrator.register_agent(
        name="LegalDocReviewAgent",
        system_message=ldr_cfg.get("system_message", "You are a legal document review specialist."),
        description=ldr_cfg.get("description", "Contract analysis, risk clauses, version comparison"),
        tools=LEGALDOCREVIEW_TOOLS,
    )

    # Register Real Estate Agent
    re_cfg = agent_configs.get("realestate_agent", {})
    orchestrator.register_agent(
        name="RealEstateAgent",
        system_message=re_cfg.get("system_message", "You are a real estate specialist."),
        description=re_cfg.get("description", "Property analysis, CMA, offer strategy, investment analysis"),
        tools=REALESTATE_TOOLS,
    )

    # Register Investment Researcher Agent
    ir_cfg = agent_configs.get("investmentresearcher_agent", {})
    orchestrator.register_agent(
        name="InvestmentResearcherAgent",
        system_message=ir_cfg.get("system_message", "You are a veteran investment researcher."),
        description=ir_cfg.get("description", "Investment research, due diligence, portfolio analysis"),
        tools=INVESTMENTRESEARCHER_TOOLS,
    )

    # Register Project Shepherd Agent
    psh_cfg = agent_configs.get("projectshepherd_agent", {})
    orchestrator.register_agent(
        name="ProjectShepherdAgent",
        system_message=psh_cfg.get("system_message", "You are an expert project coordinator."),
        description=psh_cfg.get("description", "Cross-functional project coordination and stakeholder alignment"),
        tools=PROJECTSHEPHERD_TOOLS,
    )

    # Register Security Engineer Agent
    sec_cfg = agent_configs.get("securityengineer_agent", {})
    orchestrator.register_agent(
        name="SecurityEngineerAgent",
        system_message=sec_cfg.get("system_message", "You are an application security engineer."),
        description=sec_cfg.get("description", "Threat modeling, vulnerability assessment, secure code review"),
        tools=SECURITYENGINEER_TOOLS,
    )

    # Register Frontend Developer Agent
    fed_cfg = agent_configs.get("frontenddev_agent", {})
    orchestrator.register_agent(
        name="FrontendDevAgent",
        system_message=fed_cfg.get("system_message", "You are an expert frontend developer."),
        description=fed_cfg.get("description", "React/Vue/Angular, accessibility, performance optimization"),
        tools=FRONTENDDEV_TOOLS,
    )

    # Register Backend Architect Agent
    bea_cfg = agent_configs.get("backendarchitect_agent", {})
    orchestrator.register_agent(
        name="BackendArchitectAgent",
        system_message=bea_cfg.get("system_message", "You are a senior backend architect."),
        description=bea_cfg.get("description", "System design, database architecture, API design"),
        tools=BACKENDARCHITECT_TOOLS,
    )

    # Register Tax Strategist Agent
    tax_cfg = agent_configs.get("taxstrategist_agent", {})
    orchestrator.register_agent(
        name="TaxStrategistAgent",
        system_message=tax_cfg.get("system_message", "You are a veteran tax strategist."),
        description=tax_cfg.get("description", "Tax optimization, entity structuring, compliance"),
        tools=TAXSTRATEGIST_TOOLS,
    )

    # Register Email Intelligence Agent
    ei_cfg = agent_configs.get("emailintel_agent", {})
    orchestrator.register_agent(
        name="EmailIntelAgent",
        system_message=ei_cfg.get("system_message", "You are an email intelligence specialist."),
        description=ei_cfg.get("description", "Email thread analysis, action items, decision tracking"),
        tools=EMAILINTEL_TOOLS,
    )

    # Register Sales Proposal Strategist Agent
    sp_cfg = agent_configs.get("salesproposal_agent", {})
    orchestrator.register_agent(
        name="SalesProposalAgent",
        system_message=sp_cfg.get("system_message", "You are a senior sales proposal strategist."),
        description=sp_cfg.get("description", "Win themes, executive summaries, RFP analysis"),
        tools=SALESPROPOSAL_TOOLS,
    )

    # ── Boil-the-Ocean specialist agents ──────────────────────────────────────
    # These four agents wrap the new capability tools (web_search, web_fetch,
    # file_reader, code_interpreter, knowledge_base, critique) into focused
    # personas. The orchestrator already has the raw tools, but the specialists
    # carry instructions and workflows that get the most out of them.

    # Register Research Agent
    research_cfg = agent_configs.get("research_agent", {})
    orchestrator.register_agent(
        name=RESEARCH_AGENT_NAME,
        system_message=research_cfg.get("system_message", RESEARCH_AGENT_INSTRUCTIONS),
        description=research_cfg.get("description", RESEARCH_AGENT_DESCRIPTION),
        tools=RESEARCH_AGENT_TOOLS,
    )

    # Register Code Executor Agent
    codeexec_cfg = agent_configs.get("codeexecutor_agent", {})
    orchestrator.register_agent(
        name=CODEEXECUTOR_AGENT_NAME,
        system_message=codeexec_cfg.get("system_message", CODEEXECUTOR_AGENT_INSTRUCTIONS),
        description=codeexec_cfg.get("description", CODEEXECUTOR_AGENT_DESCRIPTION),
        tools=CODEEXECUTOR_AGENT_TOOLS,
    )

    # Register Document Analyst Agent
    docanalyst_cfg = agent_configs.get("documentanalyst_agent", {})
    orchestrator.register_agent(
        name=DOCUMENTANALYST_AGENT_NAME,
        system_message=docanalyst_cfg.get("system_message", DOCUMENTANALYST_AGENT_INSTRUCTIONS),
        description=docanalyst_cfg.get("description", DOCUMENTANALYST_AGENT_DESCRIPTION),
        tools=DOCUMENTANALYST_AGENT_TOOLS,
    )

    # Register Critic Agent
    critic_cfg = agent_configs.get("critic_agent", {})
    orchestrator.register_agent(
        name=CRITIC_AGENT_NAME,
        system_message=critic_cfg.get("system_message", CRITIC_AGENT_INSTRUCTIONS),
        description=critic_cfg.get("description", CRITIC_AGENT_DESCRIPTION),
        tools=CRITIC_AGENT_TOOLS,
    )

    return orchestrator


async def interactive_loop(orchestrator: Orchestrator):
    """Run the interactive command loop with notification gateway."""
    gateway = create_default_gateway()

    print("\n" + "=" * 60)
    print("🤖 AgentSystem — Autonomous Multi-Agent Productivity System")
    print("=" * 60)

    status = orchestrator.status()
    print(f"   System:    {status['system']}")
    print(f"   Agents:    {', '.join(status['registered_agents'])}")
    print(f"   Approval:  {'Required' if status['approval_required'] else 'Auto'}")
    print(f"   Model:     {status['model_provider']}")
    print(f"   Session:   {status['active_session_id']}")
    print(f"   Memory:    {status['remembered_facts']} facts")
    print_mcp_banner()
    print("=" * 60)
    print("Commands:")
    print("  status     — Show system status")
    print("  memory     — Show remembered profile facts")
    print("  briefing   — Generate your daily briefing")
    print("  drafts     — Draft replies for important unread mail (saves to Outlook Drafts)")
    print("  eod        — Generate your end-of-day review")
    print("  new-session — Start a fresh session (keeps durable memory)")
    print("  events     — Show queued events")
    print("  start-gw   — Start notification gateway")
    print("  stop-gw    — Stop notification gateway")
    print("  quit       — Exit the system")
    print("Boil-the-Ocean commands:")
    print("  research <q>      — Multi-step web research with citations (uses ResearchAgent)")
    print("  web <q>           — Quick web search (DuckDuckGo)")
    print("  read <file>       — Read PDF/DOCX/XLSX/HTML/text → Markdown")
    print("  analyze <file>    — Deep artifact analysis (uses DocumentAnalystAgent)")
    print("  code <python>     — Run Python in the sandboxed workspace")
    print("  kb <sub>          — Knowledge base: index <path> | search <q> | list")
    print("  project <sub>     — Projects: create <name> | open <name> | note <text> |")
    print("                                  status [name] | list | archive <name>")
    print("  critique <text>   — Senior reviewer rubber-ducks a draft")
    print("                       (use 'critique <question> ||| <draft>' for best results)")
    print("  cases <sub>       — RAG over Work_cases\\Cases\\: search <q> [|||folder] |")
    print("                                  update [folder] | rebuild [folder] | list")
    print("  plans [status]    — list durable plans (optional status filter)")
    print("  plan <sub>        — durable plans: <plan_id> | resume <id> | cancel <id> [reason] |")
    print("                                  events <id> | create \"<title>\" \"<goal>\" [steps] |")
    print("                                  step <id> <idx> <status> [result] | add <id> \"<title>\"")
    print("  clip [sub]        — clipboard: read | set <text>  (no sub = read)")
    print("  active [sub]      — active case: (no sub = show) | detect | set <id-or-path> | clear")
    print("  window            — show the active window title")
    print("=" * 60)
    print("Type your request:\n")

    log_action("System", "startup", f"Agents: {status['registered_agents']}")

    while True:
        try:
            # Check for queued events while waiting for user input
            prompt_text = f"You [{gateway.queue_size} events] > " if gateway.is_running else "You > "
            user_input = await asyncio.get_event_loop().run_in_executor(
                None, lambda: input(prompt_text).strip()
            )
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down...")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            if gateway.is_running:
                await gateway.stop()
            print("Goodbye! 👋")
            log_action("System", "shutdown", "User requested exit")
            break

        if user_input.lower() == "status":
            s = orchestrator.status()
            for k, v in s.items():
                print(f"  {k}: {v}")
            print(f"  notification_gateway: {'running' if gateway.is_running else 'stopped'}")
            print(f"  queued_events: {gateway.queue_size}")
            continue

        if user_input.lower() in ("memory", "memories", "profile"):
            print(orchestrator.get_memory_summary())
            continue

        if user_input.lower() in ("briefing", "brief"):
            print(await generate_daily_briefing())
            continue

        if user_input.lower() in ("drafts", "draft-replies", "triage"):
            print(await generate_draft_replies())
            continue

        if user_input.lower() in ("eod", "end-of-day", "review"):
            print(await generate_eod_review())
            continue

        if user_input.lower() in ("new-session", "reset-session"):
            session_id = orchestrator.reset_session()
            print(f"✅ Started new session: {session_id}")
            continue

        if user_input.lower() == "events":
            print(f"  Queued events: {gateway.queue_size}")
            if gateway.queue_size > 0:
                event = await gateway.get_next_event(timeout=1.0)
                if event:
                    print(f"  Next: {event.to_prompt()}")
                    try:
                        response = await orchestrator.handle_user_input(event.to_prompt())
                        print(f"\n🤖 > {response}\n")
                    except Exception as e:
                        print(f"\n❌ Error processing event: {e}\n")
            continue

        if user_input.lower() == "start-gw":
            if not gateway.is_running:
                await gateway.start()
                print("✅ Notification gateway started")
            else:
                print("Gateway is already running")
            continue

        if user_input.lower() == "stop-gw":
            if gateway.is_running:
                await gateway.stop()
                print("✅ Notification gateway stopped")
            else:
                print("Gateway is not running")
            continue

        # ── Boil-the-Ocean commands ──────────────────────────────────────────
        lower = user_input.lower()

        if lower.startswith("research "):
            query = user_input[len("research "):].strip()
            if not query:
                print("Usage: research <query>")
                continue
            framed = (
                "Use the ResearchAgent workflow to answer this with cited sources "
                f"(search → fetch → synthesize): {query}"
            )
            try:
                response = await orchestrator.handle_user_input(framed)
                print(f"\n🤖 > {response}\n")
            except Exception as e:
                print(f"\n❌ Research failed: {e}\n")
            continue

        if lower.startswith("web "):
            q = user_input[len("web "):].strip()
            if not q:
                print("Usage: web <query>")
                continue
            print(await web_search(q))
            continue

        if lower.startswith("read "):
            path = user_input[len("read "):].strip()
            if not path:
                print("Usage: read <file-path>")
                continue
            print(await read_file(path))
            continue

        if lower.startswith("analyze "):
            path = user_input[len("analyze "):].strip()
            if not path:
                print("Usage: analyze <file-or-folder-path>")
                continue
            framed = (
                "Use the DocumentAnalystAgent workflow to read this artifact and "
                f"extract structured signals (errors, timeline, decisions, risks): {path}"
            )
            try:
                response = await orchestrator.handle_user_input(framed)
                print(f"\n🤖 > {response}\n")
            except Exception as e:
                print(f"\n❌ Analysis failed: {e}\n")
            continue

        if lower.startswith("code "):
            code = user_input[len("code "):]
            if not code.strip():
                print("Usage: code <python-source>")
                continue
            print(await run_python(code))
            continue

        if lower.startswith("kb "):
            rest = user_input[len("kb "):].strip()
            parts = rest.split(maxsplit=1)
            sub = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            if sub == "index":
                if not arg:
                    print("Usage: kb index <file-or-folder-path>")
                    continue
                print(await kb_index(arg))
            elif sub == "search":
                if not arg:
                    print("Usage: kb search <query>")
                    continue
                print(await kb_search(arg))
            elif sub in ("list", "sources", "ls"):
                print(await kb_list_sources())
            else:
                print("Usage: kb [index <path> | search <query> | list]")
            continue

        if lower.startswith("project "):
            rest = user_input[len("project "):].strip()
            parts = rest.split(maxsplit=1)
            sub = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            if sub == "create":
                if not arg:
                    print("Usage: project create <name>")
                    continue
                print(await project_create(arg))
            elif sub == "open":
                if not arg:
                    print("Usage: project open <name>")
                    continue
                print(await project_open(arg))
            elif sub == "note":
                if not arg:
                    print("Usage: project note <text>")
                    continue
                print(await project_note(arg))
            elif sub == "status":
                print(await project_status(arg))
            elif sub in ("list", "ls"):
                print(await project_list())
            elif sub == "archive":
                if not arg:
                    print("Usage: project archive <name>")
                    continue
                print(await project_archive(arg))
            else:
                print(
                    "Usage: project [create <name> | open <name> | note <text> | "
                    "status [name] | list | archive <name>]"
                )
            continue

        if lower.startswith("critique "):
            body = user_input[len("critique "):]
            if "|||" in body:
                question, draft = body.split("|||", 1)
                question, draft = question.strip(), draft.strip()
            else:
                question = "Review the following draft response."
                draft = body.strip()
            if not draft:
                print(
                    "Usage: critique <draft>\n"
                    "   or: critique <question> ||| <draft>"
                )
                continue
            print(await critique_response(question, draft))
            continue

        if lower.startswith("cases"):
            rest = user_input[len("cases"):].strip()
            parts = rest.split(maxsplit=1) if rest else []
            sub = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            if sub == "search":
                if not arg:
                    print("Usage: cases search <query> [|||<case-folder>]")
                    continue
                if "|||" in arg:
                    q, folder = arg.split("|||", 1)
                    print(await case_search(q.strip(), case_folder=folder.strip()))
                else:
                    print(await case_search(arg))
            elif sub == "update":
                print(await case_index_update(arg))
            elif sub == "rebuild":
                print(await case_index_rebuild(arg))
            elif sub in ("list", "ls", ""):
                print(await case_list_indexed())
            else:
                print(
                    "Usage: cases [search <query> [|||<case-folder>] | "
                    "update [folder] | rebuild [folder] | list]"
                )
            continue

        if lower.startswith("plans") or lower.startswith("plan"):
            # Distinguish "plans" (list) from "plan ..." (single-plan ops).
            if lower == "plans" or lower.startswith("plans "):
                rest = user_input[len("plans"):].strip()
                # `plans [status]` — list. status is optional filter.
                print(await plan_list(status=rest if rest else ""))
                continue

            rest = user_input[len("plan"):].strip()
            if not rest:
                print(
                    "Usage:\n"
                    "  plans [status]                          — list plans\n"
                    "  plan <plan_id>                          — show one plan\n"
                    "  plan resume <plan_id>                   — show next pending step\n"
                    "  plan cancel <plan_id> [reason]          — cancel a plan\n"
                    "  plan events <plan_id>                   — show event log\n"
                    "  plan create \"<title>\" \"<goal>\" [steps_json] [owner] [tags]\n"
                    "  plan step <plan_id> <step_index> <status> [result] [owner_agent]\n"
                    "  plan add <plan_id> \"<title>\" [description] [owner_agent]"
                )
                continue
            parts = rest.split(maxsplit=1)
            sub = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if sub == "resume":
                if not arg:
                    print("Usage: plan resume <plan_id>")
                else:
                    print(await plan_resume(arg.strip()))
            elif sub == "cancel":
                if not arg:
                    print("Usage: plan cancel <plan_id> [reason]")
                else:
                    cparts = arg.split(maxsplit=1)
                    pid = cparts[0]
                    reason = cparts[1] if len(cparts) > 1 else ""
                    print(await plan_cancel(pid, reason=reason))
            elif sub == "events":
                if not arg:
                    print("Usage: plan events <plan_id>")
                else:
                    print(await plan_events(arg.strip()))
            elif sub == "create":
                # plan create "<title>" "<goal>" [steps_json] [owner] [tags]
                # Use shlex to honor quoted multi-word title/goal.
                import shlex

                try:
                    tokens = shlex.split(arg)
                except ValueError as e:
                    print(f"Could not parse arguments: {e}")
                    continue
                if len(tokens) < 2:
                    print(
                        "Usage: plan create \"<title>\" \"<goal>\" "
                        "[steps_json|stepA\\nstepB] [owner] [tags]"
                    )
                    continue
                title = tokens[0]
                goal = tokens[1]
                steps_json = tokens[2] if len(tokens) > 2 else ""
                owner = tokens[3] if len(tokens) > 3 else ""
                tags = tokens[4] if len(tokens) > 4 else ""
                print(
                    await plan_create(
                        title=title,
                        goal=goal,
                        steps_json=steps_json,
                        owner=owner,
                        tags=tags,
                    )
                )
            elif sub == "step":
                # plan step <plan_id> <step_index> <status> [result] [owner_agent]
                import shlex

                try:
                    tokens = shlex.split(arg)
                except ValueError as e:
                    print(f"Could not parse arguments: {e}")
                    continue
                if len(tokens) < 3:
                    print(
                        "Usage: plan step <plan_id> <step_index> <status> "
                        "[result] [owner_agent]"
                    )
                    continue
                pid = tokens[0]
                try:
                    idx = int(tokens[1])
                except ValueError:
                    print("step_index must be an integer (0-based)")
                    continue
                status = tokens[2]
                result_text = tokens[3] if len(tokens) > 3 else ""
                owner_agent = tokens[4] if len(tokens) > 4 else ""
                print(
                    await plan_step_update(
                        plan_id=pid,
                        step_index=idx,
                        status=status,
                        result=result_text,
                        owner_agent=owner_agent,
                    )
                )
            elif sub == "add":
                # plan add <plan_id> "<title>" [description] [owner_agent]
                import shlex

                try:
                    tokens = shlex.split(arg)
                except ValueError as e:
                    print(f"Could not parse arguments: {e}")
                    continue
                if len(tokens) < 2:
                    print(
                        "Usage: plan add <plan_id> \"<title>\" "
                        "[description] [owner_agent]"
                    )
                    continue
                pid = tokens[0]
                title = tokens[1]
                description = tokens[2] if len(tokens) > 2 else ""
                owner_agent = tokens[3] if len(tokens) > 3 else ""
                print(
                    await plan_add_step(
                        plan_id=pid,
                        title=title,
                        description=description,
                        owner_agent=owner_agent,
                    )
                )
            else:
                # Treat as: plan <plan_id>
                print(await plan_get(rest.strip()))
            continue

        # ---------- clipboard ----------
        if lower == "clip" or lower.startswith("clip "):
            rest = user_input[len("clip"):].strip()
            parts = rest.split(maxsplit=1) if rest else []
            sub = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            if sub == "" or sub == "read":
                print(await read_clipboard())
            elif sub == "set":
                if not arg:
                    print("Usage: clip set <text>")
                else:
                    print(await paste_to_clipboard(arg))
            else:
                print(f"Unknown clip subcommand: {sub!r}. Try: read | set <text>")
            continue

        # ---------- active case ----------
        if lower == "active" or lower.startswith("active "):
            rest = user_input[len("active"):].strip()
            parts = rest.split(maxsplit=1) if rest else []
            sub = parts[0].lower() if parts else ""
            arg = parts[1] if len(parts) > 1 else ""
            if sub == "":
                print(await get_active_case())
            elif sub == "detect":
                print(await detect_active_case())
            elif sub == "set":
                if not arg:
                    print("Usage: active set <case_id|folder_path>")
                else:
                    print(await set_active_case(arg))
            elif sub == "clear":
                print(await clear_active_case())
            elif sub == "window":
                print(await get_active_window_title())
            else:
                print(
                    f"Unknown active subcommand: {sub!r}. "
                    "Try: (no sub) | detect | set <id-or-path> | clear | window"
                )
            continue

        # ---------- active window (shortcut) ----------
        if lower == "window":
            print(await get_active_window_title())
            continue

        try:
            response = await orchestrator.handle_user_input(user_input)
            print(f"\n🤖 > {response}\n")
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Error handling input: {e}", exc_info=True)
            print(f"\n❌ Error: {e}\n")
            log_action("System", "error", user_input[:200], str(e), status="error")


async def main():
    """Main entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        orchestrator = build_orchestrator()
        logger.info("AgentSystem initialized successfully")
        await interactive_loop(orchestrator)
    except ValueError as e:
        print(f"\n⚠️  Configuration error: {e}")
        print("Please update your .env file with valid credentials.")
        print("See .env.template for required variables.\n")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
