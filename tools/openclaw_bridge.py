"""
OpenClaw ↔ AgentSystem Webhook Bridge

Receives inbound messages from the OpenClaw messaging gateway via webhook,
routes them through the AgentSystem orchestrator, and sends replies back.

Start with an orchestrator instance:
    bridge = OpenClawBridge(orchestrator)
    bridge.start()
"""

import asyncio
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

# Ensure the project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)

OPENCLAW_API = "http://127.0.0.1:18789/api"
BRIDGE_PORT = 8401


class OpenClawBridge:
    """Webhook bridge between OpenClaw and the AgentSystem orchestrator."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the HTTP webhook server and register with OpenClaw."""
        handler_class = self._create_handler()
        self.server = HTTPServer(("0.0.0.0", BRIDGE_PORT), handler_class)

        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info("OpenClaw bridge listening on port %s", BRIDGE_PORT)

        self._register_webhook()

    def stop(self) -> None:
        """Shut down the webhook server."""
        if self.server is not None:
            self.server.shutdown()
            logger.info("OpenClaw bridge stopped.")

    # ------------------------------------------------------------------
    # OpenClaw API interactions
    # ------------------------------------------------------------------

    def _register_webhook(self) -> None:
        """Register our callback URL with the OpenClaw gateway."""
        callback_url = f"http://127.0.0.1:{BRIDGE_PORT}/incoming"
        payload = {"url": callback_url, "events": ["message.received"]}
        try:
            resp = requests.post(
                f"{OPENCLAW_API}/webhooks",
                json=payload,
                timeout=10,
            )
            resp.raise_for_status()
            logger.info("Webhook registered with OpenClaw: %s", callback_url)
        except requests.RequestException as exc:
            logger.error("Failed to register webhook with OpenClaw: %s", exc)

    def send_reply(self, channel: str, recipient: str, message: str) -> None:
        """Send a reply message through the OpenClaw gateway."""
        payload = {
            "channel": channel,
            "to": recipient,
            "text": message,
        }
        try:
            resp = requests.post(
                f"{OPENCLAW_API}/messages/send",
                json=payload,
                timeout=15,
            )
            resp.raise_for_status()
            logger.info("Reply sent to %s on %s", recipient, channel)
        except requests.RequestException as exc:
            logger.error("Failed to send reply via OpenClaw: %s", exc)

    # ------------------------------------------------------------------
    # Request handler factory
    # ------------------------------------------------------------------

    def _create_handler(self):
        """Return a BaseHTTPRequestHandler class bound to this bridge."""
        bridge = self

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                if self.path != "/incoming":
                    self.send_response(404)
                    self.end_headers()
                    return

                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    body = json.loads(self.rfile.read(content_length))

                    platform = body.get("platform", "unknown")
                    sender = body.get("from", "unknown")
                    text = body.get("text", "")

                    logger.info(
                        "Incoming message from %s on %s: %s",
                        sender,
                        platform,
                        text[:80],
                    )

                    # Run the async orchestrator in a fresh event loop
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(
                            bridge.orchestrator.handle_user_input(text)
                        )
                    finally:
                        loop.close()

                    reply_text = result if isinstance(result, str) else str(result)
                    bridge.send_reply(platform, sender, reply_text)

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok"}).encode())

                except Exception:
                    logger.exception("Error processing incoming message")
                    self.send_response(500)
                    self.end_headers()

            # Suppress default HTTP request logging
            def log_message(self, format, *args):  # noqa: A002
                pass

        return _Handler


# ---------------------------------------------------------------------------
# Standalone polling fallback
# ---------------------------------------------------------------------------


async def poll_openclaw_messages() -> list:
    """Poll OpenClaw for unread messages as a fallback.

    Returns a list of message dicts, each containing at minimum
    ``platform``, ``from``, and ``text`` keys.
    """
    try:
        resp = await asyncio.to_thread(
            requests.get,
            f"{OPENCLAW_API}/messages/unread",
            timeout=10,
        )
        resp.raise_for_status()
        messages = resp.json()
        return messages if isinstance(messages, list) else []
    except requests.RequestException as exc:
        logger.error("Failed to poll OpenClaw messages: %s", exc)
        return []
