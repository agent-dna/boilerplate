# Single-Agent LangGraph Workflow with an MCP Server

A minimal agentic workflow built with **LangGraph**: one agent that calls read-only, query-style tools served by a **FastMCP** server. The tools wrap free public APIs that need no API key.

## Architecture

```
            ┌──────────────┐   streamable HTTP   ┌────────────────────────┐
 user ───►  │  agent.py    │ ◄─────────────────► │  mcp_server.py         │
            │  (LangGraph) │        /mcp         │  (FastMCP)             │
            └──────┬───────┘                     │  get_weather           │
                   │                             │  wikipedia_summary     │
   START → agent ⇄ tools → END                   │  country_info          │
                                                 │  define_word           │
                                                 └───────────┬────────────┘
                                                             ▼
                                        Open-Meteo · Wikipedia · REST Countries · Free Dictionary
```

- **Single agent node**: the LLM decides whether to answer or call a tool.
- **Tool node**: executes the MCP tool calls and returns results to the agent.
- The loop repeats until the agent replies without requesting a tool.

## Tools (all read-only queries)

| Tool | Purpose | Backing API |
|------|---------|-------------|
| `get_weather(city)` | Current weather for a city | [Open-Meteo](https://open-meteo.com) |
| `wikipedia_summary(topic)` | Short summary of a Wikipedia article (exact title, no search) | [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) |
| `country_info(name)` | Capital, region, population, languages, currencies | [REST Countries](https://restcountries.com) |
| `define_word(word)` | English word definitions | [Free Dictionary API](https://dictionaryapi.dev) |


## Project structure

```
.
├── agent.py           # LangGraph single-agent workflow (one question per run: python agent.py "question")
├── mcp_client.py      # connects to the MCP server(s) and loads their tools for the agent
├── mcp_server.py      # FastMCP server exposing the tools
├── pyproject.toml     # dependencies, including all LLM provider packages
├── .env.sample        # copy to .env and fill in
└── README.md
```

## Setup

**You need:** Python 3.10 to 3.12, and one LLM: a local [Ollama](https://ollama.com), or an API key for Gemini, OpenAI, or any OpenAI-compatible endpoint (e.g. OpenRouter).

```bash
uv venv .venv                      # or: python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv sync   # or: pip install -e .

cp .env.sample .env                # then edit .env
```

### Configuration (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `ollama`, `gemini`, `openai`, or `openai_compatible` | `ollama` |
| `LLM_MODEL` | Model name (required for `openai_compatible`) | `llama3.1` / `gemini-2.5-flash` / `gpt-4o-mini` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `GOOGLE_API_KEY` | Required for `gemini` | – |
| `OPENAI_API_KEY` | Required for `openai` | – |
| `OPENAI_COMPATIBLE_BASE_URL` | Required for `openai_compatible`, e.g. `https://openrouter.ai/api/v1` | – |
| `OPENAI_COMPATIBLE_API_KEY` | API key for the `openai_compatible` endpoint | – |
| `MCP_PORT` | Port `mcp_server.py` listens on | `8000` |
| `MCP_URL` | MCP server endpoint the agent connects to | `http://127.0.0.1:8000/mcp` |


## Run

Start the MCP server in one terminal:

```bash
python mcp_server.py
```

Ask the agent a question in a second terminal:

```bash
python agent.py "What's the weather in San Francisco right now?"
```

Each run answers one question and exits; there is no memory between runs.

Example questions:

- `What's the weather in San Francisco right now?`
- `Look up Alan Turing on Wikipedia.` (`wikipedia_summary` needs an exact article title; it doesn't search)
- `What does the dictionary say "serendipity" means?`
