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


# Commands that take a slug as their FIRST positional after the
# (possibly nested) sub-verb. Tuple key is the path from the top App,
# e.g. ("show",) or ("file", "open") or ("set", "status").
#
# Listed exhaustively rather than introspected because cyclopts'
# signature inspection is more nuanced than worth implementing for
# this static set. Update this table when a new slug-taking command
# is added.
_SLUG_AT_POSITION: frozenset[tuple[str, ...]] = frozenset(
    {
        # Lifecycle (slug is the only positional)
        ("accept",),
        ("apply",),
        ("bump",),
        ("decline",),
        ("delete",),
        ("ghost",),
        ("log",),
        ("show",),
        ("withdraw",),
        ("touch",),  # touch is alias for bump
        # File sub-App
        ("file", "open"),
        ("file", "read"),
        ("file", "write"),
        ("file", "append"),
        ("file", "delete"),
        ("file", "list"),
        ("file", "import"),
        # Set / clear / add / remove sub-Apps (slug after sub-verb)
        ("set", "applied-on"),
        ("set", "comp-range"),
        ("set", "company"),
        ("set", "first-contact"),
        ("set", "last-activity"),
        ("set", "link"),
        ("set", "location"),
        ("set", "next-action"),
        ("set", "priority"),
        ("set", "role"),
        ("set", "source"),
        ("set", "status"),
        ("clear", "applied-on"),
        ("clear", "comp-range"),
        ("clear", "first-contact"),
        ("clear", "last-activity"),
        ("clear", "location"),
        ("clear", "next-action"),
        ("clear", "source"),
        ("add", "contact"),
        ("add", "note"),
        ("add", "tag"),
        ("remove", "contact"),
        ("remove", "link"),
        ("remove", "tag"),
    }
)


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


def _complete_slug() -> Iterable[str]:
    """Yield canonical slug names from the opportunities directory.

    Lazy-imports config / paths to keep the static-completion path fast.
    """
    from jobhound.infrastructure.config import load_config
    from jobhound.infrastructure.paths import paths_from_config

    cfg = load_config()
    paths = paths_from_config(cfg)
    opps = paths.opportunities_dir
    if not opps.exists():
        return
    for entry in opps.iterdir():
        if entry.is_dir() and not entry.name.startswith("."):
            yield entry.name


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

    word_list = list(words)

    # Strip the leading "jh" token and the partial being completed.
    # completed = the tokens that are fully typed (not including the partial).
    completed = word_list[1:-1] if len(word_list) > 1 else []

    node, leftover = _walk_to_node(completed)

    # Number of command-path tokens matched (e.g. 1 for "show", 2 for "file open")
    cmd_depth = len(completed) - len(leftover)
    cmd_path = tuple(completed[:cmd_depth])

    # Tokens after the command path are positional arguments already typed.
    in_positionals = completed[cmd_depth:]

    # Position 0 of in_positionals: emit slugs if this command takes one.
    if len(in_positionals) == 0 and cmd_path in _SLUG_AT_POSITION:
        for slug in sorted(_complete_slug()):
            print(slug)
        return

    # Otherwise, if we're still in the static tree, emit visible commands.
    if not leftover:
        for name in sorted(_visible_command_names(node)):
            print(name)
