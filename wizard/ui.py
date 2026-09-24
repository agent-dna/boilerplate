"""Terminal helpers shared by the wizard steps."""
import sys
from typing import NoReturn

from questionary import Style
from rich.console import Console

console = Console()

# questionary highlights whichever choice matches `default=` with a permanent
# reverse-video box that does not move with the arrow keys - it is not a
# "currently pointed at" indicator, just a static "this was the default" marker.
# The '»' pointer is the only reliable indicator of the current selection, so
# the box is turned off here rather than shipped in a way that looks broken.
NO_HIGHLIGHT_BOX_STYLE = Style([("selected", "noreverse noblink nobold nounderline")])

# Menu choices must stay on one line at an 80-column width (allow ~4 columns
# for the "> " pointer and padding). A wrapped choice can throw off
# questionary/prompt_toolkit's incremental redraw, so the highlight can stop
# tracking the selection even though the pointer still moves correctly.
MAX_CHOICE_WIDTH = 74


def fail(message: str) -> NoReturn:
    """Print an error message (rich markup allowed) and exit with status 1."""
    console.print(message)
    sys.exit(1)
