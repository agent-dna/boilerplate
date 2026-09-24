"""Single-agent LangGraph workflow that uses tools served by mcp_server.py.

Graph:  START -> agent -> (tool calls?) -> tools -> agent -> ... -> END

Run (in a second terminal, after starting mcp_server.py):  python agent.py
One-shot:  python agent.py "What's the weather in Tokyo?"
"""
import asyncio
import json
import os
import re
import sys
import uuid

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

SYSTEM_PROMPT = (
    "You are a helpful research assistant. Use the available tools to look up "
    "weather, Wikipedia summaries, country facts and word definitions. "
    "Only use tools when needed, and answer concisely based on tool results."
)

# Some OpenAI-compatible servers return a tool call as plain text, e.g.
# '<tools>{"name": "define_word", "arguments": {"word": "x"}}</tools>',
# instead of in the structured tool_calls field.
TEXT_TOOL_CALL_TAG = re.compile(r"<(?:tools|tool_call)>\s*")


def parse_text_tool_calls(text: str, tool_names: set[str]) -> list[dict]:
    """Extract tool calls a model wrote as text; returns [] if there are none."""
    calls = []
    for tag in TEXT_TOOL_CALL_TAG.finditer(text):
        try:
            payload, _ = json.JSONDecoder().raw_decode(text, tag.end())
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("name") not in tool_names:
            continue
        args = payload.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                continue
        if isinstance(args, dict):
            calls.append({"name": payload["name"], "args": args,
                          "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"})
    return calls


async def main():
    # --- LLM provider (switch via LLM_PROVIDER env var: ollama | gemini | openai | openai_compatible) ---
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = os.getenv("LLM_MODEL")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model=model or "gemini-2.5-flash", temperature=0)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model or "gpt-4o-mini", temperature=0)
    elif provider == "openai_compatible":
        from langchain_openai import ChatOpenAI

        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        if not base_url:
            raise ValueError("OPENAI_COMPATIBLE_BASE_URL is required for provider 'openai_compatible'")
        if not model:
            raise ValueError("LLM_MODEL is required for provider 'openai_compatible'")
        llm = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY"),
            temperature=0,
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        llm = ChatOllama(
            model=model or "llama3.1",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    # --- Tools from the MCP server ---
    client = MultiServerMCPClient(
        {
            "free_apis": {
                "url": os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp"),
                "transport": "streamable_http",
            }
        }
    )
    tools = await client.get_tools()
    print(f"Loaded MCP tools: {[t.name for t in tools]}")
    llm_with_tools = llm.bind_tools(tools)
    tool_names = {t.name for t in tools}

    # --- The single agent node ---
    async def agent(state: MessagesState):
        response = await llm_with_tools.ainvoke(
            [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        )
        if not response.tool_calls and isinstance(response.content, str):
            text_calls = parse_text_tool_calls(response.content, tool_names)
            if text_calls:
                response = AIMessage(content="", tool_calls=text_calls, id=response.id)
        return {"messages": [response]}

    # --- Graph ---
    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)  # -> "tools" or END
    builder.add_edge("tools", "agent")
    graph = builder.compile()

    # --- One-shot mode: python agent.py "your question" ---
    if len(sys.argv) > 1:
        result = await graph.ainvoke(
            {"messages": [("user", " ".join(sys.argv[1:]))]},
            {"recursion_limit": 12},
        )
        print(f"\nagent> {result['messages'][-1].content}")
        return



if __name__ == "__main__":
    asyncio.run(main())
