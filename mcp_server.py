"""FastMCP server: read-only query tools over free, no-API-key public APIs.

Run:  python mcp_server.py   ->  http://127.0.0.1:8000/mcp
"""
import os
from urllib.parse import quote

import httpx
from fastmcp import FastMCP

mcp = FastMCP("free-query-apis")

HEADERS = {"User-Agent": "single-agent-langgraph-demo/0.1 (learning project)"}
TIMEOUT = 10.0


@mcp.tool()
async def get_weather(city: str) -> dict:
    """Get current weather for a city (Open-Meteo, no API key)."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        geo = await client.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1},
        )
        geo.raise_for_status()
        results = geo.json().get("results")
        if not results:
            return {"error": f"City '{city}' not found"}
        place = results[0]

        wx = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            },
        )
        wx.raise_for_status()
        return {
            "location": f"{place['name']}, {place.get('country', '')}",
            "current": wx.json()["current"],
            "units": wx.json()["current_units"],
        }


@mcp.tool()
async def wikipedia_summary(topic: str) -> dict:
    """Get a short Wikipedia summary for a topic or article title."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS, follow_redirects=True) as client:
        r = await client.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(topic.replace(' ', '_'))}"
        )
        if r.status_code == 404:
            return {"error": f"No Wikipedia article found for '{topic}'"}
        r.raise_for_status()
        data = r.json()
        return {
            "title": data.get("title"),
            "description": data.get("description"),
            "summary": data.get("extract"),
            "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
        }


@mcp.tool()
async def country_info(name: str) -> dict:
    """Get facts about a country: capital, region, population, languages, currencies (REST Countries)."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        r = await client.get(
            f"https://restcountries.com/v3.1/name/{quote(name)}",
            params={"fields": "name,capital,region,subregion,population,languages,currencies"},
        )
        if r.status_code == 404:
            return {"error": f"Country '{name}' not found"}
        r.raise_for_status()
        return r.json()[0]


@mcp.tool()
async def define_word(word: str) -> dict:
    """Look up the English definition of a word (Free Dictionary API)."""
    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        r = await client.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}")
        if r.status_code == 404:
            return {"error": f"No definition found for '{word}'"}
        r.raise_for_status()
        entry = r.json()[0]
        return {
            "word": entry["word"],
            "meanings": [
                {
                    "part_of_speech": m["partOfSpeech"],
                    "definitions": [d["definition"] for d in m["definitions"][:2]],
                }
                for m in entry["meanings"][:3]
            ],
        }


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=int(os.getenv("MCP_PORT", "8000")))