"""Unit tests for MCP server construction and its SDK guard."""

from __future__ import annotations

import sys
import types

import pytest

from jobhound.mcp.server import _require_mcp_sdk

EXPECTED_GUIDANCE = ("jobhound[mcp]", "mcp>=2.0")


def test_require_mcp_sdk_passes_when_sdk_importable() -> None:
    _require_mcp_sdk()


def test_require_mcp_sdk_exits_when_sdk_absent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No mcp package at all — the [mcp] extra was never installed."""
    monkeypatch.setitem(sys.modules, "mcp", None)
    monkeypatch.setitem(sys.modules, "mcp.server", None)

    with pytest.raises(SystemExit) as excinfo:
        _require_mcp_sdk()

    assert excinfo.value.code == 1
    stderr = capsys.readouterr().err
    for fragment in EXPECTED_GUIDANCE:
        assert fragment in stderr


def test_require_mcp_sdk_exits_when_sdk_too_old(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """mcp 1.x: the package imports, but MCPServer does not exist.

    This is the case a bare `import mcp` check misses — it succeeds, and the
    failure surfaces later as an opaque ImportError from build_server().
    """
    monkeypatch.setitem(sys.modules, "mcp.server", types.ModuleType("mcp.server"))

    with pytest.raises(SystemExit) as excinfo:
        _require_mcp_sdk()

    assert excinfo.value.code == 1
    stderr = capsys.readouterr().err
    for fragment in EXPECTED_GUIDANCE:
        assert fragment in stderr


class _MissingTransitiveDependencyFinder:
    """Fails the mcp.server import the way an absent transitive dependency does."""

    def find_spec(self, fullname: str, path: object, target: object = None) -> None:
        if fullname == "mcp.server":
            raise ModuleNotFoundError("No module named 'cryptography'", name="cryptography")


def test_require_mcp_sdk_reports_underlying_import_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """mcp is installed but one of its own dependencies is not importable."""
    monkeypatch.delitem(sys.modules, "mcp.server", raising=False)
    monkeypatch.setattr(sys, "meta_path", [_MissingTransitiveDependencyFinder(), *sys.meta_path])

    with pytest.raises(SystemExit) as excinfo:
        _require_mcp_sdk()

    assert excinfo.value.code == 1
    assert "No module named 'cryptography'" in capsys.readouterr().err
