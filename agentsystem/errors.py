"""Structured error envelope and provider-exception sanitization.

Every failure that reaches the API boundary is rendered as a single, stable
JSON shape carrying a ``request_id`` for correlation. Raw provider exceptions
(Azure OpenAI, PostgreSQL, Redis, Blob, the model SDK) are NEVER serialized to
the client — only a safe, mapped code + generic message.

Envelope shape::

    {
      "error": {
        "code": "provider_unavailable",
        "message": "An upstream provider is temporarily unavailable.",
        "request_id": "req_ab12...",
        "details": {...}          # optional, always safe/redacted
      }
    }
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

# ── Safe, client-facing messages keyed by stable error code ─────────────────
# The message is intentionally generic. Operators get the real cause from logs
# + telemetry correlated by request_id; the client never sees provider text.
_SAFE_MESSAGES: dict[str, str] = {
    "validation_error": "The request was invalid.",
    "unauthorized": "Authentication is required or has failed.",
    "forbidden": "You do not have access to this resource.",
    "not_found": "The requested resource was not found.",
    "conflict": "The request conflicts with the current state.",
    "rate_limited": "Too many requests. Please retry later.",
    "provider_unavailable": "An upstream provider is temporarily unavailable.",
    "dependency_unavailable": "A required backend dependency is unavailable.",
    "sandbox_unavailable": "Secure code execution is not available.",
    "internal_error": "An internal error occurred.",
}

# ── HTTP status mapping (kept here so the API layer never re-derives it) ─────
_STATUS_BY_CODE: dict[str, int] = {
    "validation_error": 400,
    "unauthorized": 401,
    "forbidden": 403,
    "not_found": 404,
    "conflict": 409,
    "rate_limited": 429,
    "provider_unavailable": 503,
    "dependency_unavailable": 503,
    "sandbox_unavailable": 503,
    "internal_error": 500,
}


@dataclass(frozen=True, slots=True)
class ErrorEnvelope:
    """Serializable, client-safe error body with a correlation id."""

    code: str
    message: str
    request_id: str
    status_code: int = 500
    details: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "error": {
                "code": self.code,
                "message": self.message,
                "request_id": self.request_id,
            }
        }
        if self.details:
            body["error"]["details"] = self.details
        return body


# ── Domain exception hierarchy ──────────────────────────────────────────────
class AgentSystemError(Exception):
    """Base class for all AgentSystem domain errors.

    Carries a stable ``code`` (mapped to a safe message + HTTP status) and an
    optional ``details`` dict that MUST already be safe to expose.
    """

    code: str = "internal_error"

    def __init__(
        self,
        message: str = "",
        *,
        details: Optional[dict[str, Any]] = None,
        code: Optional[str] = None,
    ) -> None:
        super().__init__(message or self.code)
        self._message = message
        self.details = details
        if code:
            self.code = code

    @property
    def status_code(self) -> int:
        return _STATUS_BY_CODE.get(self.code, 500)

    def safe_message(self) -> str:
        return _SAFE_MESSAGES.get(self.code, _SAFE_MESSAGES["internal_error"])


class ValidationError(AgentSystemError):
    code = "validation_error"


class UnauthorizedError(AgentSystemError):
    code = "unauthorized"


class ForbiddenError(AgentSystemError):
    code = "forbidden"


class NotFoundError(AgentSystemError):
    code = "not_found"


class ConflictError(AgentSystemError):
    code = "conflict"


class RateLimitedError(AgentSystemError):
    code = "rate_limited"


class DependencyUnavailableError(AgentSystemError):
    code = "dependency_unavailable"


class SandboxUnavailableError(AgentSystemError):
    code = "sandbox_unavailable"


class ProviderError(AgentSystemError):
    """Wraps an upstream provider failure. The original text is dropped."""

    code = "provider_unavailable"


def error_envelope(
    exc: Exception,
    request_id: str,
    *,
    details: Optional[dict[str, Any]] = None,
) -> ErrorEnvelope:
    """Convert any exception into a safe :class:`ErrorEnvelope`.

    Known :class:`AgentSystemError` types keep their mapped code/status. Every
    other exception collapses to ``internal_error`` — the raw message is never
    surfaced, so provider stack traces / secrets cannot leak.
    """
    if isinstance(exc, AgentSystemError):
        return ErrorEnvelope(
            code=exc.code,
            message=exc.safe_message(),
            request_id=request_id,
            status_code=exc.status_code,
            details=details if details is not None else exc.details,
        )
    return ErrorEnvelope(
        code="internal_error",
        message=_SAFE_MESSAGES["internal_error"],
        request_id=request_id,
        status_code=500,
        details=details,
    )


def sanitize_exception(exc: Exception) -> ProviderError:
    """Wrap a raw provider/SDK exception so callers never re-raise its text.

    Use this at every boundary that talks to Azure OpenAI, PostgreSQL, Redis,
    Blob storage, or the Durable Task scheduler. The returned error exposes only
    a generic ``provider_unavailable`` code; the original exception is chained
    for server-side logging (``raise sanitize_exception(e) from e``) but its
    message is not part of the client envelope.
    """
    if isinstance(exc, ProviderError):
        return exc
    return ProviderError("upstream provider failure")


__all__ = [
    "AgentSystemError",
    "ConflictError",
    "DependencyUnavailableError",
    "ErrorEnvelope",
    "ForbiddenError",
    "NotFoundError",
    "ProviderError",
    "RateLimitedError",
    "SandboxUnavailableError",
    "UnauthorizedError",
    "ValidationError",
    "error_envelope",
    "sanitize_exception",
]
