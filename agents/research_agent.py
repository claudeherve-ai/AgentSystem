"""
ResearchAgent — multi-step web research with citations.

This specialist takes a research question and walks through:
  1. Search the open web (DuckDuckGo).
  2. Fetch the most relevant pages and extract them as readable Markdown.
  3. Synthesize a grounded answer with inline citations to source URLs.
  4. Optionally critique its own draft before returning.

The agent uses real web tools — every claim must be backed by a fetched source.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.audit import log_action  # noqa: E402
from tools.critique import CRITIQUE_TOOLS  # noqa: E402
from tools.knowledge_base import KNOWLEDGE_BASE_TOOLS  # noqa: E402
from tools.mcp_tools import (  # noqa: E402
    MCP_CONTEXT7_TOOLS,
    MCP_DEEPWIKI_TOOLS,
    MCP_DOCS_TOOLS,
    MCP_GITHUB_TOOLS,
    MCP_HUGGINGFACE_TOOLS,
    MCP_SEQUENTIAL_THINKING_TOOLS,
)
from tools.rag_tools import RAG_TOOLS  # noqa: E402
from tools.web_fetch import WEB_FETCH_TOOLS  # noqa: E402
from tools.web_search import WEB_SEARCH_TOOLS  # noqa: E402

logger = logging.getLogger(__name__)


RESEARCH_AGENT_NAME = "ResearchAgent"
RESEARCH_AGENT_DESCRIPTION = (
    "Performs multi-step web research with citations: search → fetch → synthesize. "
    "Use for questions that require current information, vendor docs, news, "
    "competitive analysis, or anything where 'check the web' is the right answer."
)

RESEARCH_AGENT_INSTRUCTIONS = (
    "You are a senior research analyst. Your job is to answer questions with grounded, "
    "cited research.\n\n"
    "WORKFLOW:\n"
    "1. SOURCE SELECTION:\n"
    "   - For Microsoft / Azure / .NET / Microsoft 365 / Power Platform / Microsoft Fabric / "
    "Microsoft Entra / Databricks-on-Azure topics, START with `microsoft_docs_search` and "
    "fall back to `web_search` only if MCP returns nothing useful.\n"
    "   - For questions about real GitHub repos, source files, issues, or PRs, use the "
    "GitHub MCP tools (`github_search_repositories`, `github_search_code`, `github_search_issues`, "
    "`github_get_file_contents`). When `GITHUB_TOKEN` is missing they return a setup message — "
    "surface that message rather than guessing.\n"
    "   - For everything else, use `web_search` to find candidate sources. Pick the most relevant 2-5.\n"
    "2. Read each source in full: `microsoft_docs_fetch` for Microsoft Learn URLs, `web_fetch` "
    "for everything else, `github_get_file_contents` for repo files. Do NOT cite a source you have not fetched.\n"
    "3. Synthesize a concise answer with inline citations like [1], [2], etc.\n"
    "4. End with a 'Sources' section listing every URL you actually used.\n"
    "5. If the user asked you to remember the result, also call `kb_index` to add it to the KB.\n"
    "6. For high-stakes questions (architecture, financial, customer-facing), call "
    "`critique_response` on your draft before returning.\n\n"
    "RULES:\n"
    "- Never fabricate facts, statistics, or quotes. If a claim cannot be backed by a fetched\n"
    "  source, drop it or label it as inference.\n"
    "- If search returns nothing useful, say so plainly. Do not bluff.\n"
    "- Prefer first-party sources (Microsoft Learn via MCP, vendor docs, RFCs, official blogs) over aggregators.\n"
    "- Keep answers tight. Long enough to be useful, short enough to be read."
)


RESEARCH_AGENT_TOOLS = (
    list(WEB_SEARCH_TOOLS)
    + list(WEB_FETCH_TOOLS)
    + list(KNOWLEDGE_BASE_TOOLS)
    + list(CRITIQUE_TOOLS)
    + list(MCP_DOCS_TOOLS)
    + list(MCP_GITHUB_TOOLS)
    + list(MCP_DEEPWIKI_TOOLS)
    + list(MCP_CONTEXT7_TOOLS)
    + list(MCP_HUGGINGFACE_TOOLS)
    + list(MCP_SEQUENTIAL_THINKING_TOOLS)
    + list(RAG_TOOLS)
)


log_action(
    agent_name=RESEARCH_AGENT_NAME,
    action="module_loaded",
    output_summary=f"{len(RESEARCH_AGENT_TOOLS)} tools available",
)
