"""Tests for hostname → extractor routing."""

from __future__ import annotations

from jobhound.application.extract import jsonld, linkedin
from jobhound.application.extract.registry import extractor_for


def test_linkedin_hosts_route_to_linkedin_extractor() -> None:
    assert extractor_for("https://www.linkedin.com/jobs/view/123") is linkedin.extract
    assert extractor_for("https://uk.linkedin.com/jobs/view/123") is linkedin.extract


def test_unknown_host_routes_to_generic_jsonld() -> None:
    assert extractor_for("https://boards.greenhouse.io/acme/jobs/123") is jsonld.extract


def test_lookalike_host_does_not_match_linkedin() -> None:
    # A host merely ending in "linkedin.com" as a substring must not match.
    assert extractor_for("https://notlinkedin.com/jobs/1") is jsonld.extract
