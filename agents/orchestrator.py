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

from config import get_agent_configs, get_model_config, get_system_config
from tools.audit import log_action
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

logger = logging.getLogger(__name__)

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
)


@dataclass(slots=True)
class AgentRegistration:
    """Lazy registration for a specialist agent."""

    name: str
    system_message: str
    description: str = ""
    tools: list[Any] = field(default_factory=list)
    handoff_agents: list[str] = field(default_factory=list)  # Agents this agent can call


def create_model_client() -> OpenAIChatCompletionClient:
    model_cfg = get_model_config()
    model_name = model_cfg.resolved_model

    if model_cfg.provider == "azure_openai":
        if not model_cfg.azure_endpoint or not model_cfg.azure_api_key:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in .env"
            )
        return OpenAIChatCompletionClient(
            model=model_name,
            azure_endpoint=model_cfg.azure_endpoint,
            api_key=model_cfg.azure_api_key,
            api_version=model_cfg.azure_api_version,
        )
    elif model_cfg.provider == "openai":
        if not model_cfg.openai_api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")
        return OpenAIChatCompletionClient(
            model=model_name, api_key=model_cfg.openai_api_key,
        )
    else:
        raise ValueError(f"Unsupported model provider: {model_cfg.provider}")


def get_default_agent_options() -> dict[str, Any]:
    model_cfg = get_model_config()
    options: dict[str, Any] = {
        "max_tokens": model_cfg.max_tokens,
        "allow_multiple_tool_calls": True,  # Enable parallel tool calls for handoff
    }
    if model_cfg.supports_custom_temperature:
        options["temperature"] = model_cfg.temperature
    return options


class Orchestrator:
    """Central orchestrator with inter-agent handoff."""

    def __init__(self):
        self._system_config = get_system_config()
        self._agent_configs = get_agent_configs()
        self._model_client: Optional[OpenAIChatCompletionClient] = None
        self._registrations: dict[str, AgentRegistration] = {}
        self._agents: dict[str, Agent] = {}
        self._coordinator: Optional[Agent] = None
        self._memory_store = MEMORY_STORE
        self._active_session_id = self._memory_store.get_active_session_id()
        self._conversation_session = AgentSession(session_id=self._active_session_id)
        self._creating: set[str] = set()  # Track agents being created to break circular handoffs

    def _get_model_client(self) -> OpenAIChatCompletionClient:
        if self._model_client is None:
            self._model_client = create_model_client()
        return self._model_client

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
                instructions = registration.system_message
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
                    client=self._get_model_client(),
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
            "When the request needs current information, vendor docs, news, or anything not in memory, use `web_search` then `web_fetch` to get the actual page text — do not bluff facts.\n"
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

    def _get_or_create_coordinator(self) -> Agent:
        if self._coordinator is None:
            specialist_tools = (
                list(BROWSE_TOOLS)
                + list(MEMORY_TOOLS)
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

            self._coordinator = Agent(
                name="Orchestrator",
                description="Coordinator that routes tasks and combines specialist results",
                client=self._get_model_client(),
                instructions=self._build_orchestrator_instructions(),
                tools=specialist_tools,
                default_options=get_default_agent_options(),
            )
        return self._coordinator

    def _build_contextualized_task(self, task: str) -> str:
        memory_summary = self._memory_store.build_memory_summary(limit=12)
        recent_turns = self._memory_store.render_recent_turns(
            self._active_session_id, limit=6,
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
    ) -> AgentRegistration:
        """
        Register a subagent with the orchestrator.

        Args:
            name: Unique agent name
            system_message: The agent's system prompt
            description: Short routing description
            tools: List of callable tools the agent can use
            handoff_agents: Other agents this agent can call
        """
        registration = AgentRegistration(
            name=name,
            system_message=system_message,
            description=description or f"Agent: {name}",
            tools=tools or [],
            handoff_agents=handoff_agents or [],
        )
        self._registrations[name] = registration
        self._agents.pop(name, None)
        self._coordinator = None

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

    async def route_task(self, task: str) -> str:
        if not self._registrations:
            return "No agents registered. Please register agents first."

        log_action("Orchestrator", "route_task", task[:200], status="started")
        coordinator = self._get_or_create_coordinator()
        contextualized_task = self._build_contextualized_task(task)
        try:
            result = await coordinator.run(
                contextualized_task,
                session=self._conversation_session,
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            if "ContentFilter" in exc_name or "content_filter" in str(exc):
                logger.warning("Content filter tripped on coordinator call: %s", exc)
                log_action("Orchestrator", "route_task", task[:200], "content_filter", status="blocked")
                return (
                    "⚠️  Azure OpenAI's content filter blocked this turn. This usually means "
                    "one of the items in my memory or conversation history tripped a filter "
                    "category (often a false positive on the 'sexual' category at medium severity).\n\n"
                    "Try one of these:\n"
                    "  • Type `reset` to start a fresh conversation session (keeps durable memory).\n"
                    "  • Type `forget <topic>` to remove a specific memory entry, then retry.\n"
                    "  • If it persists, inspect `memory\\memory.db` — a stored note or email "
                    "    excerpt is likely the trigger."
                )
            raise

        final_response = getattr(result, "text", "")
        if not final_response:
            messages = getattr(result, "messages", [])
            if messages:
                final_response = getattr(messages[-1], "text", "") or str(messages[-1])

        self._memory_store.save_turn(self._active_session_id, "user", task)
        if final_response:
            self._memory_store.save_turn(self._active_session_id, "assistant", final_response)

        log_action("Orchestrator", "route_task", task[:200], final_response[:500], status="completed")
        return final_response or "Task completed but no response was generated."

    async def handle_user_input(self, user_input: str) -> str:
        logger.info(f"User input: {user_input[:100]}...")
        return await self.route_task(user_input)

    def get_memory_summary(self) -> str:
        return self._memory_store.build_memory_summary(limit=50)

    def reset_session(self) -> str:
        self._active_session_id = self._memory_store.start_new_session()
        self._conversation_session = AgentSession(session_id=self._active_session_id)
        log_action("Orchestrator", "reset_session", output_summary=f"session_id={self._active_session_id}")
        return self._active_session_id

    def status(self) -> dict[str, Any]:
        return {
            "system": self._system_config.name,
            "approval_required": self._system_config.approval_required,
            "registered_agents": self.agent_names,
            "agent_count": len(self._registrations),
            "model_provider": get_model_config().provider,
            "active_session_id": self._active_session_id,
            "remembered_facts": self._memory_store.count_memories(),
        }
