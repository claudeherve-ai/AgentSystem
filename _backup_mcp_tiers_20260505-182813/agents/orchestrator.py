"""
AgentSystem — Orchestrator.

The central brain that receives events and routes them to specialized subagents.
Built on Microsoft Agent Framework with a coordinator agent that calls specialist agents as tools.
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from agent_framework import Agent, AgentSession
from agent_framework.openai import OpenAIChatCompletionClient

# Ensure project root is on path
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
from tools.mcp_tools import MCP_DOCS_TOOLS, MCP_GITHUB_TOOLS
from tools.memory_tools import MEMORY_STORE, MEMORY_TOOLS
from tools.plans_tools import PLANS_TOOLS
from tools.project_workspace import PROJECT_WORKSPACE_TOOLS
from tools.rag_tools import RAG_TOOLS
from tools.screen_context import SCREEN_CONTEXT_TOOLS
from tools.web_fetch import WEB_FETCH_TOOLS
from tools.web_search import WEB_SEARCH_TOOLS

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AgentRegistration:
    """Lazy registration for a specialist agent."""

    name: str
    system_message: str
    description: str = ""
    tools: list[Any] = field(default_factory=list)


def create_model_client() -> OpenAIChatCompletionClient:
    """
    Create the LLM client based on configuration.

    Uses Microsoft Agent Framework's OpenAI Chat Completions client so the
    existing Azure OpenAI chat deployment keeps working with minimal churn.
    """
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
            raise ValueError(
                "OpenAI API key not configured. Set OPENAI_API_KEY in .env"
            )
        return OpenAIChatCompletionClient(
            model=model_name,
            api_key=model_cfg.openai_api_key,
        )
    else:
        raise ValueError(f"Unsupported model provider: {model_cfg.provider}")


def get_default_agent_options() -> dict[str, Any]:
    """Build default model options for all Agent Framework agents."""
    model_cfg = get_model_config()
    options: dict[str, Any] = {
        "max_tokens": model_cfg.max_tokens,
        # Keep tool execution serial so console approval prompts do not overlap.
        "allow_multiple_tool_calls": False,
    }

    if model_cfg.supports_custom_temperature:
        options["temperature"] = model_cfg.temperature

    return options


class Orchestrator:
    """
    Central orchestrator that manages subagents and routes tasks.

    Responsibilities:
    - Maintain the agent registry
    - Receive inbound events (email, calendar, user input)
    - Route to the correct specialist agent
    - Let specialist tools enforce approvals and guardrails
    - Log everything for audit
    """

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

    def _get_model_client(self) -> OpenAIChatCompletionClient:
        """Lazy-load the model client."""
        if self._model_client is None:
            self._model_client = create_model_client()
        return self._model_client

    def _get_or_create_agent(self, name: str) -> Optional[Agent]:
        """Create a specialist agent only when it is first needed."""
        registration = self._registrations.get(name)
        if registration is None:
            return None

        if name not in self._agents:
            self._agents[name] = Agent(
                name=registration.name,
                description=registration.description or f"Agent: {registration.name}",
                client=self._get_model_client(),
                instructions=registration.system_message,
                tools=registration.tools,
                default_options=get_default_agent_options(),
            )
        return self._agents[name]

    def _build_orchestrator_instructions(self) -> str:
        """Build coordinator instructions with a routing guide for specialists."""
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
            "When the user points you at a local file or folder (PDF, DOCX, XLSX, JSON, log, code), use `read_file` / `list_dir` / `search_in_file` to inspect it before answering.\n"
            "When the request requires actually computing something, transforming data, or generating output, use `run_python` in the workspace and inspect the actual output before claiming success.\n"
            "When the user asks you to remember a document or web page for later, use `kb_index`; when they ask 'have we seen this before?' or want to recall research, use `kb_search`.\n"
            "When work spans multiple sessions or days, use the project tools (`project_create`, `project_open`, `project_note`, `project_status`) to keep durable state separate from short-term memory.\n"
            "Before sending a high-stakes response (architecture, customer-facing, code merges, financial advice), call `critique_response` on your draft and incorporate critical findings.\n"
            "For ANY question about Microsoft / Azure / .NET / Microsoft 365 / Power Platform / Microsoft Fabric / Microsoft Entra / Databricks-on-Azure, prefer `microsoft_docs_search` (and `microsoft_docs_fetch` for full pages) over generic web search — the Microsoft Docs MCP returns first-party, version-current content. Use `microsoft_code_sample_search` whenever you are about to produce Microsoft / Azure code so it is grounded in official samples.\n"
            "For questions that depend on real GitHub state (existing implementations, upstream issues / PRs, source files, repo discovery), use the GitHub MCP tools (`github_search_repositories`, `github_search_code`, `github_search_issues`, `github_get_file_contents`). They degrade gracefully with a clear setup message when `GITHUB_TOKEN` is not configured — surface that message instead of fabricating content.\n"
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
        """Create the top-level coordinator that calls specialist agents as tools."""
        if self._coordinator is None:
            specialist_tools = (
                list(MEMORY_TOOLS)
                + list(DAILY_BRIEFING_TOOLS)
                + list(END_OF_DAY_TOOLS)
                + list(DRAFT_REPLY_TOOLS)
                # Boil-the-Ocean capability tools — always available to the coordinator
                # so any conversation can search the web, read files, run code, or use
                # the knowledge base without bouncing through a specialist agent first.
                + list(WEB_SEARCH_TOOLS)
                + list(WEB_FETCH_TOOLS)
                + list(FILE_READER_TOOLS)
                + list(CODE_INTERPRETER_TOOLS)
                + list(KNOWLEDGE_BASE_TOOLS)
                + list(PROJECT_WORKSPACE_TOOLS)
                + list(CRITIQUE_TOOLS)
                # MCP-backed grounding tools — first-party Microsoft Learn
                # docs always available; GitHub MCP degrades gracefully when
                # `GITHUB_TOKEN` is not configured.
                + list(MCP_DOCS_TOOLS)
                + list(MCP_GITHUB_TOOLS)
                # RAG over Work_cases\Cases\ — semantic + FTS5 over local
                # case artifacts. Degrades to FTS-only when no embedding
                # deployment is configured (`AZURE_EMBEDDING_DEPLOYMENT`).
                + list(RAG_TOOLS)
                # Durable plan/task store — multi-step plans persisted across
                # restarts, resumable by id, with per-step owner_agent routing.
                + list(PLANS_TOOLS)
                # Screen-context tools — clipboard, active-window title,
                # auto-detected/persisted active case folder. Windows-aware;
                # degrades cleanly on other platforms.
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
        """Attach durable memory and recent conversation context to the task."""
        memory_summary = self._memory_store.build_memory_summary(limit=12)
        recent_turns = self._memory_store.render_recent_turns(
            self._active_session_id,
            limit=6,
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
    ) -> AgentRegistration:
        """
        Register a subagent with the orchestrator.

        Args:
            name: Unique agent name (e.g., "EmailAgent")
            system_message: The agent's system prompt
            description: Short routing description for the coordinator
            tools: List of callable tools the agent can use
        """
        registration = AgentRegistration(
            name=name,
            system_message=system_message,
            description=description or f"Agent: {name}",
            tools=tools or [],
        )
        self._registrations[name] = registration
        self._agents.pop(name, None)
        self._coordinator = None

        logger.info(f"Registered agent: {name} (tools: {len(tools or [])})")
        log_action("Orchestrator", "register_agent", f"Registered {name}")
        return registration

    def get_agent(self, name: str) -> Optional[Agent]:
        """Get a registered specialist agent by name."""
        return self._get_or_create_agent(name)

    @property
    def agent_names(self) -> list[str]:
        """List all registered agent names."""
        return list(self._registrations.keys())

    async def route_task(self, task: str) -> str:
        """
        Route a task to the appropriate subagent(s) using the coordinator agent.
        """
        if not self._registrations:
            return "No agents registered. Please register agents first."

        # Run the coordinator
        log_action("Orchestrator", "route_task", task[:200], status="started")
        coordinator = self._get_or_create_coordinator()
        contextualized_task = self._build_contextualized_task(task)
        try:
            result = await coordinator.run(
                contextualized_task,
                session=self._conversation_session,
            )
        except Exception as exc:  # noqa: BLE001 — we need to classify by name
            exc_name = type(exc).__name__
            if "ContentFilter" in exc_name or "content_filter" in str(exc):
                logger.warning("Content filter tripped on coordinator call: %s", exc)
                log_action(
                    "Orchestrator",
                    "route_task",
                    task[:200],
                    "content_filter",
                    status="blocked",
                )
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

        log_action(
            "Orchestrator",
            "route_task",
            task[:200],
            final_response[:500],
            status="completed",
        )

        return final_response or "Task completed but no response was generated."

    async def handle_user_input(self, user_input: str) -> str:
        """
        Handle a direct user input — the main entry point for interactive use.
        """
        logger.info(f"User input: {user_input[:100]}...")
        return await self.route_task(user_input)

    def get_memory_summary(self) -> str:
        """Return a compact summary of durable user memory."""
        return self._memory_store.build_memory_summary(limit=50)

    def reset_session(self) -> str:
        """Start a new conversational session while keeping durable memory."""
        self._active_session_id = self._memory_store.start_new_session()
        self._conversation_session = AgentSession(session_id=self._active_session_id)
        log_action(
            "Orchestrator",
            "reset_session",
            output_summary=f"session_id={self._active_session_id}",
        )
        return self._active_session_id

    def status(self) -> dict[str, Any]:
        """Return the current system status."""
        return {
            "system": self._system_config.name,
            "approval_required": self._system_config.approval_required,
            "registered_agents": self.agent_names,
            "agent_count": len(self._registrations),
            "model_provider": get_model_config().provider,
            "active_session_id": self._active_session_id,
            "remembered_facts": self._memory_store.count_memories(),
        }
