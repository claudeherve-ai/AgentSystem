"""
MCP-backed function tools for AgentSystem.

Exposes named async tools backed by Streamable-HTTP MCP servers so the
orchestrator and specialists can ground answers in vendor-authoritative sources
without bouncing through generic web search.

Servers wired up:
  - **Microsoft Docs MCP** (public, no auth) — `https://learn.microsoft.com/api/mcp`
    → `microsoft_docs_search`, `microsoft_docs_fetch`, `microsoft_code_sample_search`.
  - **GitHub MCP** (auth via `GITHUB_TOKEN`) — `https://api.githubcopilot.com/mcp/`
    → `github_search_repositories`, `github_search_code`, `github_search_issues`,
      `github_get_file_contents`. Tools degrade gracefully (return a clear
      message) when no token is configured.

Env knobs:
  - `MCP_DOCS_URL` (default: `https://learn.microsoft.com/api/mcp`)
  - `MCP_GITHUB_URL` (default: `https://api.githubcopilot.com/mcp/`)
  - `MCP_GITHUB_ENABLED` (default: `auto` — enabled when a GitHub token is set;
    set to `false` to force-disable, `true` to require it on startup).
  - `GITHUB_TOKEN` or `GITHUB_PAT` — Bearer token for GitHub MCP.

Style: same as the rest of the `tools/` package — plain async functions with
`Annotated[..., Field(...)]` parameters, audit-logged, never raise. The
orchestrator imports the `MCP_DOCS_TOOLS` / `MCP_GITHUB_TOOLS` lists and
appends them to the coordinator + specialist tool sets.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated, Optional

from pydantic import Field

from .mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)


# ── Configuration ───────────────────────────────────────────────────────────

_DEFAULT_DOCS_URL = "https://learn.microsoft.com/api/mcp"
_DEFAULT_GITHUB_URL = "https://api.githubcopilot.com/mcp/"


def _env(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip() or default


_DOCS_URL = _env("MCP_DOCS_URL", _DEFAULT_DOCS_URL)
_GITHUB_URL = _env("MCP_GITHUB_URL", _DEFAULT_GITHUB_URL)


def _github_token() -> Optional[str]:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")


def _github_enabled() -> bool:
    """
    GitHub MCP is opt-in. When `MCP_GITHUB_ENABLED=auto` (default) it activates
    only if a token is present; `false` disables; `true` requires a token and
    surfaces a clear message when missing.
    """
    flag = (os.getenv("MCP_GITHUB_ENABLED") or "auto").strip().lower()
    if flag in ("false", "0", "off", "disabled"):
        return False
    if flag in ("true", "1", "on", "enabled"):
        return True
    return _github_token() is not None


def _github_headers() -> Optional[dict[str, str]]:
    token = _github_token()
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


_GITHUB_DISABLED_MSG = (
    "GitHub MCP is not configured. Set `GITHUB_TOKEN` (or `GITHUB_PAT`) in `.env` "
    "with at least `repo` and `read:org` scopes to enable repository, code, "
    "issue, and PR search across the GitHub graph."
)


# ── Microsoft Docs MCP (public, no auth) ────────────────────────────────────

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
    Azure DevOps, GitHub Enterprise, and Databricks-on-Azure. Returns up to
    10 high-quality content excerpts with article titles, URLs, and
    self-contained snippets.

    Always prefer this over generic `web_search` for Microsoft/Azure topics —
    results come from first-party, version-current sources.
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
    """
    Fetch a Microsoft Learn article and return its full content as Markdown.

    Use this AFTER `microsoft_docs_search` when an excerpt is not enough and
    you need the complete page (procedures, prerequisites, troubleshooting
    sections, full API reference). Returns headings, code blocks, tables, and
    links preserved.
    """
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
                "scenario for which you want an official Microsoft sample "
                "(e.g., 'BlobClient upload with managed identity', "
                "'CosmosDB hierarchical partition keys')."
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
    """
    Find official Microsoft / Azure code samples via Microsoft Docs MCP.

    Use this any time you are about to generate Microsoft- or Azure-related
    code so the implementation is grounded in the latest official samples
    rather than dredged from training data.
    """
    args: dict[str, str] = {"query": query}
    if language:
        args["language"] = language
    return await call_mcp_tool(
        server_name="microsoft-docs",
        server_url=_DOCS_URL,
        tool_name="microsoft_code_sample_search",
        arguments=args,
    )


# ── GitHub MCP (auth required, opt-in) ──────────────────────────────────────

async def github_search_repositories(
    query: Annotated[
        str,
        Field(
            description=(
                "GitHub repository search query — supports qualifiers like "
                "`topic:`, `language:`, `stars:>N`, `org:`, `user:`. "
                "Example: 'topic:agent-framework language:python stars:>50'."
            )
        ),
    ],
) -> str:
    """
    Search public and accessible GitHub repositories via GitHub MCP.

    Use this to find reference implementations, libraries, samples, or
    competitor / partner projects. Requires `GITHUB_TOKEN` (or `GITHUB_PAT`).
    """
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
        Field(
            description=(
                "GitHub code search query — supports `repo:`, `language:`, "
                "`path:`, `extension:`, and free-text. "
                "Example: 'repo:microsoft/agent-framework MCPStreamableHTTPTool'."
            )
        ),
    ],
) -> str:
    """
    Search code across all of GitHub via GitHub MCP.

    Returns matching files with repository, path, and a snippet. Requires
    `GITHUB_TOKEN`.
    """
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
        Field(
            description=(
                "GitHub issues / PR search query — supports `is:issue`, `is:pr`, "
                "`repo:`, `state:open`, `author:`, `label:`. "
                "Example: 'repo:microsoft/agent-framework is:issue label:bug state:open'."
            )
        ),
    ],
) -> str:
    """
    Search GitHub issues and pull requests via GitHub MCP.

    Use this to triage known problems, review past discussions, find PR
    examples, or check whether an upstream fix has already landed. Requires
    `GITHUB_TOKEN`.
    """
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
        Field(
            description=(
                "Path to a file inside the repo, e.g., 'python/packages/core/agent_framework/_mcp.py'. "
                "Use '/' to list the repository root."
            )
        ),
    ] = "/",
    ref: Annotated[
        str,
        Field(
            description=(
                "Optional Git ref — branch name (e.g., 'main'), tag, or commit "
                "SHA. Leave empty for the default branch."
            )
        ),
    ] = "",
) -> str:
    """
    Fetch a file (or directory listing) from a GitHub repository via GitHub MCP.

    Use this to read source code, configuration, or documentation directly out
    of a repo so your reasoning is grounded in real upstream content. Requires
    `GITHUB_TOKEN`.
    """
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


# ── Tool lists consumed by orchestrator + specialists ───────────────────────

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

# Convenience: every MCP-backed tool, for callers that want the full set.
MCP_TOOLS: list = MCP_DOCS_TOOLS + MCP_GITHUB_TOOLS


def is_github_mcp_active() -> bool:
    """Return True when GitHub MCP tools are configured to make real calls."""
    return _github_enabled() and _github_token() is not None


def mcp_status() -> dict[str, object]:
    """Status dict suitable for diagnostics / smoke tests."""
    return {
        "docs_url": _DOCS_URL,
        "docs_enabled": True,
        "github_url": _GITHUB_URL,
        "github_enabled": is_github_mcp_active(),
        "github_token_present": _github_token() is not None,
    }


__all__ = [
    "MCP_TOOLS",
    "MCP_DOCS_TOOLS",
    "MCP_GITHUB_TOOLS",
    "microsoft_docs_search",
    "microsoft_docs_fetch",
    "microsoft_code_sample_search",
    "github_search_repositories",
    "github_search_code",
    "github_search_issues",
    "github_get_file_contents",
    "is_github_mcp_active",
    "mcp_status",
]
