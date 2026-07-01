"""Custom extractor for LinkedIn job pages.

LinkedIn emits no schema.org JobPosting JSON-LD. A live probe (2026-07-01)
showed the data is reliably available in the page head and body instead:

- `og:title` / `<title>`: "{company} hiring {role} in {location} | LinkedIn"
- `<link rel="canonical">`: the normalized posting URL
- `div.show-more-less-html__markup`: the full job description body

Attribute matching is order-independent, and the JD body is taken to its
balanced closing tag so nested block elements aren't truncated.
"""

from __future__ import annotations

import html as html_lib
import re

from jobhound.application.extract._html import clean_html_text
from jobhound.application.extract.models import ScrapedJob

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_TITLE_PATTERN = re.compile(
    r"^(?P<company>.+?) hiring (?P<role>.+?) in (?P<location>.+?) \| LinkedIn$"
)
_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.I)
_LINK_TAG_RE = re.compile(r"<link\b[^>]*>", re.I)
_ATTR_RE = re.compile(r'(\w[\w:-]*)\s*=\s*"([^"]*)"')
_MARKUP_OPEN_RE = re.compile(
    r'<div\b[^>]*class="[^"]*show-more-less-html__markup[^"]*"[^>]*>', re.I
)
_DIV_TAG_RE = re.compile(r"</?div\b[^>]*>", re.I)


def _attrs(tag: str) -> dict[str, str]:
    return {name.lower(): value for name, value in _ATTR_RE.findall(tag)}


def _tag_content(html: str, tag_re: re.Pattern[str], key: str, want: str, out: str) -> str | None:
    """Find the tag whose `key` attribute equals `want`, return its `out` attribute."""
    for match in tag_re.finditer(html):
        attrs = _attrs(match.group())
        if attrs.get(key) == want and out in attrs:
            return attrs[out]
    return None


def _markup_body(html: str) -> str:
    """Return the show-more-less-html__markup div's inner HTML, balanced on <div>."""
    opening = _MARKUP_OPEN_RE.search(html)
    if not opening:
        return ""
    start = opening.end()
    depth = 1
    for tag in _DIV_TAG_RE.finditer(html, start):
        depth += -1 if tag.group().startswith("</") else 1
        if depth == 0:
            return html[start : tag.start()]
    return html[start:]


def extract(html: str) -> ScrapedJob:
    """Pull company/role/location, canonical URL, and JD body from LinkedIn HTML."""
    og_title = _tag_content(html, _META_TAG_RE, "property", "og:title", "content")
    fallback = _TITLE_RE.search(html)
    raw_title = og_title or (fallback.group(1) if fallback else "")
    title = html_lib.unescape(raw_title).strip()
    parsed = _TITLE_PATTERN.match(title)
    company = parsed.group("company") if parsed else None
    role = parsed.group("role") if parsed else None
    location = parsed.group("location") if parsed else None

    canonical = _tag_content(html, _LINK_TAG_RE, "rel", "canonical", "href")

    jd_body = clean_html_text(_markup_body(html))

    return ScrapedJob.from_fields(
        company=company,
        role=role,
        location=location,
        comp_range=None,
        jd_body=jd_body,
        canonical_url=canonical,
    )
