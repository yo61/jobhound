"""Hidden `__complete` subcommand — emits completion candidates to stdout.

Invoked by the per-shell completion scripts under
``src/jobhound/_completion/``. Output is one candidate per line, no
quoting (the shell scripts handle quoting).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cyclopts import App


def _top_app() -> App:
    # Imported lazily so this module stays cheap when imported only
    # for static introspection of the App tree.
    from jobhound.cli import app

    return app


def _walk_to_node(words: list[str]) -> tuple[App, list[str]]:
    """Walk the cyclopts tree following `words` from the top App.

    Returns (deepest_matched_node, remaining_words). Stops at the
    first word that doesn't match a registered subcommand.
    """
    node = _top_app()
    i = 0
    while i < len(words):
        sub = getattr(node, "_commands", {}).get(words[i])
        if sub is None or not _is_app(sub):
            break
        node = sub
        i += 1
    return node, words[i:]


def _is_app(obj: object) -> bool:
    """True if `obj` is a cyclopts App (a sub-App, not a leaf command)."""
    from cyclopts import App

    return isinstance(obj, App)


def _visible_command_names(node: App) -> Iterable[str]:
    """Names of visible (show=True) commands registered on `node`."""
    for name, entry in getattr(node, "_commands", {}).items():
        # Skip the help/version flag entries cyclopts injects.
        if name.startswith("-"):
            continue
        # Skip hidden commands (show=False).
        if getattr(entry, "show", True) is False:
            continue
        yield name


def run(shell: str, /, *words: str) -> None:
    """Dispatch entry point.

    Args:
        shell: 'bash' | 'zsh' | 'fish'. Ignored for now; later tasks
            may use it to vary output (e.g. zsh description column).
        words: Command-line tokens typed so far. The first token is
            always 'jh'. The last token is the partial being completed
            (may be empty).
    """
    del shell  # unused for static; reserved for later
    if not words:
        return

    # Strip the leading "jh" token. The shell scripts always include it.
    rest = list(words[1:])

    # The last token is the partial we're completing.
    # The earlier tokens determine the dispatch context.
    completed = rest[:-1] if rest else []

    node, leftover = _walk_to_node(completed)
    if not leftover:
        # We're at a node in the static tree; emit its visible commands.
        for name in sorted(_visible_command_names(node)):
            print(name)
