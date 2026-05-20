"""
AgentSystem — Rate Limiting Middleware

Simple in-memory token bucket rate limiter.
Production should use Redis-backed implementation.

Environment variables:
    RATE_LIMIT_REQUESTS  — Max requests per window (default: 60)
    RATE_LIMIT_WINDOW    — Window in seconds (default: 60)
    RATE_LIMIT_ENABLED   — Set to 'false' to disable
"""
import os
import time
import logging
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("agentsystem.ratelimit")

ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
MAX_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "60"))
WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# In-memory store: {client_ip: [(timestamp,), ...]}
_buckets: dict[str, list[float]] = defaultdict(list)


def _clean_bucket(ip: str, now: float) -> int:
    """Remove expired entries and return count of remaining."""
    bucket = _buckets[ip]
    cutoff = now - WINDOW_SECONDS
    _buckets[ip] = [t for t in bucket if t > cutoff]
    return len(_buckets[ip])


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not ENABLED:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()

        count = _clean_bucket(client_ip, now)

        if count >= MAX_REQUESTS:
            retry_after = int(WINDOW_SECONDS - (now - _buckets[client_ip][0]))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded. Try again in {retry_after}s.",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        _buckets[client_ip].append(now)
        return await call_next(request)
