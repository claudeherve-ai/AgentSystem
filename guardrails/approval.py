"""
AgentSystem — Human approval handler.

Resolves requests for sensitive outbound actions according to ``APPROVAL_MODE``
(see :class:`config.ApprovalConfig`):

  * ``auto`` (default) — console prompt on a TTY, otherwise auto-approve. This
    preserves the historical cloud/Streamlit behaviour where human-in-the-loop
    is handled via chat messages and a blocking ``input()`` would hang forever.
  * ``interactive`` — always require a TTY prompt; fail CLOSED when no terminal
    is attached (never silently auto-approve).
  * ``durable`` — persist a PENDING request to the approval store and block
    until a human decides via ``/api/v1/approvals`` or the wait times out. Any
    store/config failure fails CLOSED.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def _is_interactive() -> bool:
    """Check if we're running in an interactive terminal (TTY).

    Cloud environments (Docker/ACA Streamlit) have no TTY —
    input() would hang forever, so we auto-approve there.
    The agent's chat-based approval flow handles human-in-the-loop.
    """
    # Check explicit env override
    if os.environ.get("APPROVAL_REQUIRED", "").lower() in ("false", "0", "no"):
        return False
    # Check if stdin is a TTY
    return sys.stdin.isatty()


class HumanApproval:
    """
    Handles human-in-the-loop approval for sensitive agent actions.

    The behaviour is selected at call time from ``APPROVAL_MODE`` so a single
    process can switch between auto / interactive / durable without restarting,
    and so the test suite can drive each mode via ``monkeypatch``.
    """

    def __init__(self, auto_approve_all: bool = False):
        self._auto_approve_all = auto_approve_all
        self._interactive = _is_interactive()

    async def request_approval(
        self,
        agent_name: str,
        action: str,
        details: str = "",
    ) -> tuple[bool, Optional[str]]:
        """
        Request human approval for an action.

        Returns:
            (approved: bool, feedback: Optional[str])
        """
        if self._auto_approve_all:
            logger.info(f"Auto-approved (override): {agent_name}.{action}")
            return True, None

        mode = "auto"
        cfg = None
        try:
            from config import get_approval_config

            cfg = get_approval_config()
            mode = cfg.mode
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Approval config load failed: %s", exc)
            # If the operator explicitly asked for durable, fail CLOSED rather
            # than silently downgrading to auto-approve.
            if os.environ.get("APPROVAL_MODE", "").strip().lower() == "durable":
                return False, "Approval system unavailable — failing closed."
            mode = "auto"

        if mode == "durable":
            return await self._await_durable(agent_name, action, details, cfg)

        if mode == "interactive":
            if not self._interactive:
                logger.warning(
                    "Interactive approval required for %s.%s but no TTY is "
                    "attached — failing closed.",
                    agent_name, action,
                )
                return False, (
                    "Interactive approval required but no terminal is attached."
                )
            return await self._prompt_tty(agent_name, action, details)

        # mode == "auto" (default): historical behaviour.
        if not self._interactive:
            logger.info(
                "Non-interactive mode (auto) — auto-approving %s.%s. "
                "Human-in-the-loop handled by chat interface.",
                agent_name, action,
            )
            return True, None
        return await self._prompt_tty(agent_name, action, details)

    async def _prompt_tty(
        self,
        agent_name: str,
        action: str,
        details: str = "",
    ) -> tuple[bool, Optional[str]]:
        """Blocking console approval prompt (only reached when a TTY exists)."""
        print("\n" + "=" * 60)
        print("🔒 APPROVAL REQUIRED")
        print(f"   Agent:   {agent_name}")
        print(f"   Action:  {action}")
        if details:
            display = details[:500] + "..." if len(details) > 500 else details
            print(f"   Details: {display}")
        print("=" * 60)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: input("Approve? [y/n/e(dit)]: ").strip().lower(),
        )

        if response in ("y", "yes"):
            logger.info(f"Human approved: {agent_name}.{action}")
            return True, None
        elif response in ("e", "edit"):
            feedback = await loop.run_in_executor(
                None,
                lambda: input("Your feedback/edit: ").strip(),
            )
            logger.info(f"Human requested edit: {agent_name}.{action}")
            return False, feedback
        else:
            logger.info(f"Human rejected: {agent_name}.{action}")
            return False, None

    async def _await_durable(
        self,
        agent_name: str,
        action: str,
        details: str,
        cfg,
    ) -> tuple[bool, Optional[str]]:
        """Persist a PENDING approval and block until decided or timed out.

        Fails CLOSED on any store error: a sensitive action must never proceed
        just because the approval backend is unavailable.
        """
        try:
            from tools import approvals_store
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning(
                "Approval store import failed (%s) — failing closed.", exc
            )
            return False, "Approval system unavailable — failing closed."

        wait_timeout = cfg.wait_timeout_seconds if cfg else 300
        poll = cfg.poll_interval_seconds if cfg else 2.0

        row = approvals_store.create_approval(
            agent_name=agent_name,
            action=action,
            details=details,
            ttl_seconds=wait_timeout,
        )
        if row is None:
            logger.warning(
                "Could not persist approval for %s.%s — failing closed.",
                agent_name, action,
            )
            return False, "Approval system unavailable — failing closed."

        approval_id = row.id
        logger.info(
            "Durable approval %s created for %s.%s — waiting up to %ss.",
            approval_id, agent_name, action, wait_timeout,
        )

        loop = asyncio.get_event_loop()
        deadline = loop.time() + wait_timeout
        while True:
            current = approvals_store.get_approval(approval_id)
            if current is None:
                # Store became unreadable mid-wait — fail closed.
                logger.warning(
                    "Approval %s unreadable — failing closed.", approval_id
                )
                return False, "Approval system unavailable — failing closed."

            status = current.status
            if status == "approved":
                logger.info("Durable approval %s APPROVED.", approval_id)
                return True, current.feedback or None
            if status in ("rejected", "cancelled"):
                logger.info(
                    "Durable approval %s %s.", approval_id, status.upper()
                )
                return False, current.feedback or None
            if status == "expired":
                logger.info("Durable approval %s already expired.", approval_id)
                return False, (
                    "Approval timed out before a human decision was made."
                )

            # Still pending — enforce our own deadline. ``decide_approval``
            # refuses any decision past ``expires_at``, so a late approval can
            # never win this race; we simply expire and fail closed.
            remaining = deadline - loop.time()
            if remaining <= 0:
                final = approvals_store.expire_approval(approval_id)
                if final and final.status == "approved":
                    return True, final.feedback or None
                if final and final.status in ("rejected", "cancelled"):
                    return False, final.feedback or None
                logger.info("Durable approval %s timed out.", approval_id)
                return False, (
                    "Approval timed out before a human decision was made."
                )

            # Sleep no longer than the time we have left so a long poll interval
            # can never overshoot a short wait_timeout.
            await asyncio.sleep(min(poll, remaining))
