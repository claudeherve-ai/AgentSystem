import os
import sys
import logging
import asyncio
from msal import PublicClientApplication

# Client ID for the AgentSystem (using common multitenant ID)
CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46" # Standard Microsoft CLI ID or your own
SCOPES = ["Mail.Read", "Mail.Send", "Calendars.Read", "User.Read"]

async def graph_login():
    """Initiates device code flow and returns the message for the user."""
    app = PublicClientApplication(CLIENT_ID, authority="https://login.microsoftonline.com/common")
    
    flow = app.initiate_device_flow(scopes=SCOPES)
    if "user_code" not in flow:
        return "Failed to initiate device flow. Check network/client ID."
    
    # We return the message directly so the agent can show it to the user
    return flow["message"]

async def graph_read_inbox(*args, **kwargs):
    await asyncio.sleep(0.1)
    return "Mailbox access required. Please run 'link_account' first."

async def graph_get_upcoming_events(*args, **kwargs):
    await asyncio.sleep(0.1)
    return "Calendar access required. Please run 'link_account' first."

def create_graph_client(credential):
    return None
