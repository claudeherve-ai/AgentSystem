from typing import Annotated


async def link_account() -> str:
    """Run this to get the Microsoft Device Code for linking your Email and Calendar.
    Starts a background poller so you don't have to wait for the token."""
    from tools.graph_tools import graph_login
    return await graph_login()


# Alias for consistency with other tool names
async def relink_account() -> str:
    """Run this tool whenever Microsoft connection is missing or failing.
    Initiates the device-code login flow — gives you a URL and code to enter."""
    from tools.graph_tools import graph_login
    return await graph_login()


async def finish_link() -> str:
    """Call this AFTER you have completed the browser login.
    Checks whether the background poller has acquired the token.  Instant — no wait."""
    from tools.graph_tools import graph_finish_login
    return await graph_finish_login()


async def sign_out() -> str:
    """Remove cached Microsoft credentials so the next request re-authenticates."""
    from tools.graph_tools import graph_logout
    return await graph_logout()


async def read_inbox(count: int = 10) -> str:
    """Read the latest unread emails. Returns instructions if auth is missing."""
    from tools.graph_tools import graph_read_inbox
    res = await graph_read_inbox(count=count, unread_only=True)
    if res == "ERR_AUTH_REQUIRED":
        return "Account not linked. Run 'link_account' to authenticate."
    if isinstance(res, str) and res.startswith("ERR"):
        return f"Session expired. Run 'link_account'."
    if isinstance(res, str):
        return res
    if not res:
        return "Mailbox clear — no unread messages."
    lines = ["Latest unread emails:"]
    for e in res:
        status = "[UNREAD]" if e["is_unread"] else "[READ]"
        lines.append(f"- {status} {e['subject']} (From: {e['from_name']})")
    return "\n".join(lines)


async def check_inbox(count: int = 10, unread_only: bool = True) -> str:
    """Reads latest unread emails. Convenience alias for read_inbox."""
    return await read_inbox(count=count)


EMAIL_TOOLS = [
    link_account,
    relink_account,
    finish_link,
    sign_out,
    read_inbox,
    check_inbox,
]
