
import pytest
import os
import asyncio
from tools.mcp_tools import github_search_repositories, github_get_file_contents, github_search_code

@pytest.mark.asyncio
async def test_github_mcp_integration_deep():
    """
    Tough multi-step integration test for GitHub MCP:
    1. Search for a specific high-profile repo (demonstrates connectivity & auth).
    2. Read a specific file from that repo (demonstrates session handling & path resolution).
    3. Search for a specific code pattern within that repo (demonstrates advanced tool usage).
    """
    # Check for GITHUB_TOKEN
    if not (os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")):
        pytest.skip("GITHUB_TOKEN not set, skipping integration test.")

    # Step 1: Search for the official MCP Python SDK repo
    print("\n[Step 1] Searching for modelcontextprotocol/python-sdk...")
    search_result = await github_search_repositories(query="modelcontextprotocol/python-sdk")
    assert "modelcontextprotocol/python-sdk" in search_result, f"Failed to find repo. Result: {search_result}"

    # Step 2: Get the content of README.md from that repo
    print("[Step 2] Fetching README.md from modelcontextprotocol/python-sdk...")
    file_content = await github_get_file_contents(
        owner="modelcontextprotocol",
        repo="python-sdk",
        path="README.md"
    )
    assert "# MCP Python SDK" in file_content or "Model Context Protocol" in file_content, \
        f"README content looks wrong or fetch failed. Result: {file_content[:200]}"

    # Step 3: Search for specific internal class usage in the code
    print("[Step 3] Searching for 'McpServer' in the repo code...")
    code_search = await github_search_code(query="McpServer repo:modelcontextprotocol/python-sdk")
    assert "McpServer" in code_search or "total_count" in code_search, f"Code search failed. Result: {code_search}"

    print("\n✅ GitHub MCP integration test PASSED.")

if __name__ == "__main__":
    asyncio.run(test_github_mcp_integration_deep())
