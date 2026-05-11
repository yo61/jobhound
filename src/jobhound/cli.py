"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

from cyclopts import App

from jobhound import __version__
from jobhound.commands import apply as cmd_apply
from jobhound.commands import log as cmd_log
from jobhound.commands import new as cmd_new

app = App(
    name="jh",
    help="Action-based CLI for tracking a job hunt.",
    version=__version__,
)

app.command(cmd_new.run, name="new")
app.command(cmd_apply.run, name="apply")
app.command(cmd_log.run, name="log")
