## Decision: `ruff format` formats Python code blocks in markdown; fragments carry enough context to parse

## Context: ruff 0.16 (bumped in #194) formats Python code blocks inside markdown. Fifteen files under `docs/` failed `ruff format --check`, and because the `ruff-format` hook runs repo-wide (`pass_filenames: false`), every commit touching Python failed it.

## Alternatives considered:

- Exclude `*.md` from `ruff format` (merged in #196, reverted here).
- Exclude only the dated `docs/plans/`, `docs/specs/` and `docs/superpowers/` trees.
- Wrap fragment blocks in `<!-- fmt: off -->` / `<!-- fmt: on -->`.

## Reasoning: Formatting keeps every markdown code sample checked. ruff parses each block as a standalone module, which breaks fragments:

- Indented method bodies lose their base indent (cosmetic; the prose names the class).
- Set elements and keyword arguments ending in `,` become one-element tuples: `"show",` becomes `("show",)`, `priority=X,` becomes `priority = (X,)`. Pasted back where the prose says, these are wrong code that `ruff format --check` still passes.
- A bare `return` block is not valid Python, so ruff skips it silently.

The four affected fragments now include their enclosing `frozenset({...})` or function and call, with `# ...` placeholders, so they parse and format correctly. ruff 0.16 has no option to keep a block's base indent, and skip markers would leave those blocks unchecked.

## Trade-offs accepted: A one-off reformat of fifteen dated plan and spec files, with small content edits to four of their samples. New fragment samples need the same enclosing context.

## Supersedes: the exclude from #196 (record removed in the same change)
