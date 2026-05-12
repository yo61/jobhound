"""Smoke tests for the cyclopts app skeleton."""

import jobhound


def test_help_lists_commands(invoke) -> None:
    """`--help` succeeds and mentions the program name."""
    result = invoke(["--help"])
    assert result.exit_code == 0
    assert "jh" in result.output.lower() or "Usage" in result.output


def test_version_flag(invoke) -> None:
    """`--version` prints the package version (sourced from pyproject)."""
    result = invoke(["--version"])
    assert result.exit_code == 0
    assert jobhound.__version__ in result.output
