"""Ollama setup: check the server is reachable, pick a model, and download it if needed."""
import json
import os
import sys

import httpx
import questionary
from rich.progress import Progress

from .providers import PROVIDERS, LLMConfig
from .ui import NO_HIGHLIGHT_BOX_STYLE, console, fail

DEFAULT_BASE_URL = "http://localhost:11434"


def configure_ollama(model_arg: str | None, default_model: str, interactive: bool,
                     existing: dict) -> LLMConfig | None:
    """Collect the Ollama settings. Returns None if the user wants a different provider."""
    base_url = os.getenv("OLLAMA_BASE_URL") or existing.get("OLLAMA_BASE_URL") or DEFAULT_BASE_URL

    while True:
        installed = list_models(base_url)
        if installed is None:
            console.print(
                f"[yellow]Ollama isn't reachable at {base_url}.[/yellow]\n"
                "Install it with [cyan]curl -fsSL https://ollama.com/install.sh | sh[/cyan] "
                "and make sure it is running ([cyan]ollama serve[/cyan])."
            )
            if not interactive:
                sys.exit(1)
            action = questionary.select(
                "What would you like to do?",
                choices=["Retry", "Choose a different provider", "Quit"],
                style=NO_HIGHLIGHT_BOX_STYLE,
            ).unsafe_ask()
            if action == "Quit":
                sys.exit(1)
            if action == "Retry":
                continue
            return None

        model = model_arg
        if model is None and interactive:
            model = ask_model(installed, default_model)
        model = model or default_model

        if model not in installed and f"{model}:latest" not in installed:
            if interactive and not questionary.confirm(
                f"'{model}' isn't downloaded yet (models can be several GB). Download it now?", default=True
            ).unsafe_ask():
                continue
            pull_model(base_url, model)

        # The URL is always saved, so agent.py uses the same server.
        return LLMConfig("ollama", model, base_url=base_url, save_base_url=True)


def list_models(base_url: str) -> list[str] | None:
    """Names of the models already downloaded, or None if Ollama isn't reachable."""
    try:
        return [m["name"] for m in httpx.get(f"{base_url}/api/tags", timeout=5).json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return None


def ask_model(installed: list[str], default_model: str) -> str:
    """Let the user pick an installed model, download the recommended one, or type a name."""
    recommended = PROVIDERS["ollama"]["default_model"]
    installed_match = next(
        (n for n in installed if n.split(":")[0] == default_model.split(":")[0]), None
    )
    download_label = f"Download {recommended} (recommended, roughly 5 GB)"
    custom_label = "Enter another model name"
    pick = questionary.select(
        "Which model?",
        choices=installed + [download_label, custom_label],
        default=installed_match,
        style=NO_HIGHLIGHT_BOX_STYLE,
    ).unsafe_ask()
    if pick == download_label:
        return recommended
    if pick == custom_label:
        return questionary.text("Model name (e.g. qwen2.5:7b):").unsafe_ask().strip()
    return pick


def pull_model(base_url: str, model: str) -> None:
    """Download a model through the Ollama API, showing a progress bar."""
    try:
        with Progress(console=console) as progress, httpx.stream(
            "POST", f"{base_url}/api/pull", json={"model": model, "name": model}, timeout=None
        ) as response:
            response.raise_for_status()
            task = progress.add_task(f"Pulling {model}", total=None)
            for line in response.iter_lines():
                if not line:
                    continue
                event = json.loads(line)
                if "error" in event:
                    fail(f"[red]Ollama error:[/red] {event['error']}")
                progress.update(
                    task,
                    description=f"{model}: {event.get('status', '')}",
                    total=event.get("total"),
                    completed=event.get("completed", 0),
                )
    except httpx.HTTPError as error:
        fail(f"[red]Could not download '{model}':[/red] {error}")
