"""Tests for `jh __complete` hidden subcommand and its dispatch."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _seed_slug(db_path: Path, slug: str) -> Path:
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "X"\nrole = "Y"\nslug = "{slug}"\n'
        'status = "applied"\npriority = "high"\nsource = "X"\n'
        "applied_on = 2026-05-01T12:00:00+00:00\n"
        "last_activity = 2026-05-01T12:00:00+00:00\n"
        "tags = []\n",
    )
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    return opp_dir


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


def test_complete_show_returns_slugs(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh show ""` lists slugs from opportunities_dir."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    _seed_slug(tmp_jh.db_path, "2026-05-beta-eng")

    result = invoke(["__complete", "zsh", "jh", "show", ""])
    out = set(result.output.split())
    assert "2026-05-acme-em" in out
    assert "2026-05-beta-eng" in out


def test_complete_show_returns_canonical_not_filtered(tmp_jh, invoke) -> None:
    """Slug completer returns ALL slugs regardless of partial prefix."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    _seed_slug(tmp_jh.db_path, "2026-05-beta-eng")

    result = invoke(["__complete", "zsh", "jh", "show", "ac"])
    out = set(result.output.split())
    assert "2026-05-acme-em" in out
    assert "2026-05-beta-eng" in out


def test_complete_file_open_returns_slugs(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh file open ""` lists slugs (slug at depth 2)."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "file", "open", ""])
    assert "2026-05-acme-em" in result.output


def test_complete_no_opps_dir_returns_empty(tmp_jh, invoke) -> None:
    """No opportunities_dir → no slug candidates; does not crash."""
    import shutil

    shutil.rmtree(tmp_jh.db_path / "opportunities")
    result = invoke(["__complete", "zsh", "jh", "show", ""])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_complete_file_open_filenames(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh file open <slug> ""` lists files in the opp."""
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    (opp_dir / "notes.md").write_text("hi\n")
    (opp_dir / "research.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "files", "--quiet"],
        check=True,
        capture_output=True,
    )

    result = invoke(["__complete", "zsh", "jh", "file", "open", "2026-05-acme-em", ""])
    lines = set(result.output.splitlines())
    assert "notes.md" in lines
    assert "research.md" in lines
    assert "meta.toml" not in lines  # meta.toml is protected; excluded by file_service.list_


def test_complete_filename_with_space_is_unquoted(tmp_jh, invoke) -> None:
    """Filenames with spaces are emitted as-is (one per line).

    The shell script does the quoting; the completer emits raw names.
    """
    opp_dir = _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    (opp_dir / "Job Description.md").write_text("hi\n")
    subprocess.run(["git", "-C", str(tmp_jh.db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(tmp_jh.db_path), "commit", "-m", "f", "--quiet"],
        check=True,
        capture_output=True,
    )

    result = invoke(["__complete", "zsh", "jh", "file", "open", "2026-05-acme-em", ""])
    lines = set(result.output.splitlines())
    assert "Job Description.md" in lines  # exactly one line, with the space


def test_complete_filename_unresolvable_slug_empty(tmp_jh, invoke) -> None:
    """An unresolvable slug at position 0 → empty filename candidates."""
    result = invoke(["__complete", "zsh", "jh", "file", "open", "not-a-real-slug", ""])
    assert result.exit_code == 0
    assert result.output.strip() == ""


def test_complete_set_status_returns_status_enum(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh set status <slug> ""` lists Status values."""
    _seed_slug(tmp_jh.db_path, "2026-05-acme-em")
    result = invoke(["__complete", "zsh", "jh", "set", "status", "2026-05-acme-em", ""])
    out = set(result.output.split())
    expected = {
        "prospect",
        "applied",
        "screen",
        "interview",
        "offer",
        "accepted",
        "declined",
        "rejected",
        "withdrawn",
        "ghosted",
    }
    assert expected <= out


def test_complete_set_priority_to_flag_returns_priority_enum(tmp_jh, invoke) -> None:
    """`jh __complete zsh jh set priority --to ""` lists Priority values."""
    result = invoke(["__complete", "zsh", "jh", "set", "priority", "--to", ""])
    out = set(result.output.split())
    assert out == {"high", "medium", "low"}
