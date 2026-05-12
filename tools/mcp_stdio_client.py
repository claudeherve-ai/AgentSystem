"""
Generic stdio MCP client for AgentSystem.

Speaks the Model Context Protocol over a subprocess's stdin/stdout via
JSON-RPC 2.0 (newline-delimited): initialize → notifications/initialized →
tools/call → close.

This is the stdio counterpart to `tools/mcp_client.py` (HTTP variant) and
mirrors its public surface so `tools/mcp_tools.py` can call either transport
through a uniform shape:

    result_text = await call_stdio_mcp_tool(
        server_name="filesystem",
        command="npx",
        args=["-y", "@modelcontextprotocol/server-filesystem", root_dir],
        tool_name="list_directory",
        arguments={"path": root_dir},
    )

Designed to fit the project's tool conventions:
  - Async function, never raises (returns an error string instead).
  - Audit-logged via `audit_log` with started / completed / error lifecycle.
  - Per-call subprocess (cold-starts on each call).  Most reference MCP
    servers (`@modelcontextprotocol/server-*`, `mcp-server-*`) are
    stateless from the client's perspective, so this is reliable and the
    framework's static tool-list pattern just works.

When the underlying binary (`npx`, `uvx`, etc.) is missing on PATH or
times out, this returns a clear, user-actionable error string with the
exact install / configure hint — never a stack trace.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import uuid
from typing import Any, Optional

from .audit import audit_log

logger = logging.getLogger(__name__)

_PROTOCOL_VERSION = "2024-11-05"
_DEFAULT_TIMEOUT = 30.0
_CLIENT_INFO = {"name": "AgentSystem-MCP-Stdio", "version": "1.0"}


def is_command_available(command: str) -> bool:
    """Return True when the given executable resolves on the current PATH."""
    if not command:
        return False
    return shutil.which(command) is not None


def _serialize_message(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")


def _extract_text(result: Any) -> str:
    """Best-effort projection of an MCP `tools/call` result into a string."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        # MCP tool results follow {"content": [{"type": "text", "text": "..."}, ...]}
        content = result.get("content")
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if not isinstance(item, dict):
                    chunks.append(str(item))
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    chunks.append(item["text"])
                elif "text" in item and isinstance(item["text"], str):
                    chunks.append(item["text"])
                else:
                    chunks.append(json.dumps(item, ensure_ascii=False))
            joined = "\n".join(c for c in chunks if c)
            if joined:
                return joined
        if "text" in result and isinstance(result["text"], str):
            return result["text"]
        return json.dumps(result, ensure_ascii=False, indent=2)

    if isinstance(result, list):
        return "\n".join(_extract_text(item) for item in result)

    return str(result)


async def _read_until_response(
    stdout: asyncio.StreamReader,
    request_id: str,
    deadline: float,
) -> dict[str, Any]:
    """
    Read stdout line-by-line until we see a JSON-RPC envelope whose `id`
    matches `request_id`, or until we hit `deadline`.
    """
    while True:
        timeout = max(deadline - asyncio.get_event_loop().time(), 0.05)
        try:
            line = await asyncio.wait_for(stdout.readline(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(
                "Timed out waiting for MCP server response"
            ) from exc

        if not line:
            raise RuntimeError("MCP server closed stdout before responding")

        text = line.decode("utf-8", errors="replace").strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            # Some servers print logs to stdout — ignore non-JSON lines.
            logger.debug("MCP stdio: non-JSON line ignored: %s", text[:200])
            continue
        if not isinstance(payload, dict):
            continue

        # Skip notifications/log messages without an id, or with a different id.
        if payload.get("id") != request_id:
            continue
        return payload


async def _drain_stderr(stderr: asyncio.StreamReader, sink: list[str]) -> None:
    """Consume stderr in the background so the subprocess never blocks on it."""
    try:
        while True:
            line = await stderr.readline()
            if not line:
                return
            sink.append(line.decode("utf-8", errors="replace"))
    except Exception:
        return


async def call_stdio_mcp_tool(
    *,
    server_name: str,
    command: str,
    args: list[str],
    tool_name: str,
    arguments: Optional[dict[str, Any]] = None,
    env: Optional[dict[str, str]] = None,
    timeout: float = _DEFAULT_TIMEOUT,
    cwd: Optional[str] = None,
    install_hint: Optional[str] = None,
) -> str:
    """
    Invoke a single tool on a stdio-based MCP server.

    `command` + `args` describe how to launch the server.  The function
    spawns the process, performs the MCP handshake, calls the tool once,
    extracts the textual result, and terminates the process cleanly.
    """
    arguments = arguments or {}
    audit_payload = {
        "server": server_name,
        "command": command,
        "args": args,
        "tool": tool_name,
    }
    audit_log("mcp_stdio_call_started", audit_payload)

    if not is_command_available(command):
        hint = install_hint or (
            f"`{command}` is not installed or not on PATH. Install it and try again."
        )
        msg = f"MCP `{server_name}` is not available: {hint}"
        audit_log("mcp_stdio_call_error", {**audit_payload, "error": "command_not_found"})
        return msg

    try:
        merged_env = dict(os.environ)
        if env:
            merged_env.update(env)
        # On Windows, npx and uvx are .cmd shims that require shell expansion
        # to actually launch.  Use create_subprocess_shell on Windows for those.
        process_env = merged_env

        if sys.platform == "win32" and command.lower() in ("npx", "npm", "node", "uvx", "uv"):
            cmd_str = " ".join(
                [command] + [_quote_for_cmd(a) for a in args]
            )
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=cwd,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                command,
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=process_env,
                cwd=cwd,
            )
    except FileNotFoundError:
        msg = (
            f"MCP `{server_name}` could not be launched: command `{command}` "
            f"was not found. " + (install_hint or "")
        ).strip()
        audit_log("mcp_stdio_call_error", {**audit_payload, "error": "spawn_failed"})
        return msg
    except Exception as exc:  # pragma: no cover - defensive
        msg = f"MCP `{server_name}` failed to start: {exc!r}"
        audit_log("mcp_stdio_call_error", {**audit_payload, "error": str(exc)})
        return msg

    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    stderr_buf: list[str] = []
    stderr_task = asyncio.create_task(_drain_stderr(process.stderr, stderr_buf))

    deadline = asyncio.get_event_loop().time() + timeout

    try:
        # 1) initialize
        init_id = str(uuid.uuid4())
        init_msg = {
            "jsonrpc": "2.0",
            "id": init_id,
            "method": "initialize",
            "params": {
                "protocolVersion": _PROTOCOL_VERSION,
                "clientInfo": _CLIENT_INFO,
                "capabilities": {},
            },
        }
        process.stdin.write(_serialize_message(init_msg))
        await process.stdin.drain()
        init_response = await _read_until_response(process.stdout, init_id, deadline)
        if "error" in init_response:
            err = init_response["error"]
            msg = (
                f"MCP `{server_name}` initialize failed: "
                f"{err.get('message', err)}"
            )
            audit_log(
                "mcp_stdio_call_error",
                {**audit_payload, "error": "initialize_failed", "details": str(err)},
            )
            return msg

        # 2) notifications/initialized (no response expected)
        notif = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        process.stdin.write(_serialize_message(notif))
        await process.stdin.drain()

        # 3) tools/call
        call_id = str(uuid.uuid4())
        call_msg = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        process.stdin.write(_serialize_message(call_msg))
        await process.stdin.drain()
        call_response = await _read_until_response(process.stdout, call_id, deadline)

        if "error" in call_response:
            err = call_response["error"]
            msg = (
                f"MCP `{server_name}` tool `{tool_name}` failed: "
                f"{err.get('message', err)}"
            )
            audit_log(
                "mcp_stdio_call_error",
                {**audit_payload, "error": "tool_error", "details": str(err)},
            )
            return msg

        result = call_response.get("result")
        text = _extract_text(result)
        audit_log(
            "mcp_stdio_call_completed",
            {**audit_payload, "result_chars": len(text)},
        )
        return text or f"(MCP `{server_name}` tool `{tool_name}` returned no content.)"

    except asyncio.TimeoutError:
        msg = (
            f"MCP `{server_name}` tool `{tool_name}` timed out after {timeout:.0f}s. "
            "The server is taking too long to respond — check the install or "
            "the requested arguments."
        )
        audit_log("mcp_stdio_call_error", {**audit_payload, "error": "timeout"})
        return msg
    except Exception as exc:
        msg = f"MCP `{server_name}` tool `{tool_name}` errored: {exc!r}"
        audit_log("mcp_stdio_call_error", {**audit_payload, "error": str(exc)})
        return msg
    finally:
        try:
            if process.stdin and not process.stdin.is_closing():
                process.stdin.close()
        except Exception:
            pass
        try:
            await asyncio.wait_for(process.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.wait()
            except Exception:
                pass
        stderr_task.cancel()
        try:
            await stderr_task
        except (asyncio.CancelledError, Exception):
            pass


def _quote_for_cmd(arg: str) -> str:
    """Quote a single argument for cmd.exe execution (Windows)."""
    if not arg:
        return '""'
    if not any(c in arg for c in (" ", "\t", "&", "|", "(", ")", "<", ">", "^", '"')):
        return arg
    escaped = arg.replace('"', '\\"')
    return f'"{escaped}"'


__all__ = [
    "call_stdio_mcp_tool",
    "is_command_available",
]
