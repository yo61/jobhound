"""Shared fixtures for all tests.

`tmp_jh` sets up an XDG-isolated environment and a freshly-initialised
data root, so each test gets a real `Paths` to operate on.

`invoke` runs the cyclopts app against a list of args, capturing stdout
and stderr and reporting an exit code in a CliRunner-style `Result`.

`query_paths` builds a `tmp_path` data root with three seeded opportunities
for read-side and MCP tests.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
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
    """Tmp data root with three seeded opportunities for read-side tests."""
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


@dataclass(frozen=True)
class JhEnv:
    config_home: Path
    data_home: Path
    cache_home: Path
    state_home: Path
    db_path: Path


@pytest.fixture
def tmp_jh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> JhEnv:
    """Set up XDG dirs, a config that points at a tmp db, and `git init` the db."""
    config_home = tmp_path / "config"
    data_home = tmp_path / "data"
    cache_home = tmp_path / "cache"
    state_home = tmp_path / "state"
    for d in (config_home, data_home, cache_home, state_home):
        d.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_home))
    monkeypatch.setenv("XDG_STATE_HOME", str(state_home))

    db_path = data_home / "jh"
    db_path.mkdir()
    subprocess.run(["git", "init", "--quiet", str(db_path)], check=True)
    subprocess.run(["git", "-C", str(db_path), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(db_path), "config", "user.email", "t@t"], check=True)
    (db_path / "opportunities").mkdir()
    (db_path / "archive").mkdir()
    (db_path / "_shared").mkdir()
    return JhEnv(config_home, data_home, cache_home, state_home, db_path)


@dataclass(frozen=True)
class Result:
    exit_code: int
    output: str


@pytest.fixture
def invoke(capsys: pytest.CaptureFixture[str]):
    """Run the cyclopts app and return a Result with exit_code and combined output."""
    from jobhound.cli import app

    def _invoke(args: list[str]) -> Result:
        try:
            app(args, exit_on_error=False)
            exit_code = 0
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
        except BaseException:
            exit_code = 2
        captured = capsys.readouterr()
        return Result(exit_code=exit_code, output=captured.out + captured.err)

    return _invoke
