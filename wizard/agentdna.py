"""Step 2: collect the AgentDNA API key and the names of the user, agent and MCP server."""
import os
from dataclasses import dataclass

import questionary

from .llm import saved_or_asked
from .ui import console, fail

DASHBOARD_URL = "https://dashboard.agentdna.io"

API_KEY_ENV = "AGENTDNA_API_KEY"

# The names asked for, in order: (variable, prompt). agent.py reads the user
# and agent names, mcp_server.py the MCP server name.
NAME_SETTINGS = [
    ("AGENTDNA_USER", "What's your username?:"),
    ("AGENTDNA_AGENT", "Provide a name for your Agent:"),
    ("AGENTDNA_MCP_SERVER_NAME", "Provide a name for your MCP Server:"),
]


@dataclass
class AgentDNAConfig:
    """AgentDNA settings collected by the wizard."""

    api_key: str
    save_api_key: bool  # True when the key was entered in this run and belongs in .env
    names: dict[str, str]  # variable -> name, for each entry of NAME_SETTINGS

    def env(self) -> dict[str, str]:
        """Environment variables agent.py and mcp_server.py read."""
        return {API_KEY_ENV: self.api_key, **self.names}


def configure_agentdna(interactive: bool, existing: dict) -> AgentDNAConfig:
    """Return the AgentDNA settings, asking for any that are needed.

    The API key is reused from the environment or .env when set, like the LLM
    API keys. The names are asked every run, with the current value as the
    default. Without prompts, all values must come from the environment or
    .env. `existing` holds the values already saved in .env.
    """
    ask_key = lambda: questionary.password(f"Provide your AgentDNA API key (Get it from {DASHBOARD_URL}):").unsafe_ask().strip()
    api_key, save_api_key = saved_or_asked(API_KEY_ENV, existing, ask_key if interactive else None)

    names = {}
    for name, prompt in NAME_SETTINGS:
        current = (os.getenv(name) or existing.get(name) or "").strip()
        if interactive:
            current = questionary.text(
                prompt,
                default=current,
                validate=lambda value: bool(value.strip()) or "A name is required.",
            ).unsafe_ask().strip()
        if not current:
            fail(f"[red]{name} is not set.[/red] Export it or add it to .env, then re-run.")
        names[name] = current

    return AgentDNAConfig(api_key=api_key, save_api_key=save_api_key, names=names)
