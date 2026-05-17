"""Tests for `jh completion` subgroup."""

from __future__ import annotations

from pathlib import Path


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


def test_completion_install_writes_script_to_dest(tmp_path: Path, invoke) -> None:
    result = invoke(["completion", "install", "--shell", "bash", "--dest", str(tmp_path)])
    assert result.exit_code == 0
    target = tmp_path / "jh"
    assert target.exists()
    assert "complete -F _jh_complete jh" in target.read_text()


def test_completion_install_is_idempotent(tmp_path: Path, invoke) -> None:
    invoke(["completion", "install", "--shell", "zsh", "--dest", str(tmp_path)])
    target = tmp_path / "_jh"
    invoke(["completion", "install", "--shell", "zsh", "--dest", str(tmp_path)])
    # Re-installing the same content should not duplicate or break.
    assert target.read_text().count("#compdef jh") == 1


def test_completion_install_backs_up_existing_different_content(tmp_path: Path, invoke) -> None:
    target = tmp_path / "jh"
    target.write_text("OLD CONTENT\n")
    invoke(["completion", "install", "--shell", "bash", "--dest", str(tmp_path)])
    bak = tmp_path / "jh.bak"
    assert bak.exists()
    assert bak.read_text() == "OLD CONTENT\n"
