"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

from cyclopts import App

from jobhound import __version__
from jobhound.commands import accept as cmd_accept
from jobhound.commands import apply as cmd_apply
from jobhound.commands import decline as cmd_decline
from jobhound.commands import ghost as cmd_ghost
from jobhound.commands import log as cmd_log
from jobhound.commands import new as cmd_new
from jobhound.commands import note as cmd_note
from jobhound.commands import priority as cmd_priority
from jobhound.commands import tag as cmd_tag
from jobhound.commands import withdraw as cmd_withdraw

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
app.command(cmd_note.run, name="note")
app.command(cmd_priority.run, name="priority")
app.command(cmd_tag.run, name="tag")
