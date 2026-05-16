"""End-to-end: jh show --json and jh export emit Z-suffix datetimes on lifecycle fields."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

# Z-suffix pattern: YYYY-MM-DDTHH:MM:SS[.ffffff]Z
Z_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")

LIFECYCLE_FIELDS = ("first_contact", "applied_on", "last_activity", "next_action_due")


def _seed_opp(db_path: Path, slug: str = "2026-05-acme-em") -> Path:
    """Seed one opportunity with all lifecycle fields populated and return its dir."""
    opp_dir = db_path / "opportunities" / slug
    opp_dir.mkdir(parents=True)
    (opp_dir / "correspondence").mkdir()
    (opp_dir / "meta.toml").write_text(
        f'company = "Acme"\nrole = "EM"\nslug = "{slug}"\n'
        'status = "applied"\npriority = "high"\nsource = "LinkedIn"\n'
        "first_contact = 2026-04-28T09:00:00+00:00\n"
        "applied_on = 2026-05-01T12:00:00+00:00\n"
        "last_activity = 2026-05-11T12:00:00+00:00\n"
        "next_action_due = 2026-05-20T09:00:00+00:00\n"
        'tags = ["remote"]\n',
    )
    subprocess.run(["git", "-C", str(db_path), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(db_path), "commit", "-m", "seed", "--quiet"],
        check=True,
        capture_output=True,
    )
    return opp_dir


def test_show_json_lifecycle_fields_are_z_suffix(tmp_jh, invoke) -> None:
    """jh show --json emits Z-suffix datetimes for all four lifecycle fields."""
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme", "--json"])
    assert result.exit_code == 0, result.output

    envelope = json.loads(result.output)
    assert envelope["schema_version"] == 2

    opp = envelope["opportunity"]
    for field in LIFECYCLE_FIELDS:
        value = opp.get(field)
        assert value is not None, f"{field} is missing from output"
        assert Z_RE.match(value), f"{field} = {value!r} does not match Z-suffix pattern"


def test_show_json_schema_version_is_2(tmp_jh, invoke) -> None:
    """jh show --json reports schema_version == 2."""
    _seed_opp(tmp_jh.db_path)
    result = invoke(["show", "acme", "--json"])
    assert result.exit_code == 0, result.output

    envelope = json.loads(result.output)
    assert envelope["schema_version"] == 2


def test_export_json_lifecycle_fields_are_z_suffix(tmp_jh, invoke) -> None:
    """jh export emits Z-suffix datetimes for all four lifecycle fields."""
    _seed_opp(tmp_jh.db_path)
    result = invoke(["export"])
    assert result.exit_code == 0, result.output

    envelope = json.loads(result.output)
    assert envelope["schema_version"] == 2

    assert len(envelope["opportunities"]) == 1
    opp = envelope["opportunities"][0]
    for field in LIFECYCLE_FIELDS:
        value = opp.get(field)
        assert value is not None, f"{field} is missing from export output"
        assert Z_RE.match(value), f"{field} = {value!r} does not match Z-suffix pattern"


def test_export_json_schema_version_is_2(tmp_jh, invoke) -> None:
    """jh export reports schema_version == 2."""
    _seed_opp(tmp_jh.db_path)
    result = invoke(["export"])
    assert result.exit_code == 0, result.output

    envelope = json.loads(result.output)
    assert envelope["schema_version"] == 2
