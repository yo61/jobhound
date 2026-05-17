"""`jh completion` — print or install per-shell completion scripts."""

from __future__ import annotations

from importlib import resources

from cyclopts import App

app = App(name="completion", help="Print or install jh shell completion scripts.")


def _read(shell: str) -> str:
    """Read the bundled shell script for `shell` ('bash' | 'zsh' | 'fish')."""
    name = f"jh.{shell}"
    return (resources.files("jobhound._completion") / name).read_text(encoding="utf-8")


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
