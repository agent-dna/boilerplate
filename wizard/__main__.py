"""Interactive setup wizard for the single-agent project.

    python -m wizard              guided setup, then a demo run
    python -m wizard --yes ...    non-interactive (see --help)
"""
import argparse
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
import questionary
from dotenv import dotenv_values, set_key
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress

ROOT = Path(__file__).resolve().parent.parent

PROVIDERS = {
    "ollama": {
        "label": "Ollama - runs locally, free",
        "package": "langchain-ollama",
        "module": "langchain_ollama",
        "default_model": "llama3.1",
        "key_env": None,
    },
    "gemini": {
        "label": "Google Gemini - API key (free tier available)",
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
}

DEMO_PROMPT = "What's the weather in Tokyo right now, and what are Japan's capital and population?"


def main():
    parser = argparse.ArgumentParser(prog="wizard", description="Set up and run the single-agent workflow.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="non-interactive: use flags, environment, .env values and defaults")
    parser.add_argument("--provider", choices=list(PROVIDERS), help="LLM provider")
    parser.add_argument("--model", help="model name")
    parser.add_argument("--prompt", help="question for the demo run")
    parser.add_argument("--no-run", action="store_true", help="save configuration only; skip the demo run")
    args = parser.parse_args()

    console = Console()
    interactive = not args.yes
    if interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        console.print("[red]No interactive terminal detected.[/red] Re-run with --yes (see --help).")
        sys.exit(1)

    env_file = ROOT / ".env"
    existing = dotenv_values(env_file) if env_file.exists() else {}
    console.print(Panel.fit(
        "[bold]Single-agent LangGraph + MCP[/bold]\nConfigure your LLM, then run a first query.",
        border_style="cyan",
    ))

    # ---- 1. choose and validate an LLM provider ----------------------------
    provider = args.provider
    while True:
        key_typed = False

        if provider is None:
            fallback = os.getenv("LLM_PROVIDER") or existing.get("LLM_PROVIDER") or "ollama"
            if interactive:
                provider = questionary.select(
                    "Which LLM provider?",
                    choices=[questionary.Choice(v["label"], value=k) for k, v in PROVIDERS.items()],
                    default=fallback if fallback in PROVIDERS else "ollama",
                ).unsafe_ask()
            else:
                provider = fallback
        if provider not in PROVIDERS:
            console.print(f"[red]Unknown provider '{provider}'.[/red] Choose one of: {', '.join(PROVIDERS)}")
            sys.exit(1)
        cfg = PROVIDERS[provider]

        # A model saved for a different provider would not be a sensible default.
        default_model = (
            (os.getenv("LLM_MODEL") if os.getenv("LLM_PROVIDER", provider) == provider else None)
            or (existing.get("LLM_MODEL") if existing.get("LLM_PROVIDER") == provider else None)
            or cfg["default_model"]
        )

        if provider == "ollama":
            base_url = os.getenv("OLLAMA_BASE_URL") or existing.get("OLLAMA_BASE_URL") or "http://localhost:11434"
            try:
                installed = [m["name"] for m in httpx.get(f"{base_url}/api/tags", timeout=5).json().get("models", [])]
            except (httpx.HTTPError, ValueError):
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
                ).unsafe_ask()
                if action == "Quit":
                    sys.exit(1)
                provider = provider if action == "Retry" else None
                continue

            model = args.model
            if model is None and interactive:
                installed_match = next(
                    (n for n in installed if n.split(":")[0] == default_model.split(":")[0]), None
                )
                download_label = f"Download {cfg['default_model']} (recommended, roughly 5 GB)"
                custom_label = "Enter another model name"
                pick = questionary.select(
                    "Which model?",
                    choices=installed + [download_label, custom_label],
                    default=installed_match,
                ).unsafe_ask()
                if pick == download_label:
                    model = cfg["default_model"]
                elif pick == custom_label:
                    model = questionary.text("Model name (e.g. qwen2.5:7b):").unsafe_ask().strip()
                else:
                    model = pick
            model = model or default_model

            if model not in installed and f"{model}:latest" not in installed:
                if interactive and not questionary.confirm(
                    f"'{model}' isn't downloaded yet (models can be several GB). Download it now?", default=True
                ).unsafe_ask():
                    continue
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
                                console.print(f"[red]Ollama error:[/red] {event['error']}")
                                sys.exit(1)
                            progress.update(
                                task,
                                description=f"{model}: {event.get('status', '')}",
                                total=event.get("total"),
                                completed=event.get("completed", 0),
                            )
                except httpx.HTTPError as error:
                    console.print(f"[red]Could not download '{model}':[/red] {error}")
                    sys.exit(1)
        else:
            key_env = cfg["key_env"]
            api_key = os.getenv(key_env) or existing.get(key_env)
            if api_key:
                console.print(f"Using {key_env} from your environment or .env")
            elif interactive:
                api_key = questionary.password(f"Paste your {key_env}:").unsafe_ask()
                key_typed = True
            if not api_key:
                console.print(f"[red]{key_env} is not set.[/red] Export it or add it to .env, then re-run.")
                sys.exit(1)
            model = args.model
            if model is None and interactive:
                model = questionary.text("Model name:", default=default_model).unsafe_ask().strip()
            model = model or default_model

        break

    # ---- 2. save configuration ----------------------------------------------
    env_file.touch(mode=0o600, exist_ok=True)
    set_key(str(env_file), "LLM_PROVIDER", provider, quote_mode="never")
    set_key(str(env_file), "LLM_MODEL", model, quote_mode="never")
    if provider == "ollama":
        set_key(str(env_file), "OLLAMA_BASE_URL", base_url, quote_mode="never")
    if key_typed:
        set_key(str(env_file), key_env, api_key, quote_mode="never")
    console.print(f"[green]✓[/green] Saved settings to {env_file}")

    # ---- 3. install only the selected provider's package -------------------
    if importlib.util.find_spec(cfg["module"]) is None:
        uv = shutil.which("uv")
        command = (
            [uv, "pip", "install", "--quiet", "--python", sys.executable, cfg["package"]]
            if uv
            else [sys.executable, "-m", "pip", "install", "--quiet", cfg["package"]]
        )
        with console.status(f"Installing {cfg['package']}..."):
            result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            console.print(f"[red]Failed to install {cfg['package']}:[/red]\n{result.stderr}")
            sys.exit(1)
        console.print(f"[green]✓[/green] Installed {cfg['package']}")

    if args.no_run:
        console.print("Configuration saved. Run [cyan]python -m wizard[/cyan] again to try it out.")
        return

    # ---- 4. start the MCP server, run the agent -----------------------------
    prompt = args.prompt
    if prompt is None and interactive:
        prompt = questionary.text("Try a first question:", default=DEMO_PROMPT).unsafe_ask().strip()
    prompt = prompt or DEMO_PROMPT

    # A free port per run, so the demo never clashes with something already listening.
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    run_env = {
        **os.environ,
        "LLM_PROVIDER": provider,
        "LLM_MODEL": model,
        "MCP_PORT": str(port),
        "MCP_URL": f"http://127.0.0.1:{port}/mcp",
    }
    if provider == "ollama":
        run_env["OLLAMA_BASE_URL"] = base_url
    else:
        run_env[key_env] = api_key

    server_log = tempfile.TemporaryFile("w+")
    server = subprocess.Popen(
        [sys.executable, "mcp_server.py"], cwd=ROOT, env=run_env, stdout=server_log, stderr=subprocess.STDOUT
    )
    exit_code = 0
    try:
        with console.status("Starting MCP server..."):
            deadline = time.time() + 30
            while True:
                if server.poll() is not None:
                    server_log.seek(0)
                    console.print(f"[red]MCP server exited early:[/red]\n{server_log.read()[-2000:]}")
                    sys.exit(1)
                try:
                    socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                    break
                except OSError:
                    if time.time() > deadline:
                        console.print("[red]Timed out waiting for the MCP server to start.[/red]")
                        sys.exit(1)
                    time.sleep(0.3)
        console.print(f"[green]✓[/green] MCP server ready on port {port}")

        console.rule(f"[bold]{prompt}")
        exit_code = subprocess.run([sys.executable, "agent.py", prompt], cwd=ROOT, env=run_env).returncode
        console.rule()

        if exit_code != 0:
            console.print(
                "[red]The agent run failed.[/red] Check the provider, model and API key "
                f"in {env_file}, then re-run [cyan]python -m wizard[/cyan]."
            )
        elif interactive and questionary.confirm("Keep chatting with the agent?", default=False).unsafe_ask():
            exit_code = subprocess.run([sys.executable, "agent.py"], cwd=ROOT, env=run_env).returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        server_log.close()

    if exit_code == 0:
        console.print(
            "\n[bold green]All set.[/bold green] Re-run [cyan]python -m wizard[/cyan] to change settings, "
            "or start the pieces yourself: [cyan]python mcp_server.py[/cyan] in one terminal and "
            "[cyan]python agent.py[/cyan] in another."
        )
    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)