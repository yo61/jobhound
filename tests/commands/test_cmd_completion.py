"""Tests for `jh completion` subgroup."""

from __future__ import annotations


def test_completion_bash_prints_script(invoke) -> None:
    result = invoke(["completion", "bash"])
    assert result.exit_code == 0
    assert "complete -F _jh_complete jh" in result.output


def test_completion_zsh_prints_script(invoke) -> None:
    result = invoke(["completion", "zsh"])
    assert result.exit_code == 0
    assert "#compdef jh" in result.output


def test_completion_fish_prints_script(invoke) -> None:
    result = invoke(["completion", "fish"])
    assert result.exit_code == 0
    assert "complete -c jh" in result.output
