"""Supported LLM providers, and the settings collected for the chosen one."""
from dataclasses import dataclass

from .ui import MAX_CHOICE_WIDTH

# label:         menu text (must fit on one line)
# package:       pip package the wizard installs for this provider
# module:        import name used to check whether the package is installed
# default_model: suggested model; empty means the user must name one
# key_env:       variable holding the API key, if the provider needs one
# base_url_env:  variable holding the server URL, if the provider needs one
PROVIDERS = {
    "ollama": {
        "label": "Ollama - local, free",
        "package": "langchain-ollama",
        "module": "langchain_ollama",
        "default_model": "llama3.1",
        "key_env": None,
        "base_url_env": "OLLAMA_BASE_URL",
    },
    "gemini": {
        "label": "Google Gemini - API key",
        "package": "langchain-google-genai",
        "module": "langchain_google_genai",
        "default_model": "gemini-2.5-flash",
        "key_env": "GOOGLE_API_KEY",
    },
    "openai": {
        "label": "OpenAI - API key",
        "package": "langchain-openai",
        "module": "langchain_openai",
        "default_model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
    "openai_compatible": {
        "label": "OpenAI-compatible endpoint - custom URL",
        "package": "langchain-openai",
        "module": "langchain_openai",
        "default_model": "",
        "key_env": "OPENAI_COMPATIBLE_API_KEY",
        "base_url_env": "OPENAI_COMPATIBLE_BASE_URL",
    },
}
assert all(len(p["label"]) <= MAX_CHOICE_WIDTH for p in PROVIDERS.values())


@dataclass
class LLMConfig:
    """Provider settings collected by the wizard."""

    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None
    # True when the value is new in this run and should be written to .env.
    save_base_url: bool = False
    save_api_key: bool = False

    @property
    def spec(self) -> dict:
        return PROVIDERS[self.provider]

    def env(self) -> dict[str, str]:
        """Environment variables agent.py reads for this provider."""
        values = {"LLM_PROVIDER": self.provider, "LLM_MODEL": self.model}
        if self.spec.get("base_url_env"):
            values[self.spec["base_url_env"]] = self.base_url
        if self.spec["key_env"]:
            values[self.spec["key_env"]] = self.api_key
        return values
