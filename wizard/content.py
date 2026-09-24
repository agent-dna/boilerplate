"""Text shown to the user: the agent overview and the sample questions."""
from .ui import MAX_CHOICE_WIDTH

DEMO_PROMPT = "What's the weather in Tokyo, and what are Japan's capital and population?"

# Offered as choices for the first question, so each must fit on one line.
SAMPLE_PROMPTS = [
    DEMO_PROMPT,
    "What's the weather in Pune right now?",
    # wikipedia_summary needs an exact article title, and asking for the
    # dictionary by name makes a tool call clearly expected.
    "Look up Alan Turing on Wikipedia.",
    'What does the dictionary say "serendipity" means?',
]
assert all(len(p) <= MAX_CHOICE_WIDTH for p in SAMPLE_PROMPTS)

# Shown when the wizard starts, so users know what they are setting up.
# Keep lines short enough for an 80-column terminal.
AGENT_OVERVIEW = """\
[bold]What you're setting up[/bold]
A research assistant: one LangGraph agent, driven by an LLM you choose,
that answers questions by calling tools on a local MCP server.

[bold]How it works[/bold]
  you ──► agent (LangGraph + LLM) ⇄ MCP server (FastMCP) ──► public APIs
The agent decides whether it needs a tool, calls it, reads the result,
and repeats until it can answer. One question can use several tools.

[bold]Tools[/bold] (read-only lookups over free public APIs, no keys needed)
  [cyan]get_weather(city)[/cyan]
    Finds the city, then returns its current temperature, humidity,
    wind speed and WMO weather code.                   [dim]Open-Meteo[/dim]
  [cyan]wikipedia_summary(topic)[/cyan]
    Takes an exact article title (no search) and returns its title,
    description, opening summary and link.              [dim]Wikipedia[/dim]
  [cyan]country_info(name)[/cyan]
    Returns a country's name, capital, region, subregion, population,
    languages and currencies.                      [dim]REST Countries[/dim]
  [cyan]define_word(word)[/cyan]
    Returns up to two English definitions for each of up to three
    parts of speech (noun, verb, ...).            [dim]Free Dictionary[/dim]

[bold]Next[/bold]
Pick your LLM provider and model, then ask the agent a first question."""
