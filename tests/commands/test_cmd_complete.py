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
