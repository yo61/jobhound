"""The CLI's `main()` wrapper converts known exceptions to clean stderr lines."""

from __future__ import annotations

import pytest

from jobhound import cli
from jobhound.application.file_service import FileServiceError
from jobhound.domain.slug import AmbiguousSlugError, SlugNotFoundError
from jobhound.domain.transitions import InvalidTransitionError
from jobhound.infrastructure.meta_io import ValidationError


@pytest.mark.parametrize(
    "exc",
    [
        ValidationError(
            "first_contact is a bare date (2026-05-06): run `jh migrate utc-timestamps`"
        ),
        SlugNotFoundError("no opportunity matches 'acme'"),
        AmbiguousSlugError("query 'acme' matches multiple opportunities: acme-eng, acme-platform"),
        InvalidTransitionError("cannot apply from status 'applied'"),
        FileServiceError("a representative file-service failure"),
    ],
)
def test_main_handles_known_exception_cleanly(monkeypatch, capsys, exc):
    """Each known exception type is caught and printed to stderr without a traceback."""

    def boom() -> None:
        raise exc

    monkeypatch.setattr(cli, "app", boom)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert f"jh: {exc}" in captured.err
    assert "Traceback" not in captured.err


def test_main_does_not_swallow_unexpected_exceptions(monkeypatch):
    """Unknown exceptions still propagate — they're programmer errors, not user errors."""

    def boom() -> None:
        raise RuntimeError("internal logic bug")

    monkeypatch.setattr(cli, "app", boom)

    with pytest.raises(RuntimeError, match="internal logic bug"):
        cli.main()


def test_main_does_not_swallow_keyboard_interrupt(monkeypatch):
    """Ctrl+C must propagate so the shell handles it normally."""

    def boom() -> None:
        raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "app", boom)

    with pytest.raises(KeyboardInterrupt):
        cli.main()


def test_main_handles_filesserviceerror_subclasses(monkeypatch, capsys):
    """The catch covers the FileServiceError family, not just its base class."""

    class NewFileServiceError(FileServiceError):
        """Future subclass — should still be caught by the global handler."""

    def boom() -> None:
        raise NewFileServiceError("future error mode")

    monkeypatch.setattr(cli, "app", boom)

    with pytest.raises(SystemExit) as exc_info:
        cli.main()

    assert exc_info.value.code == 1
    assert "jh: future error mode" in capsys.readouterr().err
