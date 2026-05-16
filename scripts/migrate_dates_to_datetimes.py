"""One-shot migration: bare-date lifecycle fields → tz-aware UTC datetimes.

This script is a thin wrapper around the canonical implementation in
jobhound.migrations.utc_timestamps so the CLI and tests share the same logic.

Idempotent. Safe to re-run. Operates on raw TOML so it doesn't depend on
the post-migration Opportunity type assertions.
"""

from __future__ import annotations

# Re-export so existing imports continue to work.
from jobhound.migrations.utc_timestamps import (  # noqa: F401
    LIFECYCLE_FIELDS,
    _maybe_convert,
    _migrate_one,
    migrate_data_root,
)
