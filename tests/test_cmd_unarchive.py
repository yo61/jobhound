"""Tests for `jh unarchive`."""

import subprocess


def _seed_archived(invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    invoke(["archive", "foo"])


def test_unarchive_moves_folder_back(tmp_jh, invoke) -> None:
    _seed_archived(invoke)
    result = invoke(["unarchive", "foo"])
    assert result.exit_code == 0, result.output
    assert (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").is_dir()
    assert not (tmp_jh.db_path / "archive" / "2026-05-foo-em").exists()
    log = subprocess.check_output(["git", "-C", str(tmp_jh.db_path), "log", "--oneline"], text=True)
    assert "unarchive: 2026-05-foo-em" in log


def test_unarchive_prints_slug(tmp_jh, invoke) -> None:
    _seed_archived(invoke)
    result = invoke(["unarchive", "foo"])
    assert "unarchived: 2026-05-foo-em" in result.output


def test_unarchive_missing_slug_errors(tmp_jh, invoke) -> None:
    result = invoke(["unarchive", "nonesuch"])
    assert result.exit_code != 0
    assert "no archived opportunity matches" in result.output


def test_unarchive_smart_error_when_slug_is_active(tmp_jh, invoke) -> None:
    invoke(["new", "--company", "Foo", "--role", "EM", "--now", "2026-05-01T12:00:00Z"])
    result = invoke(["unarchive", "foo"])
    assert result.exit_code != 0
    assert "matches an active opportunity" in result.output
    assert "2026-05-foo-em" in result.output
    # Sanity: nothing was moved.
    assert (tmp_jh.db_path / "opportunities" / "2026-05-foo-em").exists()
    assert not (tmp_jh.db_path / "archive" / "2026-05-foo-em").exists()
