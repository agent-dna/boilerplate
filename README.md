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
| `wikipedia_summary(topic)` | Short summary of a Wikipedia article | [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) |
| `country_info(name)` | Capital, region, population, languages, currencies | [REST Countries](https://restcountries.com) |
| `define_word(word)` | English word definitions | [Free Dictionary API](https://dictionaryapi.dev) |

> **On rate limits:** none of these APIs need a key and all have generous fair-use limits, but no public API is truly unlimited. Open-Meteo's free tier is for non-commercial use only. For heavier usage, add caching or self-host.

## Project structure

```
.
├── agent.py           # LangGraph single-agent workflow (chat loop, or one-shot: python agent.py "question")
├── mcp_server.py      # FastMCP server exposing the tools
├── wizard/            # interactive setup: provider, model, .env, demo run
├── install.sh         # Linux/macOS installer
├── install.ps1        # Windows installer
├── requirements.txt   # core deps (the wizard adds your provider's package)
├── .env.sample        # copy to .env for manual setup
└── README.md
```

## Quick start

```bash
# Linux / macOS (run inside the project, or via the hosted one-liner)
sh install.sh
```
```powershell
# Windows
.\install.ps1
```

The installer sets up Python and a virtualenv, then launches the wizard. It asks which LLM provider and model you want, saves `.env`, starts the MCP server, runs a demo query and prints the result. Non-interactive: `sh install.sh --yes -- --provider ollama --model llama3.1`.

## Manual setup

**Prerequisites:** Python 3.10+ and one LLM provider (local Ollama, Gemini, or OpenAI).

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.sample .env                # then edit .env
```

`requirements.txt` holds the core dependencies. Also install your provider's package: `langchain-ollama`, `langchain-google-genai` or `langchain-openai`.

### Configuration (`.env`)

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `ollama`, `gemini`, or `openai` | `ollama` |
| `LLM_MODEL` | Model name override | `llama3.1` / `gemini-2.5-flash` / `gpt-4o-mini` |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `GOOGLE_API_KEY` | Required for `gemini` | – |
| `OPENAI_API_KEY` | Required for `openai` | – |
| `MCP_URL` | MCP server endpoint | `http://127.0.0.1:8000/mcp` |

If using Ollama, pull a tool-calling-capable model first:

```bash
ollama pull llama3.1
```

## Run

Start the MCP server in one terminal:

```bash
python mcp_server.py
```

Start the agent in a second terminal:

```bash
python agent.py
```

Example prompts:

- `What's the weather in Pune right now?`
- `Give me a short summary of the Transformer architecture.`
- `What's the capital and population of Japan, and what's the weather there?` (chains multiple tools)
- `Define "ephemeral".`

Type `exit` or `quit` to stop.

## Extending

- **Add a tool:** define another `@mcp.tool()` async function in `mcp_server.py`; the agent picks it up automatically on next start.
- **Add another MCP server:** add an entry to the `MultiServerMCPClient` config in `agent.py`.
- **Change the agent's behavior:** edit `SYSTEM_PROMPT` in `agent.py`.

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Connection refused on startup | MCP server isn't running, or `MCP_URL` doesn't match host/port in `mcp_server.py` |
| Agent never calls tools | Model doesn't support tool calling; use a tool-capable model |
| `ValueError: Unsupported LLM_PROVIDER` | Check spelling in `.env` |
| Auth errors (Gemini/OpenAI) | Missing or invalid API key in `.env` |
| Recursion limit error | Agent looped on tool calls; raise `recursion_limit` in `agent.py` or refine the prompt |