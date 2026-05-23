"""
AgentSystem — Human approval handler.

Provides a simple console-based approval flow for outbound actions.
In production (cloud/Streamlit), auto-approves when no TTY is present
since the agent handles human-in-the-loop via chat messages.
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

    Interactive mode (local CLI with TTY): prompts via input().
    Non-interactive mode (cloud/Streamlit): auto-approves —
    the orchestrator's system prompt enforces approval via chat.
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

        if not self._interactive:
            logger.info(
                "Non-interactive mode (cloud/Streamlit) — auto-approving %s.%s. "
                "Human-in-the-loop handled by chat interface.",
                agent_name, action,
            )
            return True, None

        print("\n" + "=" * 60)
        print(f"🔒 APPROVAL REQUIRED")
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
