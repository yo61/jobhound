"""Tests for `jh export`."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _seed(db_path: Path, slug: str, *, status: str, priority: str, source: str) -> None:
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "X"\nrole = "Y"\nslug = "{slug}"\n'
        f'status = "{status}"\npriority = "{priority}"\nsource = "{source}"\n'
        "applied_on = 2026-05-01T12:00:00+00:00\nlast_activity = 2026-05-11T12:00:00+00:00\n",
    )


def _seed_archived(db_path: Path, slug: str) -> None:
    opp_dir = db_path / "archive" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "meta.toml").write_text(
        f'company = "A"\nrole = "Z"\nslug = "{slug}"\nstatus = "rejected"\npriority = "low"\n',
    )


def _seed_all(db_path: Path) -> None:
    _seed(db_path, "2026-05-acme", status="applied", priority="high", source="LinkedIn")
    _seed(db_path, "2026-04-beta", status="screen", priority="medium", source="Referral")
    _seed(db_path, "2026-05-charlie", status="applied", priority="low", source="LinkedIn")
    _seed_archived(db_path, "2026-03-delta")
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )


def test_export_default_returns_all_non_archived(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert slugs == ["2026-04-beta", "2026-05-acme", "2026-05-charlie"]


def test_export_envelope_metadata(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export"])
    payload = json.loads(result.output)
    assert payload["schema_version"] == 2
    assert "timestamp" in payload
    assert payload["db_root"] == str(tmp_jh.db_path)


def test_export_filter_by_status_comma_separated(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "applied,screen"])
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert slugs == ["2026-04-beta", "2026-05-acme", "2026-05-charlie"]


def test_export_filter_by_status_repeated(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "applied", "--status", "screen"])
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert slugs == ["2026-04-beta", "2026-05-acme", "2026-05-charlie"]


def test_export_filter_by_priority(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--priority", "high"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert slugs == ["2026-05-acme"]


def test_export_filter_by_slug_substring(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--slug", "acme"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert slugs == ["2026-05-acme"]


def test_export_active_only(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--active-only", "--include-archived"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert "2026-03-delta" not in slugs


def test_export_include_archived(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--include-archived"])
    payload = json.loads(result.output)
    slugs = sorted(o["slug"] for o in payload["opportunities"])
    assert "2026-03-delta" in slugs
    archived = {o["slug"]: o["archived"] for o in payload["opportunities"]}
    assert archived["2026-03-delta"] is True
    assert archived["2026-05-acme"] is False


def test_export_filters_and_across_dimensions(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "applied", "--priority", "high"])
    payload = json.loads(result.output)
    slugs = [o["slug"] for o in payload["opportunities"]]
    assert slugs == ["2026-05-acme"]


def test_export_invalid_status_exits_2(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--status", "bogus"])
    assert result.exit_code == 2


def test_export_empty_result_still_exits_0(tmp_jh, invoke) -> None:
    _seed_all(tmp_jh.db_path)
    result = invoke(["export", "--slug", "no-match"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["opportunities"] == []
