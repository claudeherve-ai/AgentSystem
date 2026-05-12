"""
AgentSystem — Human approval handler.

Provides a simple console-based approval flow for outbound actions.
In production, this could be replaced with a web UI, Telegram bot, or email notification.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class HumanApproval:
    """
    Handles human-in-the-loop approval for sensitive agent actions.
    Currently uses console input; extensible to other interfaces.
    """

    def __init__(self, auto_approve_all: bool = False):
        self._auto_approve_all = auto_approve_all

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

        print("\n" + "=" * 60)
        print(f"🔒 APPROVAL REQUIRED")
        print(f"   Agent:   {agent_name}")
        print(f"   Action:  {action}")
        if details:
            # Truncate very long details for display
            display = details[:500] + "..." if len(details) > 500 else details
            print(f"   Details: {display}")
        print("=" * 60)

        # Run input in executor to avoid blocking the async loop
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
