"""
Web fetch tool — pull a URL and return readable Markdown.

Uses `markdownify` if installed for a clean HTML→Markdown conversion; otherwise
falls back to a simple tag-stripper. Auto-detects anti-bot / JS-required pages
and falls back to `browse_fetch` (real Chrome CDP) when available.

Designed to be safe to call from any agent without exception leakage.
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

# Realistic browser headers to reduce bot detection
_BROWSER_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)

# ── Anti-bot / JS-required page detection patterns ──────────────────────
# These patterns indicate the HTTP response is a bot-challenge page, not
# real content. When detected, we auto-fallback to browse_fetch (Chrome CDP).
_ANTI_BOT_PATTERNS = [
    # AWS WAF challenge
    r"awsWafCookieDomainList",
    r"window\.gokuProps",
    # Cloudflare challenge
    r"cf-browser-verify",
    r"Just a moment\.\.\.",
    r"Checking your browser",
    r"cf_chl_opt",
    r"/cdn-cgi/challenge-platform",
    # Generic JS-required / anti-bot
    r"JavaScript is disabled",
    r"Enable JavaScript",
    r"please enable javascript",
    r"Your browser does not support JavaScript",
    r"Access Denied",
    r"access denied",
    r"<title>.*?Attention Required.*?</title>",
    r"<title>.*?Security Check.*?</title>",
    r"<title>.*?Robot.*?</title>",
    # Distil / Imperva / Akamai
    r"distil_r_captcha",
    r"_Incapsula_Resource",
    r"akamai.*?bot",
    # PerimeterX
    r"_pxCaptcha",
    r"window\._pxAppId",
]

_ANTI_BOT_RE = re.compile("|".join(_ANTI_BOT_PATTERNS), re.IGNORECASE)

# Short body threshold: if the body is very short AND doesn't look like
# real content, it's suspicious. Real pages are rarely < 500 chars.
_MIN_REAL_CONTENT_CHARS = 300


def _is_anti_bot_page(body: str, status_code: int) -> bool:
    """Check if the response is an anti-bot / JS-required challenge page."""
    # Short body + non-200 status is suspicious
    if status_code not in (200, 201, 304) and len(body) < _MIN_REAL_CONTENT_CHARS * 2:
        return True

    # Check for known anti-bot patterns
    if _ANTI_BOT_RE.search(body):
        return True

    # Very short body with no real content indicators
    if len(body) < _MIN_REAL_CONTENT_CHARS:
        # If it's < 300 chars and doesn't contain <html> or substantive text,
        # it's probably not real content
        if "<html" not in body.lower() and len(body.split()) < 20:
            return True

    return False


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


async def _try_browse_fallback(url: str, max_chars: int) -> str | None:
    """Try to fetch the page using browse_fetch (Chrome CDP). Returns None if unavailable."""
    try:
        from .browse_tools import browse_fetch

        result = await browse_fetch(url, max_chars=max_chars)
        # Check if browse_fetch itself returned an error about browser unavailability
        if result.startswith("Browser is not available"):
            return None
        return result
    except ImportError:
        logger.debug("browse_tools not available for fallback")
        return None
    except Exception as exc:
        logger.debug("browse_fetch fallback failed: %s", exc)
        return None


async def web_fetch(
    url: Annotated[str, Field(description="The HTTP/HTTPS URL to fetch")],
    max_chars: Annotated[int, Field(description="Maximum characters of body to return (1000-50000)")] = 12000,
) -> str:
    """
    Fetch a URL and return its body as Markdown (truncated to `max_chars`).

    Returns a clear error string instead of raising on failure.
    Auto-falls back to browser-based rendering (Chrome CDP) when the page
    requires JavaScript or presents an anti-bot challenge.
    """
    audit_id = audit_log("WebFetch.fetch", "started", {"url": url, "max_chars": max_chars})
    max_chars = max(1000, min(50000, int(max_chars or 12000)))

    if not url.lower().startswith(("http://", "https://")):
        return f"Invalid URL (must start with http:// or https://): {url}"

    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers=_BROWSER_HEADERS,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url)
            content_type = resp.headers.get("content-type", "")
            body = resp.text

        # ── Anti-bot detection + auto-fallback ──────────────────────────
        if _is_anti_bot_page(body, resp.status_code):
            logger.info(
                "Web fetch detected anti-bot page (status=%d, len=%d) for %s — trying browse fallback",
                resp.status_code, len(body), url,
            )
            fallback = await _try_browse_fallback(url, max_chars)
            if fallback is not None:
                audit_log(
                    "WebFetch.fetch", "browser_fallback",
                    {"url": url, "status": resp.status_code},
                    parent_id=audit_id,
                )
                return fallback

            # Browse fallback not available — return a helpful error
            audit_log(
                "WebFetch.fetch", "anti_bot_blocked",
                {"url": url, "status": resp.status_code},
                parent_id=audit_id,
            )
            return (
                f"Fetch failed: {url} requires JavaScript (anti-bot page detected, "
                f"status {resp.status_code}).\n\n"
                "FALLBACK CASCADE (try in order):\n"
                "1. `browse_fetch` — renders JavaScript with a real Chrome browser.\n"
                "2. `web_search` — search for the same information via search engine snippets.\n"
                "Always try web_search as a last resort — most information is available through search."
            )

        resp.raise_for_status()

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