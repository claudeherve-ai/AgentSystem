
import os
import asyncio
import uuid
import httpx
import json

async def test_github_mcp():
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
    if not token:
        print("MISSING GITHUB_TOKEN")
        return

    url = "https://api.githubcopilot.com/mcp/"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AgentSystem-Test/1.0"
    }

    # Test with current 1.0.0
    print("--- Testing with protocolVersion: 1.0.0 ---")
    body_1 = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": "1.0.0",
            "capabilities": {},
            "clientInfo": {"name": "Test", "version": "1.0"}
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=body_1)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")

    # Test with standard 2024-11-05
    print("\n--- Testing with protocolVersion: 2024-11-05 ---")
    body_2 = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "Test", "version": "1.0"}
        }
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=body_2)
        print(f"Status: {resp.status_code}")
        print(f"Body: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_github_mcp())
