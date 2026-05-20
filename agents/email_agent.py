from typing import Annotated


async def relink_account() -> str:
    """Run this tool whenever Microsoft connection is missing or failing.
    Initiates the device-code login flow — gives you a URL and code to enter."""
    from tools.graph_tools import graph_login

    return await graph_login()


async def finish_link() -> str:
    """Call this AFTER you have completed the browser login.
    Polls the device-code endpoint to acquire and cache the access token."""
    from tools.graph_tools import graph_finish_login

    return await graph_finish_login()


async def sign_out() -> str:
    """Remove cached Microsoft credentials so the next request re-authenticates."""
    from tools.graph_tools import graph_logout

    return await graph_logout()


async def check_inbox(count: int = 10, unread_only: bool = True) -> str:
    """Reads latest unread emails. Returns instructions if auth is missing."""
    from tools.graph_tools import graph_read_inbox

    res = await graph_read_inbox(count=count, unread_only=unread_only)
    if res == "ERR_AUTH_REQUIRED":
        return "Account not linked. Run 'relink_account' to authenticate."
    if isinstance(res, str) and res.startswith("ERR"):
        return f"Session expired. Run 'relink_account'."
    if isinstance(res, str):
        return f"{res}"
    if not res:
        return "Mailbox clear — no unread messages."

    lines = ["Latest unread emails:"]
    for e in res:
        status = "[UNREAD]" if e["is_unread"] else "[READ]"
        lines.append(f"- {status} {e['subject']} (From: {e['from_name']})")
    return "\n".join(lines)


EMAIL_TOOLS = [relink_account, finish_link, sign_out, check_inbox]