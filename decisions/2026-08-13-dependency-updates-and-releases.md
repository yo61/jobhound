# Decision: Only dependency updates that ship cut a release

## Decision
Dependabot's commit type is chosen by whether an update reaches users, not by
whether it is a dependency. Runtime Python dependencies keep the `deps` type,
so they appear in the changelog and cut a patch release. GitHub Actions,
pre-commit hooks, and the `dev` dependency group use `chore(deps)`, which
release-please hides and does not release. The `uv` ecosystem's minor/patch
group is split into `uv-production` and `uv-development` so Dependabot's
`prefix-development` can route each PR unambiguously.

## Context
`ci: surface dependency updates in the changelog` (#156) and `ci: use the
`deps` commit type for dependency updates` (#158) gave all three Dependabot
ecosystems the `deps` prefix, to get dependency bumps into the changelog under
a Dependencies heading.

In release-please the two behaviours are one switch: a changelog section that
is not `hidden` is releasable, and any releasable non-`feat` commit bumps the
patch version. There is no "list it but do not ship it" setting. So #156 also
made every dependency bump cut a release:

- 0.18.1 was released for #157 — cyclopts 4.22.4 → 4.22.5 (runtime) grouped
  with hypothesis 6.165.0 → 6.165.1 (dev).
- Release PR #161 proposed 0.18.2 for #160 — `ty` and `hypothesis`, both
  `direct:development`. Neither is in the published package.

An actions or pre-commit bump can never change what a user installs, and
neither can the dev group. A runtime bump can, and is also what regenerates the
Homebrew tap formula's resource stanzas, so those should still release.

## Alternatives considered

**(a) Defer merging the release PR.** Costs nothing and stays available. But
the release PR is then permanently open, rewritten and re-tested on every
dependency bump, and the decision has to be made by hand every time. Left as
the manual lever for runtime bumps that are not worth shipping immediately, not
as the answer to the noise.

**(b) Hide the `deps` section in `release-please-config.json`.** One line, and
no dependency bump ever releases. Rejected: it also removes the Dependencies
section entirely, so a shipped cyclopts or cryptography change stops appearing
in release notes — it undoes #156 rather than refining it.

**(c) Give every dependency `chore(deps)`.** Same effect as (b) from the other
end, with the same loss.

## Reasoning
The boundary that matters to a user reading a changelog, and to the tap, is
whether the published artifact changed. Commit type is where that distinction
can be made once, at the source, instead of being re-judged per release PR.
Splitting the `uv` group by `dependency-type` is required for it to hold: a
grouped PR mixing production and development updates has no documented prefix,
and the previous single group produced exactly that mix.

## Trade-offs accepted
- Dev-group updates no longer appear in the changelog at all. They are visible
  in git history and in the Dependabot PR list, which is where a contributor
  would look for them.
- Two `uv` PRs a week instead of one when both groups have updates.
- Existing `deps:` commits on main keep their type: #161 (or its successor)
  still proposes 0.18.2 for `ty` and `hypothesis`. The change applies from the
  next Dependabot run.

## Supersedes
Refines #156 and #158, which established the `deps` type for all ecosystems.
