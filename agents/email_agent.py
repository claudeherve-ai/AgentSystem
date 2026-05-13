import logging
from typing import Annotated
from tools.audit import log_action

async def link_account() -> str:
    """Run this to get the Microsoft Device Code for linking your Email and Calendar."""
    from tools.graph_tools import graph_login
    return await graph_login()

async def read_inbox(count: int = 10) -> str:
    """Read the latest emails."""
    from tools.graph_tools import graph_read_inbox
    return await graph_read_inbox()

EMAIL_TOOLS = [link_account, read_inbox]
