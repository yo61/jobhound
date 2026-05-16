"""Shared fixtures for application-layer tests.

`query_paths` is defined in tests/conftest.py and available here automatically.
It builds a `tmp_path` data root with three opportunities:
- one active and recent ("acme")
- one active and stale ("beta", last activity 30+ days before `NOW`)
- one archived ("gamma", in archive/)
"""

import pytest

from tests.conftest import NOW  # noqa: F401  re-export for tests that import it directly
from tests.storage.in_memory import InMemoryFileStore


@pytest.fixture
def in_memory_store() -> InMemoryFileStore:
    return InMemoryFileStore()
