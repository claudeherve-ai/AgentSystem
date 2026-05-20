"""
AgentSystem — Microsoft Graph integration with background device-code polling.

Key design:
- graph_login() starts the device flow AND a background poller thread.
- The poller continuously calls acquire_token_by_device_flow() and saves
  the token to cache on success.
- graph_finish_login() is a fast cache check — no blocking poll.
- A local redirect server catches the browser redirect to localhost.
"""

import os
import json
import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

from msal import PublicClientApplication, SerializableTokenCache
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Use env var if set, otherwise fall back to the configured cloud app ID
CLIENT_ID = os.getenv("GRAPH_CLIENT_ID", "04b07795-8ddb-461a-bbee-02f9e1bf7b46")
AUTHORITY = "https://login.microsoftonline.com/common"
SCOPES = ["User.Read", "Mail.Read", "Mail.Send", "Calendars.Read"]
CACHE_PATH = os.path.join(os.getcwd(), "memory", "token_cache.bin")
FLOW_STATE_PATH = os.path.join(os.getcwd(), "memory", "device_flow.json")

REDIRECT_PORT = int(os.getenv("GRAPH_REDIRECT_PORT", "8400"))

_token_cache = SerializableTokenCache()
_auth_server: HTTPServer | None = None
_auth_server_lock = threading.Lock()

# Background poller state
_poller_thread: threading.Thread | None = None
_poller_stop = threading.Event()
_poller_result: dict | None = None
_poller_lock = threading.Lock()


# ── token cache ────────────────────────────────────────────────────────────────

def _init_cache() -> None:
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, "r") as f:
                _token_cache.deserialize(f.read())
        except Exception:
            pass


def _save_cache() -> None:
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        f.write(_token_cache.serialize())
    logger.info("Token cache saved to %s", CACHE_PATH)


def _clear_cache() -> None:
    if os.path.exists(CACHE_PATH):
        os.remove(CACHE_PATH)
    _token_cache.__init__()


# ── local redirect server ─────────────────────────────────────────────────────

class _AuthRedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<!DOCTYPE html><html><head><title>Auth Complete</title>"
            b"<meta charset='utf-8'><style>"
            b"body{font-family:system-ui,sans-serif;text-align:center;"
            b"padding-top:80px;background:#0a0a0a;color:#0f0}"
            b"h1{color:#0f0;font-size:2em}p{color:#aaa;font-size:1.1em}"
            b"code{background:#1a1a1a;padding:3px 8px;border-radius:4px;color:#0f0}"
            b"</style></head><body><h1>&#10003; Authentication Successful</h1>"
            b"<p>You can close this window. The agent will detect your sign-in.</p>"
            b"</body></html>"
        )

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: N802
        pass


def _start_auth_server() -> None:
    global _auth_server
    with _auth_server_lock:
        if _auth_server is not None:
            return
        try:
            _auth_server = HTTPServer(
                ("127.0.0.1", REDIRECT_PORT), _AuthRedirectHandler
            )
            t = threading.Thread(target=_auth_server.serve_forever, daemon=True)
            t.start()
            logger.info(
                "Auth redirect server listening on http://localhost:%d",
                REDIRECT_PORT,
            )
        except OSError as exc:
            logger.warning(
                "Could not start redirect server on port %d: %s", REDIRECT_PORT, exc
            )


def _stop_auth_server() -> None:
    global _auth_server
    with _auth_server_lock:
        if _auth_server is not None:
            try:
                _auth_server.shutdown()
            except Exception:
                pass
            _auth_server = None


# ── background poller ─────────────────────────────────────────────────────────

def _background_poller(flow: dict) -> None:
    """Runs in a daemon thread.  Polls acquire_token_by_device_flow() until
    success, expiry, or explicit stop.  Saves token to module-level cache."""
    global _poller_result

    app = PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=_token_cache
    )
    flow = dict(flow)

    logger.info("Background poller started for device code %s...",
                flow.get("device_code", "")[:20])

    while not _poller_stop.is_set():
        try:
            result = app.acquire_token_by_device_flow(flow)
        except Exception as exc:
            logger.error("Background poller exception: %s", exc)
            with _poller_lock:
                _poller_result = {"error": "exception", "error_description": str(exc)}
            return

        if "access_token" in result:
            _save_cache()
            with _poller_lock:
                _poller_result = result
            logger.info("Background poller: token acquired successfully")
            _cleanup_flow_state()
            return

        error = result.get("error", "")
        if error == "authorization_pending":
            interval = flow.get("interval", 5)
            _poller_stop.wait(interval)
            continue

        if error == "slow_down":
            _poller_stop.wait(flow.get("interval", 5) + 2)
            continue

        logger.warning("Background poller terminal error: %s — %s",
                       error, result.get("error_description", ""))
        with _poller_lock:
            _poller_result = result
        _cleanup_flow_state()
        return

    logger.info("Background poller stopped by signal")


def _start_background_poller(flow: dict) -> None:
    global _poller_thread, _poller_result, _poller_stop
    _poller_stop.set()
    if _poller_thread and _poller_thread.is_alive():
        _poller_thread.join(timeout=2)
    _poller_stop.clear()
    with _poller_lock:
        _poller_result = None
    _poller_thread = threading.Thread(
        target=_background_poller, args=(flow,), daemon=True,
    )
    _poller_thread.start()
    logger.info("Background poller thread started")


def _cleanup_flow_state() -> None:
    if os.path.exists(FLOW_STATE_PATH):
        try:
            os.remove(FLOW_STATE_PATH)
        except OSError:
            pass


# ── device-code auth ──────────────────────────────────────────────────────────

async def graph_login() -> str:
    """Initiate the Microsoft device-code flow with background polling."""
    _init_cache()
    _start_auth_server()

    if os.path.exists(FLOW_STATE_PATH):
        with open(FLOW_STATE_PATH, "r") as f:
            existing = json.load(f)
        msg = str(existing.get("message", ""))
        if "expired" not in msg.lower():
            return (
                "A device login flow is already in progress.\n\n"
                f"Code: **{existing.get('user_code', '???')}**\n"
                f"URL:  {existing.get('verification_uri', 'https://login.microsoft.com/device')}\n\n"
                "The background poller is running — the token will be picked up "
                "automatically after you authenticate.  Type **finish_link** to "
                "check if it's ready."
            )

    app = PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=_token_cache
    )
    flow = app.initiate_device_flow(scopes=SCOPES)

    if "user_code" not in flow:
        error = flow.get("error_description", str(flow))
        logger.error("Device flow initiation failed: %s", error)
        return f"Error initiating device flow: {error}"

    flow_state = dict(flow)
    os.makedirs(os.path.dirname(FLOW_STATE_PATH), exist_ok=True)
    with open(FLOW_STATE_PATH, "w") as f:
        json.dump(flow_state, f)

    _start_background_poller(flow_state)

    return (
        f"Microsoft 365 Device Login (App: {CLIENT_ID[:8]}...)\n\n"
        f"1. Open: {flow['verification_uri']}\n"
        f"2. Enter Code: **{flow['user_code']}**\n\n"
        "A background poller is running — the token will automatically be "
        "picked up after you authenticate.  The browser may redirect to "
        f"localhost (port {REDIRECT_PORT} is listening).\n\n"
        "After signing in, type **finish_link** to confirm the connection."
    )


async def graph_finish_login() -> str:
    """Check whether the background poller has acquired a token.  Fast — no blocking poll."""
    _init_cache()

    with _poller_lock:
        result = _poller_result

    if result is not None and "access_token" in result:
        _save_cache()
        _cleanup_flow_state()
        _stop_auth_server()
        claims = result.get("id_token_claims", {})
        username = claims.get("preferred_username", claims.get("upn", "unknown"))
        return f"Graph Connection Secured!  Signed in as {username}."

    if result is not None and "error" in result:
        error = result.get("error", "")
        error_desc = result.get("error_description", "")
        _cleanup_flow_state()
        _stop_auth_server()
        if error in ("expired_token", "device_code_expired"):
            return "Device code expired.  Run **relink_account** for a fresh code."
        if error == "exception":
            return f"Auth error: {error_desc}"
        return f"Auth failed: {error_desc or error}"

    if os.path.exists(FLOW_STATE_PATH):
        with open(FLOW_STATE_PATH, "r") as f:
            flow = json.load(f)
        return (
            "Still waiting for you to complete authentication in the browser.\n\n"
            f"Code: **{flow.get('user_code', '???')}**\n"
            f"URL:  {flow.get('verification_uri', 'https://login.microsoft.com/device')}\n\n"
            "The background poller is running — once you sign in, "
            "type **finish_link** again and it should pick up the token immediately."
        )

    token = _get_graph_token()
    if token:
        _stop_auth_server()
        return "Graph Connection Secured!  (Token found in cache.)"

    return (
        "No active device flow found.  Run **relink_account** to start "
        "a fresh login."
    )


async def graph_logout() -> str:
    """Remove the cached token and stop background poller."""
    global _poller_stop
    _init_cache()
    app = PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=_token_cache
    )
    accounts = app.get_accounts()
    for account in (accounts if isinstance(accounts, list) else []):
        try:
            app.remove_account(account)
        except Exception:
            pass
    _clear_cache()
    _cleanup_flow_state()
    _poller_stop.set()
    _stop_auth_server()
    return "Signed out. Token cache cleared."


# ── Graph API calls ───────────────────────────────────────────────────────────

def _get_graph_token() -> str | None:
    _init_cache()
    app = PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY, token_cache=_token_cache
    )
    accounts = app.get_accounts()
    if not accounts:
        return None
    result = app.acquire_token_silent(SCOPES, account=accounts[0])
    if result and "access_token" in result:
        if _token_cache.has_state_changed:
            _save_cache()
        return result["access_token"]
    return None


async def _graph_get(path: str, params: dict | None = None) -> dict | None:
    import httpx
    token = _get_graph_token()
    if not token:
        return None
    url = f"https://graph.microsoft.com/v1.0{path}"
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, headers=headers, params=params)
        if resp.status_code == 401:
            logger.warning("Graph token expired or invalid on %s", path)
            return None
        resp.raise_for_status()
        return resp.json()


async def graph_read_inbox(
    count: int = 10,
    unread_only: bool = True,
    hours_window: int | None = None,
) -> list[dict] | str:
    filters = []
    if unread_only:
        filters.append("isRead eq false")
    if hours_window is not None:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(hours=hours_window)
        ).isoformat()
        filters.append(f"receivedDateTime ge {cutoff}")
    params: dict = {
        "$top": min(count, 50),
        "$orderby": "receivedDateTime desc",
        "$select": "id,subject,from,bodyPreview,receivedDateTime,isRead,importance",
    }
    if filters:
        params["$filter"] = " and ".join(filters)
    data = await _graph_get("/me/mailFolders/inbox/messages", params=params)
    if data is None:
        return "ERR_AUTH_REQUIRED"
    messages = data.get("value", [])
    results: list[dict] = []
    for msg in messages:
        sender = msg.get("from", {}).get("emailAddress", {})
        results.append({
            "id": msg.get("id", ""),
            "subject": msg.get("subject", "(No subject)"),
            "from": sender.get("address", "unknown"),
            "from_name": sender.get("name", "unknown"),
            "preview": msg.get("bodyPreview", ""),
            "received": msg.get("receivedDateTime", ""),
            "is_unread": not msg.get("isRead", True),
            "importance": msg.get("importance", "normal"),
        })
    return results


async def graph_get_upcoming_events(days_ahead: int = 1) -> list[dict]:
    start = datetime.now(timezone.utc).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).isoformat()
    data = await _graph_get(
        "/me/calendarView",
        params={
            "startDateTime": start,
            "endDateTime": end,
            "$top": 25,
            "$orderby": "start/dateTime",
            "$select": "subject,start,end,location",
        },
    )
    if data is None:
        return "ERR_AUTH_REQUIRED"
    events: list[dict] = []
    for ev in data.get("value", []):
        start_dt = ev.get("start", {})
        end_dt = ev.get("end", {})
        loc = ev.get("location", {}).get("displayName", "No location")
        events.append({
            "subject": ev.get("subject", "Untitled"),
            "start": f"{start_dt.get('dateTime', '')} {start_dt.get('timeZone', 'UTC')}",
            "end": f"{end_dt.get('dateTime', '')} {end_dt.get('timeZone', 'UTC')}",
            "location": loc,
        })
    return events


async def graph_create_reply_draft(message_id: str, html_body: str) -> str:
    import httpx
    token = _get_graph_token()
    if not token:
        return ""
    url = f"https://graph.microsoft.com/v1.0/messages/{message_id}/createReply"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "message": {
            "body": {"contentType": "HTML", "content": html_body},
            "isDraft": True,
        }
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code == 401:
            return ""
        resp.raise_for_status()
        return resp.json().get("id", "")


async def graph_send_email(
    to: str, subject: str, body: str, content_type: str = "Text",
) -> str:
    import httpx
    token = _get_graph_token()
    if not token:
        return "ERR_AUTH_REQUIRED"
    url = "https://graph.microsoft.com/v1.0/me/sendMail"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": content_type, "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": "true",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 401:
            return "ERR_AUTH_REQUIRED"
        resp.raise_for_status()
        return "Sent"


async def graph_create_event(
    subject: str, start_iso: str, end_iso: str, location: str = "",
) -> str:
    import httpx
    token = _get_graph_token()
    if not token:
        return "ERR_AUTH_REQUIRED"
    url = "https://graph.microsoft.com/v1.0/me/events"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload: dict = {
        "subject": subject,
        "start": {"dateTime": start_iso, "timeZone": "UTC"},
        "end": {"dateTime": end_iso, "timeZone": "UTC"},
    }
    if location:
        payload["location"] = {"displayName": location}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code == 401:
            return "ERR_AUTH_REQUIRED"
        resp.raise_for_status()
        return "Created"


def create_graph_client(credential):
    return None
