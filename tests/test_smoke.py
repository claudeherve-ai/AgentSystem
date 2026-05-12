"""
Smoke test — verify all modules import cleanly and core functionality works.
"""

import asyncio
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_config_loads():
    from config import get_system_config, get_model_config, get_agent_configs, get_guardrails_config
    sc = get_system_config()
    assert sc.name == "AgentSystem"
    assert sc.approval_required is True

    mc = get_model_config()
    assert mc.provider == "azure_openai"

    ac = get_agent_configs()
    assert "orchestrator" in ac
    assert "email_agent" in ac
    assert "calendar_agent" in ac
    assert "social_agent" in ac
    assert "finance_agent" in ac
    assert "business_agent" in ac
    assert "azurearchitect_agent" in ac
    assert "databricks_agent" in ac
    assert "research_agent" in ac
    assert "codeexecutor_agent" in ac
    assert "documentanalyst_agent" in ac
    assert "critic_agent" in ac

    gc = get_guardrails_config()
    assert "approval_gates" in gc
    assert "rate_limits" in gc
    print(f"✅ Config loads OK ({len(ac)} agent configs)")


def test_orchestrator_registration():
    from main import build_orchestrator

    orchestrator = build_orchestrator()
    status = orchestrator.status()

    assert status["agent_count"] >= 36
    assert "EmailAgent" in status["registered_agents"]
    assert "CalendarAgent" in status["registered_agents"]
    assert "DevOpsAutomatorAgent" in status["registered_agents"]
    assert "AzureSolutionArchitectAgent" in status["registered_agents"]
    assert "DatabricksSpecialistAgent" in status["registered_agents"]
    assert "ResearchAgent" in status["registered_agents"]
    assert "CodeExecutorAgent" in status["registered_agents"]
    assert "DocumentAnalystAgent" in status["registered_agents"]
    assert "CriticAgent" in status["registered_agents"]
    assert "LegalDocReviewAgent" in status["registered_agents"]
    assert "RealEstateAgent" in status["registered_agents"]
    assert "InvestmentResearcherAgent" in status["registered_agents"]
    assert "ProjectShepherdAgent" in status["registered_agents"]
    assert "SecurityEngineerAgent" in status["registered_agents"]
    assert "FrontendDevAgent" in status["registered_agents"]
    assert "BackendArchitectAgent" in status["registered_agents"]
    assert "TaxStrategistAgent" in status["registered_agents"]
    assert "EmailIntelAgent" in status["registered_agents"]
    assert "SalesProposalAgent" in status["registered_agents"]
    assert isinstance(status["active_session_id"], str)
    assert status["active_session_id"]
    assert status["remembered_facts"] >= 0
    print(f"✅ Orchestrator OK ({status['agent_count']} agents registered)")


def test_model_option_compatibility():
    from agents.orchestrator import get_default_agent_options
    from config import get_model_config

    options = get_default_agent_options()
    model_cfg = get_model_config()

    if model_cfg.resolved_model.lower().startswith("gpt-5"):
        assert "temperature" not in options
    else:
        assert options["temperature"] == model_cfg.temperature

    assert options["max_tokens"] == model_cfg.max_tokens
    assert options["allow_multiple_tool_calls"] is False
    print("✅ Model options OK")


def test_guardrails():
    from guardrails import Guardrails, ApprovalRequired
    g = Guardrails()
    assert g.requires_approval("send_email") is True
    assert g.requires_approval("post_social_media") is True
    assert g.requires_approval("send_invoice") is True
    assert g.is_auto_approved("read_inbox") is True
    assert g.is_auto_approved("draft_email") is True
    assert g.is_auto_approved("log_expense") is True
    assert g.requires_approval("read_inbox") is False

    g.check_email_rate()
    g.check_social_rate()

    assert g.check_content_length("short text") is True
    assert g.check_content_length("x" * 10000) is False

    redacted = g.redact_sensitive("SSN: 123-45-6789")
    assert "123-45-6789" not in redacted
    print("✅ Guardrails OK (approval gates, rate limits, redaction)")


def test_audit():
    from tools.audit import log_action, get_recent_actions
    rid = log_action("test_runner", "smoke_test_v2", "input", "output")
    assert rid > 0
    actions = get_recent_actions(1)
    assert len(actions) >= 1
    print("✅ Audit OK")


def test_email_tools():
    from agents.email_agent import EMAIL_TOOLS
    assert len(EMAIL_TOOLS) == 3
    names = [t.__name__ for t in EMAIL_TOOLS]
    assert "read_inbox" in names
    assert "draft_reply" in names
    assert "send_email" in names
    print("✅ Email tools OK (3 tools)")


def test_calendar_tools():
    from agents.calendar_agent import CALENDAR_TOOLS
    assert len(CALENDAR_TOOLS) == 3
    names = [t.__name__ for t in CALENDAR_TOOLS]
    assert "get_upcoming_events" in names
    assert "create_event" in names
    assert "check_conflicts" in names
    print("✅ Calendar tools OK (3 tools)")


def test_social_tools():
    from agents.social_agent import SOCIAL_TOOLS
    assert len(SOCIAL_TOOLS) == 4
    names = [t.__name__ for t in SOCIAL_TOOLS]
    assert "draft_social_post" in names
    assert "publish_post" in names
    assert "check_engagement" in names
    assert "get_posting_schedule" in names
    print("✅ Social tools OK (4 tools)")


def test_finance_tools():
    from agents.finance_agent import FINANCE_TOOLS
    assert len(FINANCE_TOOLS) == 5
    names = [t.__name__ for t in FINANCE_TOOLS]
    assert "log_expense" in names
    assert "set_budget" in names
    assert "get_budget_report" in names
    assert "create_invoice" in names
    assert "list_invoices" in names
    print("✅ Finance tools OK (5 tools)")


def test_business_tools():
    from agents.business_agent import BUSINESS_TOOLS
    assert len(BUSINESS_TOOLS) == 5
    names = [t.__name__ for t in BUSINESS_TOOLS]
    assert "create_customer" in names
    assert "log_interaction" in names
    assert "list_customers" in names
    assert "draft_proposal" in names
    assert "get_pending_followups" in names
    print("✅ Business tools OK (5 tools)")


def test_notification_gateway():
    from tools.notification import NotificationGateway, Event, create_default_gateway
    gw = create_default_gateway()
    assert gw.queue_size == 0
    assert gw.is_running is False

    event = Event("email", "new_email", "Test notification")
    assert "EMAIL" in event.to_prompt()
    assert event.priority == "normal"

    urgent = Event("calendar", "meeting_soon", "Meeting in 5 min", priority="urgent")
    assert "🚨 URGENT" in urgent.to_prompt()
    print("✅ Notification gateway OK (pollers, events, priority)")


def test_service_runner():
    from tools.service import ServiceRunner
    runner = ServiceRunner(mode="headless")
    health = runner.health_check()
    assert health["status"] == "stopped"
    assert health["mode"] == "headless"
    assert health["events_processed"] == 0
    print("✅ Service runner OK (health check)")


def test_finance_db():
    """Test finance database operations end-to-end."""
    loop = asyncio.new_event_loop()
    from agents.finance_agent import log_expense, set_budget, get_budget_report

    result = loop.run_until_complete(set_budget("test_category", 500.0, 0.8))
    assert "Budget set" in result

    result = loop.run_until_complete(log_expense("test_category", "Test expense", 100.0))
    assert "Expense logged" in result
    assert "$100.00" in result

    result = loop.run_until_complete(get_budget_report())
    assert "Budget Report" in result

    loop.close()
    print("✅ Finance DB OK (expense + budget + report)")


def test_business_db():
    """Test business CRM operations end-to-end."""
    loop = asyncio.new_event_loop()
    from agents.business_agent import create_customer, list_customers, get_pending_followups

    result = loop.run_until_complete(
        create_customer("Test Client", "test@example.com", company="TestCorp")
    )
    assert "Customer created" in result

    result = loop.run_until_complete(list_customers("active"))
    assert "Test Client" in result

    result = loop.run_until_complete(get_pending_followups())
    assert "follow-up" in result.lower()

    loop.close()
    print("✅ Business DB OK (customer + list + followups)")


def test_memory_store():
    from tools.memory_tools import MemoryStore

    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        store = MemoryStore(
            db_path=root / "agent_memory.db",
            session_state_path=root / "session_state.json",
            profile_seed_path=root / "no_seed.json",
        )

        session_id = store.get_active_session_id()
        assert session_id == store.get_active_session_id()

        key = store.remember("favorite team", "Arsenal", category="preference")
        assert key == "favorite_team"
        assert store.count_memories() == 1

        matches = store.search_memories(query="Arsenal")
        assert len(matches) == 1
        assert matches[0]["key"] == "favorite_team"

        store.save_turn(session_id, "user", "hello")
        store.save_turn(session_id, "assistant", "hi there")
        rendered = store.render_recent_turns(session_id)
        assert "User: hello" in rendered
        assert "Assistant: hi there" in rendered

        assert store.forget("favorite team") is True
        assert store.count_memories() == 0

    print("✅ Memory store OK")


def test_profile_seed_loading():
    from tools.memory_tools import MemoryStore

    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        seed_path = root / "profile_seed.json"
        seed_path.write_text(
            '[{"key":"timezone","value":"Pacific Time","category":"identity"},'
            '{"key":"katy","value":"Wife; priority family contact","category":"contact"}]',
            encoding="utf-8",
        )

        store = MemoryStore(
            db_path=root / "agent_memory.db",
            session_state_path=root / "session_state.json",
            profile_seed_path=seed_path,
        )

        rows = store.search_memories(query="timezone")
        assert any(row["value"] == "Pacific Time" for row in rows)
        contact_rows = store.search_memories(query="katy")
        assert any(row["category"] == "contact" for row in contact_rows)

    print("✅ Profile seed loading OK")


def test_azure_architect_tools():
    from agents.azurearchitect_agent import AZUREARCHITECT_TOOLS

    assert len(AZUREARCHITECT_TOOLS) >= 5
    names = [tool.__name__ for tool in AZUREARCHITECT_TOOLS]
    assert "design_cloud_architecture" in names
    assert "review_architecture_risks" in names
    assert "troubleshoot_cloud_issue" in names
    assert "plan_cloud_migration" in names
    assert "compare_cloud_options" in names
    print("✅ Azure architect tools OK (5 tools)")


def test_databricks_tools():
    from agents.databricks_agent import DATABRICKS_TOOLS

    assert len(DATABRICKS_TOOLS) >= 5
    names = [tool.__name__ for tool in DATABRICKS_TOOLS]
    assert "design_databricks_platform" in names
    assert "troubleshoot_databricks_issue" in names
    assert "optimize_spark_workload" in names
    assert "review_databricks_governance" in names
    assert "plan_databricks_delivery" in names
    print("✅ Databricks tools OK (5 tools)")


def test_daily_briefing_tool():
    from tools.daily_briefing import DAILY_BRIEFING_TOOLS, generate_daily_briefing

    assert len(DAILY_BRIEFING_TOOLS) == 1
    assert DAILY_BRIEFING_TOOLS[0].__name__ == "generate_daily_briefing"

    loop = asyncio.new_event_loop()
    with patch("tools.daily_briefing.graph_get_upcoming_events", new=AsyncMock(return_value=[])), \
         patch("tools.daily_briefing.graph_read_inbox", new=AsyncMock(return_value=[])), \
         patch("tools.daily_briefing.get_pending_followups", new=AsyncMock(return_value="No pending follow-ups.")):
        result = loop.run_until_complete(generate_daily_briefing())
    loop.close()

    assert "DAILY BRIEFING" in result
    assert "Important unread emails" in result
    assert "Pending follow-ups" in result
    print("✅ Daily briefing tool OK")


def test_eod_review_tool():
    from tools.end_of_day import END_OF_DAY_TOOLS, generate_eod_review

    assert len(END_OF_DAY_TOOLS) == 1
    assert END_OF_DAY_TOOLS[0].__name__ == "generate_eod_review"

    loop = asyncio.new_event_loop()
    with patch("tools.end_of_day.graph_get_upcoming_events", new=AsyncMock(return_value=[])), \
         patch("tools.end_of_day.graph_read_inbox", new=AsyncMock(return_value=[])), \
         patch("tools.end_of_day.get_pending_followups", new=AsyncMock(return_value="No pending follow-ups.")), \
         patch("tools.end_of_day._load_todays_actions", return_value=[]):
        result = loop.run_until_complete(generate_eod_review())
    loop.close()

    assert "END-OF-DAY REVIEW" in result
    assert "Top 3 priorities for tomorrow" in result
    assert "Tomorrow's calendar" in result
    print("✅ End-of-day review tool OK")


def test_draft_replies_tool():
    from tools.draft_replies import DRAFT_REPLY_TOOLS, generate_draft_replies

    assert len(DRAFT_REPLY_TOOLS) == 1
    assert DRAFT_REPLY_TOOLS[0].__name__ == "generate_draft_replies"

    loop = asyncio.new_event_loop()

    # Empty inbox → graceful no-op, no save attempts.
    with patch("tools.draft_replies.graph_read_inbox", new=AsyncMock(return_value=[])), \
         patch("tools.draft_replies.graph_create_reply_draft", new=AsyncMock(return_value="draft-id")):
        empty_result = loop.run_until_complete(generate_draft_replies(save_to_outlook=False))

    assert "DRAFT REPLIES" in empty_result
    assert "Inbox is clear" in empty_result or "No important unread emails" in empty_result

    # Important email → draft generated and save_to_outlook=True calls Graph.
    sample_email = {
        "id": "msg-123",
        "from": "boss@company.com",
        "from_name": "Boss",
        "subject": "Urgent: please review the proposal today",
        "preview": "Can you review the attached proposal and send feedback by EOD?",
        "received": "2099-01-01T10:00:00+00:00",
    }
    create_mock = AsyncMock(return_value="draft-abc")
    with patch("tools.draft_replies.graph_read_inbox", new=AsyncMock(return_value=[sample_email])), \
         patch("tools.draft_replies.graph_create_reply_draft", new=create_mock):
        result = loop.run_until_complete(
            generate_draft_replies(hours_window=72, save_to_outlook=True)
        )
    loop.close()

    assert "DRAFT REPLIES" in result
    assert "Boss" in result
    assert "Proposed reply" in result
    assert "Saved to Outlook Drafts" in result
    create_mock.assert_awaited()
    print("✅ Draft replies tool OK")


def test_proactive_scheduler():
    import os
    from tools import scheduler as scheduler_mod
    from tools.scheduler import (
        SCHEDULER_POLLERS,
        poll_end_of_day,
        poll_meeting_alerts,
        poll_morning_briefing,
        register_scheduler_pollers,
    )

    assert len(SCHEDULER_POLLERS) == 3

    # Use a temp state file so we don't touch real scheduler state.
    with TemporaryDirectory() as tmp:
        state_path = Path(tmp) / "scheduler_state.json"
        original_path = scheduler_mod.SCHEDULER_STATE_PATH
        scheduler_mod.SCHEDULER_STATE_PATH = state_path
        try:
            loop = asyncio.new_event_loop()

            # Force briefing hour to 0 so it always fires; EOD hour to 25 so it never does.
            os.environ["SCHEDULER_BRIEFING_HOUR"] = "0"
            os.environ["SCHEDULER_EOD_HOUR"] = "25"

            first = loop.run_until_complete(poll_morning_briefing())
            assert len(first) == 1
            assert first[0].event_type == "morning_briefing_due"
            assert first[0].priority == "high"

            # Second poll on the same day must NOT refire.
            second = loop.run_until_complete(poll_morning_briefing())
            assert second == []

            # EOD disabled by forced hour=25, so nothing fires.
            eod_none = loop.run_until_complete(poll_end_of_day())
            assert eod_none == []

            # Meeting alert poller handles Graph failures gracefully.
            with patch(
                "tools.scheduler.graph_get_upcoming_events",
                new=AsyncMock(side_effect=RuntimeError("no graph")),
            ):
                alerts = loop.run_until_complete(poll_meeting_alerts())
            assert alerts == []

            loop.close()

            # Register helper wires all three pollers into a gateway.
            from tools.notification import NotificationGateway
            gw = NotificationGateway()
            register_scheduler_pollers(gw)
            poller_names = {p["name"] for p in gw._pollers}
            assert {"morning_briefing", "end_of_day", "meeting_alerts"}.issubset(poller_names)
        finally:
            scheduler_mod.SCHEDULER_STATE_PATH = original_path
            os.environ.pop("SCHEDULER_BRIEFING_HOUR", None)
            os.environ.pop("SCHEDULER_EOD_HOUR", None)

    print("✅ Proactive scheduler OK (3 pollers)")


def test_legaldocreview_tools():
    from agents.legaldocreview_agent import LEGALDOCREVIEW_TOOLS
    assert len(LEGALDOCREVIEW_TOOLS) == 3
    names = [t.__name__ for t in LEGALDOCREVIEW_TOOLS]
    assert "review_document" in names
    assert "compare_document_versions" in names
    assert "check_compliance" in names
    print("✅ Legal doc review tools OK (3 tools)")


def test_realestate_tools():
    from agents.realestate_agent import REALESTATE_TOOLS
    assert len(REALESTATE_TOOLS) == 3
    names = [t.__name__ for t in REALESTATE_TOOLS]
    assert "prepare_cma" in names
    assert "draft_offer_strategy" in names
    assert "analyze_investment_property" in names
    print("✅ Real estate tools OK (3 tools)")


def test_investmentresearcher_tools():
    from agents.investmentresearcher_agent import INVESTMENTRESEARCHER_TOOLS
    assert len(INVESTMENTRESEARCHER_TOOLS) == 3
    names = [t.__name__ for t in INVESTMENTRESEARCHER_TOOLS]
    assert "research_company" in names
    assert "run_due_diligence" in names
    assert "analyze_portfolio" in names
    print("✅ Investment researcher tools OK (3 tools)")


def test_projectshepherd_tools():
    from agents.projectshepherd_agent import PROJECTSHEPHERD_TOOLS
    assert len(PROJECTSHEPHERD_TOOLS) == 3
    names = [t.__name__ for t in PROJECTSHEPHERD_TOOLS]
    assert "create_project_charter" in names
    assert "generate_status_report" in names
    assert "assess_project_risk" in names
    print("✅ Project shepherd tools OK (3 tools)")


def test_securityengineer_tools():
    from agents.securityengineer_agent import SECURITYENGINEER_TOOLS
    assert len(SECURITYENGINEER_TOOLS) >= 3
    names = [t.__name__ for t in SECURITYENGINEER_TOOLS]
    assert "create_threat_model" in names
    assert "review_security" in names
    assert "generate_security_checklist" in names
    print("✅ Security engineer tools OK (3 tools)")


def test_frontenddev_tools():
    from agents.frontenddev_agent import FRONTENDDEV_TOOLS
    assert len(FRONTENDDEV_TOOLS) == 5
    names = [t.__name__ for t in FRONTENDDEV_TOOLS]
    assert "design_component_architecture" in names
    assert "audit_performance" in names
    assert "generate_accessibility_report" in names
    print("✅ Frontend dev tools OK (3 tools)")


def test_backendarchitect_tools():
    from agents.backendarchitect_agent import BACKENDARCHITECT_TOOLS
    assert len(BACKENDARCHITECT_TOOLS) == 6
    names = [t.__name__ for t in BACKENDARCHITECT_TOOLS]
    assert "design_system_architecture" in names
    assert "design_database_schema" in names
    assert "design_api" in names
    print("✅ Backend architect tools OK (3 tools)")


def test_taxstrategist_tools():
    from agents.taxstrategist_agent import TAXSTRATEGIST_TOOLS
    assert len(TAXSTRATEGIST_TOOLS) == 3
    names = [t.__name__ for t in TAXSTRATEGIST_TOOLS]
    assert "analyze_tax_strategy" in names
    assert "calculate_estimated_taxes" in names
    assert "review_tax_position" in names
    print("✅ Tax strategist tools OK (3 tools)")


def test_emailintel_tools():
    from agents.emailintel_agent import EMAILINTEL_TOOLS
    assert len(EMAILINTEL_TOOLS) == 3
    names = [t.__name__ for t in EMAILINTEL_TOOLS]
    assert "analyze_email_thread" in names
    assert "extract_action_items" in names
    assert "build_email_context" in names
    print("✅ Email intel tools OK (3 tools)")


def test_salesproposal_tools():
    from agents.salesproposal_agent import SALESPROPOSAL_TOOLS
    assert len(SALESPROPOSAL_TOOLS) == 3
    names = [t.__name__ for t in SALESPROPOSAL_TOOLS]
    assert "develop_win_themes" in names
    assert "write_executive_summary" in names
    assert "analyze_rfp" in names
    print("✅ Sales proposal tools OK (3 tools)")


# ─── Boil-the-Ocean: 7 capability tools ────────────────────────────────────
def test_web_search_tool():
    from tools.web_search import WEB_SEARCH_TOOLS, web_search
    assert len(WEB_SEARCH_TOOLS) == 1
    assert WEB_SEARCH_TOOLS[0].__name__ == "web_search"
    assert callable(web_search)
    print("✅ Web search tool OK (1 tool)")


def test_web_fetch_tool():
    from tools.web_fetch import WEB_FETCH_TOOLS, web_fetch
    assert len(WEB_FETCH_TOOLS) == 1
    assert WEB_FETCH_TOOLS[0].__name__ == "web_fetch"
    assert callable(web_fetch)
    print("✅ Web fetch tool OK (1 tool)")


def test_file_reader_tools():
    from tools.file_reader import FILE_READER_TOOLS
    assert len(FILE_READER_TOOLS) == 3
    names = [t.__name__ for t in FILE_READER_TOOLS]
    assert "read_file" in names
    assert "list_dir" in names
    assert "search_in_file" in names
    print("✅ File reader tools OK (3 tools)")


def test_code_interpreter_tools():
    from tools.code_interpreter import CODE_INTERPRETER_TOOLS
    assert len(CODE_INTERPRETER_TOOLS) == 2
    names = [t.__name__ for t in CODE_INTERPRETER_TOOLS]
    assert "run_python" in names
    assert "run_shell" in names
    print("✅ Code interpreter tools OK (2 tools)")


def test_knowledge_base_tools():
    from tools.knowledge_base import KNOWLEDGE_BASE_TOOLS
    assert len(KNOWLEDGE_BASE_TOOLS) == 3
    names = [t.__name__ for t in KNOWLEDGE_BASE_TOOLS]
    assert "kb_index" in names
    assert "kb_search" in names
    assert "kb_list_sources" in names
    print("✅ Knowledge base tools OK (3 tools)")


def test_project_workspace_tools():
    from tools.project_workspace import PROJECT_WORKSPACE_TOOLS
    assert len(PROJECT_WORKSPACE_TOOLS) == 6
    names = [t.__name__ for t in PROJECT_WORKSPACE_TOOLS]
    for expected in (
        "project_create",
        "project_open",
        "project_note",
        "project_status",
        "project_list",
        "project_archive",
    ):
        assert expected in names, f"missing {expected}"
    print("✅ Project workspace tools OK (6 tools)")


def test_critique_tool():
    from tools.critique import CRITIQUE_TOOLS, critique_response
    assert len(CRITIQUE_TOOLS) == 1
    assert CRITIQUE_TOOLS[0].__name__ == "critique_response"
    assert callable(critique_response)
    print("✅ Critique tool OK (1 tool)")


# ─── Boil-the-Ocean: 4 specialist agents (constants + tool wiring) ────────
def test_research_agent_module():
    from agents.research_agent import (
        RESEARCH_AGENT_NAME,
        RESEARCH_AGENT_DESCRIPTION,
        RESEARCH_AGENT_INSTRUCTIONS,
        RESEARCH_AGENT_TOOLS,
    )
    assert RESEARCH_AGENT_NAME == "ResearchAgent"
    assert RESEARCH_AGENT_DESCRIPTION
    assert RESEARCH_AGENT_INSTRUCTIONS
    assert len(RESEARCH_AGENT_TOOLS) >= 6
    print(f"✅ Research agent OK ({len(RESEARCH_AGENT_TOOLS)} tools)")


def test_codeexecutor_agent_module():
    from agents.codeexecutor_agent import (
        CODEEXECUTOR_AGENT_NAME,
        CODEEXECUTOR_AGENT_DESCRIPTION,
        CODEEXECUTOR_AGENT_INSTRUCTIONS,
        CODEEXECUTOR_AGENT_TOOLS,
    )
    assert CODEEXECUTOR_AGENT_NAME == "CodeExecutorAgent"
    assert CODEEXECUTOR_AGENT_DESCRIPTION
    assert CODEEXECUTOR_AGENT_INSTRUCTIONS
    assert len(CODEEXECUTOR_AGENT_TOOLS) == 8
    print(f"✅ Code executor agent OK ({len(CODEEXECUTOR_AGENT_TOOLS)} tools)")


def test_documentanalyst_agent_module():
    from agents.documentanalyst_agent import (
        DOCUMENTANALYST_AGENT_NAME,
        DOCUMENTANALYST_AGENT_DESCRIPTION,
        DOCUMENTANALYST_AGENT_INSTRUCTIONS,
        DOCUMENTANALYST_AGENT_TOOLS,
    )
    assert DOCUMENTANALYST_AGENT_NAME == "DocumentAnalystAgent"
    assert DOCUMENTANALYST_AGENT_DESCRIPTION
    assert DOCUMENTANALYST_AGENT_INSTRUCTIONS
    assert len(DOCUMENTANALYST_AGENT_TOOLS) == 9
    print(f"✅ Document analyst agent OK ({len(DOCUMENTANALYST_AGENT_TOOLS)} tools)")


def test_critic_agent_module():
    from agents.critic_agent import (
        CRITIC_AGENT_NAME,
        CRITIC_AGENT_DESCRIPTION,
        CRITIC_AGENT_INSTRUCTIONS,
        CRITIC_AGENT_TOOLS,
    )
    assert CRITIC_AGENT_NAME == "CriticAgent"
    assert CRITIC_AGENT_DESCRIPTION
    assert CRITIC_AGENT_INSTRUCTIONS
    assert len(CRITIC_AGENT_TOOLS) == 1
    print(f"✅ Critic agent OK ({len(CRITIC_AGENT_TOOLS)} tool)")


# ─── End-to-end functional checks for new tools (offline-safe) ─────────────
def test_code_interpreter_runs_python():
    """run_python should execute a trivial snippet in the workspace sandbox."""
    from tools.code_interpreter import run_python

    result = asyncio.run(run_python("print(2 + 3)"))
    assert isinstance(result, str)
    assert "5" in result, f"expected '5' in output, got: {result!r}"
    print("✅ Code interpreter executes Python OK")


def test_file_reader_reads_text():
    """read_file should round-trip a tiny text file from a temp dir."""
    from tools.file_reader import read_file

    with TemporaryDirectory() as td:
        sample = Path(td) / "hello.txt"
        sample.write_text("boil the ocean\n", encoding="utf-8")
        out = asyncio.run(read_file(str(sample)))
        assert "boil the ocean" in out
    print("✅ File reader reads text OK")


def test_knowledge_base_index_and_search():
    """kb_index then kb_search should round-trip a unique sentinel string."""
    from tools.knowledge_base import kb_index, kb_search

    with TemporaryDirectory() as td:
        sample = Path(td) / "kb_smoke.txt"
        sentinel = "octopusazure7421"
        sample.write_text(
            f"This is a smoke-test note. Sentinel token: {sentinel}.\n",
            encoding="utf-8",
        )
        index_result = asyncio.run(kb_index(str(sample)))
        assert isinstance(index_result, str)
        # Must be findable via FTS5
        search_result = asyncio.run(kb_search(sentinel, top_k=3))
        assert sentinel in search_result, (
            f"sentinel {sentinel!r} not found in KB search output: {search_result!r}"
        )
    print("✅ Knowledge base index+search round-trip OK")


def test_project_workspace_create_and_open():
    """project_create then project_open should round-trip a project name."""
    from tools.project_workspace import project_create, project_open, project_archive

    name = "smoke-project-boil"
    try:
        created = asyncio.run(project_create(name, "Smoke test project."))
        assert isinstance(created, str)
        opened = asyncio.run(project_open(name))
        assert isinstance(opened, str)
        assert name in opened or "Smoke test project" in opened
    finally:
        # Clean up so re-running the suite stays idempotent.
        try:
            asyncio.run(project_archive(name))
        except Exception:
            pass
    print("✅ Project workspace create+open OK")


def test_mcp_tools_load_ok():
    """MCP tool lists import and expose the expected number of callables."""
    from tools.mcp_tools import (
        MCP_DOCS_TOOLS,
        MCP_GITHUB_TOOLS,
        MCP_TIER1_TOOLS,
        MCP_TIER2_TOOLS,
        MCP_TIER3_TOOLS,
        MCP_TOOLS,
        is_github_mcp_active,
        mcp_status,
    )

    assert len(MCP_DOCS_TOOLS) == 3, f"expected 3 docs tools, got {len(MCP_DOCS_TOOLS)}"
    assert len(MCP_GITHUB_TOOLS) == 4, f"expected 4 github tools, got {len(MCP_GITHUB_TOOLS)}"
    assert len(MCP_TIER1_TOOLS) == 7, f"expected 7 tier1 tools, got {len(MCP_TIER1_TOOLS)}"
    assert len(MCP_TIER2_TOOLS) == 6, f"expected 6 tier2 tools, got {len(MCP_TIER2_TOOLS)}"
    assert len(MCP_TIER3_TOOLS) == 8, f"expected 8 tier3 tools, got {len(MCP_TIER3_TOOLS)}"
    assert len(MCP_TOOLS) == 28, f"expected 28 total MCP tools, got {len(MCP_TOOLS)}"
    assert all(callable(t) for t in MCP_TOOLS)

    status = mcp_status()
    assert "docs_url" in status
    assert "github_url" in status
    assert "github_enabled" in status
    assert isinstance(is_github_mcp_active(), bool)
    print(
        f"✅ MCP tools OK ({len(MCP_TOOLS)} tools across 15 servers, "
        f"github_enabled={status['github_enabled']})"
    )


def test_mcp_agents_have_tools():
    """Specialists that should ground in MS Docs / GitHub MCP have those tools wired."""
    from tools.mcp_tools import MCP_DOCS_TOOLS, MCP_GITHUB_TOOLS

    docs_names = {getattr(t, "__name__", str(t)) for t in MCP_DOCS_TOOLS}
    gh_names = {getattr(t, "__name__", str(t)) for t in MCP_GITHUB_TOOLS}

    # Microsoft-Azure-heavy specialists: docs only
    from agents.azurearchitect_agent import AZUREARCHITECT_TOOLS
    from agents.databricks_agent import DATABRICKS_TOOLS

    for tools_list, label in [
        (AZUREARCHITECT_TOOLS, "AzureSolutionArchitect"),
        (DATABRICKS_TOOLS, "DatabricksSpecialist"),
    ]:
        names = {getattr(t, "__name__", str(t)) for t in tools_list}
        assert docs_names.issubset(names), f"{label} missing MCP_DOCS_TOOLS"

    # Code/issue/enterprise specialists: docs + github
    from agents.enterprise_agent import ENTERPRISE_TOOLS
    from agents.problemsolver_agent import PROBLEMSOLVER_TOOLS
    from agents.securityengineer_agent import SECURITYENGINEER_TOOLS
    from agents.seniordev_agent import SENIORDEV_TOOLS
    from agents.research_agent import RESEARCH_AGENT_TOOLS

    for tools_list, label in [
        (ENTERPRISE_TOOLS, "EnterpriseIntegration"),
        (PROBLEMSOLVER_TOOLS, "ProblemSolver"),
        (SECURITYENGINEER_TOOLS, "SecurityEngineer"),
        (SENIORDEV_TOOLS, "SeniorDev"),
        (RESEARCH_AGENT_TOOLS, "Research"),
    ]:
        names = {getattr(t, "__name__", str(t)) for t in tools_list}
        assert docs_names.issubset(names), f"{label} missing MCP_DOCS_TOOLS"
        assert gh_names.issubset(names), f"{label} missing MCP_GITHUB_TOOLS"

    print("✅ MCP wiring OK (7 specialists grounded in MS Docs + GitHub MCP)")


def test_mcp_tier1_groups_load_ok():
    """Tier 1 (HTTP, no-auth) MCP groups load with the expected tool counts."""
    from tools.mcp_tools import (
        MCP_CONTEXT7_TOOLS,
        MCP_DEEPWIKI_TOOLS,
        MCP_HUGGINGFACE_TOOLS,
        mcp_status,
    )

    assert len(MCP_DEEPWIKI_TOOLS) == 2, f"expected 2 deepwiki tools, got {len(MCP_DEEPWIKI_TOOLS)}"
    assert len(MCP_CONTEXT7_TOOLS) == 2, f"expected 2 context7 tools, got {len(MCP_CONTEXT7_TOOLS)}"
    assert len(MCP_HUGGINGFACE_TOOLS) == 3, (
        f"expected 3 huggingface tools, got {len(MCP_HUGGINGFACE_TOOLS)}"
    )
    assert all(callable(t) for t in MCP_DEEPWIKI_TOOLS)
    assert all(callable(t) for t in MCP_CONTEXT7_TOOLS)
    assert all(callable(t) for t in MCP_HUGGINGFACE_TOOLS)

    status = mcp_status()
    for key in ("deepwiki_enabled", "context7_enabled", "huggingface_enabled"):
        assert key in status, f"mcp_status missing {key}"

    print(
        "✅ MCP Tier 1 OK (DeepWiki + Context7 + Hugging Face — "
        f"deepwiki_enabled={status['deepwiki_enabled']})"
    )


def test_mcp_tier2_groups_load_ok():
    """Tier 2 (HTTP, opt-in via tokens) MCP groups load with the expected tool counts."""
    from tools.mcp_tools import (
        MCP_ATLASSIAN_TOOLS,
        MCP_NOTION_TOOLS,
        MCP_SENTRY_TOOLS,
        mcp_status,
    )

    assert len(MCP_NOTION_TOOLS) == 2, f"expected 2 notion tools, got {len(MCP_NOTION_TOOLS)}"
    assert len(MCP_SENTRY_TOOLS) == 2, f"expected 2 sentry tools, got {len(MCP_SENTRY_TOOLS)}"
    assert len(MCP_ATLASSIAN_TOOLS) == 2, (
        f"expected 2 atlassian tools, got {len(MCP_ATLASSIAN_TOOLS)}"
    )
    assert all(callable(t) for t in MCP_NOTION_TOOLS)
    assert all(callable(t) for t in MCP_SENTRY_TOOLS)
    assert all(callable(t) for t in MCP_ATLASSIAN_TOOLS)

    status = mcp_status()
    for key in ("notion_enabled", "sentry_enabled", "atlassian_enabled"):
        assert key in status, f"mcp_status missing {key}"

    print(
        "✅ MCP Tier 2 OK (Notion + Sentry + Atlassian — "
        f"notion_enabled={status['notion_enabled']}, "
        f"sentry_enabled={status['sentry_enabled']}, "
        f"atlassian_enabled={status['atlassian_enabled']})"
    )


def test_mcp_tier3_groups_load_ok():
    """Tier 3 (stdio via npx/uvx) MCP groups load with the expected tool counts."""
    from tools.mcp_tools import (
        MCP_FETCH_TOOLS,
        MCP_FILESYSTEM_TOOLS,
        MCP_GIT_TOOLS,
        MCP_MEMORY_GRAPH_TOOLS,
        MCP_SEQUENTIAL_THINKING_TOOLS,
        MCP_SQLITE_TOOLS,
        MCP_TIME_TOOLS,
        mcp_status,
    )

    assert len(MCP_FILESYSTEM_TOOLS) == 1
    assert len(MCP_SEQUENTIAL_THINKING_TOOLS) == 1
    assert len(MCP_MEMORY_GRAPH_TOOLS) == 2
    assert len(MCP_GIT_TOOLS) == 1
    assert len(MCP_SQLITE_TOOLS) == 1
    assert len(MCP_TIME_TOOLS) == 1
    assert len(MCP_FETCH_TOOLS) == 1

    for group in (
        MCP_FILESYSTEM_TOOLS,
        MCP_SEQUENTIAL_THINKING_TOOLS,
        MCP_MEMORY_GRAPH_TOOLS,
        MCP_GIT_TOOLS,
        MCP_SQLITE_TOOLS,
        MCP_TIME_TOOLS,
        MCP_FETCH_TOOLS,
    ):
        assert all(callable(t) for t in group)

    status = mcp_status()
    for key in (
        "filesystem_enabled",
        "sequential_thinking_enabled",
        "memory_graph_enabled",
        "git_enabled",
        "sqlite_enabled",
        "time_enabled",
        "fetch_enabled",
        "node_available",
        "uvx_available",
    ):
        assert key in status, f"mcp_status missing {key}"

    print(
        "✅ MCP Tier 3 OK (Filesystem + SeqThink + Memory + Git + SQLite + Time + Fetch — "
        f"node={status['node_available']}, uvx={status['uvx_available']})"
    )


def test_rag_tools_load_ok():
    """RAG tool list imports and exposes the expected callables; status is sane."""
    from tools.rag_tools import RAG_TOOLS
    from tools.rag_store import (
        default_cases_root,
        embeddings_enabled,
        embeddings_status,
    )

    assert len(RAG_TOOLS) >= 4, f"expected >=4 RAG tools, got {len(RAG_TOOLS)}"
    assert all(callable(t) for t in RAG_TOOLS)

    names = {getattr(t, "__name__", str(t)) for t in RAG_TOOLS}
    for required in {"case_search", "case_index_update", "case_index_rebuild", "case_list_indexed"}:
        assert required in names, f"missing tool: {required}"

    assert isinstance(embeddings_enabled(), bool)
    status = embeddings_status()
    assert "enabled" in status and status["enabled"] in {"true", "false"}
    assert isinstance(default_cases_root().as_posix(), str)
    print(f"✅ RAG tools OK ({len(RAG_TOOLS)} tools, embeddings={status['enabled']})")


def test_rag_index_empty_ok():
    """Indexing an empty cases-root returns a clean IndexResult, never raises."""
    import asyncio
    import tempfile
    from pathlib import Path
    from tools.rag_store import index_cases

    with tempfile.TemporaryDirectory() as tmp:
        empty_root = Path(tmp) / "Cases"
        empty_root.mkdir()
        db = Path(tmp) / "rag_test.db"
        result = asyncio.run(index_cases(empty_root, db_path=db, full_rebuild=True))

    assert result.indexed == 0
    assert result.failed == 0
    assert result.files_scanned == 0
    print("✅ RAG empty-index OK (no files, no failures)")


def test_rag_search_no_docs_returns_friendly_message():
    """Searching an unpopulated store returns a friendly string, never raises."""
    import asyncio
    from tools.rag_tools import case_search

    out = asyncio.run(case_search("anything that should not match"))
    assert isinstance(out, str)
    assert len(out) > 0
    # Either "No case artifacts are indexed yet." or "No case content matched"
    # depending on whether other tests previously populated the real store.
    assert ("No case" in out) or ("Top" in out)
    print("✅ RAG search graceful-empty OK")


def test_plans_tools_load_ok():
    """Plans tool list imports and exposes the expected callables."""
    from tools.plans_tools import PLANS_TOOLS

    names = {t.__name__ for t in PLANS_TOOLS}
    expected = {
        "plan_create",
        "plan_list",
        "plan_get",
        "plan_step_update",
        "plan_add_step",
        "plan_resume",
        "plan_cancel",
        "plan_events",
    }
    assert expected.issubset(names), f"missing tools: {expected - names}"
    print(f"✅ Plans tools OK ({len(PLANS_TOOLS)} tools)")


def test_plans_create_and_get_round_trip():
    """plan_create persists a plan with steps, plan_get returns identical content."""
    import asyncio
    import json
    import tempfile
    from pathlib import Path

    from tools import plans_store

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "plans_test.db"
        plan = plans_store.create_plan(
            title="Smoke plan",
            goal="verify round trip",
            steps=[
                {"title": "step one", "owner_agent": "ResearchAgent"},
                {"title": "step two"},
            ],
            owner="Smoke",
            tags=["smoke", "test"],
            db_path=db,
        )
        assert plan.id.startswith("plan_")
        assert len(plan.steps) == 2
        fetched = plans_store.get_plan(plan.id, db_path=db)
        assert fetched is not None
        assert fetched.id == plan.id
        assert fetched.steps[0].step_index == 0
        assert fetched.steps[0].owner_agent == "ResearchAgent"
        assert fetched.steps[1].title == "step two"
        assert fetched.status == "pending"
        # listing returns it back
        listed = plans_store.list_plans(db_path=db)
        assert any(p.id == plan.id for p in listed)
    print("✅ Plans create/get round-trip OK")


def test_plans_step_update_transitions():
    """update_step moves status pending → in_progress → done and rolls plan up."""
    import tempfile
    from pathlib import Path

    from tools import plans_store

    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "plans_test.db"
        plan = plans_store.create_plan(
            title="Transitions",
            goal="check status transitions",
            steps=[{"title": "only step"}],
            db_path=db,
        )
        # Start the step
        s1 = plans_store.update_step(plan.id, 0, status="in_progress", db_path=db)
        assert s1 is not None and s1.status == "in_progress"
        assert s1.started_at is not None
        # Plan should auto-promote to in_progress
        p_mid = plans_store.get_plan(plan.id, db_path=db)
        assert p_mid is not None and p_mid.status == "in_progress"
        # Complete the step
        s2 = plans_store.update_step(
            plan.id, 0, status="done", result="finished", db_path=db
        )
        assert s2 is not None and s2.status == "done"
        assert s2.result == "finished"
        assert s2.completed_at is not None
        # All steps terminal → plan rolls up to done
        p_end = plans_store.get_plan(plan.id, db_path=db)
        assert p_end is not None and p_end.status == "done"
        # next_pending_step returns None
        assert plans_store.next_pending_step(plan.id, db_path=db) is None
    print("✅ Plans step transitions OK")


def test_plan_create_tool_async_smoke():
    """plan_create + plan_get + plan_resume tool wrappers run end-to-end without raising."""
    import asyncio

    from tools.plans_tools import (
        plan_cancel,
        plan_create,
        plan_get,
        plan_list,
        plan_resume,
        plan_step_update,
    )

    async def _run():
        out = await plan_create(
            title="async smoke",
            goal="exercise the tool wrappers",
            steps_json='[{"title":"alpha","owner_agent":"ResearchAgent"},{"title":"beta"}]',
            owner="SmokeRunner",
            tags="smoke,wrap",
        )
        assert isinstance(out, str) and "Created plan plan_" in out
        # Pull the plan_id back out of the formatted output
        plan_id = next(
            (line.split(":", 1)[1].strip() for line in out.splitlines()
             if line.startswith("plan_id")),
            "",
        )
        assert plan_id.startswith("plan_")
        info = await plan_get(plan_id)
        assert "alpha" in info and "beta" in info
        upd = await plan_step_update(plan_id, 0, status="in_progress")
        assert "in_progress" in upd
        nxt = await plan_resume(plan_id)
        assert "Next step" in nxt
        listing = await plan_list()
        assert plan_id in listing
        cancelled = await plan_cancel(plan_id, reason="smoke complete")
        assert "cancelled" in cancelled.lower()
        return True

    assert asyncio.run(_run()) is True
    print("✅ Plans async tool wrappers OK")


def test_screen_context_tools_load_ok():
    """Screen-context module exposes the expected 7 audit-logged tools."""
    from tools.screen_context import SCREEN_CONTEXT_TOOLS

    expected = {
        "read_clipboard",
        "paste_to_clipboard",
        "get_active_window_title",
        "detect_active_case",
        "set_active_case",
        "get_active_case",
        "clear_active_case",
    }
    actual = {t.__name__ for t in SCREEN_CONTEXT_TOOLS}
    missing = expected - actual
    assert not missing, f"missing screen_context tools: {missing}"
    print(f"✅ Screen-context tools OK ({len(SCREEN_CONTEXT_TOOLS)} tools)")


def test_active_case_round_trip():
    """set_active_case -> get_active_case round-trips through the JSON store."""
    import asyncio
    import os
    import tempfile
    from pathlib import Path

    from tools import screen_context

    # Redirect ACTIVE_CASE_FILE to a tempdir so we don't trample real state.
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "memory" / "active_case.json"
        original = screen_context.ACTIVE_CASE_FILE
        screen_context.ACTIVE_CASE_FILE = tmp_path

        # And redirect Cases root to the tempdir so set_active_case
        # can resolve a real folder.
        case_id = "2026-03-17_SR_1234567"
        fake_root = Path(tmp) / "Cases"
        (fake_root / case_id).mkdir(parents=True)
        os_environ_backup = os.environ.get("CASES_ROOT")
        os.environ["CASES_ROOT"] = str(fake_root)

        try:
            async def _run():
                empty = await screen_context.get_active_case()
                assert "No active case is set" in empty
                set_msg = await screen_context.set_active_case(case_id)
                assert "Set." in set_msg or "Set\n" in set_msg, set_msg
                assert case_id in set_msg
                got = await screen_context.get_active_case()
                assert case_id in got
                assert "manual" in got
                cleared = await screen_context.clear_active_case()
                assert "cleared" in cleared.lower()
                empty2 = await screen_context.get_active_case()
                assert "No active case is set" in empty2
                return True

            assert asyncio.run(_run()) is True
        finally:
            screen_context.ACTIVE_CASE_FILE = original
            if os_environ_backup is None:
                os.environ.pop("CASES_ROOT", None)
            else:
                os.environ["CASES_ROOT"] = os_environ_backup
    print("✅ Active-case round-trip OK")


def test_detect_active_case_regex():
    """The case-id regex matches the documented YYYY-MM-DD_SR_xxxxxxx convention."""
    from tools.screen_context import CASE_FOLDER_PATTERN, _scan_text_for_case_id

    positives = {
        "2026-03-17_SR_1234567": "2026-03-17_SR_1234567",
        "Notes - 2026-04-16_SR_1234567 - draft.md": "2026-04-16_SR_1234567",
        "C:\\Users\\x\\Work_cases\\Cases\\2025-12-01_SR_9999999\\notes": "2025-12-01_SR_9999999",
        "2024-01-01_SR_12345678 (8 digits)": "2024-01-01_SR_12345678",
    }
    for raw, expected in positives.items():
        m = CASE_FOLDER_PATTERN.search(raw)
        assert m is not None, f"expected to find case-id in: {raw!r}"
        assert m.group(0) == expected
        assert _scan_text_for_case_id(raw) == expected

    negatives = [
        "no case here",
        "2026-3-17_SR_1234567",   # month not zero-padded
        "2026-03-17_SR_12345",    # too few digits
        "2026/03/17_SR_1234567",  # wrong separator
    ]
    for raw in negatives:
        assert _scan_text_for_case_id(raw) is None, f"false positive on: {raw!r}"

    print("✅ Case-id regex OK")


def test_screen_context_platform_guard():
    """On non-Windows, OS-touching tools return a clean string instead of crashing."""
    import asyncio

    from tools import screen_context

    original_is_windows = screen_context.IS_WINDOWS
    try:
        screen_context.IS_WINDOWS = False

        async def _run():
            for fn in (
                screen_context.read_clipboard,
                screen_context.get_active_window_title,
                screen_context.detect_active_case,
            ):
                out = await fn()
                assert isinstance(out, str) and "Windows-only" in out, (
                    f"{fn.__name__} did not return platform-guard string: {out!r}"
                )
            paste_out = await screen_context.paste_to_clipboard("hello")
            assert "Windows-only" in paste_out, paste_out
            return True

        assert asyncio.run(_run()) is True
    finally:
        screen_context.IS_WINDOWS = original_is_windows

    print("✅ Screen-context platform guard OK")


if __name__ == "__main__":
    test_config_loads()
    test_orchestrator_registration()
    test_model_option_compatibility()
    test_guardrails()
    test_audit()
    test_email_tools()
    test_calendar_tools()
    test_social_tools()
    test_finance_tools()
    test_business_tools()
    test_notification_gateway()
    test_service_runner()
    test_finance_db()
    test_business_db()
    test_memory_store()
    test_profile_seed_loading()
    test_azure_architect_tools()
    test_databricks_tools()
    test_daily_briefing_tool()
    test_eod_review_tool()
    test_draft_replies_tool()
    test_proactive_scheduler()
    test_legaldocreview_tools()
    test_realestate_tools()
    test_investmentresearcher_tools()
    test_projectshepherd_tools()
    test_securityengineer_tools()
    test_frontenddev_tools()
    test_backendarchitect_tools()
    test_taxstrategist_tools()
    test_emailintel_tools()
    test_salesproposal_tools()
    # Boil-the-Ocean — capability tools
    test_web_search_tool()
    test_web_fetch_tool()
    test_file_reader_tools()
    test_code_interpreter_tools()
    test_knowledge_base_tools()
    test_project_workspace_tools()
    test_critique_tool()
    # Boil-the-Ocean — specialist agents
    test_research_agent_module()
    test_codeexecutor_agent_module()
    test_documentanalyst_agent_module()
    test_critic_agent_module()
    # Boil-the-Ocean — functional round-trips
    test_code_interpreter_runs_python()
    test_file_reader_reads_text()
    test_knowledge_base_index_and_search()
    test_project_workspace_create_and_open()
    # MCP integration
    test_mcp_tools_load_ok()
    test_mcp_agents_have_tools()
    test_mcp_tier1_groups_load_ok()
    test_mcp_tier2_groups_load_ok()
    test_mcp_tier3_groups_load_ok()
    # RAG over Work_cases\Cases\
    test_rag_tools_load_ok()
    test_rag_index_empty_ok()
    test_rag_search_no_docs_returns_friendly_message()
    # Durable plan/task store
    test_plans_tools_load_ok()
    test_plans_create_and_get_round_trip()
    test_plans_step_update_transitions()
    test_plan_create_tool_async_smoke()
    # Screen-context tools (clipboard, active window, active case)
    test_screen_context_tools_load_ok()
    test_active_case_round_trip()
    test_detect_active_case_regex()
    test_screen_context_platform_guard()
    print(f"\n🎉 All 63 smoke tests passed!")
