from __future__ import annotations

import sys

import pytest

from jobhound.infrastructure.fetch.default_browser import (
    browser_from_bundle_id,
    detect_default_browser,
    parse_launchservices,
)


@pytest.mark.parametrize(
    "bundle_id, expected",
    [
        ("com.google.chrome", "chrome"),
        ("org.mozilla.firefox", "firefox"),
        ("com.apple.safari", "safari"),
        ("com.microsoft.edgemac", "edge"),
        ("com.brave.browser", "brave"),
        ("com.unknown.thing", None),
        ("COM.GOOGLE.CHROME", "chrome"),  # case-insensitive
    ],
)
def test_browser_from_bundle_id(bundle_id: str, expected: str | None) -> None:
    assert browser_from_bundle_id(bundle_id) == expected


def test_parse_launchservices_https_handler_chrome() -> None:
    data = {
        "LSHandlers": [
            {"LSHandlerURLScheme": "http", "LSHandlerRoleAll": "org.mozilla.firefox"},
            {"LSHandlerURLScheme": "https", "LSHandlerRoleAll": "com.google.chrome"},
        ]
    }
    assert parse_launchservices(data) == "chrome"


def test_parse_launchservices_https_handler_unknown_bundle() -> None:
    data = {
        "LSHandlers": [
            {"LSHandlerURLScheme": "https", "LSHandlerRoleAll": "com.example.unknownbrowser"},
        ]
    }
    assert parse_launchservices(data) is None


def test_parse_launchservices_no_handlers_returns_safari() -> None:
    assert parse_launchservices({}) == "safari"


def test_detect_default_browser_non_darwin_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert detect_default_browser() is None
