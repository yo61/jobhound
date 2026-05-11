"""Smoke tests for the typer app skeleton."""

from typer.testing import CliRunner

from jobhound.cli import app


def test_help_lists_no_commands_yet() -> None:
    """Before any commands are registered, --help still succeeds."""
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "jh" in result.output.lower() or "Usage" in result.output


def test_version_flag(tmp_jh) -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output
