"""MCP client: connects to the MCP servers the agent uses and loads their tools.

To use another MCP server, add an entry to the dictionary in `load_tools`.
"""
import os

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


async def load_tools() -> list[BaseTool]:
    """Return the tools from every configured MCP server, as LangChain tools."""
    # MCP_URL is read here rather than at import time, so values from .env apply.
    client = MultiServerMCPClient(
        {
            "free_apis": {
                "url": os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp"),
                "transport": "streamable_http",
            }
        }
    )
    return await client.get_tools()
