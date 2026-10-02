"""Code-execution sandbox: Azure Container Apps Dynamic Sessions + fail-closed.

Cloud Python execution is allowed ONLY through Azure Container Apps Dynamic
Sessions (isolated, network-restricted, per-execution). There is no host
subprocess fallback in a container or production runtime.

The pure function :func:`resolve_sandbox_engine` decides which engine a request
uses. It guarantees:

* ``CODE_SANDBOX_MODE=auto`` NEVER selects a host subprocess in a container or
  in production — it prefers Dynamic Sessions, then a local Docker sandbox, and
  otherwise **refuses** (fail closed).
* The explicit ``subprocess`` mode is refused in a container / production.
* ``dynamic_sessions`` and ``docker`` modes fail closed when their backend is
  unavailable.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from agentsystem.errors import SandboxUnavailableError
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.sandbox")

# Engine outcomes returned by resolve_sandbox_engine.
ENGINE_DOCKER = "docker"
ENGINE_DYNAMIC_SESSIONS = "dynamic_sessions"
ENGINE_SUBPROCESS = "subprocess"
ENGINE_OFF = "off"
ENGINE_REFUSE = "refuse"


def resolve_sandbox_engine(
    mode: str,
    *,
    in_container: bool,
    is_production: bool,
    docker_available: bool,
    dynamic_sessions_configured: bool,
) -> str:
    """Decide the execution engine for a code-run request (pure, testable).

    Returns one of ``docker`` / ``dynamic_sessions`` / ``subprocess`` / ``off``
    / ``refuse``. ``refuse`` means fail closed with a user-safe explanation.
    """
    cloud_locked = in_container or is_production

    if mode == "off":
        return ENGINE_OFF

    if mode == "dynamic_sessions":
        return ENGINE_DYNAMIC_SESSIONS if dynamic_sessions_configured else ENGINE_REFUSE

    if mode == "docker":
        return ENGINE_DOCKER if docker_available else ENGINE_REFUSE

    if mode == "subprocess":
        # Explicit host subprocess is permitted ONLY outside a container/prod.
        return ENGINE_REFUSE if cloud_locked else ENGINE_SUBPROCESS

    # mode == "auto" (or anything unknown → treated as auto, fail-closed biased)
    if dynamic_sessions_configured:
        return ENGINE_DYNAMIC_SESSIONS
    if docker_available:
        return ENGINE_DOCKER
    # The implicit subprocess fallback is REMOVED: auto never runs a host
    # subprocess. In a container/prod this is mandatory; even locally we fail
    # closed so behavior is predictable and secure by default.
    return ENGINE_REFUSE


@dataclass(frozen=True, slots=True)
class SandboxExecution:
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    engine: str = ""
    isolated: bool = False
    timed_out: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.error
        )


class CodeInterpreter(ABC):
    """Isolated code-execution backend."""

    engine: str = "abstract"

    @abstractmethod
    async def run_python(self, code: str, timeout: int = 30) -> SandboxExecution:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...


class DynamicSessionsInterpreter(CodeInterpreter):
    """Azure Container Apps Dynamic Sessions code interpreter (managed identity).

    Uses the pool management endpoint's ``/code/execute`` API with a bearer
    token scoped to ``https://dynamicsessions.io/.default``. Fails closed when
    the endpoint is not configured or the call errors — code never runs locally.
    """

    engine = "dynamic_sessions"
    _SCOPE = "https://dynamicsessions.io/.default"
    _API_VERSION = "2024-02-02-preview"

    def __init__(self, pool_endpoint: str) -> None:
        if not pool_endpoint:
            raise SandboxUnavailableError("Dynamic Sessions endpoint not configured")
        self._endpoint = pool_endpoint.rstrip("/")

    async def _token(self) -> str:
        from azure.identity.aio import DefaultAzureCredential

        credential = DefaultAzureCredential()
        try:
            token = await credential.get_token(self._SCOPE)
            return token.token
        finally:
            await credential.close()

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": "Bearer" + " " + token}

    async def run_python(self, code: str, timeout: int = 30) -> SandboxExecution:
        import httpx

        from agentsystem.context import new_id

        token = await self._token()
        identifier = new_id("sess")
        url = (
            f"{self._endpoint}/code/execute"
            f"?api-version={self._API_VERSION}&identifier={identifier}"
        )
        body = {
            "properties": {
                "codeInputType": "inline",
                "executionType": "synchronous",
                "code": code,
            }
        }
        try:
            async with httpx.AsyncClient(timeout=timeout + 10) as client:
                resp = await client.post(
                    url,
                    json=body,
                    headers=self._headers(token),
                )
            resp.raise_for_status()
            data = resp.json().get("properties", {})
            return SandboxExecution(
                stdout=str(data.get("stdout", "")),
                stderr=str(data.get("stderr", "")),
                exit_code=0 if data.get("status") == "Success" else 1,
                engine=self.engine,
                isolated=True,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed, never fall back
            logger.error(
                "Dynamic Sessions execution failed: %s", type(exc).__name__
            )
            return SandboxExecution(
                engine=self.engine,
                isolated=True,
                error="Secure cloud code execution is temporarily unavailable.",
            )

    async def health(self) -> bool:
        import httpx

        try:
            token = await self._token()
            url = (
                f"{self._endpoint}/session"
                f"?api-version={self._API_VERSION}&identifier=agentsystem-health-probe"
            )
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(url, headers=self._headers(token))
            return response.is_success or response.status_code == 404
        except Exception as exc:  # noqa: BLE001 - health probe must not raise
            logger.warning(
                "Dynamic Sessions health check failed: %s", type(exc).__name__
            )
            return False


def build_dynamic_sessions_interpreter(
    settings: Optional[Settings] = None,
) -> Optional[DynamicSessionsInterpreter]:
    """Return a Dynamic Sessions interpreter, or ``None`` when unconfigured."""
    settings = settings or get_settings()
    if not settings.dynamic_sessions_endpoint:
        return None
    return DynamicSessionsInterpreter(settings.dynamic_sessions_endpoint)


__all__ = [
    "CodeInterpreter",
    "DynamicSessionsInterpreter",
    "ENGINE_DOCKER",
    "ENGINE_DYNAMIC_SESSIONS",
    "ENGINE_OFF",
    "ENGINE_REFUSE",
    "ENGINE_SUBPROCESS",
    "SandboxExecution",
    "build_dynamic_sessions_interpreter",
    "resolve_sandbox_engine",
]
