"""Custom extractor for LinkedIn job pages.

LinkedIn emits no schema.org JobPosting JSON-LD. A live probe (2026-07-01)
showed the data is reliably available in the page head and body instead:

- `og:title` / `<title>`: "{company} hiring {role} in {location} | LinkedIn"
- `<link rel="canonical">`: the normalized posting URL
- `div.show-more-less-html__markup`: the full job description body
"""

from __future__ import annotations

import html as html_lib
import re

from jobhound.application.extract._html import clean_html_text
from jobhound.application.extract.models import ScrapedJob

_OG_TITLE_RE = re.compile(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"')
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_CANONICAL_RE = re.compile(r'<link[^>]*rel="canonical"[^>]*href="([^"]*)"')
_TITLE_PATTERN = re.compile(
    r"^(?P<company>.+?) hiring (?P<role>.+?) in (?P<location>.+?) \| LinkedIn$"
)
_MARKUP_RE = re.compile(r'<div class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', re.S)


def _first(pattern: re.Pattern[str], html: str) -> str | None:
    match = pattern.search(html)
    return match.group(1) if match else None


def extract(html: str) -> ScrapedJob:
    """Pull company/role/location, canonical URL, and JD body from LinkedIn HTML."""
    raw_title = _first(_OG_TITLE_RE, html) or _first(_TITLE_RE, html) or ""
    title = html_lib.unescape(raw_title).strip()
    parsed = _TITLE_PATTERN.match(title)
    company = parsed.group("company") if parsed else None
    role = parsed.group("role") if parsed else None
    location = parsed.group("location") if parsed else None

    canonical = _first(_CANONICAL_RE, html)

    jd_body = clean_html_text(_first(_MARKUP_RE, html) or "")

    return ScrapedJob.from_fields(
        company=company,
        role=role,
        location=location,
        comp_range=None,
        jd_body=jd_body,
        canonical_url=canonical,
    )
