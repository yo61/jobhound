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


def test_bash_script_filters_candidates_by_current_word_prefix() -> None:
    """bash script must filter COMPREPLY by the partial word.

    Setting COMPREPLY directly (which we do to preserve spaces) bypasses
    bash's built-in prefix matching. Without an explicit filter, every
    candidate would be offered even when the user has typed a unique
    prefix like `jh fi` (expecting `file`).
    """
    s = _script("jh.bash")
    # Either of these patterns is acceptable; both are defensible
    # ways to express "candidate must start with the current word".
    assert ('"$cand" == "$current"*' in s) or ('"$cand" == "$cur"*' in s)


def test_zsh_script_uses_at_f_split_and_compadd() -> None:
    """zsh script must split on \\n only (preserves spaces) and use compadd -a."""
    s = _script("jh.zsh")
    assert "${(@f)$(jh __complete zsh" in s
    assert "compadd -a" in s
    assert "#compdef jh" in s


def test_fish_script_disables_file_fallback() -> None:
    """fish script must use `complete -f` (no fallback to filename completion)."""
    s = _script("jh.fish")
    assert "complete -c jh" in s
    assert "-f" in s
    assert "jh __complete fish" in s


def test_bash_script_handles_files_sentinel() -> None:
    """bash stub must recognise the files sentinel and delegate to native file completion.

    When the completer emits the sentinel, the stub should fall back to
    bash's built-in path completion for the partial word — either via
    `compopt -o default` (readline's default completion) or by populating
    COMPREPLY from `compgen -f`.
    """
    from jobhound.commands._complete import FILES_SENTINEL

    s = _script("jh.bash")
    assert FILES_SENTINEL in s
    assert ("compopt -o default" in s) or ("compgen -f" in s)


def test_zsh_script_handles_files_sentinel() -> None:
    """zsh stub must recognise the files sentinel and call `_files`."""
    from jobhound.commands._complete import FILES_SENTINEL

    s = _script("jh.zsh")
    assert FILES_SENTINEL in s
    assert "_files" in s


def test_fish_script_handles_files_sentinel() -> None:
    """fish stub must recognise the files sentinel and emit path completions."""
    from jobhound.commands._complete import FILES_SENTINEL

    s = _script("jh.fish")
    assert FILES_SENTINEL in s
    assert "__fish_complete_path" in s
