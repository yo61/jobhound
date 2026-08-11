# Decision: Remove the Claude Code CI workflows from jobhound

## Decision
Delete `.github/workflows/claude-code-review.yml` (automatic Claude review
on every PR) and `.github/workflows/claude.yml` (the `@claude` mention
assistant for issues and PR comments), and delete the repository Actions
secret `CLAUDE_CODE_OAUTH_TOKEN` that both used. No Claude-driven CI
remains in this repo.

## Context
The two workflows were added on 2026-05-16 (`fa7402b`, `1dd58a6`) and
maintained since — pinned to `anthropics/claude-code-action@51ea8ea`
(v1.0.123), with a Dependabot skip guard (`d3220d7`) and a release-please
bot allowance (`7b814fe`). They were working: the last review ran
2026-08-11 and succeeded.

A survey of all 27 non-fork yo61 repos found jobhound was the only one
with either workflow, and the only one holding a `CLAUDE_*` Actions
secret. The org has no Claude token at `orgs/yo61/actions/secrets`, so
"remove it everywhere" is scoped entirely to this repo. Nothing else
referenced the workflows — no README badge, no docs, and no resource in
the `github-repos` Terraform, which manages jobhound's settings but not
its workflow files.

Robin decided to stop using the integration. No technical fault
prompted it.

## Alternatives considered

**(a) Remove only the auto-review, keep `claude.yml`.** Would have kept
on-demand `@claude` help in issues and PRs while ending unprompted
reviews. Rejected: the decision was to stop using the integration, not
to reduce its frequency.

**(b) Remove both workflows, keep the OAuth token.** Would have made
re-enabling a file-only change later. Rejected: an unused credential on
a public repo is attack surface with no current purpose.

**(c) Remove both workflows and the token (chosen).**

## Reasoning
Option (c) leaves no dormant configuration and no unused credential.
The removal is low-risk to verify: `claude-review` was never a required
status check, so the merge gate is unaffected. The
`required_status_checks` ruleset in
`github-repos/data/yo61/jobhound.yaml` gates on `Lint, typecheck, test`,
`Conventional Commits`, and `zizmor` — none of which this change
touches. No Terraform change is needed.

## Trade-offs accepted

- **Re-enabling costs more than a file.** The OAuth token cannot be
  recovered; restoring the integration means minting a fresh one via
  `claude /install-github-app` or `gh secret set`, then restoring both
  workflow files from git history.
- **No automated review on PRs.** Review coverage now rests entirely on
  the deterministic CI checks (lint, typecheck, test, commitlint,
  zizmor) plus human review — the ruleset requires one approval.
- **Loss of `@claude` in issues and PRs.** Asking Claude about this
  repo now happens in a local session rather than from a GitHub
  comment thread.

## Supersedes
Nothing. This ends the setup introduced on 2026-05-16; there was no
prior decision entry for adding it.
