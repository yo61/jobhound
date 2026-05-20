"""Tests for `jh completion` subgroup."""

from __future__ import annotations

from pathlib import Path


def test_completion_bash_prints_script(invoke) -> None:
    result = invoke(["completion", "bash"])
    assert result.exit_code == 0
    assert "complete -F _jh_complete jh" in result.output


def test_completion_zsh_prints_script(invoke) -> None:
    result = invoke(["completion", "zsh"])
    assert result.exit_code == 0
    assert "#compdef jh" in result.output


def test_completion_fish_prints_script(invoke) -> None:
    result = invoke(["completion", "fish"])
    assert result.exit_code == 0
    assert "complete -c jh" in result.output


def test_completion_install_writes_script_to_dest(tmp_path: Path, invoke) -> None:
    result = invoke(["completion", "install", "--shell", "bash", "--dest", str(tmp_path)])
    assert result.exit_code == 0
    target = tmp_path / "jh"
    assert target.exists()
    assert "complete -F _jh_complete jh" in target.read_text()


def test_completion_install_is_idempotent(tmp_path: Path, invoke) -> None:
    invoke(["completion", "install", "--shell", "zsh", "--dest", str(tmp_path)])
    target = tmp_path / "_jh"
    invoke(["completion", "install", "--shell", "zsh", "--dest", str(tmp_path)])
    # Re-installing the same content should not duplicate or break.
    assert target.read_text().count("#compdef jh") == 1


def test_completion_install_backs_up_existing_different_content(tmp_path: Path, invoke) -> None:
    target = tmp_path / "jh"
    target.write_text("OLD CONTENT\n")
    invoke(["completion", "install", "--shell", "bash", "--dest", str(tmp_path)])
    bak = tmp_path / "jh.bak"
    assert bak.exists()
    assert bak.read_text() == "OLD CONTENT\n"


# ---- maybe_refresh_installed_stubs --------------------------------------

import pytest  # noqa: E402


def _bundled_stub(shell: str) -> str:
    from importlib import resources

    return (resources.files("jobhound._completion") / f"jh.{shell}").read_text(encoding="utf-8")


def test_refresh_rewrites_outdated_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An installed stub that differs from the bundled one is overwritten.

    Addresses issue #61: after a jh upgrade, stubs go stale until the
    user manually re-runs `jh completion install`. The refresh helper
    closes that gap by detecting drift and rewriting only stubs the
    user already installed.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    stub_dir = tmp_path / ".local/share/bash-completion/completions"
    stub_dir.mkdir(parents=True)
    target = stub_dir / "jh"
    target.write_text("OLD STUB CONTENT\n")

    from jobhound.commands.completion import maybe_refresh_installed_stubs

    maybe_refresh_installed_stubs()

    assert target.read_text(encoding="utf-8") == _bundled_stub("bash")

    bak = stub_dir / "jh.bak"
    assert bak.exists(), "old content should be preserved in .bak"
    assert bak.read_text() == "OLD STUB CONTENT\n"

    captured = capsys.readouterr()
    assert "bash" in captured.err
    assert "completion" in captured.err.lower()


def test_refresh_leaves_uptodate_stub_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An installed stub matching the bundled one is untouched and silent."""
    monkeypatch.setenv("HOME", str(tmp_path))
    stub_dir = tmp_path / ".local/share/bash-completion/completions"
    stub_dir.mkdir(parents=True)
    target = stub_dir / "jh"
    target.write_text(_bundled_stub("bash"))

    from jobhound.commands.completion import maybe_refresh_installed_stubs

    maybe_refresh_installed_stubs()

    assert target.read_text(encoding="utf-8") == _bundled_stub("bash")
    assert not (stub_dir / "jh.bak").exists()
    assert capsys.readouterr().err == ""


def test_refresh_skips_when_no_stub_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without an existing stub the helper is a no-op — never auto-creates.

    Enforces the "honor prior consent" rule: users who never ran
    `jh completion install` should never have a stub appear in their
    dotfiles.
    """
    monkeypatch.setenv("HOME", str(tmp_path))

    from jobhound.commands.completion import maybe_refresh_installed_stubs

    maybe_refresh_installed_stubs()

    assert not (tmp_path / ".local/share/bash-completion/completions/jh").exists()
    assert not (tmp_path / ".zfunc/_jh").exists()
    assert not (tmp_path / ".config/fish/completions/jh.fish").exists()
    assert capsys.readouterr().err == ""


def test_refresh_silent_on_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A read-only stub directory must not crash jh.

    Failure mode that would otherwise spam users on every invocation
    in read-only environments — we'd rather silently skip the refresh
    than degrade the rest of the CLI.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    stub_dir = tmp_path / ".local/share/bash-completion/completions"
    stub_dir.mkdir(parents=True)
    target = stub_dir / "jh"
    target.write_text("OLD\n")
    stub_dir.chmod(0o500)
    try:
        from jobhound.commands.completion import maybe_refresh_installed_stubs

        maybe_refresh_installed_stubs()
    finally:
        stub_dir.chmod(0o700)

    assert target.read_text() == "OLD\n"


def test_refresh_handles_multiple_shells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Stubs for several shells installed; each is independently refreshed."""
    monkeypatch.setenv("HOME", str(tmp_path))
    bash_dir = tmp_path / ".local/share/bash-completion/completions"
    zsh_dir = tmp_path / ".zfunc"
    bash_dir.mkdir(parents=True)
    zsh_dir.mkdir(parents=True)
    (bash_dir / "jh").write_text("OLD BASH\n")
    (zsh_dir / "_jh").write_text(_bundled_stub("zsh"))  # already up-to-date

    from jobhound.commands.completion import maybe_refresh_installed_stubs

    maybe_refresh_installed_stubs()

    assert (bash_dir / "jh").read_text(encoding="utf-8") == _bundled_stub("bash")
    assert (zsh_dir / "_jh").read_text(encoding="utf-8") == _bundled_stub("zsh")
    assert (bash_dir / "jh.bak").exists()
    assert not (zsh_dir / "_jh.bak").exists()

    err = capsys.readouterr().err
    assert "bash" in err
    assert "zsh" not in err  # zsh stub matched, so no message
