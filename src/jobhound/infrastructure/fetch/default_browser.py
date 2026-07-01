"""Detect the OS default browser (macOS supported; best-effort elsewhere)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

_BUNDLE_TO_BROWSER: dict[str, str] = {
    "com.google.chrome": "chrome",
    "org.mozilla.firefox": "firefox",
    "com.apple.safari": "safari",
    "com.microsoft.edgemac": "edge",
    "com.brave.browser": "brave",
    "com.operasoftware.opera": "opera",
    "com.vivaldi.vivaldi": "vivaldi",
}


def browser_from_bundle_id(bundle_id: str) -> str | None:
    """Map a macOS application bundle id to a jobhound browser name."""
    return _BUNDLE_TO_BROWSER.get(bundle_id.lower())


def _macos_default_browser() -> str | None:
    plist = (
        Path.home()
        / "Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist"
    )
    if not plist.exists():
        return "safari"  # no explicit handler set → Safari is the system default
    with plist.open("rb") as fh:
        data = plistlib.load(fh)
    for handler in data.get("LSHandlers", []):
        if handler.get("LSHandlerURLScheme") == "https":
            role = handler.get("LSHandlerRoleAll")
            return browser_from_bundle_id(role) if role else None
    return "safari"


def detect_default_browser() -> str | None:
    """Return the default browser's jobhound name, or None if undetectable."""
    if sys.platform == "darwin":
        return _macos_default_browser()
    return None
