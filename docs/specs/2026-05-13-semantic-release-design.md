# Semantic Release & PyPI Publishing — Design Spec

Date: 2026-05-13
Status: Draft, awaiting review

## Goal

Add an automated release pipeline to `jobhound` so that:

1. Every commit landing on `main` is a Conventional Commit, enforced both
   locally (prek `commit-msg` hook) and in CI.
2. Version numbers, tags, `CHANGELOG.md`, and GitHub Releases are produced
   automatically from those commits via `release-please`.
3. Each tagged release publishes an sdist and wheel to PyPI via OIDC Trusted
   Publishing (no long-lived tokens).
4. The result enables Phase 2 of the broader plan: adding `jobhound` as a
   formula in `yo61/homebrew-tap` against the released tarball.

## Scope

In scope:

- Two new GitHub Actions workflows: `ci.yml`, `release.yml`.
- Four new repo-root config files: `release-please-config.json`,
  `.release-please-manifest.json`, `commitlint.config.mjs`, `CHANGELOG.md`.
- One additional prek hook: `compilerla/conventional-pre-commit` at the
  `commit-msg` stage.
- One-time history rewrite: bring the existing 50 commits up to
  Conventional-Commits standard before pushing to the public remote.
- One-time manual setup: GitHub repo creation, PyPI Pending Publisher,
  GitHub Environment, branch-protection ruleset, baseline `v0.1.0` tag.

Out of scope (explicitly):

- Commit-message linting on the squash-merge model (rejected — see
  Decisions §D2).
- `python-semantic-release` (rejected — see Decisions §D1).
- Multi-Python-version CI matrix. Single Python 3.13 matches
  `requires-python` in `pyproject.toml`.
- Signed commits / signed tags. Can be turned on later via repo settings
  without code changes.
- Attaching the built wheel/sdist to the GitHub Release. They live on
  PyPI; Homebrew will fetch the GitHub auto-generated source tarball.
- PyPI publishing via classic API token. OIDC only.

## Decisions

### D1. Release tool: `release-please` (over `python-semantic-release`)

Chose `googleapis/release-please-action@v4` because its release-PR review
checkpoint matches Robin's existing review-heavy culture (`ultrareview`,
multi-agent code review). `python-semantic-release` fires the release the
moment a `feat:` lands on `main` with no review step. The release-PR model
also lets `CHANGELOG.md` be edited before the release is cut.

### D2. Merge strategy: rebase-merge (over squash-merge)

The initial design proposed squash-merge with PR-title-only validation.
That model is broken: GitHub does not roll up commit types when squashing,
so a PR containing `fix:` + `fix:` + `feat:` titled `fix: …` produces a
`fix:` commit on `main`, and the `feat:` is invisible to release-please.

Rebase-merge preserves every commit verbatim on `main`. Validation runs on
every commit in the PR via `wagoid/commitlint-github-action@v6`. Trade-off
accepted: `main` accumulates more commits per PR (improves `git bisect`
granularity).

### D3. Conventional Commits enforced, going forward only

Local: prek `commit-msg` hook via `compilerla/conventional-pre-commit`.
CI: `wagoid/commitlint-github-action@v6` validates every commit in the
PR; required check on the branch protection ruleset.

Pre-public history (50 commits) is rewritten once in Step 0 of the
implementation procedure (see §Implementation Steps).

### D4. PyPI Trusted Publishing via OIDC

No PyPI API tokens are stored anywhere. The `publish` job runs inside a
GitHub Environment named `pypi`; PyPI's Trusted Publisher config pins the
trust to (`yo61/jobhound`, workflow `release.yml`, environment `pypi`).
First publish uses PyPI's "Pending Publisher" feature so the project name
is reserved before the project exists.

### D5. Pre-1.0 version semantics

`bump-minor-pre-major: true` in `release-please-config.json`. In 0.x.y,
`feat!:` or `BREAKING CHANGE:` bumps MINOR (e.g., 0.1.0 → 0.2.0), not
MAJOR. This matches the `semantic-release` default already in use in
`go-udap`. To reach 1.0.0 deliberately, use a `Release-As: 1.0.0` footer
on a commit.

### D6. Post-DDD cleanup trio kept as separate commits during Step 0

The three commits `8bbe231` / `97c82b1` / `d101bc4` (drop dead
`target_status`, remove unused `Opportunity.path`, test date fields
directly) will be reworded into separate `refactor:` / `refactor:` /
`test:` commits rather than squashed. Preserves the "reviewer found,
implementer fixed" narrative.

## Architecture

### Workflows (2 files)

**`.github/workflows/ci.yml`** — guards what lands on `main`. Triggers on
`pull_request` and `push` to `main`. Two jobs:

- `check` — runs `task dev:check` (lint, format-check, typecheck, tests)
  on Ubuntu with Python 3.13.
- `commitlint` — runs `wagoid/commitlint-github-action@v6` on `pull_request`
  events only; validates every commit in the PR head.

Both are required status checks in branch protection.

**`.github/workflows/release.yml`** — produces releases. Triggers on `push`
to `main` (which only ever happens via merged PRs). Two jobs:

- `release-please` — runs `googleapis/release-please-action@v4`. Either
  updates the long-lived Release PR with the new commits, or — if the
  Release PR was just merged — cuts the tag and the GitHub release.
  Outputs `release_created` and `tag_name` for the next job.
- `publish` — gated by `if: needs.release-please.outputs.release_created == 'true'`.
  Checks out the just-created tag, runs `uv build`, then
  `pypa/gh-action-pypi-publish@release/v1` with OIDC. Lives in the `pypi`
  GitHub Environment.

### Configuration (4 files)

**`release-please-config.json`** — `release-type: python` (auto-bumps
`version = "x.y.z"` in `pyproject.toml`), `include-v-in-tag: true`,
`bump-minor-pre-major: true`, `bump-patch-for-minor-pre-major: false`.

**`.release-please-manifest.json`** — seeds `{ ".": "0.1.0" }`.

**`commitlint.config.mjs`** — 3-line config extending
`@commitlint/config-conventional`. The CI action pulls the rules at
runtime; no `node_modules` enter the repo.

**`CHANGELOG.md`** — empty seed (`# Changelog\n`). release-please rewrites
it on each Release PR.

### Pre-commit hooks (1 modification)

Append one entry to `.pre-commit-config.yaml`:

```yaml
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.x.x
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
```

Install command becomes:
`prek install --hook-type pre-commit --hook-type commit-msg`.

### Data flow for a typical release

```
human: branch + commits (local prek validates each commit-msg)
   ↓
open PR with conventional commits throughout
   ↓
CI runs: check (dev:check) + commitlint (every commit)
   ↓
both green → rebase-merge → each commit lands verbatim on main
   ↓
release.yml: release-please parses commits, updates Release PR
   ↓
review + merge Release PR → tag + GH release → OIDC publish to PyPI
```

## File contents

### `.github/workflows/ci.yml`

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  check:
    name: Lint, typecheck, test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@<sha>           # v4
      - uses: astral-sh/setup-uv@<sha>         # v6
        with:
          enable-cache: true
          python-version: "3.13"
      - uses: arduino/setup-task@<sha>         # v2
        with:
          version: 3.x
      - run: uv sync --frozen
      - run: task dev:check

  commitlint:
    name: Conventional Commits
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    permissions:
      pull-requests: read
    steps:
      - uses: actions/checkout@<sha>           # v4
        with:
          fetch-depth: 0
      - uses: wagoid/commitlint-github-action@<sha>  # v6
        with:
          configFile: commitlint.config.mjs
```

### `.github/workflows/release.yml`

```yaml
name: Release

on:
  push:
    branches: [main]

permissions:
  contents: write
  pull-requests: write

jobs:
  release-please:
    runs-on: ubuntu-latest
    outputs:
      release_created: ${{ steps.rp.outputs.release_created }}
      tag_name:        ${{ steps.rp.outputs.tag_name }}
    steps:
      - uses: googleapis/release-please-action@<sha>  # v4
        id: rp
        with:
          config-file: release-please-config.json
          manifest-file: .release-please-manifest.json

  publish:
    needs: release-please
    if: needs.release-please.outputs.release_created == 'true'
    runs-on: ubuntu-latest
    environment:
      name: pypi
      url:  https://pypi.org/p/jobhound
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@<sha>           # v4
        with:
          ref: ${{ needs.release-please.outputs.tag_name }}
      - uses: astral-sh/setup-uv@<sha>         # v6
        with:
          python-version: "3.13"
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@<sha>  # v1
```

Action SHAs are placeholders; the implementation plan resolves them at
write time per CLAUDE.md ("look up current versions, don't assume from
memory").

### `release-please-config.json`

```json
{
  "$schema": "https://raw.githubusercontent.com/googleapis/release-please/main/schemas/config.json",
  "release-type": "python",
  "include-v-in-tag": true,
  "bump-minor-pre-major": true,
  "bump-patch-for-minor-pre-major": false,
  "packages": {
    ".": {
      "package-name": "jobhound",
      "changelog-path": "CHANGELOG.md"
    }
  }
}
```

### `.release-please-manifest.json`

```json
{ ".": "0.1.0" }
```

### `commitlint.config.mjs`

```js
export default { extends: ['@commitlint/config-conventional'] };
```

### `CHANGELOG.md`

```markdown
# Changelog
```

## Implementation steps

These run exactly once during the implementation plan. None of them can
be expressed in code — they are local git ops, click-ops on
github.com/pypi.org, or a one-time editorial pass.

### Step 0 — Rewrite history to Conventional Commits

Inputs: 50 commits on `main`, HEAD at `52cc67f`, no remote.

Outputs: rewritten `main` (~40-45 commits after sensible merges); every
subject matches `<type>(<scope>)?: <subject>`; original history preserved
as the local-only `pre-conventional-history` tag.

Process:

1. `git tag pre-conventional-history` on the current `52cc67f`. This tag
   is never pushed.
2. Assistant produces `docs/plans/2026-05-13-history-rewrite-map.md`: one
   row per existing commit (original SHA, original subject, proposed
   type+subject, squash-into-previous flag).
3. User reviews and edits the map.
4. User executes `git rebase -i --root` interactively, applying the map.
   (CLAUDE.md forbids the assistant from invoking `-i`; this is a human-
   driven step.)
5. Assistant verifies: every new subject matches the conventional-commits
   regex; tests still pass on the rewritten tip; commit count is as
   planned.
6. Assistant greps all `docs/` for SHA references that became stale (e.g.
   `docs/plans/2026-05-11-post-refactor-housekeeping.md` references
   `0190278..d101bc4`) and updates them to the new SHAs in a follow-up
   commit. Memory file `project_jh_cli.md` is updated similarly.

Known merge clusters (sampled, full map produced in Step 0.2):

- `626c5df` + `61aa7c8` (both bound `uv_build` version) → one `build:`
  commit.
- `ac8d346` + `fa06312` + `096159d` + `fe2ceea` (cyclopts switch + 3
  follow-up flag fixes) → one `refactor:` commit.
- `8bbe231` / `97c82b1` / `d101bc4` (post-DDD trio) → kept separate per
  D6.

### Step A — Create the GitHub repo

- Repo `github.com/yo61/jobhound`.
- Visibility: public (assumed to match `yo61/homebrew-tap`).
- Do not initialise with README/LICENSE/.gitignore — local repo already
  has commits.

### Step B — Baseline tag + push

After Step 0 completes:

```bash
git tag v0.1.0                                     # on rewritten HEAD
git remote add origin git@github.com:yo61/jobhound.git
git push -u origin main
git push origin v0.1.0
```

### Step C — Create the v0.1.0 GitHub Release

```bash
gh release create v0.1.0 \
  --title "v0.1.0" \
  --notes "Initial release. Baseline for release-please; subsequent versions are automated."
```

Gives release-please a clean "since this commit" boundary.

### Step D — PyPI Pending Publisher (parallel to A–C)

`pypi.org` → Account settings → Publishing → Add a new pending publisher:

| Field | Value |
|---|---|
| PyPI Project Name | `jobhound` |
| Owner | `yo61` |
| Repository name | `jobhound` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

The Pending Publisher means PyPI accepts the trust assertion before the
project exists. First successful publish creates the project.

### Step E — Repo settings

**Settings → General → Pull Requests:**
- ☐ Allow merge commits
- ☐ Allow squash merging
- ☑ Allow rebase merging
- ☑ Automatically delete head branches

**Settings → Environments → New environment:**
- Name: `pypi`
- Deployment branches: limit to `main`.
- No secrets (OIDC).

### Step F — First PR adds the workflow files

```bash
git switch -c chore/release-pipeline
# write the 6 new files (2 workflows + 4 configs) and 1 modification
# (.pre-commit-config.yaml gains the commit-msg hook entry)
git add .github/workflows/ci.yml .github/workflows/release.yml \
        release-please-config.json .release-please-manifest.json \
        commitlint.config.mjs CHANGELOG.md \
        .pre-commit-config.yaml
git commit -m "chore: add release pipeline (release-please + PyPI OIDC)"
git push -u origin chore/release-pipeline
gh pr create --title "chore: add release pipeline" --body "..."
```

The `chore:` type ensures release-please will not propose a version bump
when the workflows first activate. CI runs for the first time on this PR
and produces the status-check names that branch protection needs.

### Step G — Branch protection

After Step F's CI has run at least once:

**Settings → Branches → Add branch ruleset:**
- Target: `main`
- ☑ Restrict deletions
- ☑ Block force pushes
- ☑ Require a pull request before merging (0 reviewers)
- ☑ Require status checks to pass
  - Required: `check`, `commitlint`
  - ☑ Require branches to be up to date before merging
- ☑ Restrict direct pushes

This applies to release-please's own Release PRs too — they must pass CI
before merge.

### Step H — End-to-end verification

1. Open PR with `feat: smoke` (trivial no-op feature commit). Merge.
2. `release.yml` fires; release-please opens a Release PR proposing
   `v0.2.0` with a generated `CHANGELOG.md` entry.
3. Review + merge the Release PR. Tag `v0.2.0` is created, GH release
   published, `publish` job runs.
4. PyPI: confirm `jobhound` project created and `v0.2.0` listed.
5. Confirm `pip install jobhound==0.2.0` works from a clean venv.

If anything fails here it's much cheaper to debug than after Phase 2 is
built on top.

## Caveats

- **First publish creates the PyPI project.** If Step H fails partway,
  PyPI may already have claimed the `jobhound` name with no release. Fine
  — subsequent retries publish to the existing project.
- **PyPI has no delete-version.** Broken releases can only be *yanked*
  (hidden from default installers). The verification feat in Step H is a
  no-op precisely to avoid shipping anything broken.
- **`Release-As:` footer** is the escape hatch if a specific version is
  ever required (e.g., to deliberately bump to 1.0.0). Not part of the
  normal flow.
- **Step 0 rewrites history before there's a remote.** No shared-branch
  risk applies; this is the safest possible moment to do it.

## Follow-ups (out of this spec)

Captured in `~/.claude/projects/.../memory/project_jh_cli.md` under
"Backlog":

- Phase 2: Add `jobhound` as a formula in `yo61/homebrew-tap`. Depends on
  this spec landing and producing at least one tagged release.
- Phase 3: Add a structured-output command to `jh` (likely `jh export`
  emitting JSON) plus `jh show <slug>` for single-opportunity detail.
- Phase 4: Adapt `~/Documents/Projects/Job Hunting 2026-04/` scripts to
  consume `jh` via the Phase 3 export command, restoring the dashboard /
  digest / reminders / PDF outputs.
