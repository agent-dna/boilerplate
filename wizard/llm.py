"""Step 1: choose an LLM provider and collect its model, base URL and API key."""
import os
from collections.abc import Callable

import questionary

from .ollama import configure_ollama
from .providers import PROVIDERS, LLMConfig
from .ui import NO_HIGHLIGHT_BOX_STYLE, console, fail


def choose_llm(args, interactive: bool, existing: dict) -> LLMConfig:
    """Return the provider settings, asking for anything not given on the command line.

    `existing` holds the values already saved in .env.
    """
    provider = args.provider
    while True:
        if provider is None:
            provider = ask_provider(interactive, existing)
        if provider not in PROVIDERS:
            fail(f"[red]Unknown provider '{provider}'.[/red] Choose one of: {', '.join(PROVIDERS)}")

        default_model = suggested_model(provider, existing)
        if provider != "ollama":
            return configure_api_provider(provider, args, default_model, interactive, existing)

        llm = configure_ollama(args.model, default_model, interactive, existing)
        if llm is not None:
            return llm
        provider = None  # the user asked to choose a different provider


def ask_provider(interactive: bool, existing: dict) -> str:
    """Ask which provider to use. Without prompts, use the saved one or Ollama."""
    fallback = os.getenv("LLM_PROVIDER") or existing.get("LLM_PROVIDER") or "ollama"
    if not interactive:
        return fallback
    return questionary.select(
        "Which LLM provider?",
        choices=[questionary.Choice(v["label"], value=k) for k, v in PROVIDERS.items()],
        default=fallback if fallback in PROVIDERS else "ollama",
        style=NO_HIGHLIGHT_BOX_STYLE,
    ).unsafe_ask()


def suggested_model(provider: str, existing: dict) -> str:
    """The model saved for this provider, if any, else the provider's default."""
    # A model saved for a different provider would not be a sensible default.
    return (
        (os.getenv("LLM_MODEL") if os.getenv("LLM_PROVIDER", provider) == provider else None)
        or (existing.get("LLM_MODEL") if existing.get("LLM_PROVIDER") == provider else None)
        or PROVIDERS[provider]["default_model"]
    )


def configure_api_provider(provider: str, args, default_model: str, interactive: bool,
                           existing: dict) -> LLMConfig:
    """Collect the base URL (if the provider needs one), API key and model."""
    spec = PROVIDERS[provider]

    base_url, save_base_url = None, False
    if spec.get("base_url_env"):
        if args.base_url:
            base_url, save_base_url = args.base_url, True
        else:
            ask_url = lambda: questionary.text("Base URL (e.g. https://openrouter.ai/api/v1):").unsafe_ask().strip()
            base_url, save_base_url = saved_or_asked(spec["base_url_env"], existing, ask_url if interactive else None)

    ask_key = lambda: questionary.password(f"Paste your {spec['key_env']}:").unsafe_ask()
    api_key, save_api_key = saved_or_asked(spec["key_env"], existing, ask_key if interactive else None)

    model = args.model
    if model is None and interactive:
        model = questionary.text("Model name:", default=default_model or "").unsafe_ask().strip()
    model = model or default_model
    if not model:
        fail("[red]A model name is required for this provider.[/red]")

    return LLMConfig(provider, model, base_url, api_key, save_base_url, save_api_key)


def saved_or_asked(name: str, existing: dict, ask: Callable[[], str] | None) -> tuple[str, bool]:
    """Read a setting from the environment or .env, or ask for it (`ask` is None without prompts).

    Returns the value and whether it was entered now, and so still needs saving.
    """
    value = os.getenv(name) or existing.get(name)
    if value:
        console.print(f"Using {name} from your environment or .env")
        return value, False
    if ask is not None:
        value = ask()
    if not value:
        fail(f"[red]{name} is not set.[/red] Export it or add it to .env, then re-run.")
    return value, True
