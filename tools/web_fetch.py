"""
Web fetch tool — pull a URL and return readable Markdown.

Uses `markdownify` if installed for a clean HTML→Markdown conversion; otherwise
falls back to a simple tag-stripper. Designed to be safe to call from any agent
without exception leakage.
"""

from __future__ import annotations

import logging
import re
from typing import Annotated

import httpx
from pydantic import Field

from .audit import audit_log

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)


def _strip_html(html: str) -> str:
    cleaned = _SCRIPT_RE.sub("", html)
    text = _TAG_RE.sub("", cleaned)
    text = (
        text.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&#x27;", "'")
        .replace("&nbsp;", " ")
    )
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", text)).strip()


def _to_markdown(html: str) -> str:
    try:
        from markdownify import markdownify  # type: ignore

        md = markdownify(html, heading_style="ATX")
        return re.sub(r"\n{3,}", "\n\n", md).strip()
    except ImportError:
        return _strip_html(html)


async def web_fetch(
    url: Annotated[str, Field(description="The HTTP/HTTPS URL to fetch")],
    max_chars: Annotated[int, Field(description="Maximum characters of body to return (1000-50000)")] = 12000,
) -> str:
    """
    Fetch a URL and return its body as Markdown (truncated to `max_chars`).

    Returns a clear error string instead of raising on failure.
    """
    audit_id = audit_log("WebFetch.fetch", "started", {"url": url, "max_chars": max_chars})
    max_chars = max(1000, min(50000, int(max_chars or 12000)))

    if not url.lower().startswith(("http://", "https://")):
        return f"Invalid URL (must start with http:// or https://): {url}"

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            body = resp.text

        if "html" in content_type.lower() or body.lstrip().startswith("<"):
            text = _to_markdown(body)
        else:
            text = body

        truncated = False
        if len(text) > max_chars:
            text = text[:max_chars]
            truncated = True

        prefix = f"# Fetched: {url}\n\n"
        suffix = "\n\n_…truncated_" if truncated else ""
        result = prefix + text + suffix
        audit_log(
            "WebFetch.fetch",
            "completed",
            {"url": url, "chars": len(text), "truncated": truncated},
            parent_id=audit_id,
        )
        return result
    except httpx.HTTPStatusError as exc:
        logger.warning("Web fetch HTTP error: %s", exc)
        audit_log("WebFetch.fetch", "http_error", {"status": exc.response.status_code}, parent_id=audit_id)
        return f"Fetch failed: HTTP {exc.response.status_code} for {url}"
    except httpx.RequestError as exc:
        logger.warning("Web fetch network error: %s", exc)
        audit_log("WebFetch.fetch", "network_error", {"error": str(exc)}, parent_id=audit_id)
        return f"Fetch failed (network): {exc!s}"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Web fetch failed")
        audit_log("WebFetch.fetch", "error", {"error": str(exc)}, parent_id=audit_id)
        return f"Fetch failed: {exc!s}"


WEB_FETCH_TOOLS = [web_fetch]
