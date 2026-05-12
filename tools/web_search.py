"""
Web search tool — DuckDuckGo HTML scrape (no API key required).

Provides a single function `web_search(query, max_results)` that any specialist
agent or the orchestrator can call to get current information.

Falls back gracefully when the network is unreachable or when DuckDuckGo
changes its HTML; never raises out of the tool.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import httpx
from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_DUCKDUCKGO_HTML = "https://html.duckduckgo.com/html/"
_LINK_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_SNIPPET_RE = re.compile(
    r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_text(html: str) -> str:
    text = _TAG_RE.sub("", html)
    text = text.replace("&amp;", "&").replace("&quot;", '"')
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&#x27;", "'")
    return re.sub(r"\s+", " ", text).strip()


def _resolve_redirect(href: str) -> str:
    """DuckDuckGo HTML wraps results in a /l/?uddg=<encoded> redirect — unwrap it."""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        target = qs.get("uddg", [""])[0]
        if target:
            return unquote(target)
    return href


async def web_search(
    query: Annotated[str, Field(description="The search query")],
    max_results: Annotated[int, Field(description="Maximum number of results to return (1-10)")] = 5,
) -> str:
    """
    Search the public web via DuckDuckGo and return a Markdown list of results.

    Returns up to `max_results` items; each item has a title, URL, and a short
    snippet. If the search fails, returns a clear error string instead of raising.
    """
    audit_id = audit_log("WebSearch.search", "started", {"query": query, "max_results": max_results})
    max_results = max(1, min(10, int(max_results or 5)))
    try:
        async with httpx.AsyncClient(
            timeout=15.0,
            headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            follow_redirects=True,
        ) as client:
            resp = await client.post(
                _DUCKDUCKGO_HTML,
                data={"q": query, "kl": "us-en"},
            )
            resp.raise_for_status()
            html = resp.text

        links = _LINK_RE.findall(html)
        snippets = _SNIPPET_RE.findall(html)

        if not links:
            audit_log("WebSearch.search", "no_results", {"query": query}, parent_id=audit_id)
            return f"No web results for: {query!r}. Try a different query or check connectivity."

        lines = [f"# Web search results: {query}"]
        for i, (href, title_html) in enumerate(links[:max_results], start=1):
            url = _resolve_redirect(href)
            title = _clean_text(title_html) or url
            snippet = ""
            if i - 1 < len(snippets):
                snippet = _clean_text(snippets[i - 1])
            lines.append(f"\n**{i}. {title}**")
            lines.append(f"<{url}>")
            if snippet:
                lines.append(snippet[:500])
        result = "\n".join(lines)
        audit_log(
            "WebSearch.search",
            "completed",
            {"query": query, "result_count": min(len(links), max_results)},
            parent_id=audit_id,
        )
        return result
    except httpx.RequestError as exc:
        logger.warning("Web search network error: %s", exc)
        audit_log("WebSearch.search", "network_error", {"error": str(exc)}, parent_id=audit_id)
        return f"Web search failed (network): {exc!s}. Use a different tool or ask the user to provide source material."
    except Exception as exc:  # noqa: BLE001 — never raise out of a tool
        logger.exception("Web search failed")
        audit_log("WebSearch.search", "error", {"error": str(exc)}, parent_id=audit_id)
        return f"Web search failed: {exc!s}"


WEB_SEARCH_TOOLS = [web_search]
