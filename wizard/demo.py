"""Step 4: pick a first question, start the MCP server and run the agent on it."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

import questionary

from . import ROOT
from .content import DEMO_PROMPT, SAMPLE_PROMPTS
from .providers import LLMConfig
from .ui import NO_HIGHLIGHT_BOX_STYLE, console, fail

SERVER_START_TIMEOUT = 30  # seconds


def choose_prompt(prompt_arg: str | None, interactive: bool) -> str:
    """Return the question for the demo run: from --prompt, a sample, or typed by the user."""
    prompt = prompt_arg
    if prompt is None and interactive:
        own_question = "Ask my own question"
        prompt = questionary.select(
            "Try a first question:",
            choices=SAMPLE_PROMPTS + [own_question],
            style=NO_HIGHLIGHT_BOX_STYLE,
        ).unsafe_ask()
        if prompt == own_question:
            prompt = questionary.text("Your question:").unsafe_ask().strip()
    return prompt or DEMO_PROMPT


def run_demo(llm: LLMConfig, prompt: str, env_file: Path) -> int:
    """Run the agent once on `prompt` against a fresh MCP server. Returns the agent's exit code."""
    port = find_free_port()
    env = {
        **os.environ,
        **llm.env(),
        "MCP_PORT": str(port),
        "MCP_URL": f"http://127.0.0.1:{port}/mcp",
    }

    with mcp_server(port, env):
        console.print(f"[green]✓[/green] MCP server ready on port {port}")

        console.rule(f"[bold]{prompt}")
        exit_code = run_agent(env, prompt)
        console.rule()

        if exit_code != 0:
            console.print(
                "[red]The agent run failed.[/red] Check the provider, model and API key "
                f"in {env_file}, then re-run [cyan]python -m wizard[/cyan]."
            )
    return exit_code


def find_free_port() -> int:
    """A free local port, so the demo doesn't clash with something already listening."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@contextmanager
def mcp_server(port: int, env: dict):
    """Start mcp_server.py, wait until it accepts connections, and stop it on exit."""
    log = tempfile.TemporaryFile("w+")
    server = subprocess.Popen(
        [sys.executable, "mcp_server.py"], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
    )
    try:
        wait_until_ready(server, log, port)
        yield
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        log.close()


def wait_until_ready(server: subprocess.Popen, log, port: int) -> None:
    """Poll the port until the server answers. Exits if it crashes or takes too long."""
    with console.status("Starting MCP server..."):
        deadline = time.time() + SERVER_START_TIMEOUT
        while True:
            if server.poll() is not None:
                log.seek(0)
                fail(f"[red]MCP server exited early:[/red]\n{log.read()[-2000:]}")
            try:
                socket.create_connection(("127.0.0.1", port), timeout=0.5).close()
                return
            except OSError:
                if time.time() > deadline:
                    fail("[red]Timed out waiting for the MCP server to start.[/red]")
                time.sleep(0.3)


def run_agent(env: dict, *args: str) -> int:
    """Run agent.py with the given arguments and return its exit code."""
    return subprocess.run([sys.executable, "agent.py", *args], cwd=ROOT, env=env).returncode
