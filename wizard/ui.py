"""Terminal helpers shared by the wizard steps."""
import asyncio
import selectors
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


class _SelectEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """Event loops that wait for input with select() instead of kqueue."""

    def new_event_loop(self) -> asyncio.AbstractEventLoop:
        return asyncio.SelectorEventLoop(selectors.SelectSelector())


def use_tty_compatible_event_loop() -> None:
    """On macOS, make the prompts work when stdin is /dev/tty.

    try.sh runs the wizard with stdin redirected from /dev/tty (its own stdin
    is the pipe from curl). questionary's prompts run on asyncio, whose macOS
    event loop uses kqueue, and kqueue cannot watch /dev/tty: the first prompt
    fails with "OSError: [Errno 22] Invalid argument" and then EOFError.
    select() handles /dev/tty, so use it for the wizard's event loops. Linux
    (epoll) and Windows are not affected and keep their default loops.
    """
    if sys.platform == "darwin":
        asyncio.set_event_loop_policy(_SelectEventLoopPolicy())
