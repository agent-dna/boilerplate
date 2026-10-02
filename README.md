# Single-Agent LangGraph Workflow with an MCP Server

A minimal agentic workflow built with **LangGraph**: one agent that calls read-only, query-style tools served by a **FastMCP** server. The tools wrap free public APIs that need no API key.

## Quick start

One command downloads the project, sets it up and runs a first query. It
targets the test-prod environment unless `AGENTDNA_ENV` says otherwise (see
[Environments](#environments)):

```bash
# Linux / macOS
curl -fsSL <INSTALLER_URL>/try.sh | sh
```
```powershell
# Windows (PowerShell)
irm <INSTALLER_URL>/try.ps1 | iex
```

Already have a checkout? Run `sh try.sh` or `.\try.ps1` from inside it instead.
To target dev, set `AGENTDNA_ENV=dev` in the shell first (for example
`curl -fsSL <INSTALLER_URL>/try.sh | AGENTDNA_ENV=dev sh`), or in `.env` of an
existing checkout.

**You need:** `git`, internet access, and one LLM: a local [Ollama](https://ollama.com), or an API key for Gemini, OpenAI, or any OpenAI-compatible endpoint (e.g. OpenRouter). No Python installation is needed: the project runs on Python 3.12, which the installer gets through uv whatever Python the system has (see step 2).

**What happens:**

1. Outside a checkout, the installer clones the `main` branch into `./boilerplate`. If `./boilerplate` already holds the project (from an earlier run), it uses that folder instead, without cloning or updating it. It stops if `./boilerplate` exists but is not the project.
2. It installs [uv](https://docs.astral.sh/uv/) if missing, then creates `.venv` on a uv-managed Python 3.12 (downloaded once, about 30 MB, into uv's own folder; the system Python is neither used nor changed) and installs the dependencies. An existing `.venv` on another Python version is replaced.
3. A setup wizard asks for your LLM provider, model and API key (for Ollama, it offers to download the model), then your AgentDNA API key and the names of your user, agent and MCP server. It saves them to `.env`, together with the environment (`AGENTDNA_ENV`).
4. It starts the MCP server, sends the agent a first question and prints the answer with the link to its audit record. It then asks whether to ask another question; answering yes shows the same choice of sample questions (or your own) again. Each question is answered on its own, without memory of earlier ones. Everything shuts down when you are done.

**Afterwards**, run the same one-line command again from the same folder, or run the installer from the project folder:

```bash
cd boilerplate
sh try.sh                    # re-run the wizard (Windows: .\try.ps1)
```

Both reuse the existing project, `.venv` and `.env`.

**Another branch (debugging):** the installer takes an optional branch to use instead of `main`. A new install clones it; an existing project is switched to it (a local branch of that name is used as it is, otherwise it is fetched from GitHub).

```bash
curl -fsSL <INSTALLER_URL>/try.sh | sh -s -- --branch develop
sh try.sh --branch develop                      # from a checkout
```
```powershell
& ([scriptblock]::Create((irm <INSTALLER_URL>/try.ps1))) -Branch develop
.\try.ps1 -Branch develop                        # from a checkout
```

Or start the pieces yourself, as in [Run](#run) below.

## Environments

The agent and MCP server talk to one AgentDNA environment, selected by
`AGENTDNA_ENV`:

| `AGENTDNA_ENV` | Provenance layer | Admin server | Dashboard | CBAC service |
|----------------|------------------|--------------|-----------|--------------|
| `test-prod` (default) | `https://chain-connector-2.rubix.net` | `https://agentdna-admin.agentdna.io` | `https://dashboard.agentdna.io` | `https://cbac-service.agentdna.io` |
| `dev` | `https://chain-connector-2-dev.rubix.net` | `https://agentdna-admin-dev.agentdna.io` | `https://dashboard-dev.agentdna.io` | `https://cbac-service-dev.agentdna.io` |

- **Choosing:** the wizard uses `AGENTDNA_ENV` from the shell, else the value
  saved in `.env`, else `test-prod`, and saves its choice to `.env`. The
  installers do not set it; they are the same for every environment and clone
  the `main` branch.
- **Override:** `AGENTDNA_PROVENANCE_URL`, `AGENTDNA_ADMIN_SERVER_URL` and
  `AGENTDNA_CBAC_URL` override a single service URL.
- **Adding an environment:** add an entry to `ENVIRONMENTS` in
  `wizard/environments.py`.

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
├── mcp_client.py      # connects to the MCP server(s) and loads their tools for the agent
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

The project requires Python 3.12 exactly (`requires-python` in `pyproject.toml`, and `.python-version`).

```bash
uv venv .venv --python 3.12 --python-preference only-managed   # uv-managed 3.12, downloaded if needed
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
| `AGENTDNA_ENV` | AgentDNA environment: `test-prod` or `dev` (see [Environments](#environments)) | `test-prod` |
| `AGENTDNA_API_KEY` | AgentDNA API key, from the environment's dashboard | – |
| `AGENTDNA_USER` | Name of the AgentDNA user | – |
| `AGENTDNA_AGENT` | Name of the agent | – |
| `AGENTDNA_MCP_SERVER_NAME` | Name of the MCP server | – |
| `AGENTDNA_PROVENANCE_URL` | Optional override of the environment's provenance layer URL | from `AGENTDNA_ENV` |
| `AGENTDNA_ADMIN_SERVER_URL` | Optional override of the environment's admin server URL | from `AGENTDNA_ENV` |
| `AGENTDNA_CBAC_URL` | Optional override of the environment's CBAC service URL (MCP server authorization) | from `AGENTDNA_ENV` |

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
- **Add another MCP server:** add an entry to the `MultiServerMCPClient` config in `mcp_client.py`.
- **Change the agent's behavior:** edit `SYSTEM_PROMPT` in `agent.py`.

## Troubleshooting

| Symptom | Likely cause / fix |
|---------|--------------------|
| Installer exits right away, with nothing installed | A `./boilerplate` folder that is not this project is in the way. Rename or remove it, or run the installer from another folder |
| `unknown AGENTDNA_ENV '...'` | `AGENTDNA_ENV` in the shell or `.env` is not `test-prod` or `dev` |
| Dependency install fails with a `requires-python` / "3.12" error | The `.venv` is not on Python 3.12. Delete `.venv` and run the installer again, or create it as in [Manual setup](#manual-setup) |
| `No interactive terminal detected` | The wizard needs a real terminal. Run the installer from one, not from CI or a non-interactive shell |
| `Ollama isn't reachable` | Install Ollama and start it (`ollama serve`), or pick a different provider in the wizard |
| Connection refused on startup | MCP server isn't running, or `MCP_URL` doesn't match `MCP_PORT` |
| `OPENAI_COMPATIBLE_BASE_URL is required` | Set the endpoint URL (and `LLM_MODEL`) when using `openai_compatible` |
| Agent never calls tools | Model doesn't support tool calling; use a tool-capable model |
| `ValueError: Unsupported LLM_PROVIDER` | Check spelling in `.env` |
| Auth errors (Gemini/OpenAI) | Missing or invalid API key in `.env` |
| Recursion limit error | Agent looped on tool calls; raise `RECURSION_LIMIT` in `agent.py` or refine the prompt |