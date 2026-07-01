"""Tests for `jh new --url` (URL scraping).

The tier-1 HTTP fetch is monkeypatched to return canned LinkedIn HTML, so
the command runs end-to-end (extract → create → write JD → set link)
against a real tmp data root with no network.
"""

from __future__ import annotations

import pytest

from jobhound.infrastructure.fetch.base import FetchResult
from jobhound.infrastructure.meta_io import read_meta

_CANONICAL = "https://uk.linkedin.com/jobs/view/platform-engineer-at-liveflow-42"
_LINKEDIN_HTML = (
    "<html><head>"
    '<meta property="og:title" content="LiveFlow hiring Platform Engineer in London | LinkedIn">'
    f'<link rel="canonical" href="{_CANONICAL}">'
    "</head><body>"
    '<div class="show-more-less-html__markup">Join LiveFlow. Build the platform.</div>'
    "</body></html>"
)


@pytest.fixture
def fake_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fetch(url: str) -> FetchResult:
        return FetchResult(final_url=url, html=_LINKEDIN_HTML)

    monkeypatch.setattr("jobhound.infrastructure.fetch.http_fetch.fetch", _fetch)


def test_new_url_scrapes_and_creates_opportunity(tmp_jh, invoke, fake_fetch) -> None:
    result = invoke(["new", "--url", "https://www.linkedin.com/jobs/view/42?trk=share"])

    assert result.exit_code == 0, result.output
    opps = list((tmp_jh.db_path / "opportunities").iterdir())
    assert len(opps) == 1
    opp_dir = opps[0]
    opp = read_meta(opp_dir / "meta.toml")
    assert opp.company == "LiveFlow"
    assert opp.role == "Platform Engineer"
    assert opp.source == "LinkedIn"
    assert opp.links["posting"] == _CANONICAL

    jd = opp_dir / "job-description.md"
    assert jd.exists()
    assert "Join LiveFlow" in jd.read_text()


def test_new_url_rejects_duplicate_posting(tmp_jh, invoke, fake_fetch) -> None:
    first = invoke(["new", "--url", "https://www.linkedin.com/jobs/view/42"])
    assert first.exit_code == 0, first.output

    second = invoke(["new", "--url", "https://www.linkedin.com/jobs/view/42?trk=other-link"])
    assert second.exit_code == 1
    assert "already links" in second.output.lower()


def test_new_without_company_role_or_url_errors(tmp_jh, invoke) -> None:
    result = invoke(["new"])

    assert result.exit_code == 2
    assert "url" in result.output.lower()
