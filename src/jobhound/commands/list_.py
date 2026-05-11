"""`jh list` — one-line summary of every opportunity."""

from __future__ import annotations

from jobhound.config import load_config
from jobhound.meta_io import read_meta
from jobhound.paths import paths_from_config


def run() -> None:
    """List every opportunity as `<slug> <status> <priority>`, sorted by slug."""
    cfg = load_config()
    paths = paths_from_config(cfg)
    if not paths.opportunities_dir.exists():
        return
    for sub in sorted(paths.opportunities_dir.iterdir()):
        if not sub.is_dir():
            continue
        opp = read_meta(sub / "meta.toml")
        print(f"{opp.slug:<55} {opp.status:<12} {opp.priority}")
