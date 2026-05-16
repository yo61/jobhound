"""Tests for jh archive and delete."""

import subprocess


def _seed(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])


def test_archive_moves_folder(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["archive", "foo"])
    assert result.exit_code == 0, result.output
    assert not (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").exists()
    assert (tmp_jh.db_path / "archive" / "2026-05-foo-em").is_dir()
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "archive: 2026-05-foo-em" in log


def test_delete_removes_folder(tmp_jh, invoke) -> None:
    _seed(invoke)
    result = invoke(["delete", "foo", "--yes"])
    assert result.exit_code == 0, result.output
    assert not (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").exists()
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "delete: 2026-05-foo-em" in log


def test_delete_without_yes_aborts_in_headless(tmp_jh, invoke) -> None:
    """In a non-TTY test environment, questionary returns None so we abort."""
    _seed(invoke)
    result = invoke(["delete", "foo"])
    assert result.exit_code != 0
    assert (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").exists()
