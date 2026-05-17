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
