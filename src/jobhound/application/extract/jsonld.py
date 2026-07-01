"""Generic schema.org JobPosting JSON-LD extractor.

The default extractor for non-LinkedIn sites. ATS platforms embed a
`<script type="application/ld+json">` JobPosting block for Google Jobs;
this reads the standard schema.org fields from it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from jobhound.application.extract._html import clean_html_text
from jobhound.application.extract.models import ScrapedJob

_LD_BLOCK_RE = re.compile(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.S | re.I
)


def _iter_nodes(data: Any) -> Any:
    """Yield dict nodes from a parsed JSON-LD payload (handles arrays and @graph)."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _iter_nodes(data["@graph"])
        yield data


def _is_jobposting(node: dict[str, Any]) -> bool:
    type_ = node.get("@type")
    types = type_ if isinstance(type_, list) else [type_]
    return "JobPosting" in types


def _find_jobposting(html: str) -> dict[str, Any] | None:
    for raw in _LD_BLOCK_RE.findall(html):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(data):
            if _is_jobposting(node):
                return node
    return None


def _location(node: dict[str, Any]) -> str | None:
    loc = node.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if not isinstance(loc, dict):
        return None
    address = loc.get("address")
    if not isinstance(address, dict):
        return None
    parts = [
        address.get(key)
        for key in ("addressLocality", "addressRegion", "addressCountry")
        if address.get(key)
    ]
    return ", ".join(parts) or None


def extract(html: str) -> ScrapedJob:
    """Pull core JobPosting fields from a page's JSON-LD block."""
    node = _find_jobposting(html) or {}
    role = node.get("title")
    org = node.get("hiringOrganization")
    company = org.get("name") if isinstance(org, dict) else None
    location = _location(node)
    canonical = node.get("url")
    jd_body = clean_html_text(node.get("description") or "")

    return ScrapedJob.from_fields(
        company=company,
        role=role,
        location=location,
        comp_range=None,
        jd_body=jd_body,
        canonical_url=canonical,
    )
