"""Distributed rate limiting.

Two concrete limiters implement a shared :class:`RateLimiter` interface:

* :class:`InMemoryRateLimiter` — process-local fixed window. Used for local/dev
  and injected by tests. Deterministic and dependency-free.
* :class:`RedisRateLimiter` — shared fixed window backed by Azure Managed Redis.
  Supports Microsoft Entra token authentication (redis-py credential provider)
  and TLS. A Redis outage raises :class:`DependencyUnavailableError` on the
  request path (fail closed — never a success-shaped fallback) and reports
  unhealthy so readiness fails.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from agentsystem.errors import DependencyUnavailableError
from agentsystem.settings import Settings, get_settings

logger = logging.getLogger("agentsystem.ratelimit")


@dataclass(frozen=True, slots=True)
class RateDecision:
    allowed: bool
    retry_after: int = 0
    remaining: int = 0


class RateLimiter(ABC):
    """Backend-agnostic rate limiter."""

    @abstractmethod
    async def allow(
        self, key: str, *, max_requests: Optional[int] = None
    ) -> RateDecision:
        ...

    @abstractmethod
    async def health(self) -> bool:
        ...

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None


class InMemoryRateLimiter(RateLimiter):
    """Process-local fixed-window limiter (single replica / tests)."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._buckets: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    async def allow(
        self, key: str, *, max_requests: Optional[int] = None
    ) -> RateDecision:
        now = time.monotonic()
        cutoff = now - self._window
        limit = max_requests or self._max
        with self._lock:
            bucket = [t for t in self._buckets.get(key, []) if t > cutoff]
            if len(bucket) >= limit:
                oldest = bucket[0]
                retry_after = max(1, int(self._window - (now - oldest)))
                self._buckets[key] = bucket
                return RateDecision(False, retry_after=retry_after, remaining=0)
            bucket.append(now)
            self._buckets[key] = bucket
            return RateDecision(True, remaining=limit - len(bucket))

    async def health(self) -> bool:
        return True


class _EntraRedisCredentialProvider:
    """redis-py credential provider that mints Entra tokens on demand.

    Implements both sync and async ``get_credentials`` so redis-py can refresh
    the token when it reconnects. The username is the token's ``oid`` when
    available; the password is the access token.
    """

    def __init__(self, scope: str, username: str) -> None:
        self._scope = scope
        self._username = username

    def get_credentials(self):  # pragma: no cover - sync path unused in async app
        from azure.identity import DefaultAzureCredential

        credential = DefaultAzureCredential()
        try:
            token = credential.get_token(self._scope)
            return (self._username, token.token)
        finally:
            close = getattr(credential, "close", None)
            if close:
                close()

    async def get_credentials_async(self):
        from azure.identity.aio import DefaultAzureCredential

        credential = DefaultAzureCredential()
        try:
            token = await credential.get_token(self._scope)
            return (self._username, token.token)
        finally:
            await credential.close()


class RedisRateLimiter(RateLimiter):
    """Shared fixed-window limiter backed by Redis (Entra + TLS aware)."""

    def __init__(
        self,
        url: str,
        max_requests: int,
        window_seconds: int,
        *,
        use_entra: bool = False,
        entra_username: str = "",
        tls: bool = True,
        entra_scope: str = "https://redis.azure.com/.default",
    ) -> None:
        if not url:
            raise DependencyUnavailableError("REDIS_URL is not configured")
        self._url = url
        self._max = max_requests
        self._window = window_seconds
        self._use_entra = use_entra
        self._entra_username = entra_username
        self._tls = tls
        self._entra_scope = entra_scope
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        import redis.asyncio as redis

        kwargs: dict = {"decode_responses": True}
        if self._tls and self._url.startswith("rediss://") is False and "ssl" not in self._url:
            kwargs["ssl"] = True
        if self._use_entra:
            if not self._entra_username:
                raise DependencyUnavailableError(
                    "REDIS_USERNAME is required for Entra authentication"
                )
            kwargs["credential_provider"] = _EntraRedisCredentialProvider(
                self._entra_scope,
                self._entra_username,
            )
        self._client = redis.from_url(self._url, **kwargs)
        return self._client

    async def allow(
        self, key: str, *, max_requests: Optional[int] = None
    ) -> RateDecision:
        client = self._get_client()
        window_start = int(time.time() // self._window) * self._window
        redis_key = f"rl:{{{key}}}:{window_start}"
        limit = max_requests or self._max
        try:
            count = await client.incr(redis_key)
            if count == 1:
                await client.expire(redis_key, self._window)
        except Exception as exc:  # noqa: BLE001
            # Fail closed: a limiter outage must not silently allow floods, and
            # must surface so readiness degrades.
            logger.error("Redis rate limiter error: %s", type(exc).__name__)
            raise DependencyUnavailableError("rate limiter unavailable") from exc
        if count > limit:
            retry_after = self._window - (int(time.time()) - window_start)
            return RateDecision(False, retry_after=max(1, retry_after), remaining=0)
        return RateDecision(True, remaining=max(0, limit - count))

    async def health(self) -> bool:
        try:
            client = self._get_client()
            return bool(await client.ping())
        except Exception as exc:  # noqa: BLE001 - health probe must not raise
            logger.warning("Redis ping failed: %s", type(exc).__name__)
            return False

    async def aclose(self) -> None:
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._client = None


_limiter: Optional[RateLimiter] = None


def build_rate_limiter(settings: Optional[Settings] = None) -> RateLimiter:
    """Construct the configured rate limiter.

    Redis is used when enabled; otherwise an in-memory limiter is returned. In
    production, ``REDIS_ENABLED=true`` without a URL raises so startup fails
    closed rather than silently using a per-replica in-memory limiter.
    """
    settings = settings or get_settings()
    if settings.redis_enabled:
        return RedisRateLimiter(
            settings.redis_url,
            settings.rate_limit_requests,
            settings.rate_limit_window,
            use_entra=settings.redis_use_entra,
            entra_username=settings.redis_username,
            tls=settings.redis_tls,
            entra_scope=settings.redis_scope,
        )
    if settings.is_production:
        logger.warning(
            "REDIS_ENABLED is false in production — rate limits are per-replica "
            "only. Enable Redis for shared limits."
        )
    return InMemoryRateLimiter(
        settings.rate_limit_requests, settings.rate_limit_window
    )


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is None:
        _limiter = build_rate_limiter()
    return _limiter


def set_rate_limiter(limiter: Optional[RateLimiter]) -> None:
    """Inject/replace the process rate limiter (tests / local)."""
    global _limiter
    _limiter = limiter


__all__ = [
    "InMemoryRateLimiter",
    "RateDecision",
    "RateLimiter",
    "RedisRateLimiter",
    "build_rate_limiter",
    "get_rate_limiter",
    "set_rate_limiter",
]
