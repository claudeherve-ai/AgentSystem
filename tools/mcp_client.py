"""
Minimal Streamable-HTTP MCP client for AgentSystem.

Speaks the Model Context Protocol over HTTP via JSON-RPC 2.0:
  POST initialize -> POST notifications/initialized -> POST tools/call

Designed to fit the project's tool conventions:
  - Async function, never raises out of the call (returns an error string).
  - Audit-logged via `audit_log` with started/completed/error lifecycle.
  - Handles both `application/json` and `text/event-stream` MCP responses.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

import httpx

from .audit import audit_log

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "1.0.0"
_DEFAULT_TIMEOUT = 30.0
_USER_AGENT = "AgentSystem-MCP/1.0"


def _parse_mcp_response(resp: httpx.Response) -> dict[str, Any]:
    """
    Parse an MCP HTTP response. Servers may reply with either
    `application/json` (a single JSON-RPC envelope) or `text/event-stream`
    (one or more SSE `data:` lines, each containing a JSON-RPC envelope).
    """
    ctype = resp.headers.get("Content-Type", "")
    if "text/event-stream" in ctype:
        last_payload: dict[str, Any] = {}
        for raw_line in resp.text.splitlines():
            line = raw_line.strip()
            if not line.startswith("data:"):
                continue
            payload_str = line[len("data:"):].strip()
            if not payload_str:
                continue
            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and ("result" in payload or "error" in payload):
                last_payload = payload
        return last_payload or {"error": {"message": "Empty SSE response from MCP server"}}

    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
        return {"error": {"message": f"Unexpected MCP response shape: {type(data).__name__}"}}
    except json.JSONDecodeError:
        snippet = resp.text[:200] if resp.text else "<empty>"
        return {"error": {"message": f"Non-JSON MCP response: {snippet}"}}


def _extract_text_from_result(result: dict[str, Any]) -> str:
    """
    Pull the human-readable text out of an MCP `tools/call` result envelope.

    Standard shape:
      { "content": [ { "type": "text", "text": "..." }, ... ], "isError": false }
    """
    if not isinstance(result, dict):
        return json.dumps(result)

    if result.get("isError"):
        content = result.get("content") or []
        text_parts = [c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"]
        return f"MCP tool reported an error: {' '.join(text_parts).strip() or json.dumps(result)}"

    content = result.get("content")
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            ctype = item.get("type")
            if ctype == "text":
                text = item.get("text", "")
                if text:
                    chunks.append(text)
            elif ctype == "resource":
                resource = item.get("resource") or {}
                resource_text = resource.get("text") or json.dumps(resource)
                if resource_text:
                    chunks.append(resource_text)
            else:
                chunks.append(json.dumps(item))
        if chunks:
            return "\n\n".join(chunks)

    if "structuredContent" in result:
        return json.dumps(result["structuredContent"], indent=2)

    return json.dumps(result, indent=2)


async def call_mcp_tool(
    *,
    server_name: str,
    server_url: str,
    tool_name: str,
    arguments: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> str:
    """
    Call a single tool on a Streamable-HTTP MCP server and return result text.
    """
    arguments = arguments or {}
    audit_id = audit_log(
        f"MCP.{server_name}.{tool_name}",
        "started",
        {"server_url": server_url, "args": arguments},
    )

    # Added X-GitHub-Api-Version header for GitHub compatibility
    base_headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": _USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if headers:
        base_headers.update(headers)

    init_body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": _PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "AgentSystem", "version": "1.0"},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            init_resp = await client.post(server_url, headers=base_headers, json=init_body)
            if init_resp.status_code in (401, 403):
                return f"MCP `{server_name}` authentication failed (HTTP {init_resp.status_code})."
            if init_resp.status_code >= 400:
                snippet = init_resp.text[:200]
                return f"MCP `{server_name}` init returned HTTP {init_resp.status_code}: {snippet}"

            session_id = init_resp.headers.get("Mcp-Session-Id") or init_resp.headers.get("mcp-session-id")
            session_headers = dict(base_headers)
            if session_id:
                session_headers["Mcp-Session-Id"] = session_id

            init_payload = _parse_mcp_response(init_resp)
            if "error" in init_payload:
                return f"MCP `{server_name}` init failed: {init_payload['error'].get('message')}"

            await client.post(
                server_url,
                headers=session_headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )

            call_body = {
                "jsonrpc": "2.0",
                "id": str(uuid.uuid4()),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            call_resp = await client.post(server_url, headers=session_headers, json=call_body)

            if call_resp.status_code >= 400:
                return f"MCP `{server_name}` tool call returned HTTP {call_resp.status_code}"

            call_payload = _parse_mcp_response(call_resp)
            if "error" in call_payload:
                return f"MCP tool `{tool_name}` error: {call_payload['error'].get('message')}"

            text = _extract_text_from_result(call_payload.get("result", {}))
            audit_log(f"MCP.{server_name}.{tool_name}", "completed", {"chars": len(text)}, parent_id=audit_id)
            return text

    except Exception as exc:
        return f"MCP tool `{tool_name}` on `{server_name}` failed: {exc!s}"


__all__ = ["call_mcp_tool"]
