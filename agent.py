"""Single-agent LangGraph workflow that uses tools served by mcp_server.py.

Graph:  START -> agent -> END

The agent node is built with LangChain's `create_agent`, which runs the model
and calls tools in a loop until the model answers without requesting a tool.

Run (after starting mcp_server.py):  python agent.py "What's the weather in Tokyo?"
"""
import asyncio
import json
import os
import re
import sys
import uuid

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import after_model
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from mcp_client import load_tools

load_dotenv()

SYSTEM_PROMPT = (
    "You are a helpful research assistant. Use the available tools to look up "
    "weather, Wikipedia summaries, country facts and word definitions. "
    "Only use tools when needed, and answer concisely based on tool results."
)

# Each lookup round takes three graph steps (model, text-tool-call check, tools),
# so this allows about five rounds per question.
RECURSION_LIMIT = 18

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


def create_llm():
    """Create the chat model selected by LLM_PROVIDER: ollama | gemini | openai | openai_compatible."""
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    model = os.getenv("LLM_MODEL")

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(model=model or "gemini-2.5-flash", temperature=0)
    if provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=model or "gpt-4o-mini", temperature=0)
    if provider == "openai_compatible":
        from langchain_openai import ChatOpenAI

        base_url = os.getenv("OPENAI_COMPATIBLE_BASE_URL")
        if not base_url:
            raise ValueError("OPENAI_COMPATIBLE_BASE_URL is required for provider 'openai_compatible'")
        if not model:
            raise ValueError("LLM_MODEL is required for provider 'openai_compatible'")
        return ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=os.getenv("OPENAI_COMPATIBLE_API_KEY"),
            temperature=0,
        )
    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model or "llama3.1",
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            temperature=0,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


async def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python agent.py "your question"')

    # --- Tools from the MCP server (see mcp_client.py) ---
    tools = await load_tools()
    tool_names = {t.name for t in tools}

    # Runs after every model call. If the model wrote its tool calls as text,
    # replace its message (same id) with one carrying real tool calls, so the
    # agent goes on to run the tools.
    @after_model
    def recover_text_tool_calls(state, runtime):
        message = state["messages"][-1]
        if not isinstance(message, AIMessage) or message.tool_calls or not isinstance(message.content, str):
            return None
        text_calls = parse_text_tool_calls(message.content, tool_names)
        if not text_calls:
            return None
        return {"messages": [AIMessage(content="", tool_calls=text_calls, id=message.id)]}

    # --- The agent node: create_agent runs the model + tools loop inside it ---
    agent = create_agent(
        model=create_llm(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[recover_text_tool_calls],
    )

    # --- Graph ---
    builder = StateGraph(MessagesState)
    builder.add_node("agent", agent)
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    graph = builder.compile()

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": " ".join(sys.argv[1:])}]},
        {"recursion_limit": RECURSION_LIMIT},
    )
    print(f"\nagent> {result['messages'][-1].content}")


if __name__ == "__main__":
    asyncio.run(main())
