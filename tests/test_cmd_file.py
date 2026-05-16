"""Tests for `jh file` subcommand group."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


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


def test_file_read_prints_content(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["file", "read", "acme", "cv.md"])
    assert result.exit_code == 0
    assert "Experienced engineer" in result.output


def test_file_read_with_out_exports(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    dst = tmp_path / "exported.md"
    result = invoke(["file", "read", "acme", "cv.md", "--out", str(dst)])
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


# ── jh file import ───────────────────────────────────────────────────────────


def test_file_import_creates_file(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    src = tmp_path / "cover.md"
    src.write_text("cover letter content")
    result = invoke(["file", "import", "acme", str(src)])
    assert result.exit_code == 0, result.output
    assert "imported" in result.output
    assert "cover.md" in result.output
    written = tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "cover.md"
    assert written.read_text() == "cover letter content"


def test_file_import_with_name_override(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    src = tmp_path / "cover.md"
    src.write_text("cover letter content")
    result = invoke(["file", "import", "acme", str(src), "--name", "letter.md"])
    assert result.exit_code == 0, result.output
    assert "letter.md" in result.output
    written = tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "letter.md"
    assert written.read_text() == "cover letter content"


def test_file_import_exists_requires_overwrite(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    src = tmp_path / "cv.md"
    src.write_text("new content")
    result = invoke(["file", "import", "acme", str(src)])
    assert result.exit_code == 1
    assert "already exists" in result.output


def test_file_import_overwrite_succeeds(tmp_jh, invoke, tmp_path) -> None:
    _seed_opp(tmp_jh.db_path)
    src = tmp_path / "cv.md"
    src.write_text("new cv content")
    result = invoke(["file", "import", "acme", str(src), "--overwrite"])
    assert result.exit_code == 0
    written = tmp_jh.db_path / "opportunities" / "2026-05-acme-em" / "cv.md"
    assert written.read_text() == "new cv content"


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


# ── jh file open ────────────────────────────────────────────────────────────


def test_file_open_darwin_calls_open(tmp_jh, invoke, monkeypatch) -> None:
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("jobhound.application.file_launcher.subprocess.run") as mock_run:
        result = invoke(["file", "open", "acme", "cv.md"])
    assert result.exit_code == 0
    assert "opened" in result.output
    assert "cv.md" in result.output
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "open"
    assert cmd[1].endswith("cv.md")


def test_file_open_linux_calls_xdg_open(tmp_jh, invoke, monkeypatch) -> None:
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "linux")
    with patch("jobhound.application.file_launcher.subprocess.run") as mock_run:
        result = invoke(["file", "open", "acme", "cv.md"])
    assert result.exit_code == 0
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "xdg-open"
    assert cmd[1].endswith("cv.md")


def test_file_open_win32_calls_startfile(tmp_jh, invoke, monkeypatch) -> None:
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "win32")
    mock_startfile = MagicMock()
    with patch("jobhound.application.file_launcher.os.startfile", mock_startfile, create=True):
        result = invoke(["file", "open", "acme", "cv.md"])
    assert result.exit_code == 0
    assert mock_startfile.called
    assert mock_startfile.call_args[0][0].endswith("cv.md")


def test_file_open_temp_file_has_correct_content(tmp_jh, invoke, monkeypatch) -> None:
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    captured_path: list[Path] = []
    real_run = subprocess.run

    def _capture_open(cmd, **kwargs):
        # Only intercept the OS launcher call; pass everything else through
        if cmd and cmd[0] == "open":
            captured_path.append(Path(cmd[1]))
        else:
            return real_run(cmd, **kwargs)

    with patch("jobhound.application.file_launcher.subprocess.run", side_effect=_capture_open):
        result = invoke(["file", "open", "acme", "cv.md"])

    assert result.exit_code == 0
    assert captured_path
    tmp_path = captured_path[0]
    assert tmp_path.name == "cv.md"
    assert tmp_path.exists()
    assert tmp_path.read_text() == "# CV\n\nExperienced engineer\n"


def test_file_open_nonexistent_slug_exits_nonzero(tmp_jh, invoke, monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("jobhound.application.file_launcher.subprocess.run"):
        result = invoke(["file", "open", "no-such-slug", "cv.md"])
    assert result.exit_code != 0


def test_file_open_nonexistent_file_exits_nonzero(tmp_jh, invoke, monkeypatch) -> None:
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch("jobhound.application.file_launcher.subprocess.run"):
        result = invoke(["file", "open", "acme", "no-such-file.pdf"])
    assert result.exit_code != 0


def test_file_open_launcher_failure_exits_nonzero(tmp_jh, invoke, monkeypatch) -> None:
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    with patch(
        "jobhound.application.file_launcher.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "open"),
    ):
        result = invoke(["file", "open", "acme", "cv.md"])
    assert result.exit_code != 0
    assert "could not open" in result.output


def test_file_open_launcher_failure_temp_file_remains(tmp_jh, invoke, monkeypatch) -> None:
    """Temp file should still exist even when the OS launcher fails."""
    _seed_opp(tmp_jh.db_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    captured_path: list[Path] = []
    real_run = subprocess.run

    def _fail_on_open(cmd, **kwargs):
        if cmd and cmd[0] == "open":
            captured_path.append(Path(cmd[1]))
            raise subprocess.CalledProcessError(1, "open")
        else:
            return real_run(cmd, **kwargs)

    with patch(
        "jobhound.application.file_launcher.subprocess.run",
        side_effect=_fail_on_open,
    ):
        result = invoke(["file", "open", "acme", "cv.md"])

    assert result.exit_code != 0
    assert captured_path
    # Temp file must still be on disk so user can retry manually
    assert captured_path[0].exists()
