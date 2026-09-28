"""Single-agent LangGraph workflow that uses tools served by mcp_server.py.

Graph:  START -> agent -> END

The agent node is built with LangChain's `create_agent`, which runs the model
and calls tools in a loop until the model answers without requesting a tool.

Run (after starting mcp_server.py):  python agent.py "What's the weather in Tokyo?"
"""
import asyncio
import json
import os
import sys
import uuid

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import after_model
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph

from mcp_client import load_tools
from wizard import environments
from wizard.audit_link import display_dashboard_info

from agentdna.core import AgentDNA
from pathlib import Path
from agentdna.error import RESULT_OK
from agentdna.mcp.context import agentdna_context
from agentdna.types import IntentWorkflow

load_dotenv()

SYSTEM_PROMPT = (
    "You are a helpful research assistant. Use the available tools to look up "
    "weather, Wikipedia summaries, country facts and word definitions. "
    "Only use tools when needed, and answer concisely based on tool results."
)

_HERE = Path(__file__).resolve().parent
SKILLS_FILE = _HERE / "SKILLS.md"

USER = AgentDNA(
    name=os.getenv("AGENTDNA_USER"),
    type="user",
    api_key=os.getenv("AGENTDNA_API_KEY"),
    provenance_layer_url=environments.provenance_url()
)

AGENT = AgentDNA(
    name=os.getenv("AGENTDNA_AGENT"),
    type="agent",
    api_key=os.getenv("AGENTDNA_API_KEY"),
    provenance_layer_url=environments.provenance_url(),
    agent_policy_file=SKILLS_FILE
)

# Each lookup round takes three graph steps (model, text-tool-call check, tools),
# so this allows about five rounds per question.
RECURSION_LIMIT = 18

# Some OpenAI-compatible servers return a tool call as plain text instead of in
# the structured tool_calls field, in varying wrappers, e.g.
#   <tools>{"name": "define_word", "arguments": {"word": "x"}}</tools>
#   <tool_call>{"name": "define_word", "arguments": {"word": "x"}}</tool_call>
#   <{"name": "wikipedia_summary", "arguments": {"topic": "Alan Turing"}}>
# The wrapper is ignored: any JSON object in the text with a known tool name
# and an arguments object counts as a call.
TOOL_CALL_ARGUMENT_KEYS = ("arguments", "parameters")

class AgentState(MessagesState):
    agentdna_workflow: IntentWorkflow

def parse_text_tool_calls(text: str, tool_names: set[str]) -> list[dict]:
    """Extract tool calls a model wrote as text; returns [] if there are none."""
    decoder = json.JSONDecoder()
    calls = []
    start = text.find("{")
    while start != -1:
        try:
            payload, end = decoder.raw_decode(text, start)
        except json.JSONDecodeError:
            start = text.find("{", start + 1)
            continue
        call = as_tool_call(payload, tool_names)
        if call:
            calls.append(call)
            start = text.find("{", end)  # skip the call's own nested objects
        else:
            start = text.find("{", start + 1)  # a call may be nested inside
    return calls


def as_tool_call(payload, tool_names: set[str]) -> dict | None:
    """Return a tool call if payload is {"name": <known tool>, "arguments": {...}}."""
    if not isinstance(payload, dict) or payload.get("name") not in tool_names:
        return None
    key = next((k for k in TOOL_CALL_ARGUMENT_KEYS if k in payload), None)
    if key is None:
        return None
    args = payload[key]
    if isinstance(args, str):  # some models send the arguments as a JSON string
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            return None
    if not isinstance(args, dict):
        return None
    return {"name": payload["name"], "args": args,
            "id": f"call_{uuid.uuid4().hex[:12]}", "type": "tool_call"}


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


def create_agent_node(tools: list):
    """Build the agent and return the graph node that runs it."""
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

    # create_agent runs the model + tools loop.
    agent = create_agent(
        model=create_llm(),
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[recover_text_tool_calls],
    )

    async def agent_node(state: AgentState, config: RunnableConfig) -> dict:
        """Run the agent on the conversation and return the messages it added."""
        # Passing config on keeps the graph's recursion limit and callbacks.
        incoming_workflow = state["agentdna_workflow"]
        if incoming_workflow is None:
            raise RuntimeError("expected AgentDNA workflow from user")

        verification_code = AGENT.verify(incoming_workflow)
        if verification_code != RESULT_OK:
            failed_msg = "authentication failed for the User"
            failed_workflow = AGENT.build(
                failed_msg,
                previous_workflows=incoming_workflow,
                verification_code=verification_code
            )
            AGENT.record(failed_workflow)
            raise RuntimeError(failed_msg)

        with agentdna_context(AGENT, incoming_workflow) as ctx:
            result = await agent.ainvoke({"messages": state["messages"]}, config)
            final_message = result["messages"][-1]

            if len(ctx.workflows) == 0:
                raise RuntimeError("Agent didn't get requests from other end")

            updated_workflow = AGENT.build(
                str(final_message),
                previous_workflows=ctx.workflows
            )
        
        
        return {
            "messages": result["messages"][len(state["messages"]):],
            "agentdna_workflow": updated_workflow
        }

    return agent_node


async def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python agent.py "your question"')

    # --- Tools from the MCP server (see mcp_client.py) ---
    tools = await load_tools()

    # --- Graph ---
    builder = StateGraph(AgentState)
    builder.add_node("agent", create_agent_node(tools))
    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)
    graph = builder.compile()

    question = " ".join(sys.argv[1:])
    agentdna_workflow = USER.build(question)

    result = await graph.ainvoke(
        {
            "messages": [{"role": "user", "content": " ".join(sys.argv[1:])}],
            "agentdna_workflow": agentdna_workflow
        },
        {"recursion_limit": RECURSION_LIMIT},
    )

    # AGENTDNA: Audit the complete conversation trail on-chain
    _, tx_id = USER.record(result["agentdna_workflow"])

    print(f"\nagent> {result['messages'][-1].content}")

    if tx_id:
        display_dashboard_info(tx_id=tx_id)


if __name__ == "__main__":
    asyncio.run(main())
