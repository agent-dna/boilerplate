"""Dashboard link of an audited workflow: print it, and open it in a browser.

Used by agent.py, and by the wizard's demo run (demo.py), which shows the link
after its own output (see TX_ID_FILE_ENV).
"""
import os
import sys
import webbrowser
from pathlib import Path

from rich.console import Console

from .environments import intent_url

# When set to a file path, agent.py writes the transaction ID there instead of
# showing the link. The wizard sets it so it can show the link below its own
# output.
TX_ID_FILE_ENV = "AGENTDNA_TX_ID_FILE"


def show_audit_link(intent_id: str, console: Console | None = None) -> None:
    """Print the dashboard link of the audited workflow and open it in a browser if possible."""
    console = console or Console()
    url = intent_url(intent_id)  # on the dashboard of the selected environment
    # soft_wrap keeps the URL on one line, so it stays clickable.
    console.print(
        "\nCurrent workflow has been audited and the record is stored on the Provenance Layer. "
        "To know more, click the link below:\n\n"
        f"     [link={url}]{url}[/link]",
        soft_wrap=True,
    )
    if has_desktop():
        try:
            webbrowser.open(url)
        except webbrowser.Error:
            pass  # the link is printed above


def has_desktop() -> bool:
    """Whether a browser opened from here would appear in front of the user."""
    # Over SSH the browser would open on the remote machine, not the user's.
    if os.getenv("SSH_CONNECTION"):
        return False
    # On Linux without a graphical session, webbrowser can fall back to a text
    # browser (lynx, w3m) inside this terminal, so require a display.
    if sys.platform.startswith("linux"):
        return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))
    return True

def display_dashboard_info(intent_id: str):
    # Under the wizard, hand the ID over so the link appears after the
    # wizard's own output; otherwise show it here.
        handoff_file = os.getenv(TX_ID_FILE_ENV)
        if handoff_file:
            Path(handoff_file).write_text(intent_id, encoding="utf-8")
        else:
            show_audit_link(intent_id)