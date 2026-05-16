"""`jh stats` — show aggregate funnel and source counts."""

from __future__ import annotations

import json
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import OpportunityQuery
from jobhound.application.serialization import stats_to_dict
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    *,
    json_out: Annotated[bool, Parameter(name=["--json"])] = False,
) -> None:
    """Show aggregate funnel and source counts."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    stats = query.stats()
    if json_out:
        print(json.dumps(stats_to_dict(stats), indent=2))
    else:
        _print_human(stats_to_dict(stats))


def _print_human(data: dict) -> None:
    print("Funnel:")
    for status, count in data.get("funnel", {}).items():
        if count:
            print(f"  {status:<20s} {count}")
    sources = data.get("sources", {})
    if sources:
        print()
        print("Sources:")
        for source, count in sorted(sources.items()):
            print(f"  {source:<20s} {count}")
