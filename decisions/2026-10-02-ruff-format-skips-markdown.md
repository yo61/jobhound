## Decision: `ruff format` excludes `*.md`

## Context: ruff 0.16 (bumped in #194) formats Python code blocks inside markdown. Fifteen files under `docs/` failed `ruff format --check`, and because the `ruff-format` hook runs repo-wide (`pass_filenames: false`), every commit touching Python failed it.

## Alternatives considered:

- Reformat the fifteen docs files once and keep markdown in scope.
- Skip the hook per commit (`SKIP=ruff-format`).

## Reasoning: The markdown under `docs/` is dated plans and specs: snapshots of code as proposed at the time, often fragments (method bodies without their class). Reformatting rewrites those records and mangles fragments (it dedented methods out of their class). Skipping the hook per commit hides real Python formatting failures.

## Trade-offs accepted: Code samples in new docs are not format-checked.

## Supersedes: none
