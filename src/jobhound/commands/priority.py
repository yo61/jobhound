"""`jh priority` — set priority to high/medium/low."""

from __future__ import annotations

import sys
from dataclasses import replace
from typing import Annotated

from cyclopts import Parameter

from jobhound.config import load_config
from jobhound.paths import paths_from_config
from jobhound.repository import OpportunityRepository

_VALID = {"high", "medium", "low"}


def run(
    slug_query: str,
    /,
    *,
    to: str,
    no_commit: Annotated[bool, Parameter(negative=())] = False,
) -> None:
    """Set the priority of an opportunity."""
    if to not in _VALID:
        print(f"--to must be one of {sorted(_VALID)}", file=sys.stderr)
        raise SystemExit(1)
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    opp, opp_dir = repo.find(slug_query)
    updated = replace(opp, priority=to)
    repo.save(updated, opp_dir, message=f"priority: {opp.slug} {to}", no_commit=no_commit)
    print(f"priority {opp.slug}: {to}")
