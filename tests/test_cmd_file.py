"""Tests for `jh file` subcommand group."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _seed_opp(db_path: Path, slug: str = "2026-05-acme-em") -> Path:
    """Seed one opportunity with a notes.md and a cv.md."""
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "Acme"\nrole = "EM"\nslug = "{slug}"\n'
        'status = "applied"\npriority = "high"\n'
        "applied_on = 2026-05-01\nlast_activity = 2026-05-11\n",
    )
    (opp_dir / "notes.md").write_text("- 2026-05-01 first note\n")
    (opp_dir / "cv.md").write_text("# CV\n\nExperienced engineer\n")
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    return opp_dir


def test_file_list_shows_files(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "list", "acme"])
    assert result.exit_code == 0
    assert "notes.md" in result.output
    assert "cv.md" in result.output


def test_file_show_prints_content(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "show", "acme", "cv.md"])
    assert result.exit_code == 0
    assert "Experienced engineer" in result.output


def test_file_show_with_out_exports(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    dst = tmp_path / "exported.md"
    result = invoke(["file", "show", "acme", "cv.md", "--out", str(dst)])
    assert result.exit_code == 0
    assert "exported" in result.output
    assert "Experienced engineer" in dst.read_text()


def test_file_write_creates_new(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "write", "acme", "draft.md", "--content", "v1"])
    assert result.exit_code == 0
    assert "wrote" in result.output
    written = tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "draft.md"
    assert written.read_text() == "v1"


def test_file_write_meta_toml_rejected(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "write", "acme", "meta.toml", "--content", "x"])
    assert result.exit_code == 1
    assert "meta.toml is protected" in result.output


def test_file_write_exists_requires_overwrite(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "write", "acme", "cv.md", "--content", "v2"])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_file_write_overwrite_succeeds(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "write", "acme", "cv.md", "--content", "v2", "--overwrite"])
    assert result.exit_code == 0
    written = tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "cv.md"
    assert written.read_text() == "v2"


def test_file_write_from_path(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    src = tmp_path / "external.md"
    src.write_text("external content")
    result = invoke(["file", "write", "acme", "imported.md", "--from", str(src)])
    assert result.exit_code == 0


def test_file_append_to_existing(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "append", "acme", "notes.md", "--content", "new note\n"])
    assert result.exit_code == 0
    assert "appended" in result.output
    notes = (tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "notes.md").read_text()
    assert "new note" in notes


def test_file_delete_with_yes_succeeds(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "delete", "acme", "cv.md", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output
    assert not (tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "cv.md").exists()
