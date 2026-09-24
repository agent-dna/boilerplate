"""Steps 2 and 3: save the settings to .env and install the provider's package."""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import set_key

from .providers import LLMConfig
from .ui import console, fail


def save_env(env_file: Path, llm: LLMConfig) -> None:
    """Write the chosen settings to .env, creating it readable by the owner only."""
    values = {"LLM_PROVIDER": llm.provider, "LLM_MODEL": llm.model}
    if llm.save_base_url:
        values[llm.spec["base_url_env"]] = llm.base_url
    if llm.save_api_key:
        values[llm.spec["key_env"]] = llm.api_key

    env_file.touch(mode=0o600, exist_ok=True)
    for name, value in values.items():
        set_key(str(env_file), name, value, quote_mode="never")
    console.print(f"[green]✓[/green] Saved settings to {env_file}")


def install_provider_package(llm: LLMConfig) -> None:
    """Install the provider's LangChain package if it isn't installed yet (with uv when available)."""
    package = llm.spec["package"]
    if importlib.util.find_spec(llm.spec["module"]) is not None:
        return

    uv = shutil.which("uv")
    command = (
        [uv, "pip", "install", "--quiet", "--python", sys.executable, package]
        if uv
        else [sys.executable, "-m", "pip", "install", "--quiet", package]
    )
    with console.status(f"Installing {package}..."):
        result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"[red]Failed to install {package}:[/red]\n{result.stderr}")
    console.print(f"[green]✓[/green] Installed {package}")
