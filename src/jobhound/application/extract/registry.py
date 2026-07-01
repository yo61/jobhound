"""Route a posting URL to the extractor for its site.

The extensibility seam: LinkedIn uses its custom extractor; every other
host falls back to the generic JSON-LD extractor. Adding a site with a
bespoke shape means registering its host here.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

from jobhound.application.extract import jsonld, linkedin
from jobhound.application.extract.models import ScrapedJob

Extractor = Callable[[str], ScrapedJob]


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def extractor_for(url: str) -> Extractor:
    """Return the extractor function for `url`'s host (JSON-LD by default)."""
    host = _host(url)
    if _matches(host, "linkedin.com"):
        return linkedin.extract
    return jsonld.extract
