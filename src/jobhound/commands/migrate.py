"""`jh migrate` subcommand group. Currently exposes `utc-timestamps`."""

from __future__ import annotations

from pathlib import Path

from cyclopts import App

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.git import commit_change
from jobhound.migrations.utc_timestamps import migrate_data_root

app = App(name="migrate", help="One-shot data migrations.")


@app.command(name="utc-timestamps")
def utc_timestamps() -> None:
    """Migrate bare-date lifecycle fields to tz-aware UTC datetimes.

    Idempotent. Safe to re-run. Writes a single git commit if anything changed.
    """
    cfg = load_config()
    root = Path(cfg.db_path)
    count = migrate_data_root(root)
    if count == 0:
        print("No bare-date fields found; nothing to do.")
        return
    commit_change(
        root,
        "chore(migration): UTC datetime conversion",
        enabled=True,
    )
    print(f"Migrated {count} meta.toml file(s) and committed.")
