# Single-Agent LangGraph Workflow with an MCP Server

A minimal agentic workflow built with **LangGraph**: one agent that calls read-only, query-style tools served by a **FastMCP** server. The tools wrap free public APIs that need no API key.

## Quick start

One command downloads the project, sets it up and runs a first query.

```bash
# Linux / macOS
curl -fsSL <INSTALLER_URL>/try.sh | sh
```
```powershell
# Windows (PowerShell)
irm <INSTALLER_URL>/try.ps1 | iex
```

Already have a checkout? Run `sh try.sh` or `.\try.ps1` from inside it instead.

**You need:** Python 3.10+, `git`, and one LLM: a local [Ollama](https://ollama.com), or an API key for Gemini, OpenAI, or any OpenAI-compatible endpoint (e.g. OpenRouter). To use a Python other than `python3`, set `TRY_AGENTDNA_PYTHON` to its path.

**What happens:**

1. Outside a checkout, the installer clones the latest stable release into `./boilerplate`. It stops if that folder already exists.
2. It installs [uv](https://docs.astral.sh/uv/) if missing, creates `.venv` and installs the dependencies.
3. A setup wizard asks for your LLM provider, model and API key (for Ollama, it offers to download the model), and saves them to `.env`.
4. It starts the MCP server, sends the agent a demo question, prints the answer and shuts everything down.

**Afterwards**, run it again from the project folder:

```bash
cd boilerplate
sh try.sh                    # re-run the wizard (Windows: .\try.ps1)
```

Or start the pieces yourself, as in [Run](#run) below.

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

> **On rate limits:** none of these APIs need a key and all have generous fair-use limits, but no public API is truly unlimited. Open-Meteo's free tier is for non-commercial use only. For heavier usage, add caching or self-host.

## Project structure

```
.
├── agent.py           # LangGraph single-agent workflow (chat loop, or one-shot: python agent.py "question")
├── mcp_server.py      # FastMCP server exposing the tools
├── wizard/            # interactive setup: provider, model, .env, demo run
├── try.sh             # Linux/macOS installer (Quick start)
├── try.ps1            # Windows installer (Quick start)
├── pyproject.toml     # core deps, plus one optional extra per LLM provider
├── .env.sample        # copy to .env for manual setup
└── README.md
```

## Manual setup

Only needed if you'd rather not use the installer.

```bash
uv venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
uv pip install -r pyproject.toml --extra ollama   # or gemini, openai, openai_compatible, all

cp .env.sample .env                # then edit .env
```

Or let the wizard write `.env` for you: `python -m wizard` (add `--yes --provider ... --model ...` to skip the prompts; see `--help`).

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
- `Look up Alan Turing on Wikipedia.` (`wikipedia_summary` needs an exact article title; it doesn't search)
- `What's the capital and population of Japan, and what's the weather there?` (chains multiple tools)
- `What does the dictionary say "serendipity" means?`

Type `exit` or `quit` to stop.

## Extending

- **Add a tool:** define another `@mcp.tool()` async function in `mcp_server.py`; the agent picks it up automatically on next start.
- **Add another MCP server:** add an entry to the `MultiServerMCPClient` config in `agent.py`.
- **Change the agent's behavior:** edit `SYSTEM_PROMPT` in `agent.py`.

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| `Installation directory already exists` | A `./boilerplate` folder is already there. `cd` into it and run `sh try.sh`, or run the installer from another folder |
| `Python 3.10 or newer is required` | Install a newer Python, or point `TRY_AGENTDNA_PYTHON` at one |
| `No interactive terminal detected` | The wizard needs a real terminal. Run the installer from one, not from CI or a non-interactive shell |
| `Ollama isn't reachable` | Install Ollama and start it (`ollama serve`), or pick a different provider in the wizard |
| Connection refused on startup | MCP server isn't running, or `MCP_URL` doesn't match `MCP_PORT` |
| `OPENAI_COMPATIBLE_BASE_URL is required` | Set the endpoint URL (and `LLM_MODEL`) when using `openai_compatible` |
| Agent never calls tools | Model doesn't support tool calling; use a tool-capable model |
| `ValueError: Unsupported LLM_PROVIDER` | Check spelling in `.env` |
| Auth errors (Gemini/OpenAI) | Missing or invalid API key in `.env` |
| Recursion limit error | Agent looped on tool calls; raise `recursion_limit` in `agent.py` or refine the prompt |