"""Smoke tests for the cyclopts app skeleton."""

import jobhound


def test_help_lists_commands(invoke) -> None:
    """`--help` succeeds and mentions the program name."""
    result = invoke(["--help"])
    assert result.exit_code == 0
    assert "jh" in result.output.lower() or "Usage" in result.output


def test_version_flag(invoke) -> None:
    """`--version` prints the package version (sourced from pyproject)."""
    result = invoke(["--version"])
    assert result.exit_code == 0
    assert jobhound.__version__ in result.output


# ---- main() and the completion-refresh hook ----------------------------

import contextlib  # noqa: E402

import pytest  # noqa: E402


def test_main_runs_completion_refresh_for_normal_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`jh <anything>` must run the completion-refresh helper before dispatch.

    Issue #61: stale stubs after a jh upgrade are invisible to users —
    they only notice when completion breaks. The hook fixes drift on
    any jh invocation, so any normal command implicitly heals it.
    """
    calls: list[str] = []
    monkeypatch.setattr(
        "jobhound.commands.completion.maybe_refresh_installed_stubs",
        lambda: calls.append("refreshed"),
        raising=False,
    )
    monkeypatch.setattr("sys.argv", ["jh", "--version"])

    from jobhound.cli import main

    with contextlib.suppress(SystemExit):
        main()

    assert calls == ["refreshed"]


def test_main_skips_completion_refresh_for_complete_fastpath(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`jh __complete ...` is on the typing hot path — must not stat user stubs.

    Shell completion fires on every keystroke; running a multi-file
    drift check there would slow every TAB press noticeably and serve
    no purpose (the stub that just invoked us can't refresh itself
    mid-call anyway).
    """
    calls: list[str] = []
    monkeypatch.setattr(
        "jobhound.commands.completion.maybe_refresh_installed_stubs",
        lambda: calls.append("refreshed"),
        raising=False,
    )
    monkeypatch.setattr("sys.argv", ["jh", "__complete", "bash", "jh", ""])

    from jobhound.cli import main

    main()

    assert calls == []
