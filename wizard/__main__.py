"""Interactive setup wizard for the single-agent project.

    python -m wizard              guided setup, then a demo run
    python -m wizard --yes ...    non-interactive (see --help)

Steps, each in its own module:
    1. choose an LLM provider and model          llm.py, ollama.py
    2. save the settings to .env                 settings.py
    3. install the provider's package            settings.py
    4. start the MCP server and run the agent    demo.py
"""
import argparse
import sys

from dotenv import dotenv_values
from rich.panel import Panel

from . import ROOT
from .content import AGENT_OVERVIEW
from .demo import choose_prompt, run_demo
from .llm import choose_llm
from .providers import PROVIDERS
from .settings import install_provider_package, save_env
from .ui import console, fail


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="wizard", description="Set up and run the single-agent workflow.")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="non-interactive: use flags, environment, .env values and defaults")
    parser.add_argument("--provider", choices=list(PROVIDERS), help="LLM provider")
    parser.add_argument("--model", help="model name")
    parser.add_argument("--base-url", help="base URL (for the openai_compatible provider)")
    parser.add_argument("--prompt", help="question for the demo run")
    parser.add_argument("--no-run", action="store_true", help="save configuration only; skip the demo run")
    return parser.parse_args()


def main():
    args = parse_args()
    interactive = not args.yes

    if interactive and not (sys.stdin.isatty() and sys.stdout.isatty()):
        fail("[red]No interactive terminal detected.[/red] Re-run with --yes (see --help).")

    env_file = ROOT / ".env"
    existing = dotenv_values(env_file) if env_file.exists() else {}
    console.print(Panel.fit(AGENT_OVERVIEW, title="[bold]Single-agent LangGraph + MCP[/bold]", border_style="cyan"))

    llm = choose_llm(args, interactive, existing)
    save_env(env_file, llm)
    install_provider_package(llm)

    if args.no_run:
        console.print("Configuration saved. Run [cyan]python -m wizard[/cyan] again to try it out.")
        return

    prompt = choose_prompt(args.prompt, interactive)
    sys.exit(run_demo(llm, prompt, env_file))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
