"""Tests for the tier-2 browser fetch adapter.

The real Chromium path isn't unit-tested; these cover the extra-missing
guard and the per-host profile directory, both of which need no browser.
"""

from __future__ import annotations

import importlib.util

import pytest

from jobhound.infrastructure.fetch import browser_fetch
from jobhound.infrastructure.fetch.base import FetchError
from tests.conftest import JhEnv

_PLAYWRIGHT_INSTALLED = importlib.util.find_spec("playwright") is not None


@pytest.mark.skipif(
    _PLAYWRIGHT_INSTALLED,
    reason="the missing-extra guard only fires when Playwright is absent",
)
def test_fetch_without_playwright_raises_actionable_error() -> None:
    with pytest.raises(FetchError) as exc:
        browser_fetch.fetch("https://www.linkedin.com/jobs/view/1")

    message = str(exc.value).lower()
    assert "playwright" in message
    assert "jobhound[browser]" in message


def test_default_profile_dir_is_per_host_under_state(tmp_jh: JhEnv) -> None:
    path = browser_fetch.default_profile_dir("https://www.linkedin.com/jobs/view/1")

    assert path.name == "www.linkedin.com"
    assert "browser" in path.parts
    assert str(path).startswith(str(tmp_jh.state_home))
