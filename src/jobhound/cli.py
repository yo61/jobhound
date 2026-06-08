"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

from typing import Any


def _build_cyclopts_app() -> Any:
    """Build and return the fully-wired cyclopts App.

    Called lazily so that the heavy command-module imports (questionary,
    prompt_toolkit, etc.) are skipped on the ``__complete`` fast-path.
    """
    from cyclopts import App

    from jobhound import __version__
    from jobhound.commands import _complete as cmd_complete
    from jobhound.commands import accept as cmd_accept
    from jobhound.commands import apply as cmd_apply
    from jobhound.commands import archive as cmd_archive
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
    from jobhound.commands.file import app as file_app

    _cyclopts_app = App(
        name="jh",
        help="Action-based CLI for tracking a job hunt.",
        version=__version__,
    )

    _cyclopts_app.command(cmd_new.run, name="new")
    _cyclopts_app.command(cmd_apply.run, name="apply")
    _cyclopts_app.command(cmd_log.run, name="log")
    _cyclopts_app.command(cmd_withdraw.run, name="withdraw")
    _cyclopts_app.command(cmd_ghost.run, name="ghost")
    _cyclopts_app.command(cmd_accept.run, name="accept")
    _cyclopts_app.command(cmd_decline.run, name="decline")
    _cyclopts_app.command(cmd_bump.run, name="bump")
    _cyclopts_app.command(cmd_list.run, name="list")
    _cyclopts_app.command(cmd_archive.run, name="archive")
    _cyclopts_app.command(cmd_unarchive.run, name="unarchive")
    _cyclopts_app.command(cmd_delete.run, name="delete")
    _cyclopts_app.command(cmd_show.run, name="show")
    _cyclopts_app.command(cmd_export.run, name="export")
    _cyclopts_app.command(cmd_stats.run, name="stats")
    _cyclopts_app.command(file_app)
    _cyclopts_app.command(completion_app)
    _cyclopts_app.command(cmd_set.app)
    _cyclopts_app.command(cmd_clear.app)
    _cyclopts_app.command(cmd_contact.app)
    _cyclopts_app.command(cmd_note.app)
    _cyclopts_app.command(cmd_tag.app)
    _cyclopts_app.command(cmd_link.app)
    _cyclopts_app.command(cmd_migrate.app)
    _cyclopts_app.command(cmd_complete.run, name="__complete", show=False)

    def _run_mcp() -> None:
        """Run the MCP server over stdio."""
        from jobhound.mcp.server import main as mcp_main

        mcp_main()

    _cyclopts_app.command(_run_mcp, name="mcp")

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
