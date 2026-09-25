---
name: almanac
description: >
  A research assistant that answers factual questions by looking things up in
  free public data sources: current weather for any city, Wikipedia article
  summaries, country facts, and English word definitions. It chooses which
  lookups to make, combines results from several sources in one answer, and
  answers concisely from what the sources return.
---

# Almanac: Skills

Almanac is a single-agent research assistant built with LangGraph. It answers
questions by calling read-only tools served by a local MCP server. Each tool
wraps a free public API that needs no API key.

This document describes what Almanac can do and how each skill behaves: its
inputs, outputs, data sources and limits. It also covers how the agent combines
skills, what is out of scope, and how to add new skills.

---

## Contents

1. [At a glance](#at-a-glance)
2. [How Almanac works](#how-almanac-works)
3. [Skills](#skills)
   - [Current weather](#skill-1-current-weather)
   - [Wikipedia summaries](#skill-2-wikipedia-summaries)
   - [Country facts](#skill-3-country-facts)
   - [Word definitions](#skill-4-word-definitions)
4. [Combining skills](#combining-skills)
5. [Asking good questions](#asking-good-questions)
6. [What Almanac does not do](#what-almanac-does-not-do)
7. [Errors and edge cases](#errors-and-edge-cases)
8. [Models and providers](#models-and-providers)
9. [Configuration](#configuration)
10. [Data sources, usage limits and privacy](#data-sources-usage-limits-and-privacy)
11. [Adding a skill](#adding-a-skill)
12. [Reference](#reference)

---

## At a glance

| Skill | Tool | Input | Returns | Source |
|-------|------|-------|---------|--------|
| Current weather | `get_weather` | `city` (string) | Temperature, humidity, wind speed, WMO weather code | [Open-Meteo](https://open-meteo.com) |
| Wikipedia summaries | `wikipedia_summary` | `topic` (exact article title) | Title, short description, opening summary, link | [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) |
| Country facts | `country_info` | `name` (country name) | Names, capital, region, subregion, population, languages, currencies | [REST Countries](https://restcountries.com) |
| Word definitions | `define_word` | `word` (English word) | Up to 3 parts of speech, up to 2 definitions each | [Free Dictionary API](https://dictionaryapi.dev) |

Common properties of all skills:

- **Read-only.** No skill changes data anywhere. They only query public APIs.
- **No keys.** None of the APIs need an account or API key.
- **Live data.** Every call goes to the source at the time of the question.
  Nothing is cached.
- **10-second timeout** per HTTP request.
- **English.** Wikipedia and the dictionary are queried in English.

---

## How Almanac works

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

### The loop

1. **Question in.** The question is passed to the agent together with a short
   system prompt that describes the available lookups.
2. **Decide.** The LLM either answers directly or requests one or more tool
   calls.
3. **Look up.** Requested tools run on the MCP server, and their results are
   added to the conversation.
4. **Repeat.** The LLM sees the results and decides again: another lookup, or
   the final answer.
5. **Answer out.** When the LLM replies without requesting a tool, the run ends
   and that reply is printed.

### Components

| File | Role |
|------|------|
| `agent.py` | Builds the LangGraph graph (one agent node, one tool node), selects the LLM provider and runs the question. |
| `mcp_client.py` | Connects to the MCP server and loads its tools as LangChain tools. |
| `mcp_server.py` | FastMCP server (`free-query-apis`) that defines the four tools. Listens on `127.0.0.1:8000/mcp` by default. |
| `wizard/` | Interactive setup: provider, model, `.env`, and a first demo question. |

### Behaviour settings

- **System prompt.** "You are a helpful research assistant. Use the available
  tools to look up weather, Wikipedia summaries, country facts and word
  definitions. Only use tools when needed, and answer concisely based on tool
  results."
- **Temperature 0**, so answers are as repeatable as the model allows.
- **Step limit.** Each run is capped at 12 graph steps (`recursion_limit`). One
  lookup round uses two steps (agent, then tools), so a question can use about
  five rounds of lookups before the run stops with a recursion-limit error.
- **One question per run.** Almanac runs as `python agent.py "question"`. It
  keeps no memory between runs.

---

## Skills

### Skill 1: Current weather

**Tool:** `get_weather(city: str) -> dict`
**Source:** Open-Meteo geocoding API, then Open-Meteo forecast API

Returns the current conditions for a city.

#### What it does

1. Looks up `city` with Open-Meteo's geocoding search and takes the **first
   match**.
2. Requests the current values for that location's latitude and longitude:
   - `temperature_2m`: air temperature 2 m above ground
   - `relative_humidity_2m`: relative humidity
   - `wind_speed_10m`: wind speed 10 m above ground
   - `weather_code`: a WMO weather code (see below)
3. Returns the location, the values and their units.

#### Output

```json
{
  "location": "Tokyo, Japan",
  "current": {
    "time": "2026-09-25T09:00",
    "interval": 900,
    "temperature_2m": 24.1,
    "relative_humidity_2m": 68,
    "wind_speed_10m": 11.2,
    "weather_code": 3
  },
  "units": {
    "time": "iso8601",
    "interval": "seconds",
    "temperature_2m": "°C",
    "relative_humidity_2m": "%",
    "wind_speed_10m": "km/h",
    "weather_code": "wmo code"
  }
}
```

*(Values are illustrative.)* Units are Open-Meteo's defaults: °C, %, km/h.
The `time` field is in GMT.

#### WMO weather codes

The tool returns the numeric code only. The LLM translates it in its answer.
Common codes:

| Code | Meaning |
|------|---------|
| 0 | Clear sky |
| 1, 2, 3 | Mainly clear, partly cloudy, overcast |
| 45, 48 | Fog, depositing rime fog |
| 51, 53, 55 | Drizzle: light, moderate, dense |
| 61, 63, 65 | Rain: slight, moderate, heavy |
| 71, 73, 75 | Snowfall: slight, moderate, heavy |
| 80, 81, 82 | Rain showers: slight, moderate, violent |
| 95 | Thunderstorm |
| 96, 99 | Thunderstorm with slight or heavy hail |

#### Good questions

- "What's the weather in Pune right now?"
- "Is it windy in Wellington?"
- "How humid is it in Singapore at the moment?"
- "Compare the temperature in Oslo and Cairo."

#### Limits

- **Current conditions only.** No forecasts, no history, no sunrise or sunset,
  no precipitation amounts, no air quality.
- **First match wins.** Ambiguous names resolve to whichever place the
  geocoder ranks first. "Springfield" or "Portland" may not be the one you
  meant. The returned `location` includes the country, so check it. Adding a
  qualifier helps the model pick a better name, but the tool itself only
  accepts a city name.
- **Cities and places only.** Street addresses and coordinates are not
  supported.
- **Unknown places** return `{"error": "City '<city>' not found"}`.

---

### Skill 2: Wikipedia summaries

**Tool:** `wikipedia_summary(topic: str) -> dict`
**Source:** English Wikipedia REST API (`/page/summary/<title>`)

Returns the opening summary of an English Wikipedia article.

#### What it does

1. Turns `topic` into an article title by replacing spaces with underscores.
2. Requests the summary for that exact title. Wikipedia redirects are followed,
   so common alternative titles work, for example "JFK" → "John F. Kennedy".
3. Returns the article's title, short description, summary and URL.

#### Output

```json
{
  "title": "Alan Turing",
  "description": "English computer scientist (1912–1954)",
  "summary": "Alan Mathison Turing was an English mathematician, computer scientist, ...",
  "url": "https://en.wikipedia.org/wiki/Alan_Turing"
}
```

*(Text shortened.)*

#### Good questions

- "Look up Alan Turing on Wikipedia."
- "What does Wikipedia say about the Eiffel Tower?"
- "Give me the Wikipedia summary of Photosynthesis."
- "Summarise the Wikipedia article on the Treaty of Versailles."

#### Limits

- **No search.** The tool needs an exact article title or a title that
  redirects to one. It does not search Wikipedia. A description such as
  "Transformer architecture" matches no article. "Transformer" alone is the
  electrical device, and the machine-learning article has its own title.
  Questions that name the subject exactly work best.
- **Disambiguation pages.** Some titles lead to a "may refer to" page. The
  summary then lists meanings instead of describing one subject.
- **Summary only.** Returns the lead section, not the full article, its
  sections, infobox, tables or references.
- **English Wikipedia only.**
- **Missing articles** return `{"error": "No Wikipedia article found for '<topic>'"}`.

---

### Skill 3: Country facts

**Tool:** `country_info(name: str) -> dict`
**Source:** REST Countries v3.1 (`/name/<name>`)

Returns key facts about a country.

#### What it does

1. Looks up countries whose name matches `name`.
2. Returns the **first match**, limited to these fields: `name`, `capital`,
   `region`, `subregion`, `population`, `languages`, `currencies`.

#### Output

```json
{
  "name": {
    "common": "Japan",
    "official": "Japan",
    "nativeName": { "jpn": { "official": "日本", "common": "日本" } }
  },
  "capital": ["Tokyo"],
  "region": "Asia",
  "subregion": "Eastern Asia",
  "population": 125836021,
  "languages": { "jpn": "Japanese" },
  "currencies": { "JPY": { "name": "Japanese yen", "symbol": "¥" } }
}
```

*(Values are illustrative. The API supplies the population figure, which may
not be the latest estimate.)*

Notes on the fields:

- `capital` is a list. Some countries have more than one, and some have none.
- `languages` maps ISO 639 codes to language names.
- `currencies` maps ISO 4217 codes to a name and symbol.

#### Good questions

- "What's the capital and population of Japan?"
- "Which currencies are used in Switzerland?"
- "What languages are spoken in Belgium?"
- "Which region and subregion is Peru in?"

#### Limits

- **Partial name matching.** The API matches parts of names, and the tool
  keeps only the first result. Short or shared names can return the wrong
  country. For example, "Niger" may return Nigeria, and "Guinea" has several
  candidates. Full, distinctive names work best.
- **Fixed fields.** No area, borders, time zones, calling codes, flags, GDP or
  head of state. Those fields exist in REST Countries but are not requested.
- **Population** comes from the dataset and is not a live figure.
- **Unknown names** return `{"error": "Country '<name>' not found"}`.

---

### Skill 4: Word definitions

**Tool:** `define_word(word: str) -> dict`
**Source:** Free Dictionary API (`/api/v2/entries/en/<word>`)

Returns English definitions for a word.

#### What it does

1. Looks up `word` in the English dictionary.
2. Takes the first entry and returns up to **three** parts of speech, each with
   up to **two** definitions.

#### Output

```json
{
  "word": "serendipity",
  "meanings": [
    {
      "part_of_speech": "noun",
      "definitions": [
        "A combination of events which have come together by chance to make a surprisingly good or wonderful outcome.",
        "An unsought, unintended, and/or unexpected, but fortunate, discovery and/or learning experience that happens by accident."
      ]
    }
  ]
}
```

*(Values are illustrative.)*

#### Good questions

- "What does the dictionary say 'serendipity' means?"
- "Define 'ephemeral' using the dictionary."
- "Is 'run' a noun or a verb? Look it up."
- "Look up the definition of 'ubiquitous'."

#### Limits

- **Definitions only.** No pronunciation, audio, example sentences, synonyms,
  antonyms or etymology in the result, even where the API has them.
- **Trimmed.** Words with many senses are cut to three parts of speech and two
  definitions each.
- **Single words.** Phrases and idioms are rarely found.
- **English only.**
- **Unknown words** return `{"error": "No definition found for '<word>'"}`.

#### When is the tool used?

Most LLMs can define common words from memory. Following the system prompt,
the model may answer directly instead of calling the tool. Mentioning "the
dictionary" or "look it up" makes a tool call clearly expected.

---

## Combining skills

Almanac can use several skills for one question, in one round or across
rounds. The model decides the order.

### Parallel lookups

Independent lookups can be requested together.

> **"What's the weather in Tokyo, and what are Japan's capital and population?"**
>
> 1. `get_weather("Tokyo")` and `country_info("Japan")`
> 2. Answer combining both results.

### Chained lookups

One result can supply the input for the next lookup.

> **"What's the weather in the capital of Kenya?"**
>
> 1. `country_info("Kenya")` returns `capital: ["Nairobi"]`
> 2. `get_weather("Nairobi")`
> 3. Answer with the current weather in Nairobi.

> **"Look up the capital of Portugal on Wikipedia."**
>
> 1. `country_info("Portugal")` returns `capital: ["Lisbon"]`
> 2. `wikipedia_summary("Lisbon")`
> 3. Answer with the summary.

### Comparisons

> **"Which is warmer right now, Madrid or Rome, and which country has more people?"**
>
> 1. `get_weather("Madrid")`, `get_weather("Rome")`, `country_info("Spain")`,
>    `country_info("Italy")`
> 2. Answer comparing the values.

### More combined questions

- "Define 'archipelago' and give me the Wikipedia summary of Indonesia."
- "What currency does Thailand use, and what's the weather in Bangkok?"
- "Look up Marie Curie on Wikipedia and tell me the population of her birth country."
- "What languages are spoken in Canada, and is it snowing in Ottawa?"

How reliably a model plans chained or parallel calls varies. Larger models
with strong tool-calling support do this more consistently. The step limit
allows about five rounds of lookups per question.

---

## Asking good questions

| Do | Why |
|----|-----|
| Name cities, countries and subjects exactly. | Every tool matches names; none searches. |
| Use Wikipedia article titles ("Alan Turing", "Eiffel Tower"). | `wikipedia_summary` needs an exact title. |
| Use full country names ("Republic of the Congo", "Niger"). | `country_info` returns the first partial match. |
| Say "look up" or name the source for definitions. | Otherwise the model may answer from memory. |
| Ask for current conditions. | Weather is current only. |
| Ask one clear question at a time. | Each run is independent, with no follow-ups. |

Questions that often go wrong:

- "Summarise the Transformer architecture." This is not an article title, so
  the lookup fails or the model answers from memory.
- "What's the weather in Springfield?" Ambiguous. The first geocoding match
  may not be the intended place.
- "Will it rain tomorrow in Paris?" Forecasts are not available.
- "And what about Germany?" There is no memory of earlier questions.

---

## What Almanac does not do

- **No writing or actions.** It cannot send messages, create files, change
  settings or call non-read-only APIs.
- **No web search** or browsing beyond the four sources above.
- **No forecasts or history** for weather. Current conditions only.
- **No memory.** Each run starts fresh.
- **No files or images.** Text questions only.
- **No non-English lookups.** Wikipedia and the dictionary are English only.
  The model may still answer in another language if asked.
- **No guaranteed citations.** `wikipedia_summary` returns a URL, which the
  model may or may not include in its answer.
- **Not authoritative.** Results depend on public datasets and on the LLM
  summarising them correctly.

When no skill applies, the model answers from its own knowledge or says it
cannot help, depending on the model.

---

## Errors and edge cases

### "Not found" results

Each tool returns a plain error object instead of failing when the source has
no match:

| Tool | Error |
|------|-------|
| `get_weather` | `{"error": "City '<city>' not found"}` |
| `wikipedia_summary` | `{"error": "No Wikipedia article found for '<topic>'"}` |
| `country_info` | `{"error": "Country '<name>' not found"}` |
| `define_word` | `{"error": "No definition found for '<word>'"}` |

The model sees the error and can retry with a different input, for example
another spelling or title, or tell the user the lookup failed.

### Other failures

Timeouts (over 10 seconds), network errors and server errors from a source
(HTTP 5xx, rate limiting) raise an exception inside the tool. They are not
turned into a friendly message.

### Tool calls written as text

Some OpenAI-compatible servers return a model's tool call as plain text, for
example `<tools>{"name": "define_word", "arguments": {...}}</tools>`, instead
of in the structured `tool_calls` field. Almanac detects this. When a reply has
no structured tool calls but contains a `<tools>` or `<tool_call>` block naming
one of its tools, it converts the block into a real tool call and continues.
Replies from providers that return structured calls are not changed.

### Step limit

A question that needs more than about five rounds of lookups, or a model that
keeps calling tools in a loop, stops with a recursion-limit error. Raise
`recursion_limit` in `agent.py` or ask a narrower question.

---

## Models and providers

Almanac needs an LLM that supports **tool calling**. Models without it answer
every question from memory and never use the skills.

| Provider | `LLM_PROVIDER` | Default model | Needs |
|----------|----------------|---------------|-------|
| Ollama (local) | `ollama` | `llama3.1` | A running Ollama server |
| Google Gemini | `gemini` | `gemini-2.5-flash` | `GOOGLE_API_KEY` |
| OpenAI | `openai` | `gpt-4o-mini` | `OPENAI_API_KEY` |
| Any OpenAI-compatible endpoint | `openai_compatible` | none, must be set | `OPENAI_COMPATIBLE_BASE_URL`, `LLM_MODEL`, usually `OPENAI_COMPATIBLE_API_KEY` |

Notes:

- **Tool-calling quality varies.** Larger models, and models trained for tool
  use, plan multi-step lookups better and are less likely to skip a tool.
- **Coding-tuned models** can be less reliable for general questions like
  these. With some servers they also return tool calls as text; see
  [Tool calls written as text](#tool-calls-written-as-text).
- **Self-hosted servers** must have tool calling enabled. vLLM, for example,
  needs `--enable-auto-tool-choice` with a suitable `--tool-call-parser`, and
  llama.cpp needs `--jinja`.

---

## Configuration

Settings are read from the environment or from `.env` in the project folder.
`.env.sample` lists them all. The setup wizard (`try.sh`, `try.ps1` or
`python -m wizard`) writes them for you.

| Variable | Used by | Purpose | Default |
|----------|---------|---------|---------|
| `LLM_PROVIDER` | agent | `ollama`, `gemini`, `openai` or `openai_compatible` | `ollama` |
| `LLM_MODEL` | agent | Model name | Provider default (see above) |
| `OLLAMA_BASE_URL` | agent | Ollama server URL | `http://localhost:11434` |
| `GOOGLE_API_KEY` | agent | Gemini API key | – |
| `OPENAI_API_KEY` | agent | OpenAI API key | – |
| `OPENAI_COMPATIBLE_BASE_URL` | agent | Endpoint URL, e.g. `https://openrouter.ai/api/v1` | – |
| `OPENAI_COMPATIBLE_API_KEY` | agent | Endpoint API key | – |
| `MCP_URL` | agent (`mcp_client.py`) | MCP server endpoint | `http://127.0.0.1:8000/mcp` |
| `MCP_PORT` | MCP server | Port the server listens on | `8000` |

`MCP_URL` and `MCP_PORT` must point to the same port.

### Running

```bash
# Terminal 1: the MCP server
python mcp_server.py

# Terminal 2: one question
python agent.py "What's the weather in Pune right now?"
```

The wizard does both for you. It starts the server on a free port, runs one
question and stops the server afterwards.

---

## Data sources, usage limits and privacy

| Source | Terms | Notes |
|--------|-------|-------|
| [Open-Meteo](https://open-meteo.com) | Free for **non-commercial** use | Commercial use needs a paid plan. Fair-use limits apply. |
| [Wikipedia REST API](https://en.wikipedia.org/api/rest_v1/) | Free, content under CC BY-SA | Requests identify themselves with a User-Agent header, as Wikimedia asks. |
| [REST Countries](https://restcountries.com) | Free, community-run | No guaranteed availability. |
| [Free Dictionary API](https://dictionaryapi.dev) | Free, community-run | No guaranteed availability. |

- **No API keys, but not unlimited.** All four have fair-use limits. For heavy
  use, add caching or host the data yourself.
- **What leaves your machine:**
  - **Lookup inputs** (city, topic, country, word) are sent to the matching
    public API.
  - **The full question and the tool results** are sent to your LLM provider,
    unless you use a local model through Ollama.
- **The MCP server listens on `127.0.0.1` only**, so other machines cannot
  reach it.

---

## Adding a skill

A skill is one `@mcp.tool()` function in `mcp_server.py`. The agent loads all
tools from the server when it starts, so no change to `agent.py` is needed to
make a new tool available.

### 1. Add the tool

```python
@mcp.tool()
async def get_exchange_rate(base: str, target: str) -> dict:
    """Get the latest exchange rate between two currencies (ISO 4217 codes, e.g. USD, EUR)."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        r = await client.get(
            "https://api.frankfurter.app/latest",
            params={"from": base.upper(), "to": target.upper()},
        )
        if r.status_code == 404:
            return {"error": f"Unknown currency '{base}' or '{target}'"}
        r.raise_for_status()
        data = r.json()
        return {"base": data["base"], "date": data["date"], "rates": data["rates"]}
```

*(Illustrative example of the pattern. Check the API's current terms before
use.)*

### 2. Follow the existing conventions

- **Write the docstring for the model.** The LLM reads it to decide when and
  how to call the tool. Say what the input should look like, for example "ISO
  4217 codes" or "exact article title".
- **Use typed parameters.** They become the tool's input schema.
- **Return a small dict** containing only the fields an answer needs. Large
  responses cost tokens and distract the model.
- **Return `{"error": ...}` for "not found"** instead of raising, so the model
  can recover.
- **Stay read-only**, and reuse the shared `TIMEOUT` and `HEADERS`.

### 3. Tell the agent about it

Add the new capability to `SYSTEM_PROMPT` in `agent.py`, for example "…country
facts, word definitions and exchange rates". Then document it in this file and
in the overview shown by the wizard (`wizard/content.py`).

### Adding another MCP server

To use tools from another MCP server, add an entry to the dictionary in
`load_tools()` in `mcp_client.py`:

```python
client = MultiServerMCPClient(
    {
        "free_apis": {"url": os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp"), "transport": "streamable_http"},
        "another": {"url": "http://127.0.0.1:9000/mcp", "transport": "streamable_http"},
    }
)
```

Tools from all servers are given to the agent together, so tool names must be
unique across servers.

---

## Reference

### Tool signatures

```python
get_weather(city: str) -> dict
wikipedia_summary(topic: str) -> dict
country_info(name: str) -> dict
define_word(word: str) -> dict
```

### Endpoints called

| Tool | Request |
|------|---------|
| `get_weather` | `GET https://geocoding-api.open-meteo.com/v1/search?name=<city>&count=1` |
| | `GET https://api.open-meteo.com/v1/forecast?latitude=…&longitude=…&current=temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code` |
| `wikipedia_summary` | `GET https://en.wikipedia.org/api/rest_v1/page/summary/<Title_With_Underscores>` |
| `country_info` | `GET https://restcountries.com/v3.1/name/<name>?fields=name,capital,region,subregion,population,languages,currencies` |
| `define_word` | `GET https://api.dictionaryapi.dev/api/v2/entries/en/<word>` |

### Agent settings

| Setting | Value | Where |
|---------|-------|-------|
| Graph | `START → agent ⇄ tools → END` | `agent.py` |
| Temperature | 0 | `agent.py` |
| Step limit | 12 (`recursion_limit`) | `agent.py` |
| MCP transport | Streamable HTTP | `mcp_client.py` |
| MCP server name | `free-query-apis` | `mcp_server.py` |
| HTTP timeout | 10 s per request | `mcp_server.py` |
