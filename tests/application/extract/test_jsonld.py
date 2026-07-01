"""Tests for the generic schema.org JobPosting JSON-LD extractor.

ATS platforms (Greenhouse, Lever, Workday, Ashby) publish a JobPosting
JSON-LD block for Google Jobs. This extractor is the default path for
any site that isn't LinkedIn.
"""

from __future__ import annotations

import json
from typing import Any

from jobhound.application.extract.jsonld import extract


def _page_with_jsonld(payload: dict[str, Any]) -> str:
    block = json.dumps(payload)
    return (
        "<html><head>"
        f'<script type="application/ld+json">{block}</script>'
        "</head><body></body></html>"
    )


def test_extracts_core_jobposting_fields() -> None:
    html = _page_with_jsonld(
        {
            "@context": "https://schema.org",
            "@type": "JobPosting",
            "title": "Senior Backend Engineer",
            "description": "<p>We are hiring.</p><p>Join us.</p>",
            "hiringOrganization": {"@type": "Organization", "name": "Acme Corp"},
            "jobLocation": {
                "@type": "Place",
                "address": {
                    "@type": "PostalAddress",
                    "addressLocality": "Berlin",
                    "addressCountry": "Germany",
                },
            },
            "url": "https://boards.greenhouse.io/acme/jobs/12345",
        }
    )

    job = extract(html)

    assert job.company == "Acme Corp"
    assert job.role == "Senior Backend Engineer"
    assert job.location is not None and "Berlin" in job.location
    assert job.canonical_url == "https://boards.greenhouse.io/acme/jobs/12345"
    assert "We are hiring" in job.jd_body
    assert "hiring.Join" not in job.jd_body


def test_page_without_jsonld_reports_all_missing() -> None:
    html = "<html><head><title>Careers</title></head><body>No structured data</body></html>"

    job = extract(html)

    assert job.company is None
    assert job.role is None
    assert set(job.missing) >= {"company", "role", "canonical_url", "jd_body"}
