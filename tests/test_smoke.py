"""Smoke test: the package imports and exposes a version."""

import jobhound


def test_package_has_version() -> None:
    assert jobhound.__version__ == "0.1.0"
