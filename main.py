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

from config import get_system_config
from agents.factory import build_orchestrator
from agents.orchestrator import Orchestrator
from tools.audit import log_action
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
