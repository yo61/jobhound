"""Tests for the shell completion scripts.

We don't invoke real bash/zsh/fish in CI (interactive). Instead we
verify the scripts contain the load-bearing constructs that handle
spaces and call `jh __complete`. Manual smoke-test against a real
shell is in the README.
"""

from __future__ import annotations

from importlib import resources


def _script(name: str) -> str:
    return (resources.files("jobhound._completion") / name).read_text(encoding="utf-8")


def test_bash_script_uses_mapfile_for_space_safety() -> None:
    """bash script must use mapfile -t (not naive splitting) for space safety."""
    s = _script("jh.bash")
    assert "mapfile -t" in s
    assert "jh __complete bash" in s
    assert "complete -F _jh_complete jh" in s


def test_bash_script_uses_printf_q_to_escape() -> None:
    """bash script must escape candidates via printf %q for filenames-with-spaces."""
    s = _script("jh.bash")
    assert "%q" in s
