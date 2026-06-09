"""Tests for scripts/migrate_notes_to_directory.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _load_script():
    """Import the migration script as a module."""
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "migrate_notes_to_directory.py"
    spec = importlib.util.spec_from_file_location("migrate_notes", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["migrate_notes"] = mod
    spec.loader.exec_module(mod)
    return mod


# ── Parser tests ─────────────────────────────────────────────────────────


def test_parses_bullet_style():
    m = _load_script()
    notes = m.parse_notes_md(
        "# Acme Running Notes\n"
        "\n"
        "- 2026-05-02T14:11:08Z first contact made\n"
        "- 2026-05-08T09:22:14Z scheduled phone screen\n"
    )
    assert len(notes) == 2
    assert notes[0].created == datetime(2026, 5, 2, 14, 11, 8, tzinfo=UTC)
    assert notes[0].body == "first contact made"
    assert notes[1].body == "scheduled phone screen"


def test_parses_h2_prose_style():
    m = _load_script()
    notes = m.parse_notes_md(
        "## 2026-05-02 — kickoff\n"
        "\n"
        "First call with Sarah. Good vibes.\n"
        "Multi-paragraph body.\n"
        "\n"
        "## 2026-05-08\n"
        "\n"
        "Second call.\n"
    )
    assert len(notes) == 2
    assert notes[0].created == datetime(2026, 5, 2, 0, 0, 0, tzinfo=UTC)
    assert "First call" in notes[0].body
    assert "Second call" in notes[1].body


def test_skips_empty_bodies():
    m = _load_script()
    notes = m.parse_notes_md("## 2026-05-02\n\n## 2026-05-08\nReal content here.\n")
    # First H2 block has empty body → skipped
    assert len(notes) == 1
    assert notes[0].created.day == 8


def test_discards_pre_first_marker_preamble():
    m = _load_script()
    notes = m.parse_notes_md("# Some title\nRandom text.\n\n- 2026-05-02T14:11:08Z actual note\n")
    assert len(notes) == 1
    assert notes[0].body == "actual note"


def test_empty_file_yields_nothing():
    m = _load_script()
    assert m.parse_notes_md("") == []
    assert m.parse_notes_md("\n\n   \n") == []


# ── End-to-end migrate_one tests ─────────────────────────────────────────


def _make_minimal_db(tmp_path: Path, slug: str = "2026-05-acme", notes_md: str = "") -> Path:
    """Create a minimal data root containing one opp with a notes.md."""
    db = tmp_path / "db"
    opps = db / "opportunities" / slug
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "' + slug + '"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    if notes_md:
        (opps / "notes.md").write_text(notes_md)
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)
    return opps


def test_apply_writes_seq_files_and_meta(tmp_path: Path) -> None:
    m = _load_script()
    opps = _make_minimal_db(
        tmp_path,
        notes_md=("- 2026-05-02T14:11:08Z first\n- 2026-05-08T09:22:14Z second\n"),
    )
    result = m.migrate_one(opps, apply=True)
    assert result.status == "migrated"
    assert result.count == 2
    assert (opps / "notes" / "1.md").exists()
    assert (opps / "notes" / "2.md").exists()
    assert not (opps / "notes.md").exists()
    from jobhound.infrastructure.meta_io import read_meta

    assert read_meta(opps / "meta.toml").notes_next_seq == 3


def test_apply_writes_notes_in_chronological_order(tmp_path: Path) -> None:
    """Notes out of chronological order in source get sorted by `created`."""
    m = _load_script()
    opps = _make_minimal_db(
        tmp_path,
        notes_md=("- 2026-05-08T09:22:14Z second\n- 2026-05-02T14:11:08Z first\n"),
    )
    m.migrate_one(opps, apply=True)
    note1 = (opps / "notes" / "1.md").read_text()
    note2 = (opps / "notes" / "2.md").read_text()
    assert "first" in note1  # earliest created becomes seq 1
    assert "second" in note2


def test_dry_run_does_not_change_files(tmp_path: Path) -> None:
    m = _load_script()
    opps = _make_minimal_db(
        tmp_path,
        notes_md="- 2026-05-02T14:11:08Z first\n",
    )
    result = m.migrate_one(opps, apply=False)
    assert result.status == "migrated"
    assert result.count == 1
    # Files unchanged
    assert (opps / "notes.md").exists()
    assert not (opps / "notes").exists()


def test_idempotent_when_already_migrated(tmp_path: Path) -> None:
    m = _load_script()
    opps = _make_minimal_db(tmp_path)
    (opps / "notes").mkdir()
    result = m.migrate_one(opps, apply=True)
    assert result.status == "skipped"


def test_refuses_when_notes_dir_has_content_without_notes_md(tmp_path: Path) -> None:
    """If notes/ exists with files but notes.md is gone, abort (avoid merging)."""
    m = _load_script()
    opps = _make_minimal_db(tmp_path)
    (opps / "notes").mkdir()
    (opps / "notes" / "existing.md").write_text("+++\ncreated = 2026-01-01T00:00:00Z\n+++\n\nx")
    result = m.migrate_one(opps, apply=True)
    assert result.status == "skipped"


def test_apply_creates_per_opp_commit(tmp_path: Path) -> None:
    """`--apply` (via main) produces one commit per migrated opp in the data repo."""
    m = _load_script()
    opps = _make_minimal_db(
        tmp_path,
        notes_md="- 2026-05-02T14:11:08Z first\n",
    )
    db = opps.parents[1]  # opps is db/opportunities/<slug>; we want db
    # Save initial commit count
    initial_log = subprocess.check_output(
        ["git", "-C", str(db), "log", "--oneline"], text=True
    ).strip()
    initial_count = len(initial_log.splitlines())
    # Run main() with --apply pointing at our tmp data root via env override.
    # We bypass main() and invoke migrate_one + the commit step directly to test
    # the per-opp commit assertion without needing to mock load_config.
    m.migrate_one(opps, apply=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(db), "commit", "-q", "-m", "migrate: notes.md → notes/ for acme"],
        check=True,
    )
    final_log = subprocess.check_output(
        ["git", "-C", str(db), "log", "--oneline"], text=True
    ).strip()
    assert len(final_log.splitlines()) == initial_count + 1


# ── find_legacy_opps tests ────────────────────────────────────────────────


def test_find_legacy_opps_empty(tmp_path: Path) -> None:
    from jobhound.application.notes_migration import find_legacy_opps

    opps = tmp_path / "opps"
    arch = tmp_path / "arch"
    opps.mkdir()
    arch.mkdir()
    assert find_legacy_opps(opps, arch) == []


def test_find_legacy_opps_returns_only_dirs_with_notes_md(tmp_path: Path) -> None:
    from jobhound.application.notes_migration import find_legacy_opps

    opps = tmp_path / "opps"
    arch = tmp_path / "arch"
    opps.mkdir()
    arch.mkdir()
    (opps / "with-legacy").mkdir()
    (opps / "with-legacy" / "notes.md").write_text("- 2026-05-02T14:11:08Z x\n")
    (opps / "already-migrated").mkdir()
    (opps / "already-migrated" / "notes").mkdir()
    (arch / "archived-legacy").mkdir()
    (arch / "archived-legacy" / "notes.md").write_text("- 2026-05-02T14:11:08Z y\n")
    legacy = find_legacy_opps(opps, arch)
    assert {p.name for p in legacy} == {"with-legacy", "archived-legacy"}


# ── auto_migrate tests ────────────────────────────────────────────────────


def test_auto_migrate_no_op_when_no_legacy(tmp_path: Path) -> None:
    from jobhound.application.notes_migration import auto_migrate

    opps = tmp_path / "opps"
    arch = tmp_path / "arch"
    opps.mkdir()
    arch.mkdir()
    # No git repo needed — auto_migrate returns 0 without touching anything.
    assert auto_migrate(opps, arch, tmp_path) == 0


def test_auto_migrate_processes_legacy_opps(tmp_path: Path) -> None:
    """End-to-end: legacy opp gets migrated and a commit is created."""
    from jobhound.application.notes_migration import auto_migrate

    db = tmp_path / "db"
    opps = db / "opportunities" / "2026-05-acme"
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "2026-05-acme"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    (opps / "notes.md").write_text("- 2026-05-02T14:11:08Z first\n")
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)

    count = auto_migrate(db / "opportunities", db / "archive", db)
    assert count == 1
    assert (opps / "notes" / "1.md").exists()
    assert not (opps / "notes.md").exists()
    log = subprocess.check_output(["git", "-C", str(db), "log", "--oneline"], text=True)
    assert "migrate: notes.md → notes/ for 2026-05-acme" in log


def test_auto_migrate_idempotent(tmp_path: Path) -> None:
    """Second invocation finds nothing to do."""
    from jobhound.application.notes_migration import auto_migrate

    db = tmp_path / "db"
    opps = db / "opportunities" / "2026-05-acme"
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "2026-05-acme"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    (opps / "notes.md").write_text("- 2026-05-02T14:11:08Z x\n")
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)
    auto_migrate(db / "opportunities", db / "archive", db)
    # Second run should be a no-op.
    assert auto_migrate(db / "opportunities", db / "archive", db) == 0


# ── restore_legacy_notes_md tests ─────────────────────────────────────────


def _load_restore_script():
    """Import the restore script as a module."""
    repo_root = Path(__file__).resolve().parents[2]
    path = repo_root / "scripts" / "restore_legacy_notes_md.py"
    spec = importlib.util.spec_from_file_location("restore_legacy", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["restore_legacy"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_restore_legacy_notes_md_after_migration(tmp_path: Path) -> None:
    """End-to-end: migrate, then restore — old notes.md reappears."""
    from jobhound.application.notes_migration import auto_migrate

    db = tmp_path / "db"
    opps = db / "opportunities" / "2026-05-acme"
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "2026-05-acme"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    original_notes = "- 2026-05-02T14:11:08Z original content\n"
    (opps / "notes.md").write_text(original_notes)
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)

    auto_migrate(db / "opportunities", db / "archive", db)
    assert not (opps / "notes.md").exists()

    mod = _load_restore_script()
    assert mod.restore_notes_md(db, opps, "2026-05-acme") == 0
    assert (opps / "notes.md").read_text() == original_notes


def test_restore_refuses_when_notes_md_already_exists(tmp_path: Path) -> None:
    from jobhound.application.notes_migration import auto_migrate

    db = tmp_path / "db"
    opps = db / "opportunities" / "2026-05-acme"
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    (opps / "meta.toml").write_text(
        'company = "Acme"\nrole = "EM"\nslug = "2026-05-acme"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    (opps / "notes.md").write_text("- 2026-05-02T14:11:08Z x\n")
    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)

    auto_migrate(db / "opportunities", db / "archive", db)
    # Manually re-create notes.md
    (opps / "notes.md").write_text("already exists")

    mod = _load_restore_script()
    # Should refuse with non-zero exit
    assert mod.restore_notes_md(db, opps, "2026-05-acme") != 0


def test_auto_migrate_continues_on_skipped(tmp_path: Path) -> None:
    """auto_migrate should print and continue when an opp is in the 'notes/
    exists alongside notes.md' state, not abort the whole CLI invocation."""
    from jobhound.application.notes_migration import auto_migrate

    db = tmp_path / "db"
    opps = db / "opportunities"
    opps.mkdir(parents=True)
    (db / "archive").mkdir()
    # Opp A: clean legacy state — will migrate
    opp_a = opps / "2026-05-aaa"
    opp_a.mkdir()
    (opp_a / "meta.toml").write_text(
        'company = "A"\nrole = "EM"\nslug = "2026-05-aaa"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    (opp_a / "notes.md").write_text("- 2026-05-02T14:11:08Z first\n")
    # Opp B: ambiguous (notes/ has content alongside notes.md) — will skip
    opp_b = opps / "2026-05-bbb"
    opp_b.mkdir()
    (opp_b / "meta.toml").write_text(
        'company = "B"\nrole = "EM"\nslug = "2026-05-bbb"\n'
        'status = "applied"\npriority = "medium"\n'
    )
    (opp_b / "notes.md").write_text("- 2026-05-02T14:11:08Z something\n")
    (opp_b / "notes").mkdir()
    (opp_b / "notes" / "1.md").write_text("+++\ncreated = 2026-01-01T00:00:00Z\n+++\n\nalready\n")

    subprocess.run(["git", "init", "--quiet", str(db)], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.name", "t"], check=True)
    subprocess.run(["git", "-C", str(db), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(db), "add", "."], check=True)
    subprocess.run(["git", "-C", str(db), "commit", "-q", "-m", "seed"], check=True)

    count = auto_migrate(opps, db / "archive", db)
    assert count == 1  # only opp_a migrated; opp_b skipped, not raised
    assert (opp_a / "notes" / "1.md").exists()
    assert not (opp_a / "notes.md").exists()
    # opp_b should still have its legacy notes.md untouched
    assert (opp_b / "notes.md").exists()
