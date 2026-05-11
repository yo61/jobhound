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
  resolved in commits `8bbe231`, `97c82b1`, `d101bc4`.
