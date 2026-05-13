"""Shared fixtures for application-layer tests.

`query_paths` builds a `tmp_path` data root with three opportunities:
- one active and recent ("acme")
- one active and stale ("beta", last activity 30+ days before `TODAY`)
- one archived ("gamma", in archive/)

Each opp also has a small set of files for read_file / files() tests.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from jobhound.infrastructure.paths import Paths

TODAY = date(2026, 5, 13)


def _write_meta(opp_dir: Path, **fields: Any) -> None:
    """Write a minimal meta.toml. fields override defaults."""
    opp_dir.mkdir(parents=True, exist_ok=True)
    (opp_dir / "correspondence").mkdir(exist_ok=True)
    defaults: dict[str, Any] = {
        "company": "Acme",
        "role": "Engineer",
        "slug": opp_dir.name,
        "status": "applied",
        "priority": "medium",
    }
    defaults.update(fields)
    lines = []
    for key, value in defaults.items():
        if isinstance(value, str):
            lines.append(f'{key} = "{value}"')
        elif isinstance(value, list):
            inner = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{inner}]")
        elif isinstance(value, date):
            lines.append(f"{key} = {value.isoformat()}")
        else:
            lines.append(f"{key} = {value!r}")
    (opp_dir / "meta.toml").write_text("\n".join(lines) + "\n")


@pytest.fixture
def query_paths(tmp_path: Path) -> Paths:
    db_root = tmp_path / "db"
    opps_dir = db_root / "opportunities"
    arch_dir = db_root / "archive"
    shared_dir = db_root / "_shared"
    for d in (opps_dir, arch_dir, shared_dir):
        d.mkdir(parents=True)

    _write_meta(
        opps_dir / "2026-05-acme-em",
        company="Acme",
        role="EM",
        status="applied",
        priority="high",
        source="LinkedIn",
        applied_on=date(2026, 5, 1),
        last_activity=date(2026, 5, 11),
        tags=["remote"],
    )
    (opps_dir / "2026-05-acme-em" / "notes.md").write_text("notes\n")
    (opps_dir / "2026-05-acme-em" / "cv.md").write_text("# CV\n")
    (opps_dir / "2026-05-acme-em" / "correspondence" / "intro.md").write_text("hi\n")

    _write_meta(
        opps_dir / "2026-04-beta-eng",
        company="Beta",
        role="Engineer",
        status="screen",
        priority="medium",
        source="Referral",
        applied_on=date(2026, 4, 1),
        last_activity=date(2026, 4, 10),
    )

    _write_meta(
        arch_dir / "2026-03-gamma-staff",
        company="Gamma",
        role="Staff Engineer",
        status="rejected",
        priority="low",
        source="LinkedIn",
        applied_on=date(2026, 3, 1),
        last_activity=date(2026, 3, 20),
    )

    return Paths(
        db_root=db_root,
        opportunities_dir=opps_dir,
        archive_dir=arch_dir,
        shared_dir=shared_dir,
        cache_dir=tmp_path / "cache",
        state_dir=tmp_path / "state",
    )
