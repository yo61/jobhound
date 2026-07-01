"""Tests for the LinkedIn HTML extractor.

The markup shapes here mirror what a live probe of two real LinkedIn
postings on 2026-07-01 exposed (see the URL-scraping design spec):
`og:title` = "{company} hiring {role} in {location} | LinkedIn", a
`rel="canonical"` link to the normalized URL, and the job body inside
`div.show-more-less-html__markup`. LinkedIn emits no JSON-LD.
"""

from __future__ import annotations

from jobhound.application.extract.linkedin import extract


def _linkedin_html(*, title: str, canonical: str, jd_body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta property="og:title" content="{title}">
  <link rel="canonical" href="{canonical}">
  <title>{title}</title>
</head>
<body>
  <div class="show-more-less-html__markup">{jd_body}</div>
</body>
</html>"""


def test_extracts_company_role_location_and_canonical() -> None:
    html = _linkedin_html(
        title=(
            "LiveFlow hiring Graduate Platform Engineer - Growth "
            "in London, England, United Kingdom | LinkedIn"
        ),
        canonical=(
            "https://uk.linkedin.com/jobs/view/"
            "graduate-platform-engineer-growth-at-liveflow-4383908452"
        ),
        jd_body="About LiveFlow. We are hiring engineers.",
    )

    job = extract(html)

    assert job.company == "LiveFlow"
    assert job.role == "Graduate Platform Engineer - Growth"
    assert job.location == "London, England, United Kingdom"
    assert job.canonical_url == (
        "https://uk.linkedin.com/jobs/view/graduate-platform-engineer-growth-at-liveflow-4383908452"
    )
    assert "About LiveFlow" in job.jd_body


def test_full_page_reports_only_comp_range_missing() -> None:
    html = _linkedin_html(
        title="Camunda hiring Engineering Manager - Infrastructure in United Kingdom | LinkedIn",
        canonical="https://uk.linkedin.com/jobs/view/engineering-manager-infrastructure-at-camunda-4431949667",
        jd_body="We are hiring an Engineering Manager.",
    )

    job = extract(html)

    # LinkedIn never exposes structured salary, so comp_range is always absent.
    assert job.missing == ("comp_range",)


def test_block_tags_become_whitespace_not_concatenation() -> None:
    # A live probe showed naive tag-stripping glued "need" + "Interview"
    # across a block boundary. Block tags must separate, not vanish.
    html = _linkedin_html(
        title="Acme hiring Engineer in Remote | LinkedIn",
        canonical="https://uk.linkedin.com/jobs/view/engineer-at-acme-1",
        jd_body="First line.<br>Second line.<ul><li>Alpha</li><li>Beta</li></ul>",
    )

    job = extract(html)

    assert "line.Second" not in job.jd_body
    assert "AlphaBeta" not in job.jd_body
    # Block boundaries become line breaks, preserving structure for the .md body.
    lines = [line.strip() for line in job.jd_body.splitlines() if line.strip()]
    assert "First line." in lines
    assert "Second line." in lines
    assert "Alpha" in lines
    assert "Beta" in lines


def test_unparseable_page_reports_all_missing_fields() -> None:
    html = "<html><head><title>Sign in | LinkedIn</title></head><body></body></html>"

    job = extract(html)

    assert job.company is None
    assert job.role is None
    assert job.location is None
    assert job.canonical_url is None
    assert job.jd_body == ""
    assert set(job.missing) == {
        "company",
        "role",
        "location",
        "comp_range",
        "jd_body",
        "canonical_url",
    }
