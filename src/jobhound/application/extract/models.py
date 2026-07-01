"""The ScrapedJob value returned by every extractor."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScrapedJob:
    """Fields pulled from a job-posting page.

    Any field an extractor could not determine is left `None` (or empty
    for `jd_body`) and named in `missing`, so callers can decide whether
    what was found is enough to create an opportunity.
    """

    company: str | None
    role: str | None
    location: str | None
    comp_range: str | None
    jd_body: str
    canonical_url: str | None
    missing: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_fields(
        cls,
        *,
        company: str | None,
        role: str | None,
        location: str | None,
        comp_range: str | None,
        jd_body: str,
        canonical_url: str | None,
    ) -> ScrapedJob:
        """Build a ScrapedJob, deriving `missing` from the falsy fields."""
        values = {
            "company": company,
            "role": role,
            "location": location,
            "comp_range": comp_range,
            "jd_body": jd_body,
            "canonical_url": canonical_url,
        }
        missing = tuple(name for name, value in values.items() if not value)
        return cls(**values, missing=missing)
