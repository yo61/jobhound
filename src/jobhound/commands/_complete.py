"""Hidden `__complete` subcommand — emits completion candidates to stdout.

Invoked by the per-shell completion scripts under
``src/jobhound/_completion/``. Output is one candidate per line, no
quoting (the shell scripts handle quoting).

The command itself is registered with ``show=False`` so it does not
appear in ``jh --help``.
"""

from __future__ import annotations


def run(shell: str, /, *words: str) -> None:
    """Stub. Will dispatch in later tasks.

    Args:
        shell: One of 'bash', 'zsh', 'fish'. Used to vary output
            quoting in later refinements; for the stub it is ignored.
        words: The command-line tokens typed so far, including the
            current partial last word.
    """
    # Intentionally empty for the smoke test — no candidates yet.
    return
