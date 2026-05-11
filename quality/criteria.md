# Quality Criteria — jh CLI

Seeded 2026-05-11 from review findings during the DDD refactor. Each criterion
records a real failure the reviewers caught. New criteria should be added only
when a new failure pattern emerges, not preemptively.

Format per `~/.claude/CLAUDE.md` "Quality Gate" section.

---

## Category: Domain modelling

### Criteria
- Business rules and invariants live on the aggregate entity, not in command handlers.
  If a command contains `dataclasses.replace(entity, ...)` with multiple fields,
  the rule belongs on the entity as a named method.

### Severity: blocking
### Source: 2026-05-11 DDD refactor Phase 2; the audit found 11 commands all
calling `replace(opp, ...)` inline. Anemic-domain anti-pattern.
### Last triggered: 2026-05-11

---

## Category: Error-path test coverage

### Criteria
- Every `raise SomeError` in production code has a test that triggers it.
  If the production code can fail, the test suite must prove it does.

### Severity: blocking
### Source: 2026-05-11 DDD refactor Task 1 (`FileExistsError` paths in
`create()` and `archive()` were untested); Task 5 (`test_ghost_rejects_terminal`
and `test_decline_rejects_non_offer` were missing while their counterparts
existed).
### Last triggered: 2026-05-11

---

## Category: Test assertions on typed fields

### Criteria
- Test assertions on typed fields compare to the type, not to a primitive
  equivalent. `assert opp.priority == Priority.HIGH`, not `== "high"`.
  String equality on a `StrEnum` passes today but breaks the type contract
  if the field is ever regressed to `str`.

### Severity: warning
### Source: 2026-05-11 DDD refactor Task 9; three test files used
`opp.priority == "high"` and would have passed even if `priority` regressed
to a plain string.
### Last triggered: 2026-05-11

---

## Category: Replace, don't deprecate

### Criteria
- No backward-compat re-exports if nothing actually imports them.
  When a refactor moves a constant/function, delete the old location
  entirely. If a test was the only consumer, rewrite the test against the
  new location.

### Severity: blocking
### Source: `~/.claude/CLAUDE.md` global philosophy; triggered 2026-05-11 in
DDD refactor Task 8 (dead `ACTIVE_STATUSES`/`CLOSED_STATUSES`/`ALL_STATUSES`
re-exports kept "for tests"; the right fix was to rewrite the one test).
### Last triggered: 2026-05-11

---

## Category: Cyclomatic complexity

### Criteria
- ≤8 cyclomatic complexity per function. `radon cc src/ -s -a` or equivalent.
  Long `if`/`elif` chains over a discriminating string should be a dispatch
  table or `match` statement.

### Severity: blocking
### Source: `~/.claude/CLAUDE.md` "Hard limits"; triggered 2026-05-11 in
DDD refactor Task 7 (`Status.legal_targets` was CC=14, refactored to a
dispatch table at CC=2).
### Last triggered: 2026-05-11

---

## Category: Comments and docstrings match implementation

### Criteria
- Comments and docstrings referencing types, structures, or invariants
  must match the current implementation. When a refactor changes the
  structure, update the comment in the same commit.

### Severity: warning
### Source: 2026-05-11 DDD refactor Task 7 (`(str, Enum)` docstring left
after switching to `StrEnum`); Task 8 (stale "module-level cycle" comment
after the cycle was eliminated).
### Last triggered: 2026-05-11

---

## Category: Test design — set/dict literals

### Criteria
- Don't use literal duplicates to test dedup behaviour. Python collapses
  `{"b", "a", "b"}` to `{"a", "b"}` at parse time, so the input never
  exercises the dedup path. Use sequential calls with overlapping inputs
  instead.

### Severity: blocking
### Source: 2026-05-11 DDD refactor Task 6; spec test
`test_with_tags_dedupes_and_sorts` passed a duplicate set literal that
collapsed at parse time. Implementer caught and rewrote.
### Last triggered: 2026-05-11

---

## Category: Repeated function-local imports

### Criteria
- If the same function-local `from X import Y` appears in 3+ methods of
  the same class/module, consolidate to a single private module-level
  wrapper function. Local imports are for breaking import cycles; six
  copies is noise.

### Severity: warning
### Source: 2026-05-11 DDD refactor Task 5; six methods of `Opportunity`
each had an inline `from jobhound.transitions import require_transition`.
Consolidated to a single `_require_transition` helper.
### Last triggered: 2026-05-11
