"""
AgentSystem — Guardrails engine.

Enforces approval gates, rate limits, content safety, and audit logging.
All outbound agent actions pass through this module.
"""

import asyncio
import logging
import re
import time
from collections import defaultdict
from typing import Any

from config import get_guardrails_config

logger = logging.getLogger(__name__)


class ApprovalRequired(Exception):
    """Raised when an action requires human approval."""
    def __init__(self, action: str, details: str = ""):
        self.action = action
        self.details = details
        super().__init__(f"Approval required for: {action}. {details}")


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""
    def __init__(self, resource: str, limit: int, window: str):
        super().__init__(f"Rate limit exceeded: {resource} ({limit}/{window})")


class Guardrails:
    """Central guardrails engine for the agent system."""

    def __init__(self):
        self._config = get_guardrails_config()
        self._rate_counters: dict[str, list[float]] = defaultdict(list)
        self._approval_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    @property
    def always_approve_actions(self) -> list[str]:
        gates = self._config.get("approval_gates", {})
        return gates.get("always_approve", [])

    @property
    def auto_approve_actions(self) -> list[str]:
        gates = self._config.get("approval_gates", {})
        return gates.get("auto_approve", [])

    def requires_approval(self, action: str) -> bool:
        """Check if an action requires human approval."""
        return action in self.always_approve_actions

    def is_auto_approved(self, action: str) -> bool:
        """Check if an action can proceed without human approval."""
        return action in self.auto_approve_actions

    async def check_approval(self, action: str, details: str = "") -> bool:
        """
        Check if an action is approved. Returns True if auto-approved.
        Raises ApprovalRequired if human must approve.
        """
        if self.is_auto_approved(action):
            logger.info(f"Auto-approved action: {action}")
            return True

        if self.requires_approval(action):
            logger.warning(f"Action requires human approval: {action} — {details}")
            raise ApprovalRequired(action, details)

        # Unknown actions default to requiring approval
        logger.warning(f"Unknown action '{action}' — defaulting to approval required")
        raise ApprovalRequired(action, details)

    def check_rate_limit(self, resource: str, limit: int, window_seconds: int = 3600):
        """
        Check and enforce rate limits. Raises RateLimitExceeded if over limit.
        """
        now = time.time()
        cutoff = now - window_seconds

        # Prune old entries
        self._rate_counters[resource] = [
            t for t in self._rate_counters[resource] if t > cutoff
        ]

        if len(self._rate_counters[resource]) >= limit:
            window_label = "hour" if window_seconds == 3600 else f"{window_seconds}s"
            raise RateLimitExceeded(resource, limit, window_label)

        self._rate_counters[resource].append(now)

    def check_email_rate(self):
        """Enforce email rate limits."""
        limits = self._config.get("rate_limits", {})
        self.check_rate_limit("emails_hour", limits.get("emails_per_hour", 20), 3600)
        self.check_rate_limit("emails_day", limits.get("emails_per_day", 100), 86400)

    def check_social_rate(self):
        """Enforce social media rate limits."""
        limits = self._config.get("rate_limits", {})
        self.check_rate_limit("social_hour", limits.get("social_posts_per_hour", 5), 3600)
        self.check_rate_limit("social_day", limits.get("social_posts_per_day", 10), 86400)

    def redact_sensitive(self, text: str) -> str:
        """Redact sensitive patterns from text (for logging only)."""
        safety = self._config.get("content_safety", {})
        patterns = safety.get("redact_patterns", [])
        redacted = text
        for pattern in patterns:
            try:
                redacted = re.sub(pattern, "[REDACTED]", redacted)
            except re.error:
                continue
        return redacted

    def check_content_length(self, text: str) -> bool:
        """Check if outbound content is within length limits."""
        safety = self._config.get("content_safety", {})
        max_len = safety.get("max_outbound_length", 5000)
        return len(text) <= max_len
