"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

from cyclopts import App

from jobhound import __version__
from jobhound.commands import accept as cmd_accept
from jobhound.commands import add as cmd_add
from jobhound.commands import apply as cmd_apply
from jobhound.commands import archive as cmd_archive
from jobhound.commands import bump as cmd_bump
from jobhound.commands import clear as cmd_clear
from jobhound.commands import decline as cmd_decline
from jobhound.commands import delete as cmd_delete
from jobhound.commands import export as cmd_export
from jobhound.commands import ghost as cmd_ghost
from jobhound.commands import list_ as cmd_list
from jobhound.commands import log as cmd_log
from jobhound.commands import migrate as cmd_migrate
from jobhound.commands import new as cmd_new
from jobhound.commands import remove as cmd_remove
from jobhound.commands import set as cmd_set
from jobhound.commands import show as cmd_show
from jobhound.commands import stats as cmd_stats
from jobhound.commands import withdraw as cmd_withdraw
from jobhound.commands.file import app as file_app

app = App(
    name="jh",
    help="Action-based CLI for tracking a job hunt.",
    version=__version__,
)

app.command(cmd_new.run, name="new")
app.command(cmd_apply.run, name="apply")
app.command(cmd_log.run, name="log")
app.command(cmd_withdraw.run, name="withdraw")
app.command(cmd_ghost.run, name="ghost")
app.command(cmd_accept.run, name="accept")
app.command(cmd_decline.run, name="decline")
app.command(cmd_bump.run, name="bump")
app.command(cmd_list.run, name="list")
app.command(cmd_archive.run, name="archive")
app.command(cmd_delete.run, name="delete")
app.command(cmd_show.run, name="show")
app.command(cmd_export.run, name="export")
app.command(cmd_stats.run, name="stats")
app.command(file_app)
app.command(cmd_set.app)
app.command(cmd_clear.app)
app.command(cmd_add.app)
app.command(cmd_remove.app)
app.command(cmd_migrate.app)


def _run_mcp() -> None:
    """Run the MCP server over stdio."""
    from jobhound.mcp.server import main as mcp_main

    mcp_main()


app.command(_run_mcp, name="mcp")


def main() -> None:
    """Entry point. Convert known exceptions into clean stderr lines + exit 1.

    Cyclopts dispatches to commands; commands may raise domain / service /
    infrastructure exceptions that descend from `Exception`. Without this
    wrapper they propagate as full Python tracebacks — opaque for the user.
    This is the outer net; per-command handlers (e.g. `commands/file.py:_handle_error`)
    still provide richer messages for specific exception families before
    propagation reaches here.
    """
    import sys

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
