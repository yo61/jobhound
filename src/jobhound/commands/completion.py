"""`jh completion` — print or install per-shell completion scripts."""

from __future__ import annotations

import os
import shutil
import sys
from importlib import resources
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter

app = App(name="completion", help="Print or install jh shell completion scripts.")

_SHELL_TARGETS: dict[str, tuple[str, str]] = {
    # shell -> (default_directory_template, filename)
    "bash": ("~/.local/share/bash-completion/completions", "jh"),
    "zsh": ("~/.zfunc", "_jh"),
    "fish": ("~/.config/fish/completions", "jh.fish"),
}


def _read(shell: str) -> str:
    """Read the bundled shell script for `shell` ('bash' | 'zsh' | 'fish')."""
    name = f"jh.{shell}"
    return (resources.files("jobhound._completion") / name).read_text(encoding="utf-8")


def _detect_shell() -> str | None:
    """Detect the user's shell from $SHELL. Return one of bash/zsh/fish, or None."""
    sh = os.environ.get("SHELL", "")
    name = Path(sh).name
    return name if name in _SHELL_TARGETS else None


@app.command(name="bash")
def bash() -> None:
    """Print the bash completion script to stdout."""
    print(_read("bash"))


@app.command(name="zsh")
def zsh() -> None:
    """Print the zsh completion script to stdout."""
    print(_read("zsh"))


@app.command(name="fish")
def fish() -> None:
    """Print the fish completion script to stdout."""
    print(_read("fish"))


@app.command(name="install")
def install(
    *,
    shell: Annotated[str | None, Parameter(name=["--shell"])] = None,
    dest: Annotated[str | None, Parameter(name=["--dest"])] = None,
) -> None:
    """Install the jh completion script for the current shell.

    Args:
        shell: Override shell detection. One of 'bash', 'zsh', 'fish'.
        dest: Override the default install directory. The filename
            inside the dir is still determined by shell.
    """
    detected = shell or _detect_shell()
    if detected is None or detected not in _SHELL_TARGETS:
        print(
            "ERROR: could not detect shell. Pass --shell bash|zsh|fish.",
            flush=True,
        )
        raise SystemExit(1)

    dir_tpl, filename = _SHELL_TARGETS[detected]
    target_dir = Path(dest) if dest else Path(dir_tpl).expanduser()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename

    new_content = _read(detected)

    if target.exists() and target.read_text(encoding="utf-8") == new_content:
        print(f"jh completion: {target} is already up to date.")
        return

    if target.exists():
        # Use filename + ".bak" rather than with_suffix to avoid replacing
        # an existing extension (.fish -> .bak would lose the .fish).
        backup = target.parent / (target.name + ".bak")
        shutil.copy2(target, backup)
        print(f"jh completion: backed up existing {target} -> {backup}")

    target.write_text(new_content, encoding="utf-8")
    print(f"jh completion: wrote {target}")

    # Per-shell hint.
    if detected == "zsh":
        print("Add this to your ~/.zshrc if you haven't already:")
        print("  fpath+=~/.zfunc")
        print("  autoload -U compinit && compinit")
    elif detected == "bash":
        print("Reload your shell or `source ~/.bashrc` to activate.")
    elif detected == "fish":
        print("Reload fish (functions auto-discover; usually no action needed).")


def maybe_refresh_installed_stubs() -> None:
    """Refresh any installed completion stub that's drifted from the bundled one.

    For each shell whose stub exists at its conventional install path,
    compare contents against the bundled stub in the wheel. If they
    differ, back up the old file as ``<name>.bak`` and rewrite from
    the bundled copy, announcing the refresh on stderr.

    Only honors stubs that already exist — we never auto-install for
    users who never ran ``jh completion install``. Read/write errors
    are swallowed silently so a hostile filesystem can't make every
    ``jh`` invocation noisy.
    """
    for shell, (dir_tpl, filename) in _SHELL_TARGETS.items():
        target = Path(dir_tpl).expanduser() / filename
        if not target.is_file():
            continue
        try:
            installed = target.read_text(encoding="utf-8")
        except OSError:
            continue
        bundled = _read(shell)
        if installed == bundled:
            continue
        try:
            backup = target.parent / (target.name + ".bak")
            shutil.copy2(target, backup)
            target.write_text(bundled, encoding="utf-8")
        except OSError:
            continue
        print(
            f"jh: refreshed {shell} completion stub at {target}",
            file=sys.stderr,
        )
