"""
MCP-backed function tools for AgentSystem — 3-tier "boil-the-ocean" expansion.

Exposes named async tools backed by Model Context Protocol servers so the
orchestrator and specialists can ground answers in vendor-authoritative
sources without bouncing through generic web search or guessing.

15 MCP servers across 3 tiers (12 new on top of the original 2):

  Existing (Streamable-HTTP, in `tools/mcp_client.py`):
    1. Microsoft Docs MCP   (always on, no auth)         — 3 tools
    2. GitHub MCP           (opt-in via GITHUB_TOKEN)    — 4 tools

  Tier 1 — HTTP-based, key-free, ALWAYS-ON:
    3. DeepWiki MCP        — 2 tools (semantic search across indexed GitHub repos)
    4. Context7 MCP        — 2 tools (latest official docs for any library)
    5. Hugging Face MCP    — 3 tools (model / dataset / paper search)

  Tier 2 — HTTP-based, opt-in via env (graceful when unconfigured):
    6. Notion MCP          — 2 tools (workspace search + database query)
    7. Sentry MCP          — 2 tools (issue list + issue details)
    8. Atlassian MCP       — 2 tools (Jira/Confluence search)

  Tier 3 — STDIO via npx/uvx (auto-disabled when binary missing or env not set):
    9.  Filesystem MCP             — 1 tool (`@modelcontextprotocol/server-filesystem`)
    10. Sequential Thinking MCP    — 1 tool (`@modelcontextprotocol/server-sequential-thinking`)
    11. Memory Graph MCP           — 2 tools (`@modelcontextprotocol/server-memory`)
    12. Git MCP                    — 1 tool (`mcp-server-git` via uvx)
    13. SQLite MCP                 — 1 tool (`mcp-server-sqlite` via uvx)
    14. Time MCP                   — 1 tool (`mcp-server-time` via uvx)
    15. Fetch MCP                  — 1 tool (`mcp-server-fetch` via uvx)

Style: same as the rest of the `tools/` package — plain async functions
with `Annotated[..., Field(...)]` parameters, audit-logged via the
underlying clients, never raise.  Each tool returns a clear actionable
"<X is not configured>" string when its transport isn't available, so the
agent never sees an exception.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Optional

from pydantic import Field

from .mcp_client import call_mcp_tool
from .mcp_stdio_client import call_stdio_mcp_tool, is_command_available

logger = logging.getLogger(__name__)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _env(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip() or default


def _flag_enabled(name: str, *, default_when_token_present: bool = False, token: Optional[str] = None) -> bool:
    """
    Three-state env flag: `auto` (default) | `true` / `1` | `false` / `0`.

    `auto` returns `default_when_token_present` if a token is supplied,
    otherwise False.  This matches the existing GitHub MCP pattern.
    """
    flag = (os.getenv(name) or "auto").strip().lower()
    if flag in ("false", "0", "off", "disabled", "no"):
        return False
    if flag in ("true", "1", "on", "enabled", "yes"):
        return True
    return default_when_token_present and bool(token)


def _missing_msg(server: str, install_hint: str) -> str:
    return f"MCP `{server}` is not configured. {install_hint}"


# ── Existing: Microsoft Docs MCP (HTTP, public, always on) ─────────────────

_DOCS_URL = _env("MCP_DOCS_URL", "https://learn.microsoft.com/api/mcp")


async def microsoft_docs_search(
    query: Annotated[
        str,
        Field(
            description=(
                "Free-text query, phrased as a developer or architect would search "
                "Microsoft Learn (e.g., 'AKS private cluster DNS resolution', "
                "'Azure Databricks Unity Catalog metastore', "
                "'Microsoft Entra Conditional Access named locations')."
            )
        ),
    ],
) -> str:
    """
    Search official Microsoft Learn documentation via Microsoft Docs MCP.

    Use this for grounded, vendor-accurate answers about Azure, Microsoft 365,
    .NET, Power Platform, Windows, Microsoft Fabric, Microsoft Entra,
    Azure DevOps, GitHub Enterprise, and Databricks-on-Azure.
    """
    return await call_mcp_tool(
        server_name="microsoft-docs",
        server_url=_DOCS_URL,
        tool_name="microsoft_docs_search",
        arguments={"query": query},
    )


async def microsoft_docs_fetch(
    url: Annotated[
        str,
        Field(
            description=(
                "Full URL of a Microsoft Learn (`learn.microsoft.com`) article to "
                "fetch in Markdown form. Use the URLs returned by "
                "`microsoft_docs_search`."
            )
        ),
    ],
) -> str:
    """Fetch a Microsoft Learn article and return its full content as Markdown."""
    return await call_mcp_tool(
        server_name="microsoft-docs",
        server_url=_DOCS_URL,
        tool_name="microsoft_docs_fetch",
        arguments={"url": url},
    )


async def microsoft_code_sample_search(
    query: Annotated[
        str,
        Field(
            description=(
                "Code-oriented descriptive query, SDK / class / method name, or "
                "scenario for which you want an official Microsoft sample."
            )
        ),
    ],
    language: Annotated[
        str,
        Field(
            description=(
                "Optional language filter — one of: csharp, javascript, "
                "typescript, python, powershell, azurecli, java, sql, kusto, "
                "cpp, go, rust, ruby, php, al."
            )
        ),
    ] = "",
) -> str:
    """Find official Microsoft / Azure code samples via Microsoft Docs MCP."""
    args: dict[str, str] = {"query": query}
    if language:
        args["language"] = language
    return await call_mcp_tool(
        server_name="microsoft-docs",
        server_url=_DOCS_URL,
        tool_name="microsoft_code_sample_search",
        arguments=args,
    )


# ── Existing: GitHub MCP (HTTP, opt-in via GITHUB_TOKEN) ───────────────────

_GITHUB_URL = _env("MCP_GITHUB_URL", "https://api.githubcopilot.com/mcp/")


def _github_token() -> Optional[str]:
    raw = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
    return raw.strip() if raw else None


def _github_enabled() -> bool:
    return _flag_enabled(
        "MCP_GITHUB_ENABLED",
        default_when_token_present=True,
        token=_github_token(),
    )


def _github_headers() -> Optional[dict[str, str]]:
    token = _github_token()
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
    }


_GITHUB_DISABLED_MSG = _missing_msg(
    "GitHub",
    "Set `GITHUB_TOKEN` (or `GITHUB_PAT`) in `.env` with at least `repo` "
    "and `read:org` scopes to enable repository, code, issue, and PR search.",
)


async def github_search_repositories(
    query: Annotated[
        str,
        Field(description="GitHub repository search query — supports `topic:`, `language:`, `stars:>N`, `org:`, `user:`."),
    ],
) -> str:
    """Search public and accessible GitHub repositories via GitHub MCP."""
    if not _github_enabled():
        return _GITHUB_DISABLED_MSG
    return await call_mcp_tool(
        server_name="github",
        server_url=_GITHUB_URL,
        tool_name="search_repositories",
        arguments={"query": query},
        headers=_github_headers(),
    )


async def github_search_code(
    query: Annotated[
        str,
        Field(description="GitHub code search query — supports `repo:`, `language:`, `path:`, `extension:`, and free-text."),
    ],
) -> str:
    """Search code across all of GitHub via GitHub MCP."""
    if not _github_enabled():
        return _GITHUB_DISABLED_MSG
    return await call_mcp_tool(
        server_name="github",
        server_url=_GITHUB_URL,
        tool_name="search_code",
        arguments={"query": query},
        headers=_github_headers(),
    )


async def github_search_issues(
    query: Annotated[
        str,
        Field(description="GitHub issues / PR search query — supports `is:issue`, `is:pr`, `repo:`, `state:open`, `author:`, `label:`."),
    ],
) -> str:
    """Search GitHub issues and pull requests via GitHub MCP."""
    if not _github_enabled():
        return _GITHUB_DISABLED_MSG
    return await call_mcp_tool(
        server_name="github",
        server_url=_GITHUB_URL,
        tool_name="search_issues",
        arguments={"query": query},
        headers=_github_headers(),
    )


async def github_get_file_contents(
    owner: Annotated[str, Field(description="GitHub repository owner (user or org), e.g., 'microsoft'.")],
    repo: Annotated[str, Field(description="GitHub repository name, e.g., 'agent-framework'.")],
    path: Annotated[
        str,
        Field(description="Path to a file inside the repo, or '/' to list the repository root."),
    ] = "/",
    ref: Annotated[
        str,
        Field(description="Optional Git ref — branch, tag, or commit SHA. Empty for default branch."),
    ] = "",
) -> str:
    """Fetch a file (or directory listing) from a GitHub repository via GitHub MCP."""
    if not _github_enabled():
        return _GITHUB_DISABLED_MSG
    arguments: dict[str, str] = {"owner": owner, "repo": repo, "path": path or "/"}
    if ref:
        arguments["ref"] = ref
    return await call_mcp_tool(
        server_name="github",
        server_url=_GITHUB_URL,
        tool_name="get_file_contents",
        arguments=arguments,
        headers=_github_headers(),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  TIER 1 — HTTP, key-free, always-on
# ─────────────────────────────────────────────────────────────────────────────

# T1a: DeepWiki MCP (Cognition AI, public, no auth)
_DEEPWIKI_URL = _env("DEEPWIKI_MCP_URL", "https://mcp.deepwiki.com/mcp")


def _deepwiki_enabled() -> bool:
    return _flag_enabled("DEEPWIKI_MCP_ENABLED", default_when_token_present=True, token="auto")


_DEEPWIKI_DISABLED_MSG = _missing_msg(
    "DeepWiki",
    "Set `DEEPWIKI_MCP_ENABLED=true` in `.env` to activate. No API key required.",
)


async def deepwiki_ask_question(
    repository: Annotated[
        str,
        Field(description="GitHub repository in `owner/name` form, e.g. 'microsoft/agent-framework'."),
    ],
    question: Annotated[
        str,
        Field(description="Natural-language question to ask the indexed repository's docs and code."),
    ],
) -> str:
    """
    Ask a free-form question against a GitHub repository's deep-indexed wiki
    via DeepWiki MCP.  Best for "how does X work in repo Y?" investigations
    where the answer lives across multiple files / READMEs.
    """
    if not _deepwiki_enabled():
        return _DEEPWIKI_DISABLED_MSG
    return await call_mcp_tool(
        server_name="deepwiki",
        server_url=_DEEPWIKI_URL,
        tool_name="ask_question",
        arguments={"repoName": repository, "question": question},
    )


async def deepwiki_read_wiki_structure(
    repository: Annotated[
        str,
        Field(description="GitHub repository in `owner/name` form."),
    ],
) -> str:
    """
    Return the indexed wiki/page structure for a GitHub repository so you
    can pick a page to drill into via `deepwiki_ask_question`.
    """
    if not _deepwiki_enabled():
        return _DEEPWIKI_DISABLED_MSG
    return await call_mcp_tool(
        server_name="deepwiki",
        server_url=_DEEPWIKI_URL,
        tool_name="read_wiki_structure",
        arguments={"repoName": repository},
    )


# T1b: Context7 MCP (Upstash, public, no auth)
_CONTEXT7_URL = _env("CONTEXT7_MCP_URL", "https://mcp.context7.com/mcp")


def _context7_enabled() -> bool:
    return _flag_enabled("CONTEXT7_MCP_ENABLED", default_when_token_present=True, token="auto")


_CONTEXT7_DISABLED_MSG = _missing_msg(
    "Context7",
    "Set `CONTEXT7_MCP_ENABLED=true` in `.env` to activate. No API key required.",
)


async def context7_resolve_library(
    library_name: Annotated[
        str,
        Field(description="Official library name, e.g. 'Next.js', 'React', 'Azure SDK for Python'."),
    ],
    query: Annotated[
        str,
        Field(description="What you want to learn — used to rank library matches by relevance."),
    ],
) -> str:
    """
    Resolve a library name to a Context7-compatible library ID (format
    `/org/project`).  Always call this first, then use the returned ID
    with `context7_get_library_docs`.
    """
    if not _context7_enabled():
        return _CONTEXT7_DISABLED_MSG
    return await call_mcp_tool(
        server_name="context7",
        server_url=_CONTEXT7_URL,
        tool_name="resolve-library-id",
        arguments={"libraryName": library_name, "query": query},
    )


async def context7_get_library_docs(
    library_id: Annotated[
        str,
        Field(description="Context7 library ID from `context7_resolve_library`, e.g. '/vercel/next.js' or '/microsoft/typescript'."),
    ],
    query: Annotated[
        str,
        Field(description="Specific question or topic, e.g. 'How to set up authentication with JWT'."),
    ],
) -> str:
    """
    Fetch the latest official documentation snippets for a library via
    Context7 MCP.  Returns version-current docs and code samples — much
    more accurate than relying on training data for fast-moving libraries.
    """
    if not _context7_enabled():
        return _CONTEXT7_DISABLED_MSG
    return await call_mcp_tool(
        server_name="context7",
        server_url=_CONTEXT7_URL,
        tool_name="get-library-docs",
        arguments={"context7CompatibleLibraryID": library_id, "topic": query},
    )


# T1c: Hugging Face MCP (public, no auth required for catalog search)
_HF_URL = _env("HUGGINGFACE_MCP_URL", "https://huggingface.co/mcp")


def _hf_enabled() -> bool:
    return _flag_enabled("HUGGINGFACE_MCP_ENABLED", default_when_token_present=True, token="auto")


def _hf_headers() -> Optional[dict[str, str]]:
    token = os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


_HF_DISABLED_MSG = _missing_msg(
    "Hugging Face",
    "Set `HUGGINGFACE_MCP_ENABLED=true` in `.env`. Optional: `HUGGINGFACE_TOKEN` for higher rate limits.",
)


async def huggingface_model_search(
    query: Annotated[
        str,
        Field(description="Search query for the Hugging Face model hub, e.g. 'llama 3 8b instruct gguf'."),
    ],
) -> str:
    """Search the Hugging Face model hub for matching models."""
    if not _hf_enabled():
        return _HF_DISABLED_MSG
    return await call_mcp_tool(
        server_name="huggingface",
        server_url=_HF_URL,
        tool_name="hf_model_search",
        arguments={"query": query},
        headers=_hf_headers(),
    )


async def huggingface_dataset_search(
    query: Annotated[
        str,
        Field(description="Search query for the Hugging Face datasets hub."),
    ],
) -> str:
    """Search the Hugging Face datasets hub for matching datasets."""
    if not _hf_enabled():
        return _HF_DISABLED_MSG
    return await call_mcp_tool(
        server_name="huggingface",
        server_url=_HF_URL,
        tool_name="hf_dataset_search",
        arguments={"query": query},
        headers=_hf_headers(),
    )


async def huggingface_paper_search(
    query: Annotated[
        str,
        Field(description="Search query for Hugging Face Papers (curated daily ML papers)."),
    ],
) -> str:
    """Search Hugging Face Papers — useful for finding recent AI/ML research."""
    if not _hf_enabled():
        return _HF_DISABLED_MSG
    return await call_mcp_tool(
        server_name="huggingface",
        server_url=_HF_URL,
        tool_name="hf_paper_search",
        arguments={"query": query},
        headers=_hf_headers(),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  TIER 2 — HTTP, opt-in via env (graceful when unconfigured)
# ─────────────────────────────────────────────────────────────────────────────

# T2a: Notion MCP
_NOTION_URL = _env("NOTION_MCP_URL", "https://mcp.notion.com/mcp")


def _notion_token() -> Optional[str]:
    return os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY")


def _notion_enabled() -> bool:
    return _flag_enabled("NOTION_MCP_ENABLED", default_when_token_present=True, token=_notion_token())


def _notion_headers() -> Optional[dict[str, str]]:
    token = _notion_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


_NOTION_DISABLED_MSG = _missing_msg(
    "Notion",
    "Set `NOTION_TOKEN` in `.env` (Notion integration secret) to enable workspace search.",
)


async def notion_search(
    query: Annotated[
        str,
        Field(description="Natural-language search across the user's Notion workspace."),
    ],
) -> str:
    """Search pages and databases in the user's Notion workspace via Notion MCP."""
    if not _notion_enabled():
        return _NOTION_DISABLED_MSG
    return await call_mcp_tool(
        server_name="notion",
        server_url=_NOTION_URL,
        tool_name="search",
        arguments={"query": query},
        headers=_notion_headers(),
    )


async def notion_fetch_page(
    page_id: Annotated[
        str,
        Field(description="Notion page ID (UUID) or full Notion URL."),
    ],
) -> str:
    """Fetch the full content of a Notion page by ID via Notion MCP."""
    if not _notion_enabled():
        return _NOTION_DISABLED_MSG
    return await call_mcp_tool(
        server_name="notion",
        server_url=_NOTION_URL,
        tool_name="fetch",
        arguments={"id": page_id},
        headers=_notion_headers(),
    )


# T2b: Sentry MCP
_SENTRY_URL = _env("SENTRY_MCP_URL", "https://mcp.sentry.dev/mcp")


def _sentry_token() -> Optional[str]:
    return os.getenv("SENTRY_AUTH_TOKEN") or os.getenv("SENTRY_TOKEN")


def _sentry_enabled() -> bool:
    return _flag_enabled("SENTRY_MCP_ENABLED", default_when_token_present=True, token=_sentry_token())


def _sentry_headers() -> Optional[dict[str, str]]:
    token = _sentry_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


_SENTRY_DISABLED_MSG = _missing_msg(
    "Sentry",
    "Set `SENTRY_AUTH_TOKEN` in `.env` (User Auth Token from Sentry) to enable error monitoring queries.",
)


async def sentry_find_issues(
    query: Annotated[
        str,
        Field(description="Sentry issue search query, e.g. 'is:unresolved level:error project:backend'."),
    ],
    organization_slug: Annotated[
        str,
        Field(description="Sentry organization slug. If empty, uses SENTRY_ORG env var."),
    ] = "",
) -> str:
    """Search recent Sentry issues via Sentry MCP."""
    if not _sentry_enabled():
        return _SENTRY_DISABLED_MSG
    org = organization_slug or _env("SENTRY_ORG")
    args: dict[str, str] = {"query": query}
    if org:
        args["organizationSlug"] = org
    return await call_mcp_tool(
        server_name="sentry",
        server_url=_SENTRY_URL,
        tool_name="find_issues",
        arguments=args,
        headers=_sentry_headers(),
    )


async def sentry_get_issue_details(
    issue_id: Annotated[
        str,
        Field(description="Sentry issue ID or short ID."),
    ],
    organization_slug: Annotated[
        str,
        Field(description="Sentry organization slug. If empty, uses SENTRY_ORG env var."),
    ] = "",
) -> str:
    """Get full details (events, stack traces, breadcrumbs) for a Sentry issue."""
    if not _sentry_enabled():
        return _SENTRY_DISABLED_MSG
    org = organization_slug or _env("SENTRY_ORG")
    args: dict[str, str] = {"issueId": issue_id}
    if org:
        args["organizationSlug"] = org
    return await call_mcp_tool(
        server_name="sentry",
        server_url=_SENTRY_URL,
        tool_name="get_issue_details",
        arguments=args,
        headers=_sentry_headers(),
    )


# T2c: Atlassian MCP (Jira + Confluence)
_ATLASSIAN_URL = _env("ATLASSIAN_MCP_URL", "https://mcp.atlassian.com/v1/sse")


def _atlassian_token() -> Optional[str]:
    return os.getenv("ATLASSIAN_TOKEN") or os.getenv("JIRA_TOKEN")


def _atlassian_enabled() -> bool:
    return _flag_enabled("ATLASSIAN_MCP_ENABLED", default_when_token_present=True, token=_atlassian_token())


def _atlassian_headers() -> Optional[dict[str, str]]:
    token = _atlassian_token()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


_ATLASSIAN_DISABLED_MSG = _missing_msg(
    "Atlassian",
    "Set `ATLASSIAN_TOKEN` in `.env` (Atlassian API token) to enable Jira/Confluence search.",
)


async def jira_search_issues(
    jql: Annotated[
        str,
        Field(description="Jira JQL query, e.g. 'project = ABC AND status = Open ORDER BY priority DESC'."),
    ],
) -> str:
    """Search Jira issues by JQL via Atlassian MCP."""
    if not _atlassian_enabled():
        return _ATLASSIAN_DISABLED_MSG
    return await call_mcp_tool(
        server_name="atlassian",
        server_url=_ATLASSIAN_URL,
        tool_name="searchJiraIssuesUsingJql",
        arguments={"jql": jql},
        headers=_atlassian_headers(),
    )


async def confluence_search_pages(
    cql: Annotated[
        str,
        Field(description="Confluence CQL query, e.g. 'space = ENG AND title ~ \"runbook\"'."),
    ],
) -> str:
    """Search Confluence pages by CQL via Atlassian MCP."""
    if not _atlassian_enabled():
        return _ATLASSIAN_DISABLED_MSG
    return await call_mcp_tool(
        server_name="atlassian",
        server_url=_ATLASSIAN_URL,
        tool_name="searchConfluenceUsingCql",
        arguments={"cql": cql},
        headers=_atlassian_headers(),
    )


# ─────────────────────────────────────────────────────────────────────────────
#  TIER 3 — STDIO via npx / uvx (auto-disabled when binary missing)
# ─────────────────────────────────────────────────────────────────────────────

def _stdio_enabled(env_var: str, command: str) -> bool:
    """STDIO MCPs require both `_ENABLED` env opt-in AND the command on PATH."""
    flag = (os.getenv(env_var) or "auto").strip().lower()
    if flag in ("false", "0", "off", "disabled", "no"):
        return False
    if not is_command_available(command):
        return False
    return True


# T3a: Filesystem MCP (npx @modelcontextprotocol/server-filesystem)
def _fs_roots() -> list[str]:
    raw = _env("MCP_FILESYSTEM_ROOTS")
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(os.pathsep) if p.strip()]
    return [p for p in parts if os.path.isdir(p)]


_FS_DISABLED_MSG = _missing_msg(
    "Filesystem",
    "Install Node.js and set `MCP_FILESYSTEM_ENABLED=true` plus "
    "`MCP_FILESYSTEM_ROOTS=<dir1>;<dir2>` (semicolon-separated allowlist) "
    "in `.env`. Tool wraps `npx @modelcontextprotocol/server-filesystem`.",
)


async def filesystem_list_directory(
    path: Annotated[
        str,
        Field(description="Absolute path to a directory inside one of the configured `MCP_FILESYSTEM_ROOTS`."),
    ],
) -> str:
    """List the contents of a directory via Filesystem MCP (sandboxed to allowlisted roots)."""
    if not _stdio_enabled("MCP_FILESYSTEM_ENABLED", "npx"):
        return _FS_DISABLED_MSG
    roots = _fs_roots()
    if not roots:
        return _missing_msg("Filesystem", "Set `MCP_FILESYSTEM_ROOTS=<dir>` (semicolon-separated) in `.env`.")
    return await call_stdio_mcp_tool(
        server_name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", *roots],
        tool_name="list_directory",
        arguments={"path": path},
    )


# T3b: Sequential Thinking MCP (npx @modelcontextprotocol/server-sequential-thinking)
_SEQ_DISABLED_MSG = _missing_msg(
    "Sequential-Thinking",
    "Install Node.js and set `MCP_SEQUENTIAL_THINKING_ENABLED=true` in `.env`. "
    "Tool wraps `npx @modelcontextprotocol/server-sequential-thinking`.",
)


async def sequential_thinking_step(
    thought: Annotated[
        str,
        Field(description="The current reasoning step or thought to record / refine."),
    ],
    thought_number: Annotated[
        int,
        Field(description="1-based index of this thought in the chain."),
    ] = 1,
    total_thoughts: Annotated[
        int,
        Field(description="Estimated total thoughts in the chain (can grow)."),
    ] = 5,
    next_thought_needed: Annotated[
        bool,
        Field(description="Whether another thought is required after this one."),
    ] = True,
) -> str:
    """
    Record one step of structured reasoning via Sequential Thinking MCP.

    Use for hard problems where breaking the work into explicit steps —
    with the option to revise or branch — improves the final answer.
    """
    if not _stdio_enabled("MCP_SEQUENTIAL_THINKING_ENABLED", "npx"):
        return _SEQ_DISABLED_MSG
    return await call_stdio_mcp_tool(
        server_name="sequential-thinking",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-sequential-thinking"],
        tool_name="sequentialthinking",
        arguments={
            "thought": thought,
            "thoughtNumber": thought_number,
            "totalThoughts": total_thoughts,
            "nextThoughtNeeded": next_thought_needed,
        },
    )


# T3c: Memory Graph MCP (npx @modelcontextprotocol/server-memory)
_MEMGRAPH_DISABLED_MSG = _missing_msg(
    "Memory-Graph",
    "Install Node.js and set `MCP_MEMORY_GRAPH_ENABLED=true` in `.env`. "
    "Tool wraps `npx @modelcontextprotocol/server-memory`.",
)


def _memgraph_env() -> dict[str, str]:
    path = _env("MCP_MEMORY_GRAPH_PATH")
    if not path:
        return {}
    return {"MEMORY_FILE_PATH": path}


async def memory_graph_create_entities(
    entities_json: Annotated[
        str,
        Field(description="JSON array of entity objects: [{\"name\":\"...\",\"entityType\":\"...\",\"observations\":[\"...\"]}, ...]"),
    ],
) -> str:
    """Create entities in the persistent knowledge graph via Memory Graph MCP."""
    if not _stdio_enabled("MCP_MEMORY_GRAPH_ENABLED", "npx"):
        return _MEMGRAPH_DISABLED_MSG
    import json as _json
    try:
        entities = _json.loads(entities_json)
    except _json.JSONDecodeError as exc:
        return f"Invalid `entities_json`: {exc}"
    return await call_stdio_mcp_tool(
        server_name="memory-graph",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
        tool_name="create_entities",
        arguments={"entities": entities},
        env=_memgraph_env(),
    )


async def memory_graph_search_nodes(
    query: Annotated[
        str,
        Field(description="Query string to match entity names, types, or observations in the graph."),
    ],
) -> str:
    """Search the persistent knowledge graph for matching nodes via Memory Graph MCP."""
    if not _stdio_enabled("MCP_MEMORY_GRAPH_ENABLED", "npx"):
        return _MEMGRAPH_DISABLED_MSG
    return await call_stdio_mcp_tool(
        server_name="memory-graph",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-memory"],
        tool_name="search_nodes",
        arguments={"query": query},
        env=_memgraph_env(),
    )


# T3d: Git MCP (uvx mcp-server-git)
_GIT_DISABLED_MSG = _missing_msg(
    "Git",
    "Install `uv` (https://docs.astral.sh/uv/) and set `MCP_GIT_ENABLED=true` "
    "in `.env`. Tool wraps `uvx mcp-server-git --repository <path>`.",
)


async def git_status_log(
    repository_path: Annotated[
        str,
        Field(description="Absolute path to a local Git repository."),
    ],
    max_commits: Annotated[
        int,
        Field(description="Number of recent commits to include in the log (default 10)."),
    ] = 10,
) -> str:
    """Read Git status + recent commit log for a local repository via Git MCP."""
    if not _stdio_enabled("MCP_GIT_ENABLED", "uvx"):
        return _GIT_DISABLED_MSG
    if not os.path.isdir(repository_path):
        return f"Repository path does not exist: {repository_path}"
    return await call_stdio_mcp_tool(
        server_name="git",
        command="uvx",
        args=["mcp-server-git", "--repository", repository_path],
        tool_name="git_log",
        arguments={"repo_path": repository_path, "max_count": max_commits},
    )


# T3e: SQLite MCP (uvx mcp-server-sqlite)
_SQLITE_DISABLED_MSG = _missing_msg(
    "SQLite",
    "Install `uv` and set `MCP_SQLITE_ENABLED=true` plus `MCP_SQLITE_DB=<path-to-.db>` "
    "in `.env`. Tool wraps `uvx mcp-server-sqlite --db-path <path>`.",
)


async def sqlite_query(
    sql: Annotated[
        str,
        Field(description="SELECT-only SQL query against the configured SQLite database."),
    ],
) -> str:
    """Run a read-only SQL query against the configured SQLite DB via SQLite MCP."""
    if not _stdio_enabled("MCP_SQLITE_ENABLED", "uvx"):
        return _SQLITE_DISABLED_MSG
    db_path = _env("MCP_SQLITE_DB")
    if not db_path:
        return _missing_msg("SQLite", "Set `MCP_SQLITE_DB=<path-to-.db>` in `.env`.")
    return await call_stdio_mcp_tool(
        server_name="sqlite",
        command="uvx",
        args=["mcp-server-sqlite", "--db-path", db_path],
        tool_name="read_query",
        arguments={"query": sql},
    )


# T3f: Time MCP (uvx mcp-server-time)
_TIME_DISABLED_MSG = _missing_msg(
    "Time",
    "Install `uv` and set `MCP_TIME_ENABLED=true` in `.env`. Tool wraps `uvx mcp-server-time`.",
)


async def time_get_current(
    timezone: Annotated[
        str,
        Field(description="IANA timezone name, e.g. 'America/New_York', 'Europe/London', 'UTC'."),
    ] = "UTC",
) -> str:
    """Get the current time in any IANA timezone via Time MCP."""
    if not _stdio_enabled("MCP_TIME_ENABLED", "uvx"):
        return _TIME_DISABLED_MSG
    return await call_stdio_mcp_tool(
        server_name="time",
        command="uvx",
        args=["mcp-server-time"],
        tool_name="get_current_time",
        arguments={"timezone": timezone},
    )


# T3g: Fetch MCP (uvx mcp-server-fetch)
_FETCH_DISABLED_MSG = _missing_msg(
    "Fetch",
    "Install `uv` and set `MCP_FETCH_ENABLED=true` in `.env`. Tool wraps `uvx mcp-server-fetch`.",
)


async def mcp_fetch_url(
    url: Annotated[
        str,
        Field(description="HTTP(S) URL to fetch and convert to Markdown."),
    ],
    max_length: Annotated[
        int,
        Field(description="Maximum number of characters to return (default 5000)."),
    ] = 5000,
) -> str:
    """Fetch a web page and return Markdown via the official Fetch MCP server."""
    if not _stdio_enabled("MCP_FETCH_ENABLED", "uvx"):
        return _FETCH_DISABLED_MSG
    return await call_stdio_mcp_tool(
        server_name="fetch",
        command="uvx",
        args=["mcp-server-fetch"],
        tool_name="fetch",
        arguments={"url": url, "max_length": max_length},
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Tool group lists consumed by orchestrator + specialists
# ─────────────────────────────────────────────────────────────────────────────

# Existing
MCP_DOCS_TOOLS: list = [
    microsoft_docs_search,
    microsoft_docs_fetch,
    microsoft_code_sample_search,
]

MCP_GITHUB_TOOLS: list = [
    github_search_repositories,
    github_search_code,
    github_search_issues,
    github_get_file_contents,
]

# Tier 1 — HTTP, key-free
MCP_DEEPWIKI_TOOLS: list = [
    deepwiki_ask_question,
    deepwiki_read_wiki_structure,
]

MCP_CONTEXT7_TOOLS: list = [
    context7_resolve_library,
    context7_get_library_docs,
]

MCP_HUGGINGFACE_TOOLS: list = [
    huggingface_model_search,
    huggingface_dataset_search,
    huggingface_paper_search,
]

# Tier 2 — HTTP, opt-in
MCP_NOTION_TOOLS: list = [notion_search, notion_fetch_page]
MCP_SENTRY_TOOLS: list = [sentry_find_issues, sentry_get_issue_details]
MCP_ATLASSIAN_TOOLS: list = [jira_search_issues, confluence_search_pages]

# Tier 3 — STDIO
MCP_FILESYSTEM_TOOLS: list = [filesystem_list_directory]
MCP_SEQUENTIAL_THINKING_TOOLS: list = [sequential_thinking_step]
MCP_MEMORY_GRAPH_TOOLS: list = [memory_graph_create_entities, memory_graph_search_nodes]
MCP_GIT_TOOLS: list = [git_status_log]
MCP_SQLITE_TOOLS: list = [sqlite_query]
MCP_TIME_TOOLS: list = [time_get_current]
MCP_FETCH_TOOLS: list = [mcp_fetch_url]

# Convenience aggregations
MCP_TIER1_TOOLS: list = (
    list(MCP_DEEPWIKI_TOOLS) + list(MCP_CONTEXT7_TOOLS) + list(MCP_HUGGINGFACE_TOOLS)
)
MCP_TIER2_TOOLS: list = (
    list(MCP_NOTION_TOOLS) + list(MCP_SENTRY_TOOLS) + list(MCP_ATLASSIAN_TOOLS)
)
MCP_TIER3_TOOLS: list = (
    list(MCP_FILESYSTEM_TOOLS)
    + list(MCP_SEQUENTIAL_THINKING_TOOLS)
    + list(MCP_MEMORY_GRAPH_TOOLS)
    + list(MCP_GIT_TOOLS)
    + list(MCP_SQLITE_TOOLS)
    + list(MCP_TIME_TOOLS)
    + list(MCP_FETCH_TOOLS)
)

# Every MCP-backed tool, flat list.
MCP_TOOLS: list = (
    list(MCP_DOCS_TOOLS)
    + list(MCP_GITHUB_TOOLS)
    + list(MCP_TIER1_TOOLS)
    + list(MCP_TIER2_TOOLS)
    + list(MCP_TIER3_TOOLS)
)


def is_github_mcp_active() -> bool:
    """Return True when GitHub MCP tools are configured to make real calls."""
    return _github_enabled() and _github_token() is not None


# Display labels in a stable order. Keep in sync with mcp_status() keys below.
_MCP_DISPLAY: list[tuple[str, str]] = [
    ("docs",          "docs_enabled"),
    ("deepwiki",      "deepwiki_enabled"),
    ("context7",      "context7_enabled"),
    ("huggingface",   "huggingface_enabled"),
    ("github",        "github_enabled"),
    ("notion",        "notion_enabled"),
    ("sentry",        "sentry_enabled"),
    ("atlassian",     "atlassian_enabled"),
    ("filesystem",    "filesystem_enabled"),
    ("seq-think",     "sequential_thinking_enabled"),
    ("memory-graph",  "memory_graph_enabled"),
    ("git",           "git_enabled"),
    ("sqlite",        "sqlite_enabled"),
    ("time",          "time_enabled"),
    ("fetch",         "fetch_enabled"),
]


def format_mcp_banner() -> list[str]:
    """Return banner lines summarizing MCP server status (active vs disabled).

    Designed to slot into the AgentSystem startup status panel. Ensures the
    operator can immediately see which MCP servers are live and which are
    missing — catches token/config bugs in <2 seconds instead of via failed
    agent calls.
    """
    status = mcp_status()
    active: list[str] = []
    disabled: list[str] = []
    for label, key in _MCP_DISPLAY:
        if bool(status.get(key)):
            active.append(label)
        else:
            disabled.append(label)
    total = len(_MCP_DISPLAY)

    # Hint at the most common cause when a popular HTTP MCP is off
    hints: list[str] = []
    if not status.get("github_enabled") and not status.get("github_token_present"):
        hints.append("github: set GITHUB_TOKEN in .env")
    if not status.get("node_available") and any(
        not status.get(k) for k in ("filesystem_enabled", "sequential_thinking_enabled", "memory_graph_enabled")
    ):
        hints.append("npx not found (Tier-3 stdio servers need Node.js)")
    if not status.get("uvx_available") and any(
        not status.get(k) for k in ("git_enabled", "sqlite_enabled", "time_enabled", "fetch_enabled")
    ):
        hints.append("uvx not found (some Tier-3 stdio servers need uv)")

    lines = [
        f"   MCP active:   {', '.join(active) if active else '(none)'}  ({len(active)}/{total})",
        f"   MCP disabled: {', '.join(disabled) if disabled else '(none)'}  ({len(disabled)}/{total})",
    ]
    if hints:
        lines.append(f"   MCP hints:    {' | '.join(hints)}")
    return lines


def print_mcp_banner() -> None:
    """Print the MCP server status banner to stdout."""
    for line in format_mcp_banner():
        print(line)


def mcp_status() -> dict[str, object]:
    """Status dict suitable for diagnostics / smoke tests."""
    return {
        # Existing
        "docs_url": _DOCS_URL,
        "docs_enabled": True,
        "github_url": _GITHUB_URL,
        "github_enabled": is_github_mcp_active(),
        "github_token_present": _github_token() is not None,
        # Tier 1
        "deepwiki_url": _DEEPWIKI_URL,
        "deepwiki_enabled": _deepwiki_enabled(),
        "context7_url": _CONTEXT7_URL,
        "context7_enabled": _context7_enabled(),
        "huggingface_url": _HF_URL,
        "huggingface_enabled": _hf_enabled(),
        # Tier 2
        "notion_enabled": _notion_enabled(),
        "sentry_enabled": _sentry_enabled(),
        "atlassian_enabled": _atlassian_enabled(),
        # Tier 3
        "filesystem_enabled": _stdio_enabled("MCP_FILESYSTEM_ENABLED", "npx") and bool(_fs_roots()),
        "sequential_thinking_enabled": _stdio_enabled("MCP_SEQUENTIAL_THINKING_ENABLED", "npx"),
        "memory_graph_enabled": _stdio_enabled("MCP_MEMORY_GRAPH_ENABLED", "npx"),
        "git_enabled": _stdio_enabled("MCP_GIT_ENABLED", "uvx"),
        "sqlite_enabled": _stdio_enabled("MCP_SQLITE_ENABLED", "uvx") and bool(_env("MCP_SQLITE_DB")),
        "time_enabled": _stdio_enabled("MCP_TIME_ENABLED", "uvx"),
        "fetch_enabled": _stdio_enabled("MCP_FETCH_ENABLED", "uvx"),
        # Roll-ups
        "node_available": is_command_available("npx"),
        "uvx_available": is_command_available("uvx"),
        "total_tools": len(MCP_TOOLS),
    }


__all__ = [
    # Aggregations
    "MCP_TOOLS",
    "MCP_TIER1_TOOLS",
    "MCP_TIER2_TOOLS",
    "MCP_TIER3_TOOLS",
    # Existing groups
    "MCP_DOCS_TOOLS",
    "MCP_GITHUB_TOOLS",
    # Tier 1 groups
    "MCP_DEEPWIKI_TOOLS",
    "MCP_CONTEXT7_TOOLS",
    "MCP_HUGGINGFACE_TOOLS",
    # Tier 2 groups
    "MCP_NOTION_TOOLS",
    "MCP_SENTRY_TOOLS",
    "MCP_ATLASSIAN_TOOLS",
    # Tier 3 groups
    "MCP_FILESYSTEM_TOOLS",
    "MCP_SEQUENTIAL_THINKING_TOOLS",
    "MCP_MEMORY_GRAPH_TOOLS",
    "MCP_GIT_TOOLS",
    "MCP_SQLITE_TOOLS",
    "MCP_TIME_TOOLS",
    "MCP_FETCH_TOOLS",
    # Existing tools
    "microsoft_docs_search",
    "microsoft_docs_fetch",
    "microsoft_code_sample_search",
    "github_search_repositories",
    "github_search_code",
    "github_search_issues",
    "github_get_file_contents",
    # Tier 1 tools
    "deepwiki_ask_question",
    "deepwiki_read_wiki_structure",
    "context7_resolve_library",
    "context7_get_library_docs",
    "huggingface_model_search",
    "huggingface_dataset_search",
    "huggingface_paper_search",
    # Tier 2 tools
    "notion_search",
    "notion_fetch_page",
    "sentry_find_issues",
    "sentry_get_issue_details",
    "jira_search_issues",
    "confluence_search_pages",
    # Tier 3 tools
    "filesystem_list_directory",
    "sequential_thinking_step",
    "memory_graph_create_entities",
    "memory_graph_search_nodes",
    "git_status_log",
    "sqlite_query",
    "time_get_current",
    "mcp_fetch_url",
    # Helpers
    "is_github_mcp_active",
    "mcp_status",
    "format_mcp_banner",
    "print_mcp_banner",
]
