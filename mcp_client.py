"""MCP client: connects to the MCP server the agent uses and loads its tools.

The agent passes the URL to connect to: the AgentDNA provenance relay's URL for
the server (see agent.py), so every tool call is signed on the way through.
"""
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient


async def load_tools(mcp_url: str) -> list[BaseTool]:
    """Return the tools of the MCP server at mcp_url, as LangChain tools."""
    client = MultiServerMCPClient(
        {
            "free_apis": {
                "url": mcp_url,
                "transport": "streamable_http",
            }
        }
    )
    return await client.get_tools()
