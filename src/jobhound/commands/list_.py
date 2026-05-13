"""`jh list` — one-line summary of every opportunity."""

from __future__ import annotations

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository


def run() -> None:
    """List every opportunity as `<slug> <status> <priority>`, sorted by slug."""
    cfg = load_config()
    repo = OpportunityRepository(paths_from_config(cfg), cfg)
    for opp in repo.all():
        print(f"{opp.slug:<55} {opp.status:<12} {opp.priority}")
