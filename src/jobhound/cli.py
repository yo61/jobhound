"""The `jh` CLI entry point. Commands are registered explicitly below."""

from __future__ import annotations

from cyclopts import App

from jobhound import __version__
from jobhound.commands import accept as cmd_accept
from jobhound.commands import apply as cmd_apply
from jobhound.commands import archive as cmd_archive
from jobhound.commands import contact as cmd_contact
from jobhound.commands import decline as cmd_decline
from jobhound.commands import delete as cmd_delete
from jobhound.commands import edit as cmd_edit
from jobhound.commands import export as cmd_export
from jobhound.commands import ghost as cmd_ghost
from jobhound.commands import link as cmd_link
from jobhound.commands import list_ as cmd_list
from jobhound.commands import log as cmd_log
from jobhound.commands import new as cmd_new
from jobhound.commands import note as cmd_note
from jobhound.commands import priority as cmd_priority
from jobhound.commands import show as cmd_show
from jobhound.commands import sync as cmd_sync
from jobhound.commands import tag as cmd_tag
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
app.command(cmd_note.run, name="note")
app.command(cmd_priority.run, name="priority")
app.command(cmd_tag.run, name="tag")
app.command(cmd_link.run, name="link")
app.command(cmd_contact.run, name="contact")
app.command(cmd_list.run, name="list")
app.command(cmd_edit.run, name="edit")
app.command(cmd_archive.run, name="archive")
app.command(cmd_delete.run, name="delete")
app.command(cmd_sync.run, name="sync")
app.command(cmd_show.run, name="show")
app.command(cmd_export.run, name="export")
app.command(file_app)


def _run_mcp() -> None:
    """Entry point for `jh mcp` — starts the MCP server on stdio."""
    from jobhound.mcp.server import main as mcp_main

    mcp_main()


app.command(_run_mcp, name="mcp")
