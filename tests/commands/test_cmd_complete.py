"""Tests for `jh __complete` hidden subcommand and its dispatch."""

from __future__ import annotations


def test_complete_command_is_hidden_from_help(invoke) -> None:
    """`jh --help` must not list `__complete`."""
    result = invoke(["--help"])
    assert result.exit_code == 0
    assert "__complete" not in result.output


def test_complete_runs_and_exits_zero(invoke) -> None:
    """`jh __complete zsh jh ""` runs without error."""
    result = invoke(["__complete", "zsh", "jh", ""])
    assert result.exit_code == 0


def test_complete_top_level_lists_visible_commands(invoke) -> None:
    """`jh __complete zsh jh ""` lists top-level commands."""
    result = invoke(["__complete", "zsh", "jh", ""])
    out = set(result.output.split())
    assert "show" in out
    assert "list" in out
    assert "new" in out
    assert "file" in out
    assert "set" in out
    assert "clear" in out
    assert "remove" in out
    assert "__complete" not in out  # hidden


def test_complete_sub_app_lists_subcommands(invoke) -> None:
    """`jh __complete zsh jh file ""` lists `file` subcommands."""
    result = invoke(["__complete", "zsh", "jh", "file", ""])
    out = set(result.output.split())
    assert {"list", "read", "write", "append", "delete", "open", "import"} <= out
