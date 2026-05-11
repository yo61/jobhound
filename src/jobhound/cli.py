"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

import typer

from jobhound import __version__
from jobhound.commands import apply as cmd_apply
from jobhound.commands import log as cmd_log
from jobhound.commands import new as cmd_new

app = typer.Typer(
    name="jh",
    help="Action-based CLI for tracking a job hunt.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Root callback; reserved for future global options."""


app.command(name="new")(cmd_new.run)
app.command(name="apply")(cmd_apply.run)
app.command(name="log")(cmd_log.run)
