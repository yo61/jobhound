"""Tests for `jh show`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _seed_opp(db_path: Path, slug: str = "2026-05-acme-em") -> Path:
    """Seed one opportunity and return its dir."""
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "Acme"\nrole = "EM"\nslug = "{slug}"\n'
        'status = "applied"\npriority = "high"\nsource = "LinkedIn"\n'
        "applied_on = 2026-05-01T12:00:00+00:00\nlast_activity = 2026-05-11T12:00:00+00:00\n"
        'tags = ["remote"]\n',
    )
    (opp_dir / "resume.pdf").write_bytes(b"%PDF-1.4 fake\n")
    notes_dir = opp_dir / "notes"
    notes_dir.mkdir()
    (notes_dir / "0001.md").write_text("+++\nseq = 1\n+++\nfirst note\n")
    (opp_dir / "correspondence" / "0001-email.eml").write_text("From: x\n")
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    return opp_dir


def test_show_human_output_contains_company_status_path(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme"])
    assert result.exit_code == 0
    assert "Acme" in result.output
    assert "EM" in result.output
    assert "applied" in result.output.lower()
    assert "2026-05-acme-em" in result.output


def test_show_human_lists_files(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme"])
    assert "resume.pdf" in result.output


def test_show_human_hides_meta_and_protected_streams(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme"])
    assert "meta.toml" not in result.output
    assert "notes/" not in result.output
    assert "0001.md" not in result.output
    assert "correspondence/" not in result.output


def test_show_json_output_is_envelope(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema_version"] == 2
    assert "timestamp" in payload
    assert payload["db_root"] == str(tmp_jh.db_path)
    assert payload["opportunity"]["slug"] == "2026-05-acme-em"
    assert payload["opportunity"]["computed"]["is_active"] is True


def test_show_short_flag_j_equals_long_json(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme", "-j"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["opportunity"]["slug"] == "2026-05-acme-em"


def test_show_unknown_slug_exits_2(tmp_jh, invoke) -> None:
    result = invoke(["show", "nonexistent"])
    assert result.exit_code == 2
    assert "no opportunity matches" in result.output


def test_show_resolves_substring(tmp_jh, invoke) -> None:
    _seed_opp(tmp_jh.db_path, slug="2026-05-acme-em")
    result = invoke(["show", "acme"])
    assert result.exit_code == 0
    assert "2026-05-acme-em" in result.output
