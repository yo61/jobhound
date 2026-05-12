"""Smoke test: the package imports and exposes a version."""

import re

import jobhound


def test_package_has_version() -> None:
    """The version tracks pyproject.toml via release-please; don't hardcode it."""
    assert isinstance(jobhound.__version__, str)
    assert re.fullmatch(r"\d+\.\d+\.\d+", jobhound.__version__), jobhound.__version__
