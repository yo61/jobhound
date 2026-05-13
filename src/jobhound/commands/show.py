"""`jh show <slug>` — print one opportunity in human text or JSON."""

from __future__ import annotations

import json
import sys
from datetime import UTC, date, datetime
from typing import Annotated

from cyclopts import Parameter

from jobhound.application.query import OpportunityQuery
from jobhound.application.serialization import show_envelope
from jobhound.application.snapshots import FileEntry, OpportunitySnapshot
from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config


def run(
    slug: str,
    /,
    *,
    json_out: Annotated[bool, Parameter(name=["--json"])] = False,
) -> None:
    """Show one opportunity. Defaults to human text; `--json` for the envelope."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    query = OpportunityQuery(paths)
    try:
        snap = query.find(slug, today=date.today())
    except SlugNotFoundError:
        print(f"jh: no opportunity matches: {slug}", file=sys.stderr)
        raise SystemExit(2) from None
    except AmbiguousSlugError as exc:
        print(f"jh: {exc}", file=sys.stderr)
        raise SystemExit(2) from None
    if json_out:
        envelope = show_envelope(
            snap,
            timestamp=datetime.now(UTC),
            db_root=paths.db_root,
        )
        print(json.dumps(envelope, indent=2))
    else:
        _print_human(snap, query.files(snap.opportunity.slug))


def _print_human(snap: OpportunitySnapshot, files: list[FileEntry]) -> None:
    opp = snap.opportunity
    print(f"{opp.company} — {opp.role}  ({opp.slug})")
    print()
    print(f"  Status:        {opp.status.value}")
    print(f"  Priority:      {opp.priority.value}")
    if opp.applied_on is not None:
        print(f"  Applied:       {opp.applied_on.isoformat()}")
    if opp.last_activity is not None:
        print(f"  Last activity: {opp.last_activity.isoformat()}")
    if snap.computed.days_since_activity is not None:
        print(f"  Days quiet:    {snap.computed.days_since_activity}")
    if opp.next_action is not None:
        due = f" (due {opp.next_action_due.isoformat()})" if opp.next_action_due is not None else ""
        print(f"  Next action:   {opp.next_action}{due}")
    if opp.tags:
        print(f"  Tags:          {', '.join(opp.tags)}")
    if opp.source is not None:
        print(f"  Source:        {opp.source}")
    if opp.location is not None:
        print(f"  Location:      {opp.location}")
    if opp.comp_range is not None:
        print(f"  Comp:          {opp.comp_range}")
    if opp.contacts:
        print()
        print("  Contacts:")
        for c in opp.contacts:
            line = f"    {c.name}"
            if c.role:
                line += f" ({c.role})"
            if c.channel:
                line += f" — {c.channel}"
            print(line)
    if opp.links:
        print()
        print("  Links:")
        for name, url in opp.links.items():
            print(f"    {name}: {url}")
    if files:
        print()
        print("  Files:")
        for entry in files:
            print(f"    {entry.name}  ({entry.size} bytes)")
    print()
    print(f"  Path: {snap.path}")
