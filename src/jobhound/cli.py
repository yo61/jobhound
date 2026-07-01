"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

from typing import Any


def _build_cyclopts_app() -> Any:
    """Build and return the fully-wired cyclopts App.

    Called lazily so that the heavy command-module imports (questionary,
    prompt_toolkit, etc.) are skipped on the ``__complete`` fast-path.
    """
    from cyclopts import App, Group

    from jobhound import __version__
    from jobhound.commands import _complete as cmd_complete
    from jobhound.commands import accept as cmd_accept
    from jobhound.commands import apply as cmd_apply
    from jobhound.commands import archive as cmd_archive
    from jobhound.commands import browser as cmd_browser
    from jobhound.commands import bump as cmd_bump
    from jobhound.commands import clear as cmd_clear
    from jobhound.commands import contact as cmd_contact
    from jobhound.commands import decline as cmd_decline
    from jobhound.commands import delete as cmd_delete
    from jobhound.commands import export as cmd_export
    from jobhound.commands import ghost as cmd_ghost
    from jobhound.commands import link as cmd_link
    from jobhound.commands import list_ as cmd_list
    from jobhound.commands import log as cmd_log
    from jobhound.commands import migrate as cmd_migrate
    from jobhound.commands import new as cmd_new
    from jobhound.commands import note as cmd_note
    from jobhound.commands import set as cmd_set
    from jobhound.commands import show as cmd_show
    from jobhound.commands import stats as cmd_stats
    from jobhound.commands import tag as cmd_tag
    from jobhound.commands import unarchive as cmd_unarchive
    from jobhound.commands import withdraw as cmd_withdraw
    from jobhound.commands.completion import app as completion_app
    from jobhound.commands.config import app as config_app
    from jobhound.commands.file import app as file_app

    _cyclopts_app = App(
        name="jh",
        help="Action-based CLI for tracking a job hunt.",
        version=__version__,
    )

    opp_group = Group("Opportunity actions", sort_key=1)
    object_group = Group("Object groups", sort_key=2)
    utility_group = Group("Utilities", sort_key=3)

    _cyclopts_app.command(cmd_new.run, name="new", group=opp_group)
    _cyclopts_app.command(cmd_apply.run, name="apply", group=opp_group)
    _cyclopts_app.command(cmd_log.run, name="log", group=opp_group)
    _cyclopts_app.command(cmd_accept.run, name="accept", group=opp_group)
    _cyclopts_app.command(cmd_decline.run, name="decline", group=opp_group)
    _cyclopts_app.command(cmd_withdraw.run, name="withdraw", group=opp_group)
    _cyclopts_app.command(cmd_ghost.run, name="ghost", group=opp_group)
    _cyclopts_app.command(cmd_bump.run, name="bump", group=opp_group)
    _cyclopts_app.command(cmd_archive.run, name="archive", group=opp_group)
    _cyclopts_app.command(cmd_unarchive.run, name="unarchive", group=opp_group)
    _cyclopts_app.command(cmd_delete.run, name="delete", group=opp_group)
    _cyclopts_app.command(cmd_show.run, name="show", group=opp_group)
    _cyclopts_app.command(cmd_list.run, name="list", group=opp_group)
    _cyclopts_app.command(cmd_stats.run, name="stats", group=opp_group)
    # Sub-Apps carry their own group via the .group attribute; cyclopts rejects
    # `group=` as a kwarg on .command() for App instances.
    for sub in (cmd_set.app, cmd_clear.app):
        sub.group = opp_group
        _cyclopts_app.command(sub)

    for sub in (
        file_app,
        cmd_contact.app,
        cmd_note.app,
        cmd_tag.app,
        cmd_link.app,
        cmd_browser.app,
    ):
        sub.group = object_group
        _cyclopts_app.command(sub)

    _cyclopts_app.command(cmd_export.run, name="export", group=utility_group)
    cmd_migrate.app.group = utility_group
    _cyclopts_app.command(cmd_migrate.app)
    completion_app.group = utility_group
    _cyclopts_app.command(completion_app)
    config_app.group = utility_group
    _cyclopts_app.command(config_app)

    _cyclopts_app.command(cmd_complete.run, name="__complete", show=False)

    def _run_mcp() -> None:
        """Run the MCP server over stdio."""
        from jobhound.mcp.server import main as mcp_main

        mcp_main()

    _cyclopts_app.command(_run_mcp, name="mcp", group=utility_group)

    return _cyclopts_app


_cyclopts_app_cache: Any = None


def get_app() -> Any:
    """Return the fully-wired cyclopts App, building it on first call."""
    global _cyclopts_app_cache
    if _cyclopts_app_cache is None:
        _cyclopts_app_cache = _build_cyclopts_app()
    return _cyclopts_app_cache


def app(*args: Any, **kwargs: Any) -> Any:
    """Proxy callable that builds the App on first use and dispatches to it.

    Module-level so that tests can patch ``cli.app`` and ``conftest.invoke``
    can import it directly. Using a function (not the App object) means the
    lazy-build stays transparent to callers.
    """
    return get_app()(*args, **kwargs)


def main() -> None:
    """Entry point. Convert known exceptions into clean stderr lines + exit 1.

    Fast-path: if the first argument is ``__complete``, dispatch directly to
    the completion handler without building the full App (skips ~38ms of
    questionary/prompt_toolkit imports).

    Cyclopts dispatches to commands; commands may raise domain / service /
    infrastructure exceptions that descend from ``Exception``. Without this
    wrapper they propagate as full Python tracebacks — opaque for the user.
    This is the outer net; per-command handlers (e.g. ``commands/file.py:_handle_error``)
    still provide richer messages for specific exception families before
    propagation reaches here.
    """
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "__complete":
        # Fast path: skip building the full cyclopts App + all command modules.
        # Dispatch directly to the completion handler.
        from jobhound.commands._complete import run as _complete_run

        _complete_run(*sys.argv[2:])
        return

    # Heal any drift between an installed completion stub and the bundled
    # one — closes the gap where a jh upgrade leaves stale stubs on disk
    # until the user re-runs `jh completion install` (issue #61).
    from jobhound.commands import completion as _completion

    _completion.maybe_refresh_installed_stubs()

    # Auto-migrate legacy notes.md before any command runs. No-op when nothing
    # to migrate; fail-fast (raises) if any opp can't be migrated.
    try:
        from jobhound.application.notes_migration import auto_migrate
        from jobhound.infrastructure.config import load_config
        from jobhound.infrastructure.paths import paths_from_config

        cfg = load_config()
        paths = paths_from_config(cfg)
        auto_migrate(paths.opportunities_dir, paths.archive_dir, paths.db_root)
    except FileNotFoundError:
        # No config / no data root yet — that's fine; the command itself
        # will report the missing config in a more useful way.
        pass
    except RuntimeError as exc:
        # Per-opp migration failed; refuse to run the requested command.
        print(f"jh: auto-migration aborted: {exc}", file=sys.stderr)
        print(
            "jh: run `uv run scripts/migrate_notes_to_directory.py` to investigate.",
            file=sys.stderr,
        )
        sys.exit(1)

    from jobhound.application.file_service import FileServiceError
    from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
    from jobhound.domain.transitions import InvalidTransitionError
    from jobhound.infrastructure.meta_io import ValidationError

    expected = (
        ValidationError,
        SlugNotFoundError,
        AmbiguousSlugError,
        InvalidTransitionError,
        FileServiceError,
    )

    try:
        app()
    except expected as exc:
        print(f"jh: {exc}", file=sys.stderr)
        sys.exit(1)
