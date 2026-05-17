"""Hidden `__complete` subcommand — emits completion candidates to stdout.

Invoked by the per-shell completion scripts under
``src/jobhound/_completion/``. Output is one candidate per line, no
quoting (the shell scripts handle quoting).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Annotated

import cyclopts

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

# Static command tree for completion: sub-App names at each level.
# Only sub-Apps (groups with children) are listed; leaf commands are not.
# Update this when a new sub-App group is added or renamed.
_SUB_APP_NAMES: dict[str, frozenset[str]] = {
    "file": frozenset({"open", "read", "write", "append", "delete", "list", "export", "import"}),
    "completion": frozenset({"bash", "fish", "zsh", "install"}),
    "set": frozenset(
        {
            "applied-on",
            "comp-range",
            "company",
            "first-contact",
            "last-activity",
            "link",
            "location",
            "next-action",
            "priority",
            "role",
            "source",
            "status",
        }
    ),
    "clear": frozenset(
        {
            "applied-on",
            "comp-range",
            "first-contact",
            "last-activity",
            "location",
            "next-action",
            "source",
        }
    ),
    "add": frozenset({"contact", "note", "tag"}),
    "remove": frozenset({"contact", "link", "tag"}),
    "migrate": frozenset({"utc-timestamps"}),
}

# Top-level visible commands (excluding hidden __complete).
# Update when a top-level command is added or renamed.
_TOP_LEVEL_COMMANDS: frozenset[str] = frozenset(
    {
        "accept",
        "add",
        "apply",
        "archive",
        "bump",
        "clear",
        "completion",
        "decline",
        "delete",
        "export",
        "file",
        "ghost",
        "list",
        "log",
        "mcp",
        "migrate",
        "new",
        "remove",
        "set",
        "show",
        "stats",
        "withdraw",
    }
)


def _walk_static(words: list[str]) -> tuple[tuple[str, ...], list[str]]:
    """Walk the static command tree following `words`.

    Returns (matched_path, remaining_words). Matches any known top-level
    command at depth 1 (including leaf commands like ``show``), then
    optionally matches a depth-2 sub-command for grouping commands (like
    ``file open``).

    This replaces the cyclopts-App-based ``_walk_to_node`` and avoids
    importing the full App (and its heavy dependencies) on the completion
    fast-path. In cyclopts, every registered command — leaf or sub-App — is
    stored as an ``App`` instance, so the original tree-walk entered both.
    """
    if not words or words[0] not in _TOP_LEVEL_COMMANDS:
        return (), list(words)
    # Matched at depth 1.
    sub_commands = _SUB_APP_NAMES.get(words[0])
    if sub_commands is None or len(words) < 2:
        # Leaf command or no second word: stay at depth 1.
        return (words[0],), list(words[1:])
    # First word is a grouped command; try depth 2.
    if words[1] in sub_commands:
        return (words[0], words[1]), list(words[2:])
    return (words[0],), list(words[1:])


def _visible_at(cmd_path: tuple[str, ...]) -> Iterable[str]:
    """Return visible command names at the given tree depth.

    Uses static tables, not the live cyclopts App.
    """
    if len(cmd_path) == 0:
        return _TOP_LEVEL_COMMANDS
    if len(cmd_path) == 1:
        sub = _SUB_APP_NAMES.get(cmd_path[0])
        return sub if sub is not None else frozenset()
    return frozenset()


def _top_app() -> App:
    # Used only when the cyclopts App is needed (e.g. when this module is
    # registered as a command with the App, not on the completion fast-path).
    from jobhound.cli import get_app

    return get_app()  # type: ignore[return-value]


# (cmd_path after slug) -> enum class spec ('module:Class') for positional 1.
# The slug is at position 0; the enum value at position 1.
_POSITIONAL_ENUM_AT_POSITION_1: dict[tuple[str, ...], str] = {
    ("set", "status"): "jobhound.domain.status:Status",
}

# (cmd_path, flag_name) -> enum class spec for the flag's value.
_FLAG_ENUMS: dict[tuple[tuple[str, ...], str], str] = {
    (("set", "priority"), "--to"): "jobhound.domain.priority:Priority",
}


def _load_enum(spec: str) -> Iterable[str]:
    """Import the enum referenced by 'module.path:ClassName' and yield values."""
    import importlib

    module_name, _, class_name = spec.partition(":")
    mod = importlib.import_module(module_name)
    cls = getattr(mod, class_name)
    for member in cls:
        yield member.value


# Commands where positional 1 (after the slug) is a filename inside
# the slug's directory. All under `file`.
_FILENAME_AT_POSITION_1: frozenset[tuple[str, ...]] = frozenset(
    {
        ("file", "open"),
        ("file", "read"),
        ("file", "write"),
        ("file", "append"),
        ("file", "delete"),
        ("file", "import"),
    }
)


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


def _complete_filename(slug: str) -> Iterable[str]:
    """Yield filenames in the given opportunity, via file_service.

    Lazy imports keep the slug-only completion path cheap.
    """
    from jobhound.application import file_service
    from jobhound.domain.slug import resolve_slug
    from jobhound.infrastructure.config import load_config
    from jobhound.infrastructure.paths import paths_from_config
    from jobhound.infrastructure.storage.git_local import GitLocalFileStore

    cfg = load_config()
    paths = paths_from_config(cfg)
    try:
        canonical = resolve_slug(slug, paths.opportunities_dir)
    except Exception:
        return  # ambiguous/missing slug → no candidates
    store = GitLocalFileStore(paths)
    for entry in file_service.list_(store, canonical.name):
        yield entry.name


def run(
    shell: str, /, *words: Annotated[str, cyclopts.Parameter(allow_leading_hyphen=True)]
) -> None:
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

    cmd_path, leftover = _walk_static(completed)

    # Tokens after the command path are positional arguments already typed.
    in_positionals = leftover

    # Flag-value completion: if the previous completed token is a known flag.
    if in_positionals:
        prev = in_positionals[-1]
        if prev.startswith("--"):
            spec = _FLAG_ENUMS.get((cmd_path, prev))
            if spec is not None:
                for v in sorted(_load_enum(spec)):
                    print(v)
                return

    # Position 0 of in_positionals: emit slugs if this command takes one.
    if len(in_positionals) == 0 and cmd_path in _SLUG_AT_POSITION:
        for slug in sorted(_complete_slug()):
            print(slug)
        return

    # Position 1 = filename (for file sub-App commands)
    if len(in_positionals) == 1 and cmd_path in _FILENAME_AT_POSITION_1:
        slug = in_positionals[0]
        for name in sorted(_complete_filename(slug)):
            print(name)
        return

    # Position 1 = positional enum (e.g. jh set status <slug> <value>)
    if len(in_positionals) == 1 and cmd_path in _POSITIONAL_ENUM_AT_POSITION_1:
        spec = _POSITIONAL_ENUM_AT_POSITION_1[cmd_path]
        for v in sorted(_load_enum(spec)):
            print(v)
        return

    # Otherwise, if we've fully matched the path (no leftover), emit
    # the visible sub-commands at this node.
    if not leftover:
        for name in sorted(_visible_at(cmd_path)):
            print(name)
