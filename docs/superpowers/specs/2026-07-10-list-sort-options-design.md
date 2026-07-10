# List sort options (issue #60)

## Goal

Make list-style output sortable and predictable:

- Case-insensitive ordering by default (today it is case-sensitive
  byte-order, so `Alpha.md`, `Charlie.md`, `bravo.md`).
- `jh file list` gains `--sort <key>` and `--reverse`/`-r`.
- `jh list` and `jh stats` (sources) switch their default ordering to
  case-insensitive.

## Scope

Three display-layer touch points. No storage or domain contract changes —
`FileStore.list` stays byte-order deterministic; case-insensitive
collation is a display concern applied at the command layer.

### 1. `jh file list` — sort flags (`src/jobhound/commands/file.py`)

- Add `FileSortKey(StrEnum)` with members `NAME` / `SIZE` / `DATE`
  (values surface in `--help` and shell completion).
- Add parameters to `list_`:
  - `sort: Annotated[FileSortKey, Parameter(name=["--sort"])] = FileSortKey.NAME`
  - `reverse: Annotated[bool, Parameter(name=["--reverse", "-r"], negative=())] = False`
- Sort at the command layer via a pure helper
  `_sort_entries(entries, sort, reverse) -> FileEntryList`. Per-key
  default direction, borrowed from `ls`:
  | key    | comparison key      | default direction     |
  | ------ | ------------------- | --------------------- |
  | `name` | `e.name.casefold()` | ascending             |
  | `size` | `e.size`            | descending (largest)  |
  | `date` | `e.mtime`           | descending (newest)   |
  - `--reverse` flips the chosen key's default direction.
- Register completion in `_complete.py`'s `_FLAG_ENUMS`:
  `(("file", "list"), "--sort"): "jobhound.commands.file:FileSortKey"`.

### 2. `jh list` + `jh stats` slug order (`src/jobhound/application/query.py`)

`OpportunityQuery.list()` is the authoritative slug sort for both
commands (line 122). Change the sort key to case-insensitive:

```python
snaps.sort(key=lambda s: s.opportunity.slug.casefold())
```

Note: the issue's pointer to `repository.py:41` (`all()`) is stale —
`all()` is only used by `scrape_service` for dedup and never reaches
`jh list` output, so it is deliberately left untouched.

### 3. `jh stats` sources (`src/jobhound/commands/stats.py:119`)

```python
for source, count in sorted(sources.items(), key=lambda kv: kv[0].casefold()):
```

## Testing

- `_sort_entries`: key × direction × reverse matrix, plus case-insensitive
  name ordering (`Alpha`, `bravo`, `Charlie`); default is `name` ascending.
- CLI: `jh file list` wires `--sort`/`--reverse` through to output order.
- `query.list`: mixed-case slugs order case-insensitively.
- `jh stats`: sources render in case-insensitive order.

## Out of scope

- `repository.all()` — not user-facing.
- `jh stats` funnel — intentionally fixed `Status` enum order.

## Version impact

`feat:` commit → minor bump → **0.17.0** via release-please. Merging the
resulting Release PR exercises the new Homebrew bottle pipeline end-to-end.
