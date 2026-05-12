# Post-Refactor Housekeeping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture institutional knowledge from the 2026-05-11 DDD refactor (quality criteria + decision journal) and verify the refactored CLI works end-to-end against a real data root.

**Architecture:** Three independent housekeeping tasks. Tasks 1-2 create new top-level folders (`quality/`, `decisions/`) seeded from the DDD refactor's review findings, following the project conventions specified in the user's global `~/.claude/CLAUDE.md`. Task 3 is a manual smoke test against a throwaway XDG data root, verifying the post-refactor CLI works end-to-end (the test suite covers unit paths but no human-driven session has exercised the new code yet). No production code changes.

**Tech Stack:** Markdown docs + `uv run jh ...` for the smoke test + `XDG_DATA_HOME` env override for isolation.

**Reference:** The 2026-05-11 DDD refactor lives in `docs/plans/2026-05-11-ddd-refactor.md` (now complete) and commits `9b99dc9..65f7ff9` on `main` (SHAs updated 2026-05-13 after Conventional Commits history rewrite; the original SHAs were `0190278..d101bc4`).

**Repo state when starting:** On `main`, 142 tests passing, no remote, working directory clean. Per `feedback_commit_on_main_no_remote.md`, commit directly on `main`.

---

## Task 1: Seed `quality/criteria.md` from DDD review findings

**Goal:** Distill the eight repeatable patterns the spec + code-quality reviewers caught during the DDD refactor into a project-local quality checklist. Format per `~/.claude/CLAUDE.md` "Quality Gate" section.

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/quality/criteria.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/robin/code/github/yo61/jobhound/quality
```

- [ ] **Step 2: Write `quality/criteria.md` with the eight seed criteria**

Create `/Users/robin/code/github/yo61/jobhound/quality/criteria.md` with this content:

```markdown
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
```

- [ ] **Step 3: Verify the file**

```bash
ls -la /Users/robin/code/github/yo61/jobhound/quality/criteria.md
wc -l /Users/robin/code/github/yo61/jobhound/quality/criteria.md
```

Expected: file exists, ~90 lines.

- [ ] **Step 4: Commit**

```bash
cd /Users/robin/code/github/yo61/jobhound
git add quality/criteria.md
git commit -m "Seed quality/criteria.md from DDD refactor review findings"
```

---

## Task 2: Log the DDD refactor decision

**Goal:** Create `decisions/2026-05-11-ddd-refactor.md` capturing the architectural decision, alternatives, and trade-offs while the context is still fresh. Format per `~/.claude/CLAUDE.md` "Decision Journal" section.

**Files:**
- Create: `/Users/robin/code/github/yo61/jobhound/decisions/2026-05-11-ddd-refactor.md`

- [ ] **Step 1: Create the directory**

```bash
mkdir -p /Users/robin/code/github/yo61/jobhound/decisions
```

- [ ] **Step 2: Write the decision entry**

Create `/Users/robin/code/github/yo61/jobhound/decisions/2026-05-11-ddd-refactor.md`:

```markdown
# Decision: Restructure `jh` around DDD building blocks

## Decision
Adopt Domain-Driven Design layering for the `jh` CLI: introduce an
`OpportunityRepository` as the sole persistence surface, push behaviour
methods onto the `Opportunity` aggregate root, and replace stringly-typed
primitives with value objects (`Status`, `Priority`, `Slug`, `Contact`).

Executed as a four-phase plan: Phase 1 repository, Phase 2 entity
behaviour, Phase 3 Status value object, Phase 4 remaining value objects.
Each phase is independently committable and reversible.

## Context
The original `jh` CLI shipped as a 1.4-KLOC anemic-domain implementation:
each of the 17 commands directly called `meta_io.read_meta`,
`dataclasses.replace(opp, ...)`, `meta_io.write_meta`, and
`git.commit_change`. Domain rules were scattered:
- Status state-transition rules in `transitions.py` as a verb-keyed
  `if`/`elif` chain
- Priority validation in `commands/priority.py` only (the model accepted
  any string)
- Slug validation/building/resolution split across three files
- Contact dict-building inline in `commands/contact.py` with no type

The DDD audit on 2026-05-11 ranked refactor payoff by duplication count
and rule-scatter, then proposed the four phases.

## Alternatives considered
**(a) Leave as-is.** Scope was a single user, 1.4 KLOC. CLAUDE.md says
"no premature abstraction; don't create utilities until you've written
the same code three times." But the duplication count (11×) was well past
that threshold, so this option was rejected.

**(b) Phase 1 only (repository extraction).** This captures the biggest
single win — collapses 11-fold IO duplication into one class. Phase 1
alone shrinks every command ~30%. But it leaves the entity anemic and
the value-object rules scattered.

**(c) Full four-phase refactor.** Each phase pays back; later phases
build on earlier ones (Phase 2's entity methods are easier to write once
Phase 1 has eliminated IO boilerplate; Phase 3's `Status.legal_targets`
makes Phase 2's transitions thinner).

## Reasoning
Option (c) was chosen because:
- The four phases stack cleanly (each adds value without invalidating
  the previous one).
- Phase boundaries are real stop points — if pressure shifted, the user
  could stop after any phase with a coherent codebase.
- Reviews flagged that even Phase 1 alone benefited from the
  `OpportunityRepository.create()` and `.save()` abstractions handling
  edge cases (slug rename, scaffolding) that the inline code didn't.

## Trade-offs accepted
- **+5 source modules** (`repository.py`, `status.py`, `priority.py`,
  `slug_value.py`, `contact.py`). Adds layering that an outsider has to
  learn.
- **+58 tests** (84 → 142). Test suite is larger but each new test
  asserts a real domain rule, not implementation detail.
- **Net +827 lines** across 32 files. Some files shrank dramatically;
  others gained value-object scaffolding. The aggregate root grew from
  ~100 lines to ~175 as behaviour migrated in.
- **Learning curve** for `Status.legal_targets(verb='log')` vs.
  the old `if status in ACTIVE_STATUSES and target in {...}`. The new
  API is more discoverable but less direct for a reader who doesn't know
  the value-object idiom.
- **Deferred** (not done; intentionally left for later):
  - `Link` value object (would justify itself when links grow fields).
  - `NextAction` value object pairing `description + due`.
  - Notes + correspondence inside the aggregate boundary (would justify
    itself when a rule spans them, e.g. "no correspondence after
    withdrawn").
  - Domain events (would justify themselves with digests, alerts, or
    external integrations).

## Supersedes
Nothing — this is the first decision logged in this project.

## Outcome (filled in post-hoc)
- 4 phases, 11 tasks, 12 commits.
- Subagent-driven execution flow worked well at this scale (see
  `~/.claude/projects/-Users-robin-code-github-yo61-jobhound/memory/feedback_direct_execution.md`).
- Two-stage review (spec compliance + code quality) caught defects the
  plan-writer missed: a self-contradictory error-message template, a
  set-literal dedup test that didn't exercise dedup, dead backward-compat
  re-exports, three missed test-fixture updates.
- Final reviewer flagged three follow-ups (dead `target_status` param,
  dead `Opportunity.path` field, `.isoformat()` on `date | None`); all
  resolved in commits `891989d`, `c783084`, `65f7ff9` (SHAs updated 2026-05-13 after history rewrite).
```

- [ ] **Step 3: Verify the file**

```bash
wc -l /Users/robin/code/github/yo61/jobhound/decisions/2026-05-11-ddd-refactor.md
```

Expected: ~75 lines.

- [ ] **Step 4: Commit**

```bash
cd /Users/robin/code/github/yo61/jobhound
git add decisions/2026-05-11-ddd-refactor.md
git commit -m "Log DDD refactor decision"
```

---

## Task 3: End-to-end smoke test against a throwaway data root

**Goal:** Run the post-refactor `jh` binary through a representative command sequence against a clean XDG data root and verify on-disk state + git log behave as expected. The 142-test unit suite covers paths in isolation, but no human-driven session has exercised the new code against a real data root.

**Files:** None modified. This task is a manual verification only — it produces commits in a throwaway location (`/tmp/jh-smoke/jh/`), not in the project repo.

**Working directory:** `/Users/robin/code/github/yo61/jobhound` throughout.

**XDG override:** `xdg_base_dirs.xdg_data_home()` honors the `XDG_DATA_HOME` env var per the XDG spec. Setting it to `/tmp/jh-smoke` makes `jh` use `/tmp/jh-smoke/jh/` as its data root. No config-file edits needed.

- [ ] **Step 1: Prepare a clean data root**

```bash
export XDG_DATA_HOME=/tmp/jh-smoke
rm -rf "$XDG_DATA_HOME"
mkdir -p "$XDG_DATA_HOME"
echo "Data root: $XDG_DATA_HOME/jh"
```

Expected: directory is fresh and empty.

- [ ] **Step 2: Create a new opportunity**

```bash
uv run jh new --company "Acme" --role "Engineer" \
  --next-action "Initial review" --next-action-due 2026-05-25 --today 2026-05-11
```

Expected stdout: `Created opportunities/2026-05-acme-engineer`

Verify on disk:

```bash
ls "$XDG_DATA_HOME/jh/opportunities/"
# Expected: 2026-05-acme-engineer/

ls "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/"
# Expected: correspondence/  meta.toml  notes.md  research.md

cat "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/meta.toml"
# Expected: company = "Acme", role = "Engineer", status = "prospect",
#           priority = "medium", first_contact = 2026-05-11,
#           last_activity = 2026-05-11, next_action = "Initial review",
#           next_action_due = 2026-05-25
```

- [ ] **Step 3: Apply (status → applied)**

```bash
uv run jh apply acme \
  --next-action "Wait for screen" --next-action-due 2026-05-25 --today 2026-05-12
```

Expected stdout: `applied: 2026-05-acme-engineer`

Verify:

```bash
grep -E '^status|^applied_on|^last_activity' \
  "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/meta.toml"
# Expected:
#   status = "applied"
#   applied_on = 2026-05-12
#   last_activity = 2026-05-12
```

- [ ] **Step 4: Log an interaction (status → screen)**

```bash
echo "Hi Acme, looking forward to the screening." > /tmp/jh-smoke-draft.md
uv run jh log acme \
  --channel email --direction to --who recruiter --body /tmp/jh-smoke-draft.md \
  --next-status screen --next-action "Prep" --next-action-due 2026-05-20 \
  --today 2026-05-14
```

Expected stdout: `logged: 2026-05-acme-engineer applied → screen`

Verify:

```bash
ls "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/correspondence/"
# Expected: 2026-05-14-email-to-recruiter.md

grep '^status' "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/meta.toml"
# Expected: status = "screen"
```

- [ ] **Step 5: Note + tag + priority + link + contact**

```bash
uv run jh note acme --msg "Recruiter sounded warm" --today 2026-05-15
uv run jh tag acme --add remote --add senior
uv run jh priority acme --to high
uv run jh link acme --name jd --url https://example.com/jd
uv run jh contact acme --name "Jane Doe" --role-title "Recruiter" --channel email
```

Verify:

```bash
cat "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/notes.md"
# Expected: "- 2026-05-15 Recruiter sounded warm"

cat "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/meta.toml"
# Expected fields:
#   priority = "high"
#   tags = ["remote", "senior"]
#   [[contacts]] with name = "Jane Doe", role = "Recruiter", channel = "email"
#   [links] with jd = "https://example.com/jd"
```

- [ ] **Step 6: List**

```bash
uv run jh list
# Expected: one line:
#   2026-05-acme-engineer       screen       high
```

- [ ] **Step 7: Withdraw (status → withdrawn)**

```bash
uv run jh withdraw acme --today 2026-05-20
```

Expected stdout: `withdraw: 2026-05-acme-engineer`

Verify:

```bash
grep '^status' "$XDG_DATA_HOME/jh/opportunities/2026-05-acme-engineer/meta.toml"
# Expected: status = "withdrawn"
```

- [ ] **Step 8: Verify git log captured each operation**

```bash
git -C "$XDG_DATA_HOME/jh" log --oneline
```

Expected: ~10 commits, one per `jh` command (new, apply, log, note, tag, priority, link, contact, withdraw). Commit messages should match the format `<verb>: <slug>` or `<verb>: <slug> <detail>`.

If any operation is missing a commit, that's a bug — flag it.

- [ ] **Step 9: Cleanup**

```bash
rm -rf /tmp/jh-smoke /tmp/jh-smoke-draft.md
unset XDG_DATA_HOME
```

- [ ] **Step 10: Report back**

If every step succeeded with the expected output, report:

> Smoke test passed. All 9 verb invocations exit 0, file state matches, git log shows N commits.

If any step failed unexpectedly:

> Smoke test FAILED at Step X. <describe the unexpected output>.

This task does not produce a commit in the jh repository — it produces a verdict.

---

## What NOT to do after this plan

After Tasks 1–3 are complete, stop. Specifically, do not preemptively:

- **Promote any of the deferred DDD items** (Link VO, NextAction VO,
  notes/correspondence aggregate, domain events) without a real driver —
  a new feature, a recurring rule that spans concerns, or an external
  integration that benefits from events. The audit ranked these below
  the four-phase work for a reason; that reasoning still holds.
- **Expand `quality/criteria.md` speculatively.** New criteria should
  be added only when a new failure pattern emerges in a real review,
  not preemptively. The global CLAUDE.md says: "Criteria triggered 3+
  times: promote to 'always check'. Criteria never triggered after 10+
  evaluations: suggest pruning." Let the file grow from triggered
  evidence, not theory.
- **Start a system review.** Global CLAUDE.md says to suggest one
  every 2+ weeks or at a milestone. The DDD refactor is a milestone,
  but the system has only one project, one decision, and no rules
  yet — there's nothing to review. Defer until a second decision lands.
- **Set up `/knowledge/`** (the third standing folder from the global
  CLAUDE.md). The `jh` project is a tool for the user, not a domain
  with hypotheses and confirmed rules. The folder structure doesn't
  fit this project shape. Skip unless a real knowledge-architecture
  use case appears.
