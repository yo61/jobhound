from __future__ import annotations

import pytest

from jobhound.infrastructure.fetch.default_browser import browser_from_bundle_id


@pytest.mark.parametrize(
    "bundle_id, expected",
    [
        ("com.google.chrome", "chrome"),
        ("org.mozilla.firefox", "firefox"),
        ("com.apple.safari", "safari"),
        ("com.microsoft.edgemac", "edge"),
        ("com.brave.browser", "brave"),
        ("com.unknown.thing", None),
    ],
)
def test_browser_from_bundle_id(bundle_id: str, expected: str | None) -> None:
    assert browser_from_bundle_id(bundle_id) == expected
