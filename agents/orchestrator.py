"""
AgentSystem — Orchestrator v2.0

Inter-agent handoff enabled. Specialist agents can call other agents
as tools, creating a mesh of collaborative intelligence.
"""
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent_framework import Agent, AgentSession
from agent_framework.openai import OpenAIChatCompletionClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    MissingModelCredentialsError,
    get_agent_configs,
    get_azure_openai_auth_kwargs,
    get_model_config,
    get_models_config,
    get_system_config,
)
from tools.audit import log_action
from telemetry import get_tracer
from tools.code_interpreter import CODE_INTERPRETER_TOOLS
from tools.critique import CRITIQUE_TOOLS
from tools.daily_briefing import DAILY_BRIEFING_TOOLS
from tools.draft_replies import DRAFT_REPLY_TOOLS
from tools.end_of_day import END_OF_DAY_TOOLS
from tools.file_reader import FILE_READER_TOOLS
from tools.knowledge_base import KNOWLEDGE_BASE_TOOLS
from tools.mcp_tools import (
    MCP_ATLASSIAN_TOOLS,
    MCP_CONTEXT7_TOOLS,
    MCP_DEEPWIKI_TOOLS,
    MCP_DOCS_TOOLS,
    MCP_FETCH_TOOLS,
    MCP_FILESYSTEM_TOOLS,
    MCP_GIT_TOOLS,
    MCP_GITHUB_TOOLS,
    MCP_HUGGINGFACE_TOOLS,
    MCP_MEMORY_GRAPH_TOOLS,
    MCP_NOTION_TOOLS,
    MCP_SENTRY_TOOLS,
    MCP_SEQUENTIAL_THINKING_TOOLS,
    MCP_SQLITE_TOOLS,
    MCP_TIME_TOOLS,
)
from tools.memory_tools import MEMORY_STORE, MEMORY_TOOLS
from tools.plans_tools import PLANS_TOOLS
from tools.project_workspace import PROJECT_WORKSPACE_TOOLS
from tools.rag_tools import RAG_TOOLS
from tools.screen_context import SCREEN_CONTEXT_TOOLS
from tools.web_fetch import WEB_FETCH_TOOLS
from tools.web_search import WEB_SEARCH_TOOLS
from tools.browse_tools import BROWSE_TOOLS
from tools.data_parser import DATA_PARSER_TOOLS
from toolkits import POWER_TOOLS_BASE

logger = logging.getLogger(__name__)

# ── Shared operating directive injected into EVERY specialist agent ────────
# Hardens all agents to do thorough, verified, production-grade work rather
# than shallow template answers. Kept short so it never crowds out the
# agent-specific system message.
GROUNDING_DIRECTIVE = """

## MANDATORY GROUNDING GATE — PASS BEFORE ANSWERING
You MUST ground every answer in real evidence. Before presenting your final response,
run through this checklist. If any check fails, you MUST search/read/run first:

1. **TECHNOLOGY / PRODUCT / API / FRAMEWORK QUESTIONS**
   → Search web or `microsoft_docs_search` FIRST. Cite at least one source URL.
   → If the source disagrees with your knowledge, DEFER TO THE SOURCE.

2. **CODE IN YOUR ANSWER**
   → MUST be tested via `run_python` in the sandbox, OR you MUST cite an existing
     implementation you have read. Never present untested code as correct.

3. **NUMBERS / CALCULATIONS / METRICS**
   → MUST show your calculation or cite the source of the number.
   → If computed locally, include the `run_python` output.

4. **"BEST PRACTICE" / "INDUSTRY STANDARD" / "RECOMMENDED" CLAIMS**
   → MUST cite at least one verifiable source (URL, doc, benchmark).
   → Unsourced claims of consensus are not evidence.

5. **ARCHITECTURE / DESIGN DECISIONS**
   → MUST run `critique_response` on your proposal before presenting.
   → State what trade-offs you accepted and what alternatives you rejected.

6. **FILE / DOCUMENT / CASE REFERENCES**
   → MUST `read_file` or `case_search` to inspect the actual content.
   → Never summarize a file you have not read.

7. **WEB PAGE EXTRACTION (FETCHING LIVE CONTENT)**
   → Always try `web_fetch` FIRST — it handles most pages fast and reliably.
   → If `web_fetch` returns blank/incomplete (JS-rendered SPA, anti-bot), try `browse_health` to check
     browser availability, then `browse_fetch` as the fallback for JS-heavy sites.
   → KNOWN HOSTILE SITES (skip fetch entirely, go straight to web_search):
     - reuters.com (DataDome)
     - bloomberg.com (paywall + anti-bot)
     - wsj.com (paywall)
     - ft.com (paywall)
     For these sites, `web_search` gives you headlines, dates, and enough context to cite.
   → If `browse_fetch` is unavailable or blocked, DO NOT retry — immediately fall back to
     `web_search`, extract headlines/summaries from search result snippets, and cite them.
     Search snippets ARE valid sources — they come from the actual page <title> and <meta> tags.
   → For news specifically, search "{topic} news today" to get the freshest results.
   → Never present "tool unavailable" as a dead end. There is always another way.

If you cannot ground a claim, say "I cannot verify this because [reason]" —
never present speculation as fact.
"""

BOIL_THE_OCEAN_DIRECTIVE = """

## OPERATING STANDARD — BOIL THE OCEAN
You work for a principal-level engineer. Mediocre or partial answers are unacceptable.
For every non-trivial task:
1. DO THE WHOLE THING. Deliver the complete, production-grade solution — not a sketch,
   not a "here's how you would". Include edge cases, error handling, and trade-offs.
2. VERIFY BEFORE YOU CLAIM. If you state a computational, numerical, or code-correctness
   result, PROVE it: run `run_python` (or the relevant tool) in the sandbox and cite the
   REAL output. Never assert a number, benchmark, or "this works" you have not executed.
3. USE YOUR TOOLS. Search, fetch docs, read files, run code, and delegate to other agents
   instead of guessing. Ground every claim in evidence.
4. SELF-CRITIQUE on high-stakes work (architecture, security, code to be merged, cost,
   anything irreversible): review your own draft for correctness and gaps before returning.
5. BE HONEST. Separate facts from assumptions. Flag risks. If something cannot be verified,
   say so explicitly rather than bluffing.
Aim for "holy shit, it did all that" — complete, correct, verified, and immediately usable.
"""

# ── Base capability tools available to ALL specialist agents ──────────────
BASE_CAPABILITY_TOOLS = (
    list(WEB_SEARCH_TOOLS)
    + list(WEB_FETCH_TOOLS)
    + list(BROWSE_TOOLS)
    + list(FILE_READER_TOOLS)
    + list(CODE_INTERPRETER_TOOLS)
    + list(KNOWLEDGE_BASE_TOOLS)
    + list(CRITIQUE_TOOLS)
    + list(MCP_DOCS_TOOLS)
    + list(MCP_GITHUB_TOOLS)
    + list(MCP_SEQUENTIAL_THINKING_TOOLS)
    + list(POWER_TOOLS_BASE)
    + list(DATA_PARSER_TOOLS)
)


@dataclass(slots=True)
class AgentRegistration:
    """Lazy registration for a specialist agent."""

    name: str
    system_message: str
    description: str = ""
    tools: list[Any] = field(default_factory=list)
    handoff_agents: list[str] = field(default_factory=list)  # Agents this agent can call
    model_profile: Optional[str] = None  # PR3: opt-in routing profile (None → catalog policy/legacy)
    require_critique: bool = False  # If True, orchestrator forces a critique pass before returning


def create_model_client() -> OpenAIChatCompletionClient:
    """Build the chat-completion client for whichever provider has usable creds.

    Honors the provider configured in ``agents.yaml`` when its credentials are
    present, but transparently falls back between ``azure_openai`` and ``openai``
    when the configured provider is missing (or has placeholder) credentials.
    Raises :class:`MissingModelCredentialsError` only when NEITHER provider is
    usable, so the API layer can return a clean 503 instead of a raw 500.
    """
    model_cfg = get_model_config()

    # Surface, but don't hard-fail on, providers we don't yet support natively.
    if model_cfg.provider not in ("azure_openai", "openai"):
        logger.warning(
            "Model provider %r is not natively supported yet; "
            "falling back to any configured Azure OpenAI / OpenAI credentials.",
            model_cfg.provider,
        )

    if not (model_cfg.has_azure_credentials or model_cfg.has_openai_credentials):
        raise MissingModelCredentialsError(
            "No LLM provider is configured. Set AZURE_OPENAI_ENDPOINT plus "
            "AZURE_OPENAI_API_KEY or AZURE_OPENAI_USE_ENTRA=true, or set "
            "OPENAI_API_KEY (placeholder values are ignored)."
        )

    provider = model_cfg.effective_provider
    model_name = model_cfg.effective_model

    if provider != model_cfg.provider:
        logger.warning(
            "Configured provider %r lacks usable credentials; "
            "falling back to %r.",
            model_cfg.provider,
            provider,
        )

    if provider == "azure_openai":
        return OpenAIChatCompletionClient(
            model=model_name,
            azure_endpoint=model_cfg.azure_endpoint,
            api_version=model_cfg.azure_api_version,
            **get_azure_openai_auth_kwargs(model_cfg),
        )
    return OpenAIChatCompletionClient(
        model=model_name, api_key=model_cfg.openai_api_key,
    )


def _is_trivial_chat(task: str) -> bool:
    """True for greetings, acknowledgments, and pure social chat that
    don't need grounding enforcement."""
    task_lower = task.strip().lower()
    trivial_patterns = [
        "hey", "hi", "hello", "yo", "sup", "hola",
        "thanks", "thank you", "thx", "ty",
        "ok", "okay", "kk", "got it", "cool",
        "good morning", "good afternoon", "good evening",
        "how are you", "what's up", "howdy",
        "bye", "see you", "later", "cya",
        "lol", "haha", "nice", "awesome",
    ]
    return task_lower in trivial_patterns or len(task_lower) < 3


def get_default_agent_options() -> dict[str, Any]:
    model_cfg = get_model_config()
    options: dict[str, Any] = {
        "max_tokens": model_cfg.max_tokens,
        "allow_multiple_tool_calls": True,  # Enable parallel tool calls for handoff
    }
    if model_cfg.supports_custom_temperature:
        options["temperature"] = model_cfg.temperature
    return options


@dataclass(slots=True)
class SessionState:
    """Per-conversation execution state.

    Bundling ``session_id`` + the Agent Framework :class:`AgentSession` + the
    session-scoped ``case_context`` into ONE object is what lets the HTTP layer
    give every request/run its own isolated state instead of sharing a single
    process-global session across all users. CLI/local callers get their own
    dedicated instance too.
    """

    session_id: str
    conversation_session: AgentSession
    case_context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TurnResult:
    """Structured result of one orchestrator turn (real agent attribution)."""

    text: str
    agents_used: list[str] = field(default_factory=list)
    selected_agent: Optional[str] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0


class Orchestrator:
    """Central orchestrator with inter-agent handoff."""

    def __init__(self):
        self._system_config = get_system_config()
        self._agent_configs = get_agent_configs()
        self._model_client: Optional[OpenAIChatCompletionClient] = None
        self._registrations: dict[str, AgentRegistration] = {}
        self._agents: dict[str, Agent] = {}
        self._coordinator: Optional[Agent] = None
        self._api_coordinator: Optional[Agent] = None
        self._memory_store = MEMORY_STORE
        self._creating: set[str] = set()
        # Backward-compatible LOCAL session state for CLI / dashboard callers.
        # The API path NEVER uses this — it passes its own isolated SessionState
        # so one user's conversation can never leak into another's.
        local_session_id = self._memory_store.get_active_session_id()
        self._local_session_state = SessionState(
            session_id=local_session_id,
            conversation_session=AgentSession(session_id=local_session_id),
        )
        self._artifact_dirs_initialized = False  # Track agents being created to break circular handoffs

    # ── Backward-compatible accessors (delegate to the LOCAL session) ────────
    @property
    def _active_session_id(self) -> str:
        return self._local_session_state.session_id

    @_active_session_id.setter
    def _active_session_id(self, value: str) -> None:
        self._local_session_state.session_id = value

    @property
    def _conversation_session(self) -> AgentSession:
        return self._local_session_state.conversation_session

    @_conversation_session.setter
    def _conversation_session(self, value: AgentSession) -> None:
        self._local_session_state.conversation_session = value

    @property
    def case_context(self) -> dict[str, Any]:
        return self._local_session_state.case_context

    @case_context.setter
    def case_context(self, value: dict[str, Any]) -> None:
        self._local_session_state.case_context = value

    def new_session_state(
        self,
        session_id: Optional[str] = None,
        persisted_state: Optional[dict[str, Any]] = None,
    ) -> SessionState:
        """Build a fresh, ISOLATED session state (honoring ``session_id``).

        The API layer calls this per request so each user/session gets its own
        conversation history and case context. When ``session_id`` is provided
        it is honored so a client can continue an existing conversation.
        """
        sid = session_id or self._memory_store.start_new_session()
        conversation_session = AgentSession(session_id=sid)
        case_context: dict[str, Any] = {}
        if persisted_state:
            serialized_session = persisted_state.get("conversation_session")
            if serialized_session:
                conversation_session = AgentSession.from_dict(serialized_session)
                if conversation_session.session_id != sid:
                    raise ValueError("persisted conversation session id mismatch")
            serialized_context = persisted_state.get("case_context", {})
            if isinstance(serialized_context, dict):
                case_context = dict(serialized_context)
        return SessionState(
            session_id=sid,
            conversation_session=conversation_session,
            case_context=case_context,
        )

    def serialize_session_state(self, state: SessionState) -> dict[str, Any]:
        """Return the JSON-safe snapshot stored with the durable session."""
        return {
            "conversation_session": state.conversation_session.to_dict(),
            "case_context": dict(state.case_context),
        }

    def _get_model_client(self) -> OpenAIChatCompletionClient:
        if self._model_client is None:
            self._model_client = create_model_client()
        return self._model_client

    # ── PR3: per-agent multi-model routing (opt-in, fails safe to legacy) ──
    def _routing_enabled(self) -> bool:
        """Whether the model router is enabled (defaults on; never raises)."""
        try:
            return get_models_config().enabled
        except Exception:  # pragma: no cover - defensive
            return False

    def _profile_for_agent(self, name: str, registration: AgentRegistration) -> Optional[str]:
        """Resolve the routing profile for an agent.

        Precedence: explicit ``registration.model_profile`` → catalog ``policy``
        entry keyed by the agent's registration name → ``None`` (legacy client).
        Never raises; any catalog problem degrades to ``None``.
        """
        if registration.model_profile:
            return registration.model_profile
        try:
            from routing import get_router

            return get_router().catalog.policy.get(name)
        except Exception:
            return None

    def _client_for_agent(
        self, name: str, registration: AgentRegistration
    ) -> OpenAIChatCompletionClient:
        """Build a specialist's client via the router, falling back to legacy.

        Any router/catalog failure (including missing credentials) falls through
        to :meth:`_get_model_client`, which preserves the existing clean-503
        behavior when no provider is configured.
        """
        if self._routing_enabled():
            profile = self._profile_for_agent(name, registration)
            if profile:
                try:
                    from routing import get_router

                    client = get_router().build_client(profile)
                    logger.info("Agent %s routed via profile %r", name, profile)
                    return client
                except MissingModelCredentialsError:
                    # Let the legacy path raise the canonical clean error below.
                    pass
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning(
                        "Routing failed for agent %s (profile %r): %s; using legacy client.",
                        name, profile, exc,
                    )
        return self._get_model_client()

    def _annotate_routing(self, span: Any) -> None:
        """Best-effort: attach the default profile's model.* attrs to a span."""
        try:
            if not self._routing_enabled():
                return
            from routing import get_router

            resolved = get_router().resolve()
            for key, value in resolved.as_attributes().items():
                span.set_attribute(key, value)
        except Exception:  # pragma: no cover - telemetry must never break routing
            pass

    def _routing_status(self) -> dict[str, Any]:
        """Compact, secret-free routing summary for ``status()`` (never raises)."""
        if not self._routing_enabled():
            return {"enabled": False}
        try:
            from routing import get_router

            catalog = get_router().catalog
            return {
                "enabled": True,
                "default_profile": catalog.default_profile,
                "profiles": sorted(catalog.profiles),
                "policy_entries": len(catalog.policy),
                "warnings": list(catalog.warnings),
            }
        except Exception as exc:
            return {"enabled": True, "available": False, "error": str(exc)}

    def _get_or_create_agent(self, name: str) -> Optional[Agent]:
        """Create a specialist agent with inter-agent handoff tools."""
        registration = self._registrations.get(name)
        if registration is None:
            return None

        if name not in self._agents:
            # Detect and break circular handoff dependencies
            if name in self._creating:
                logger.warning("Circular handoff detected for %s — deferring", name)
                return None
            self._creating.add(name)

            try:
                # Build augmented instructions
                instructions = registration.system_message + GROUNDING_DIRECTIVE + BOIL_THE_OCEAN_DIRECTIVE
                try:
                    from skills.claude_skills_integration import build_skill_context_for_agent
                    skill_ctx = build_skill_context_for_agent(name)
                    if skill_ctx:
                        instructions = instructions + "\n" + skill_ctx
                        logger.info("Augmented %s with claude-skills context", name)
                except Exception:
                    pass

                # Build tool list: base capabilities + agent-specific tools + handoff agents
                tools = list(BASE_CAPABILITY_TOOLS) + list(registration.tools)

                # Add handoff agents as tools — skip if circular
                handoff_count = 0
                pending_handoffs = []
                for handoff_name in registration.handoff_agents:
                    if handoff_name == name:
                        continue
                    if handoff_name in self._creating:
                        # Circular — add to pending, resolve after agent is built
                        pending_handoffs.append(handoff_name)
                        continue
                    handoff_agent = self._get_or_create_agent(handoff_name)
                    if handoff_agent is not None:
                        hreg = self._registrations.get(handoff_name)
                        tools.append(
                            handoff_agent.as_tool(
                                name=f"call_{handoff_name}",
                                description=f"Delegate to {handoff_name}: {hreg.description if hreg else ''}",
                                arg_name="request",
                                arg_description=f"Full task description for {handoff_name}",
                            )
                        )
                        handoff_count += 1

                if handoff_count > 0:
                    instructions += (
                        f"\n\n## INTER-AGENT HANDOFF\n"
                        f"You can call these agents for specialized help:\n" +
                        "\n".join(f"  - call_{h} — delegate work to {h}"
                                  for h in registration.handoff_agents
                                  if h != name and h not in pending_handoffs) +
                        "\nUse handoffs when the task spans another agent's expertise. "
                        "Always synthesize their output into a coherent final response."
                    )

                self._agents[name] = Agent(
                    name=registration.name,
                    description=registration.description or f"Agent: {registration.name}",
                    client=self._client_for_agent(name, registration),
                    instructions=instructions,
                    tools=tools,
                    default_options=get_default_agent_options(),
                )

                # Now resolve pending (circular) handoffs
                for pending_name in pending_handoffs:
                    pending_agent = self._agents.get(pending_name)
                    if pending_agent is not None:
                        hreg = self._registrations.get(pending_name)
                        self._agents[name].tools.append(
                            pending_agent.as_tool(
                                name=f"call_{pending_name}",
                                description=f"Delegate to {pending_name}: {hreg.description if hreg else ''}",
                                arg_name="request",
                                arg_description=f"Full task description for {pending_name}",
                            )
                        )
                        handoff_count += 1
                        logger.info("Resolved circular handoff: %s → %s", name, pending_name)

                if handoff_count > 0:
                    logger.info("Agent %s has %d handoff agents", name, handoff_count)

            finally:
                self._creating.discard(name)
        return self._agents[name]

    def _build_orchestrator_instructions(self) -> str:
        orchestrator_config = self._agent_configs.get("orchestrator", {})
        base_instructions = orchestrator_config.get(
            "system_message",
            "You are the orchestrator. Route tasks to the appropriate specialist agent.",
        ).strip()
        routing_guide = "\n".join(
            f"- {registration.name}: {registration.description or f'Specialist agent for {registration.name}'}"
            for registration in self._registrations.values()
        )
        return (
            f"{base_instructions}\n\n"
            "You do not execute specialist work yourself. Use the specialist tools available to you.\n"
            "Choose the minimum number of specialists needed for each request.\n"
            "Prefer a single specialist unless the task clearly spans multiple domains.\n"
            "When the answer is achievable with the available tools and context, finish it end-to-end instead of stopping at partial advice.\n"
            "Prefer durable fixes over temporary workarounds, and fix tightly related structural issues when they are the reason the user keeps hitting the same problem.\n"
            "Use the daily briefing tool for requests about daily planning, urgent unread mail, follow-ups, or start-of-day summaries.\n"
            "Use the end-of-day review tool when the user asks to wrap the day, review what got done, preview tomorrow, or plan priorities for tomorrow.\n"
            "Use the draft replies tool when the user asks for draft replies, inbox triage, or help answering important unread mail — it saves drafts to Outlook for manual review.\n"
            "When the request needs current information, vendor docs, news, or anything not in memory, use `web_search` then `web_fetch` to get the actual page text — do not bluff facts. For news from known-hostile sites (reuters.com, bloomberg.com, wsj.com, ft.com), skip fetching and use web_search snippets — they give headlines/dates. Prefer accessible news sources: apnews.com, bbc.com/news, cnbc.com, theverge.com, arstechnica.com, techcrunch.com. NEWS WORKFLOW (mandatory for any news/latest request): 1) web_search for article URLs and snippets; 2) web_fetch each article URL — if blocked, use the snippet; 3) ONLY cite articles you fetched or have snippet evidence for; 4) include dates; 5) never present section hubs as news — find individual articles.\n"
            "When `web_fetch` fails because a page is JS-rendered (blank or incomplete), use `browse_fetch` instead — it runs a real Chrome browser to extract content from modern SPAs, Microsoft docs, Azure portals, and any React/Vue/Angular page.\n"
            "When the user points you at a local file or folder (PDF, DOCX, XLSX, JSON, log, code), use `read_file` / `list_dir` / `search_in_file` to inspect it before answering.\n"
            "When the request requires actually computing something, transforming data, or generating output, use `run_python` in the workspace and inspect the actual output before claiming success.\n"
            "When the user asks you to remember a document or web page for later, use `kb_index`; when they ask 'have we seen this before?' or want to recall research, use `kb_search`.\n"
            "When work spans multiple sessions or days, use the project tools (`project_create`, `project_open`, `project_note`, `project_status`) to keep durable state separate from short-term memory.\n"
            "Before sending a high-stakes response (architecture, customer-facing, code merges, financial advice), call `critique_response` on your draft and incorporate critical findings.\n"
            "For ANY question about Microsoft / Azure / .NET / Microsoft 365 / Power Platform / Microsoft Fabric / Microsoft Entra / Databricks-on-Azure, prefer `microsoft_docs_search` (and `microsoft_docs_fetch` for full pages) over generic web search — the Microsoft Docs MCP returns first-party, version-current content. Use `microsoft_code_sample_search` whenever you are about to produce Microsoft / Azure code so it is grounded in official samples.\n"
            "For questions that depend on real GitHub state (existing implementations, upstream issues / PRs, source files, repo discovery), use the GitHub MCP tools (`github_search_repositories`, `github_search_code`, `github_search_issues`, `github_get_file_contents`). They degrade gracefully with a clear setup message when `GITHUB_TOKEN` is not configured — surface that message instead of fabricating content.\n"
            "For deep, version-current OSS / framework / library context, prefer `deepwiki_ask_question` (any GitHub repo wiki) and `context7_get_library_docs` (call `context7_resolve_library` first to convert a package name into a Context7 ID) over generic web search. For ML model / dataset / paper grounding, call `huggingface_model_search`, `huggingface_dataset_search`, or `huggingface_paper_search` before recommending models or building inference pipelines.\n"
            "For knowledge work, incident triage, and multi-system coordination, use the Tier 2 MCP tools when their tokens are configured: `notion_search` / `notion_fetch_page` for personal/team docs, `sentry_find_issues` / `sentry_get_issue_details` for production errors, and `jira_search_issues` / `confluence_search_pages` for tickets and team wikis. Each tool degrades cleanly when its token is absent — surface the setup message rather than fabricating data.\n"
            "For complex reasoning, structured exploration, and durable artifacts, use the Tier 3 stdio MCP tools when available: call `sequentialthinking` to decompose hard architecture or debugging problems before answering, `memory_graph_*` to build a long-running knowledge graph, `filesystem_*` to read/write inside `MCP_FILESYSTEM_ROOTS`, `git_*` to inspect repository history, `sqlite_*` to query a local DB, `time_get_current_time` for tz-aware timestamps, and `mcp_fetch` for clean Markdown extraction from a URL. Each requires its transport (Node or uv) plus its env opt-in — surface the setup message rather than guessing.\n"
            "For ANY question that mentions a customer case, SR# / case folder, Work_cases path, or specific customer artifact, ALWAYS call `case_search` first to ground the answer in the user's actual case files. Use `case_index_update` to refresh the local index before answering when the user mentions a new case folder. Use `case_list_indexed` if you need to know which cases are searchable.\n"
            "For multi-step or multi-day work (architecture builds, customer cases that will span follow-ups, anything where the user is likely to say 'continue' or 'where were we' later), use `plan_create` to persist a durable plan, set each step's `owner_agent` to the specialist that will execute it, and call `plan_step_update` as work progresses. When the user says 'resume', 'continue', 'where were we', or references a plan_id, call `plan_resume` (or `plan_get`) FIRST to ground in the persisted state instead of restarting from scratch.\n"
            "When the user references something on their screen ('this', 'what I copied', 'the case I'm looking at'), call `read_clipboard` and `get_active_window_title`; when they mention a case in passing, call `detect_active_case` to silently set the working case from the active window or clipboard. Always call `get_active_case` at the start of any case-scoped task to confirm you're working on the right case.\n"
            "Proactive scheduler events arrive from [SCHEDULER]: morning_briefing_due should run the daily briefing; end_of_day_due should run the end-of-day review; meeting_soon should produce a concise pre-meeting prep note using memory and recent context.\n"
            "Before asking follow-up questions, use the provided durable memory and recent session context.\n"
            "Do not ask for profile details or prior context that are already present in memory unless the user is updating them.\n"
            "If the user asks you to remember, update, forget, or review personal facts, use the memory tools.\n"
            "Do not ask whether you should continue when the next step is obvious; continue until the request is actually complete or you have a real blocker.\n"
            "Verify outcomes before presenting them as complete.\n"
            "If the request is missing critical details even after consulting memory and recent context, ask a concise follow-up question.\n"
            "Specialist tools already enforce their own approval checks for risky actions.\n"
            "After using specialists, provide one clear final response to the user.\n\n"
            "Available specialists:\n"
            f"{routing_guide}"
        )

    def _get_or_create_coordinator(self, *, include_legacy_memory: bool = True) -> Agent:
        coordinator = self._coordinator if include_legacy_memory else self._api_coordinator
        if coordinator is None:
            specialist_tools = (
                list(BROWSE_TOOLS)
                + list(DAILY_BRIEFING_TOOLS)
                + list(END_OF_DAY_TOOLS)
                + list(DRAFT_REPLY_TOOLS)
                + list(WEB_SEARCH_TOOLS)
                + list(WEB_FETCH_TOOLS)
                + list(FILE_READER_TOOLS)
                + list(CODE_INTERPRETER_TOOLS)
                + list(KNOWLEDGE_BASE_TOOLS)
                + list(PROJECT_WORKSPACE_TOOLS)
                + list(CRITIQUE_TOOLS)
                + list(MCP_DOCS_TOOLS)
                + list(MCP_GITHUB_TOOLS)
                + list(MCP_DEEPWIKI_TOOLS)
                + list(MCP_CONTEXT7_TOOLS)
                + list(MCP_HUGGINGFACE_TOOLS)
                + list(MCP_NOTION_TOOLS)
                + list(MCP_SENTRY_TOOLS)
                + list(MCP_ATLASSIAN_TOOLS)
                + list(MCP_FILESYSTEM_TOOLS)
                + list(MCP_SEQUENTIAL_THINKING_TOOLS)
                + list(MCP_MEMORY_GRAPH_TOOLS)
                + list(MCP_GIT_TOOLS)
                + list(MCP_SQLITE_TOOLS)
                + list(MCP_TIME_TOOLS)
                + list(MCP_FETCH_TOOLS)
                + list(RAG_TOOLS)
                + list(PLANS_TOOLS)
                + list(SCREEN_CONTEXT_TOOLS)
            )
            if include_legacy_memory:
                specialist_tools.extend(MEMORY_TOOLS)
            for registration in self._registrations.values():
                agent = self._get_or_create_agent(registration.name)
                if agent is None:
                    continue
                specialist_tools.append(
                    agent.as_tool(
                        name=registration.name,
                        description=registration.description or f"Handle tasks for {registration.name}",
                        arg_name="request",
                        arg_description=f"The full task or follow-up for {registration.name}.",
                    )
                )

            coordinator = Agent(
                name="Orchestrator",
                description="Coordinator that routes tasks and combines specialist results",
                client=self._get_model_client(),
                instructions=self._build_orchestrator_instructions(),
                tools=specialist_tools,
                default_options=get_default_agent_options(),
            )
            if include_legacy_memory:
                self._coordinator = coordinator
            else:
                self._api_coordinator = coordinator
        return coordinator

    def _build_contextualized_task(
        self,
        task: str,
        session_id: Optional[str] = None,
        *,
        include_legacy_memory: bool = True,
    ) -> str:
        sid = session_id or self._active_session_id
        if not include_legacy_memory:
            return (
                "Continue the scoped conversation using only the supplied "
                "session state. Do not read or write legacy global memory.\n\n"
                "CURRENT USER MESSAGE\n"
                f"{task}"
            )
        memory_summary = self._memory_store.build_memory_summary(limit=12)
        recent_turns = self._memory_store.render_recent_turns(
            sid, limit=6,
        )
        return (
            "Continue an ongoing conversation with the same human user.\n"
            "Use the durable memory and recent conversation context when relevant.\n"
            "Avoid asking for identity or preference details that are already known.\n\n"
            "DURABLE MEMORY\n"
            f"{memory_summary}\n\n"
            "RECENT SESSION CONTEXT\n"
            f"{recent_turns}\n\n"
            "CURRENT USER MESSAGE\n"
            f"{task}"
        )

    def register_agent(
        self,
        name: str,
        system_message: str,
        description: str = "",
        tools: Optional[list] = None,
        handoff_agents: Optional[list[str]] = None,
        model_profile: Optional[str] = None,
        require_critique: bool = False,
    ) -> AgentRegistration:
        """
        Register a subagent with the orchestrator.

        Args:
            name: Unique agent name
            system_message: The agent's system prompt
            description: Short routing description
            tools: List of callable tools the agent can use
            handoff_agents: Other agents this agent can call
            model_profile: Optional routing profile override (PR3). When None,
                the catalog ``policy`` map (keyed by ``name``) decides, falling
                back to the legacy shared client.
        """
        registration = AgentRegistration(
            name=name,
            system_message=system_message,
            description=description or f"Agent: {name}",
            tools=tools or [],
            handoff_agents=handoff_agents or [],
            model_profile=model_profile,
            require_critique=require_critique,
        )
        self._registrations[name] = registration
        self._agents.pop(name, None)
        self._coordinator = None
        self._api_coordinator = None

        logger.info(
            "Registered agent: %s (tools: %d, handoffs: %d)",
            name, len(tools or []), len(handoff_agents or []),
        )
        log_action("Orchestrator", "register_agent", f"Registered {name}")
        return registration

    def get_agent(self, name: str) -> Optional[Agent]:
        return self._get_or_create_agent(name)

    @property
    def agent_names(self) -> list[str]:
        return list(self._registrations.keys())

    async def route_task(
        self,
        task: str,
        *,
        session_state: Optional["SessionState"] = None,
        context: Any = None,
    ) -> str:
        """Route a task and return the final response text.

        ``session_state`` isolates conversation/case state per caller. When it is
        ``None`` the backward-compatible LOCAL state is used (CLI / dashboard),
        which is NEVER shared with API requests. ``context`` is an optional
        :class:`agentsystem.context.RunContext` used only for telemetry
        correlation.
        """
        result = await self.run_turn(
            task, session_state=session_state, context=context
        )
        return result.text

    async def run_turn(
        self,
        task: str,
        *,
        session_state: Optional["SessionState"] = None,
        context: Any = None,
    ) -> "TurnResult":
        """Execute one turn and return structured attribution.

        This is the durable-run entry point: the run service calls it with an
        explicit, isolated :class:`SessionState` per run so no orchestration
        state is shared across users.
        """
        state = session_state or self._local_session_state
        if not self._registrations:
            return TurnResult(text="No agents registered. Please register agents first.")

        async with get_tracer().span(
            "agent.route_task",
            kind="route",
            attributes={
                "task.length": len(task),
                "agents.registered": len(self._registrations),
                "session.id": state.session_id,
            },
        ) as span:
            if context is not None:
                try:
                    for key, value in context.as_log_fields().items():
                        span.set_attribute(f"ctx.{key}", value)
                except Exception:  # pragma: no cover - telemetry must not break routing
                    pass
            log_action("Orchestrator", "route_task", task[:200], status="started")
            self._annotate_routing(span)
            is_api_request = context is not None
            coordinator = self._get_or_create_coordinator(
                include_legacy_memory=not is_api_request
            )
            contextualized_task = self._build_contextualized_task(
                task,
                session_id=state.session_id,
                include_legacy_memory=not is_api_request,
            )

            # ── Attempt 1 ──
            try:
                result = await coordinator.run(
                    contextualized_task,
                    session=state.conversation_session,
                )
            except Exception as exc:
                exc_name = type(exc).__name__
                if "ContentFilter" in exc_name or "content_filter" in str(exc):
                    logger.warning("Content filter tripped on coordinator call — resetting session and retrying")
                    span.add_event("content_filter.retry", {"stage": "coordinator"})
                    # Auto-reset THIS state to clear conversation history that may trigger filter
                    self._reset_state(state)
                    # Retry with clean session + simpler prompt
                    try:
                        safe_task = (
                            "The user wants to publish a social media post. "
                            "Use the most appropriate specialist to handle this. "
                            "Do not mention tools or agent names in your response. "
                            "Keep it brief and professional.\n\n"
                            f"User request: {task}"
                        )
                        result = await coordinator.run(safe_task, session=state.conversation_session)
                    except Exception as retry_exc:
                        logger.error("Retry also failed: %s", retry_exc)
                        span.set_attribute("route.outcome", "content_filter_blocked")
                        return TurnResult(text=(
                            "⚠️  Azure OpenAI's content filter is blocking this request "
                            "(jailbreak filter false positive).\n\n"
                            "Fix: Configure a custom content filter in Azure AI Foundry:\n"
                            "  1. Go to https://ai.azure.com → Content Filters\n"
                            "  2. Create filter with 'jailbreak' severity set to 'low' or 'off'\n"
                            "  3. Assign it to deployment 'gpt-5.4-mini'\n\n"
                            "Temporary workaround: Type `reset` and try with simpler phrasing."
                        ))
                else:
                    raise

            final_response = getattr(result, "text", "")
            if not final_response:
                messages = getattr(result, "messages", [])
                if messages:
                    final_response = getattr(messages[-1], "text", "") or str(messages[-1])

            # Detect content filter failures in subagent calls + auto-recover
            if final_response and (
                "content_filter" in final_response.lower()
                or "Function failed" in final_response
                or "jailbreak" in final_response.lower()
            ):
                logger.warning("Subagent content filter detected — resetting and retrying once")
                span.add_event("content_filter.retry", {"stage": "subagent"})
                self._reset_state(state)
                try:
                    safe_task = (
                        "The user has a simple request. Handle it directly and professionally. "
                        "Do not mention internal tool names or agent names.\n\n"
                        f"User: {task}"
                    )
                    result = await coordinator.run(safe_task, session=state.conversation_session)
                    final_response = getattr(result, "text", "")
                    # Don't flag again on retry — just return whatever we got
                except Exception:
                    final_response = (
                        "⚠️  Content filter persists after session reset. "
                        "Configure a custom content filter in Azure AI Foundry "
                        "with jailbreak severity = low/off for deployment 'gpt-5.4-mini'.\n\n"
                        "Workaround: Type `reset`, then try your request with different wording."
                    )

            # Real agent attribution: parse specialist tool calls from the result.
            agents_used = self._extract_agents_used(result)
            usage = self._extract_usage(result)

            # Opt-out self-review: on high-stakes tasks, run a rubber-duck pass
            # and annotate (never re-run) the draft when it surfaces real issues.
            final_response = await self._maybe_auto_critique(task, final_response, span)

            # ── Enforcement pipeline (Phase 1) ──────────────────────────
            # Classify domain → verify grounding → audit completion.
            # Non-blocking by default: annotates issues, never blocks.
            final_response = await self._run_enforcement_pipeline(
                task, final_response, span
            )

            self._memory_store.save_turn(state.session_id, "user", task)
            if final_response:
                self._memory_store.save_turn(state.session_id, "assistant", final_response)

            log_action("Orchestrator", "route_task", task[:200], final_response[:500], status="completed")
            span.set_attribute("response.length", len(final_response or ""))
            if agents_used:
                span.set_attribute("agents.used", ",".join(agents_used))
            return TurnResult(
                text=final_response or "Task completed but no response was generated.",
                agents_used=agents_used,
                selected_agent=agents_used[0] if agents_used else None,
                prompt_tokens=usage[0],
                completion_tokens=usage[1],
            )

    def _reset_state(self, state: "SessionState") -> None:
        """Start a fresh conversation for one session state (isolated)."""
        new_id = self._memory_store.start_new_session()
        state.session_id = new_id
        state.conversation_session = AgentSession(session_id=new_id)

    def _extract_agents_used(self, result: Any) -> list[str]:
        """Best-effort: which registered specialists the coordinator invoked.

        Parses tool/function-call names off the result messages and maps them to
        registered agent names (direct tool name or ``call_<agent>`` handoff).
        Never raises — attribution is a nicety, not a correctness gate.
        """
        registered = set(self._registrations.keys())
        used: list[str] = []
        try:
            messages = getattr(result, "messages", None) or []
            for message in messages:
                for call_name in self._iter_tool_call_names(message):
                    name = call_name
                    if name.startswith("call_"):
                        name = name[len("call_"):]
                    if name in registered and name not in used:
                        used.append(name)
        except Exception:  # pragma: no cover - defensive
            return used
        return used

    @staticmethod
    def _iter_tool_call_names(message: Any):
        """Yield function/tool-call names from a message, tolerating AF shapes."""
        # Common shapes: message.tool_calls[*].name, or content items with a
        # ``name``/``function`` attribute for function calls.
        for attr in ("tool_calls", "function_calls"):
            calls = getattr(message, attr, None)
            if calls:
                for call in calls:
                    name = getattr(call, "name", None) or getattr(
                        getattr(call, "function", None), "name", None
                    )
                    if name:
                        yield str(name)
        contents = getattr(message, "contents", None) or getattr(
            message, "content", None
        )
        if isinstance(contents, (list, tuple)):
            for item in contents:
                name = getattr(item, "name", None)
                if name and getattr(item, "type", "") in (
                    "function_call",
                    "tool_call",
                ):
                    yield str(name)

    @staticmethod
    def _extract_usage(result: Any) -> tuple[int, int]:
        """Best-effort (prompt_tokens, completion_tokens) from an AF result."""
        try:
            usage = getattr(result, "usage", None) or getattr(
                result, "usage_details", None
            )
            if usage is not None:
                prompt = int(
                    getattr(usage, "input_token_count", 0)
                    or getattr(usage, "prompt_tokens", 0)
                    or 0
                )
                completion = int(
                    getattr(usage, "output_token_count", 0)
                    or getattr(usage, "completion_tokens", 0)
                    or 0
                )
                return prompt, completion
        except Exception:  # pragma: no cover - defensive
            pass
        return 0, 0

    async def handle_user_input(self, user_input: str) -> str:
        logger.info(f"User input: {user_input[:100]}...")
        return await self.route_task(user_input)

    async def _maybe_auto_critique(self, task: str, final_response: str, span: Any = None) -> str:
        """Annotate-only self-review for high-stakes drafts.

        Runs the existing ``critique_response`` tool against our own draft. If it
        finds material issues, append a short "Self-review" note so the user sees
        the caveat. NEVER re-runs the coordinator and NEVER raises — any failure
        (no creds, timeout, parse error) degrades silently to the original draft.
        """
        import asyncio

        from tools.critique import (
            auto_critique_mode,
            critique_response,
            has_material_findings,
            should_auto_critique,
        )

        if not final_response or not should_auto_critique(task, final_response):
            return final_response
        if auto_critique_mode() != "annotate":
            return final_response

        try:
            critique_text = await asyncio.wait_for(
                critique_response(task, final_response, severity="important"),
                timeout=float(os.getenv("AUTO_CRITIQUE_TIMEOUT", "30")),
            )
        except Exception as exc:  # noqa: BLE001
            logger.info("Auto-critique skipped (%s)", type(exc).__name__)
            if span is not None:
                span.add_event("auto_critique.skipped", {"reason": type(exc).__name__})
            return final_response

        if not has_material_findings(critique_text):
            if span is not None:
                span.add_event("auto_critique.clean")
            return final_response

        if span is not None:
            span.add_event("auto_critique.annotated")
        log_action("Orchestrator", "auto_critique", task[:200], "material findings appended")
        return (
            f"{final_response}\n\n"
            f"---\n"
            f"### 🦆 Self-review (automated)\n"
            f"I ran a rubber-duck pass on the answer above and flagged points worth a look:\n\n"
            f"{critique_text.strip()}"
        )

    def get_memory_summary(self) -> str:
        return self._memory_store.build_memory_summary(limit=50)

    def reset_session(self) -> str:
        self._active_session_id = self._memory_store.start_new_session()
        self._conversation_session = AgentSession(session_id=self._active_session_id)
        log_action("Orchestrator", "reset_session", output_summary=f"session_id={self._active_session_id}")
        return self._active_session_id

    async def _run_enforcement_pipeline(
        self, task: str, final_response: str, span: Any = None
    ) -> str:
        """Run the enforcement pipeline: classify → verify grounding → audit completion.

        Non-blocking by default (ENFORCEMENT_MODE=strict in env to block).
        Annotates the response with enforcement findings. Never raises.

        Skips trivial messages (greetings, < 20 chars, pure social chat).
        """
        import os

        # Skip trivial messages — no grounding needed for greetings/chit-chat
        task_stripped = (task or "").strip()
        if len(task_stripped) < 20 or _is_trivial_chat(task_stripped):
            return final_response

        try:
            from enforcement.domain_classifier import classify_domain
            from enforcement.grounding_check import verify_grounding
            from enforcement.completion_audit import audit_completion

            # Step 1: Classify domain
            classification = classify_domain(task)
            if span:
                span.set_attribute("enforcement.domains", ",".join(classification.domains))
                span.set_attribute("enforcement.high_stakes", classification.is_high_stakes)
                span.set_attribute("enforcement.confidence", classification.confidence)

            # Step 2: Verify grounding
            grounding = verify_grounding(
                final_response,
                required_tools=classification.required_tools,
                domains=classification.domains,
                specialist_name="orchestrator",
            )

            # Step 3: Audit completion
            completion = audit_completion(final_response)

            # Build annotation — only append when ENFORCEMENT_ANNOTATE=true
            # (off by default — keeps UI clean; check logs for enforcement data)
            if os.getenv("ENFORCEMENT_ANNOTATE", "").strip().lower() in ("true", "1", "yes"):
                annotations: list[str] = []
                if grounding.annotation:
                    annotations.append(grounding.annotation)
                if completion.annotation:
                    annotations.append(completion.annotation)
                if annotations:
                    enforcement_note = "\n\n---\n**🔍 Enforcement**\n" + "\n".join(
                        f"- {a}" for a in annotations
                    )
                    final_response = final_response + enforcement_note

            if span:
                span.set_attribute("enforcement.grounding_passed", grounding.passed)
                span.set_attribute("enforcement.completion_passed", completion.completed)
                span.set_attribute("enforcement.evidence_quality", grounding.evidence_quality)

            # Log enforcement findings at INFO level — these are expected
            # annotations, not errors. They surface when an agent answered
            # from memory instead of evidence, which is the pipeline working.
            if not grounding.passed or not completion.completed:
                logger.info(
                    "Enforcement: grounding=%s completion=%s domains=%s",
                    "PASS" if grounding.passed else "FAIL",
                    "PASS" if completion.completed else "FAIL",
                    classification.domains,
                )

        except Exception as exc:  # noqa: BLE001
            logger.warning("Enforcement pipeline degraded: %s", exc)

        return final_response

    def status(self) -> dict[str, Any]:
        return {
            "system": self._system_config.name,
            "approval_required": self._system_config.approval_required,
            "registered_agents": self.agent_names,
            "agent_count": len(self._registrations),
            "model_provider": get_model_config().provider,
            "active_session_id": self._active_session_id,
            "remembered_facts": self._memory_store.count_memories(),
            "routing": self._routing_status(),
        }
