"""Tests for the LinkedIn HTML extractor.

The markup shapes here mirror what a live probe of two real LinkedIn
postings on 2026-07-01 exposed (see the URL-scraping design spec):
`og:title` = "{company} hiring {role} in {location} | LinkedIn", a
`rel="canonical"` link to the normalized URL, and the job body inside
`div.show-more-less-html__markup`. LinkedIn emits no JSON-LD.
"""

from __future__ import annotations

from pathlib import Path

from jobhound.application.extract.linkedin import extract

_FIXTURES = Path(__file__).parent / "fixtures"


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


def test_extracts_from_real_captured_page() -> None:
    # Real LinkedIn markup (trimmed from a live probe): actual attribute
    # ordering and body HTML, so this guards against markup drift and the
    # extractor's real failure modes — not just shapes it already handles.
    html = (_FIXTURES / "linkedin_liveflow.html").read_text()

    job = extract(html)

    assert job.company == "LiveFlow"
    assert job.role == "Graduate Platform Engineer - Growth"
    assert job.location == "London, England, United Kingdom"
    assert job.canonical_url is not None and job.canonical_url.endswith("-4383908452")
    assert len(job.jd_body) > 1000
    assert "needInterview" not in job.jd_body  # block boundaries kept separate


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


def test_nested_divs_in_body_are_not_truncated() -> None:
    # Regex can't balance nested tags; the body must survive a nested <div>.
    html = _linkedin_html(
        title="Acme hiring Engineer in Remote | LinkedIn",
        canonical="https://uk.linkedin.com/jobs/view/engineer-at-acme-1",
        jd_body="Intro paragraph.<div>Responsibilities section</div>Closing paragraph.",
    )

    job = extract(html)

    assert "Intro paragraph." in job.jd_body
    assert "Responsibilities section" in job.jd_body
    assert "Closing paragraph." in job.jd_body


def test_extraction_is_insensitive_to_attribute_order() -> None:
    # A markup reshuffle (content before property, href before rel) must still work.
    html = (
        "<html><head>"
        '<meta content="Acme hiring SRE in Remote | LinkedIn" property="og:title">'
        '<link href="https://uk.linkedin.com/jobs/view/sre-at-acme-9" rel="canonical">'
        "</head><body>"
        '<div class="show-more-less-html__markup">Body text.</div>'
        "</body></html>"
    )

    job = extract(html)

    assert job.company == "Acme"
    assert job.role == "SRE"
    assert job.canonical_url == "https://uk.linkedin.com/jobs/view/sre-at-acme-9"


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
