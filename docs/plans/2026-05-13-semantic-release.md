# Semantic Release & PyPI Publishing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up an automated release pipeline for `jobhound` (release-please + PyPI Trusted Publishing) and bring all existing history up to Conventional Commits standard before the repo goes public.

**Architecture:** Two GitHub Actions workflows (CI gate + release pipeline) driven by Conventional Commits. release-please opens long-lived Release PRs that, when merged, tag the repo and trigger an OIDC PyPI publish. Branch protection enforces rebase-merge-only with CI checks required. Pre-public history is rewritten once to retroactively conform.

**Tech Stack:** GitHub Actions, `googleapis/release-please-action@v4`, `wagoid/commitlint-github-action@v6`, `pypa/gh-action-pypi-publish@release/v1` (OIDC), `compilerla/conventional-pre-commit` (prek), `uv build`.

**Reference spec:** [`docs/specs/2026-05-13-semantic-release-design.md`](../specs/2026-05-13-semantic-release-design.md). Read this before starting — the *why* lives there.

---

## Pre-flight

- **Repo state at start.** `main` at `52cc67f`, 50 commits, no remote, working tree clean. Per `memory/feedback_commit_on_main_no_remote.md`, commit on `main` directly until Step F (which switches to PR-only).
- **Who does what.** Tasks labelled **[user-driven]** require a human (interactive `git rebase`, GitHub/PyPI click-ops). Tasks labelled **[agent-driven]** can be executed by an LLM agent. The split matters because CLAUDE.md forbids the assistant from using `git rebase -i`, and click-ops can't be automated.
- **Safety net.** Task 2 tags `pre-conventional-history` before the rebase. Task 14 runs `actionlint` + `zizmor` before any workflow file leaves the local repo. End-to-end verification (Task 13) uses a deliberately trivial no-op `feat:` so a broken release ships nothing meaningful.
- **Rollback.** Up to (and including) Task 4, everything is local — `git reset --hard pre-conventional-history` is the rollback. From Task 4 onward, the GitHub repo exists and PyPI publishing becomes possible; rollback then means yanking a PyPI version and force-pushing the repo (acceptable while pre-1.0 and unused by downstream consumers).

## File structure

New files created by this plan:

```
.github/workflows/ci.yml                          # Lint+test on PR/push; commitlint on PR
.github/workflows/release.yml                     # release-please + OIDC PyPI publish
release-please-config.json                        # release-please configuration
.release-please-manifest.json                     # Pins current version (0.1.0)
commitlint.config.mjs                             # Conventional-Commits rules for the CI action
CHANGELOG.md                                      # Seed; release-please rewrites
docs/plans/2026-05-13-history-rewrite-map.md      # Per-commit rewrite plan, produced in Task 1
```

Modified files:

```
.pre-commit-config.yaml                           # Add commit-msg hook
docs/plans/2026-05-11-post-refactor-housekeeping.md  # Update stale SHA references (Task 3)
~/.claude/projects/.../memory/project_jh_cli.md   # Update stale SHA references (Task 3)
```

---

## Task 1 [agent-driven]: Produce the commit-rewrite map

**Goal:** Write the file that drives Task 2's interactive rebase. One row per existing commit (50 rows), classified by Conventional type, with squash clusters identified.

**Files:**
- Create: `docs/plans/2026-05-13-history-rewrite-map.md`

- [ ] **Step 1: Snapshot the existing log for the appendix**

```bash
git log --reverse --format='%h %s' main > /tmp/jh-history.txt
wc -l /tmp/jh-history.txt
```

Expected: 50 lines. If different, stop — the spec assumed 50; deviation means commits landed after the spec was written and the map below is stale.

- [ ] **Step 2: Write the rewrite map file**

Create `docs/plans/2026-05-13-history-rewrite-map.md` with the exact content below. This is the proposed map; the user reviews and edits it before Task 2 executes.

````markdown
# History Rewrite Map — 50 → ~47 commits

Generated 2026-05-13 from `git log --reverse main` at HEAD `52cc67f`.

**Legend:**
- **REWORD** — keep commit, change subject only.
- **SQUASH-PREV** — merge into the immediately previous commit. In `git rebase -i`, mark the line `fixup` (drop the original message) or `squash` (combine messages).
- **KEEP** — leave the subject as-is (already conventional or close enough that rewrite adds no value).

**Rebase-todo correspondence:**
- REWORD → `reword <sha>`
- SQUASH-PREV → `fixup <sha>` (drops the old subject in favor of the previous commit's; use `squash` if you want the old body preserved as additional paragraphs)

| # | Old SHA | Action | New subject |
|---|---------|--------|-------------|
| 1 | `365be4b` | REWORD | `chore: initialize jobhound package` |
| 2 | `626c5df` | REWORD | `docs: add jh-cli design spec and implementation plan` |
| 3 | `61aa7c8` | REWORD | `build: bound uv_build version in build-system requires` |
| 4 | `0fa8358` | REWORD | `build: add dev Taskfile and pre-commit hooks` |
| 5 | `2b855f2` | REWORD | `test: add smoke test for project layout` |
| 6 | `ae54bc5` | REWORD | `feat: add Config loader with XDG-strict paths` |
| 7 | `6c5af00` | REWORD | `feat: add Paths dataclass` |
| 8 | `12175dc` | REWORD | `chore: remove pytest pythonpath workaround` |
| 9 | `f3a4b20` | REWORD | `feat: add Opportunity dataclass and adopt xdg-base-dirs` |
| 10 | `e922bdc` | REWORD | `feat: add meta.toml read/write/validate` |
| 11 | `54e5438` | REWORD | `feat: add slug resolver` |
| 12 | `b537637` | REWORD | `feat: add auto-commit helper` |
| 13 | `89c4303` | REWORD | `feat: add prompt helpers and date parser` |
| 14 | `b614d34` | REWORD | `feat: add typer app skeleton and shared test fixture` |
| 15 | `9576541` | REWORD | `feat: add jh new command` |
| 16 | `3c6080b` | REWORD | `feat: add jh apply command and transitions module` |
| 17 | `70d957e` | REWORD | `chore: revert chflags workaround (repo moved out of iCloud Documents)` |
| 18 | `37b924c` | REWORD | `feat: add jh log command` |
| 19 | `ac8d346` | REWORD | `refactor: switch CLI framework from typer to cyclopts` |
| 20 | `fa06312` | SQUASH-PREV | (merged into #19) |
| 21 | `096159d` | SQUASH-PREV | (merged into #19) |
| 22 | `fe2ceea` | SQUASH-PREV | (merged into #19) |
| 23 | `ed3bca9` | REWORD | `docs: convert remaining plan snippets from typer to cyclopts` |
| 24 | `630e7c6` | REWORD | `feat: add jh withdraw, ghost, accept, decline commands` |
| 25 | `04e0cac` | REWORD | `feat: add jh note, priority, tag commands` |
| 26 | `5f6fe9c` | REWORD | `feat: add jh link and contact commands` |
| 27 | `f74c9b7` | REWORD | `feat: add jh list command` |
| 28 | `3d68698` | REWORD | `feat: add jh edit command with validation loop` |
| 29 | `5a4b7a0` | REWORD | `feat: add jh archive, delete, sync commands` |
| 30 | `a3a78d6` | REWORD | `docs: add DDD refactor plan` |
| 31 | `0190278` | REWORD | `refactor: add OpportunityRepository` |
| 32 | `d44baab` | REWORD | `refactor: migrate apply/note/tag/priority/link/contact to OpportunityRepository` |
| 33 | `0d6f1ae` | REWORD | `refactor: migrate log and terminal-status verbs to OpportunityRepository` |
| 34 | `f27450e` | REWORD | `refactor: migrate new/archive/delete/edit/list to OpportunityRepository` |
| 35 | `903f13f` | REWORD | `refactor: push state-transition behaviour onto Opportunity entity` |
| 36 | `33db122` | REWORD | `refactor: push field-shaped behaviour onto Opportunity entity` |
| 37 | `5be5afa` | REWORD | `refactor: add Status enum with transition tables` |
| 38 | `9c74e82` | REWORD | `refactor: use Status enum for Opportunity.status` |
| 39 | `8f4c8d8` | REWORD | `refactor: add Priority enum` |
| 40 | `a46716d` | REWORD | `refactor: add Slug value object` |
| 41 | `c28afe1` | REWORD | `refactor: add Contact value object` |
| 42 | `8bbe231` | REWORD | `refactor: drop dead target_status parameter from run_transition` |
| 43 | `97c82b1` | REWORD | `refactor: remove unused Opportunity.path field` |
| 44 | `d101bc4` | REWORD | `test: assert date fields directly instead of via isoformat()` |
| 45 | `b6a5263` | REWORD | `docs: seed quality/criteria.md from DDD refactor review findings` |
| 46 | `5c94da4` | REWORD | `docs: log DDD refactor decision` |
| 47 | `39d9b71` | REWORD | `fix: drop None values from opportunity links at parse time` |
| 48 | `0af779b` | REWORD | `chore: add one-shot yaml-to-toml migration script` |
| 49 | `cc16925` | REWORD | `docs: add post-refactor housekeeping plan` |
| 50 | `52cc67f` | REWORD | `docs: log YAML-to-TOML migration decision` |

**Result:** 50 → 47 commits (3 squashes in the cyclopts cluster).

**Bodies and trailers:** `git rebase -i` preserves commit bodies and trailers (e.g., the existing `Co-Authored-By:` lines on commits 19-22, 31-44) untouched when you use `reword`. With `fixup` the previous commit's body is kept and the squashed commits' subjects + bodies are discarded; with `squash` you get to merge bodies interactively. For the cyclopts cluster the recommendation is `fixup` — the follow-up commits' bodies describe transient iterations, not durable rationale.

**Editor template:** the resulting `git rebase -i --root` todo list will be:

```
reword 365be4b chore: initialize jobhound package
reword 626c5df docs: add jh-cli design spec and implementation plan
reword 61aa7c8 build: bound uv_build version in build-system requires
... (lines 4–18 all reword) ...
reword ac8d346 refactor: switch CLI framework from typer to cyclopts
fixup  fa06312
fixup  096159d
fixup  fe2ceea
reword ed3bca9 docs: convert remaining plan snippets from typer to cyclopts
... (lines 24–50 all reword) ...
```

When `reword` opens the editor, replace the entire subject line with the "New subject" from the table. Save and close. The rebase continues.
````

- [ ] **Step 3: Pause for user review of the map**

Before executing Task 2, the user reviews and edits this map. Treat editorial disagreements as the point of the exercise — the map is *proposed*, not authoritative.

Output for the human reviewer:
```
Rewrite map written to docs/plans/2026-05-13-history-rewrite-map.md.
Please review. To approve: say "map approved" or edit the file and say "use the edited map."
```

Stop here. Do not proceed to Task 2 until the user explicitly approves.

---

## Task 2 [user-driven]: Execute the history rewrite

**Goal:** Apply the approved map. After this task, `main` has ~47 conventional commits.

**Files:** modifies `.git` (no source files).

- [ ] **Step 1: Verify the working tree is clean and the map is in place**

Run (agent does this):
```bash
git status --porcelain
test -f docs/plans/2026-05-13-history-rewrite-map.md && echo "map present" || echo "map missing"
git log --oneline | wc -l
```

Expected: empty output from `git status`; "map present"; "50".

- [ ] **Step 2: Tag the pre-conventional safety net**

Run (agent does this):
```bash
git tag pre-conventional-history
git tag -l pre-conventional-history
```

Expected: `pre-conventional-history` listed. **Do not push this tag** — local-only safety net.

- [ ] **Step 3: User executes the interactive rebase**

The user runs this themselves (assistant cannot drive `-i`):

```bash
git rebase -i --root
```

When the editor opens the todo list, the user converts each `pick` line to either `reword` or `fixup` per the map, then saves. For each `reword` the editor reopens with the original message — the user replaces the subject line with the new subject from the map and saves. The cyclopts cluster (commits 20-22 in the map) is marked `fixup`; the editor does not reopen for those.

If the rebase pauses mid-way (e.g., merge conflict), `git rebase --abort` returns to `pre-conventional-history` state.

- [ ] **Step 4: Verify subjects conform to Conventional Commits**

Run (agent does this):
```bash
git log --format='%s' | grep -vE '^(feat|fix|chore|docs|refactor|test|build|ci|perf|style|revert)(\(.+\))?!?: .+'
```

Expected: empty output. Any lines printed are non-conforming subjects that the user must fix via `git rebase -i --root` again (targeting just the offending commit with `reword`).

- [ ] **Step 5: Verify commit count is as planned**

```bash
git log --oneline | wc -l
```

Expected: 47. If different, the map was followed incorrectly. Investigate before continuing.

- [ ] **Step 6: Verify the code still works**

```bash
task dev:check
```

Expected: all 142 tests pass; ruff clean; ty clean. If anything fails, the rebase introduced semantic change (impossible if only `reword`/`fixup` were used) — investigate before continuing.

- [ ] **Step 7: Confirm the safety net still exists**

```bash
git rev-parse pre-conventional-history
git rev-parse HEAD
```

Expected: two different SHAs. `pre-conventional-history` points at the original `52cc67f`; `HEAD` is the new rewritten tip.

---

## Task 3 [agent-driven]: Update stale SHA references

**Goal:** The rewrite invalidated SHA references inside `docs/` and the memory file. Fix them so the post-refactor housekeeping plan and project memory match the new history.

**Files:**
- Modify: `docs/plans/2026-05-11-post-refactor-housekeeping.md`
- Modify: `~/.claude/projects/-Users-robin-code-github-yo61-jobhound/memory/project_jh_cli.md`

- [ ] **Step 1: Find all stale SHA references**

```bash
git grep -E '\b[0-9a-f]{7,40}\b' -- 'docs/' | grep -vE '^docs/plans/2026-05-13-history-rewrite-map\.md:'
```

The rewrite map file itself contains old SHAs by design — exclude it. Every other hit is a candidate for update.

Also check the memory file:

```bash
grep -E '\b[0-9a-f]{7,40}\b' /Users/robin/.claude/projects/-Users-robin-code-github-yo61-jobhound/memory/project_jh_cli.md
```

- [ ] **Step 2: Build the old→new SHA mapping**

For each stale SHA, find its new equivalent by matching subject lines:

```bash
# For each old SHA in step 1's output:
OLD_SUBJECT=$(git show --no-patch --format='%s' <OLD_SHA> 2>/dev/null || \
              grep -A1 "<OLD_SHA>" docs/plans/2026-05-13-history-rewrite-map.md | head -2)
# Find the new commit whose subject contains the topic
git log --format='%h %s' | grep -i "<topic from OLD_SUBJECT>"
```

Notable known-stale references in `docs/plans/2026-05-11-post-refactor-housekeeping.md`: `0190278..d101bc4` (the DDD refactor range), `8bbe231`, `97c82b1`, `d101bc4`. Map each to the new SHA.

- [ ] **Step 3: Edit `docs/plans/2026-05-11-post-refactor-housekeeping.md`**

Replace each stale SHA with the new SHA. Preserve range notation (`..`) where used.

- [ ] **Step 4: Edit the memory file**

The memory file mentions specific SHAs in the same DDD-refactor context. Update them.

- [ ] **Step 5: Commit the doc updates**

```bash
git add docs/plans/2026-05-11-post-refactor-housekeeping.md
git commit -m "docs: update SHA references after history rewrite"
```

(The memory file is outside the repo; the edit in Step 4 is sufficient — no commit needed.)

- [ ] **Step 6: Verify**

```bash
git log --oneline | wc -l        # expect 48 (47 + this docs commit)
git log -1 --format='%s'         # expect "docs: update SHA references after history rewrite"
task dev:check                   # expect pass
```

---

## Task 4 [user-driven + agent-driven]: Baseline tag, create GitHub repo, push

**Goal:** Push the rewritten history to the new public repo with v0.1.0 as the baseline release tag.

**Files:** none.

- [ ] **Step 1 [agent]: Tag v0.1.0 on the current HEAD**

```bash
git tag v0.1.0
git tag -l v0.1.0
```

Expected: `v0.1.0` listed.

- [ ] **Step 2 [user]: Create the GitHub repository**

In a browser at `github.com`:
- Click "New repository"
- Owner: `yo61`
- Name: `jobhound`
- Description: `Action-based CLI for tracking a job hunt`
- Visibility: **Public**
- **Do NOT** initialise with README, .gitignore, or LICENSE — local repo already has these.

Confirm creation by visiting `github.com/yo61/jobhound`.

- [ ] **Step 3 [agent]: Add the remote and push**

```bash
git remote add origin git@github.com:yo61/jobhound.git
git push -u origin main
git push origin v0.1.0
```

Expected: both pushes succeed. `git remote -v` shows `origin` pointing at the new repo.

- [ ] **Step 4 [user or agent]: Create the v0.1.0 GitHub Release**

If `gh` CLI is authenticated:

```bash
gh release create v0.1.0 \
  --title "v0.1.0" \
  --notes "Initial release. Baseline for release-please; subsequent versions are automated."
```

Otherwise via the web UI: Releases → "Draft a new release" → choose tag `v0.1.0` → fill in title and notes → "Publish release."

- [ ] **Step 5: Verify**

```bash
gh release view v0.1.0
```

Expected: shows the release with the title and notes from Step 4.

---

## Task 5 [user-driven]: Configure PyPI Pending Publisher

**Goal:** Pre-authorise the GitHub Actions workflow to publish a new `jobhound` project on PyPI via OIDC. Can be done at any point before Task 13.

**Files:** none.

- [ ] **Step 1: Sign in to PyPI**

`pypi.org` → log in to the account that will own `jobhound`.

- [ ] **Step 2: Add a new pending publisher**

Account → Publishing → "Add a new pending publisher". Fill in:

| Field | Value |
|---|---|
| PyPI Project Name | `jobhound` |
| Owner | `yo61` |
| Repository name | `jobhound` |
| Workflow filename | `release.yml` |
| Environment name | `pypi` |

Click "Add". The publisher appears in the "Pending publishers" list.

- [ ] **Step 3: Verify**

The Pending publishers page shows one row for `jobhound` with the values above. No `jobhound` project exists on PyPI yet — that's expected; Task 13 will create it on first publish.

---

## Task 6 [agent-driven]: Look up current action SHAs

**Goal:** Resolve the latest commit SHA for each GitHub Action used in the workflows. Per CLAUDE.md, pin actions to SHAs with version comments.

**Files:** none yet (Task 7 uses the SHAs collected here).

- [ ] **Step 1: Resolve each action's SHA**

For each action below, run the lookup and record the resulting SHA + the human-readable major version:

```bash
git ls-remote https://github.com/actions/checkout            refs/tags/v4 | awk '{print $1}'
git ls-remote https://github.com/astral-sh/setup-uv          refs/tags/v6 | awk '{print $1}'
git ls-remote https://github.com/arduino/setup-task          refs/tags/v2 | awk '{print $1}'
git ls-remote https://github.com/wagoid/commitlint-github-action refs/tags/v6 | awk '{print $1}'
git ls-remote https://github.com/googleapis/release-please-action refs/tags/v4 | awk '{print $1}'
git ls-remote https://github.com/pypa/gh-action-pypi-publish refs/heads/release/v1 | awk '{print $1}'
```

Notes:
- `setup-uv@v6` is the current major as of 2026; verify the lookup succeeds. If it fails, fall back to `v5` and update the version comment.
- `pypa/gh-action-pypi-publish` does not tag with `vN.M.K`; its stable branch is `release/v1`. Pin to whatever commit `release/v1` currently points at.

Record the six SHAs. They'll be used verbatim in Task 7.

- [ ] **Step 2: Optionally verify against the live tag**

For each action, browse to `https://github.com/<owner>/<repo>/commits/<tag>` and confirm the top commit's SHA matches what `ls-remote` returned. (Useful sanity check; not strictly required.)

---

## Task 7 [agent-driven]: Write the release-pipeline files on a feature branch

**Goal:** Create all six new files and modify `.pre-commit-config.yaml`, on a `chore/release-pipeline` branch, ready for PR.

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`
- Create: `release-please-config.json`
- Create: `.release-please-manifest.json`
- Create: `commitlint.config.mjs`
- Create: `CHANGELOG.md`
- Modify: `.pre-commit-config.yaml`

- [ ] **Step 1: Create the feature branch**

```bash
git switch -c chore/release-pipeline
git status --short
git branch --show-current
```

Expected: empty status; current branch = `chore/release-pipeline`.

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

Substitute `<SHA-CHECKOUT>`, `<SHA-SETUP-UV>`, `<SHA-SETUP-TASK>`, `<SHA-COMMITLINT>` with the values from Task 6.

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
      - uses: actions/checkout@<SHA-CHECKOUT>  # v4
      - uses: astral-sh/setup-uv@<SHA-SETUP-UV>  # v6
        with:
          enable-cache: true
          python-version: "3.13"
      - uses: arduino/setup-task@<SHA-SETUP-TASK>  # v2
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
      - uses: actions/checkout@<SHA-CHECKOUT>  # v4
        with:
          fetch-depth: 0
      - uses: wagoid/commitlint-github-action@<SHA-COMMITLINT>  # v6
        with:
          configFile: commitlint.config.mjs
```

- [ ] **Step 3: Write `.github/workflows/release.yml`**

Substitute `<SHA-CHECKOUT>`, `<SHA-RELEASE-PLEASE>`, `<SHA-SETUP-UV>`, `<SHA-PYPI-PUBLISH>` from Task 6.

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
      - uses: googleapis/release-please-action@<SHA-RELEASE-PLEASE>  # v4
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
      url: https://pypi.org/p/jobhound
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@<SHA-CHECKOUT>  # v4
        with:
          ref: ${{ needs.release-please.outputs.tag_name }}
      - uses: astral-sh/setup-uv@<SHA-SETUP-UV>  # v6
        with:
          python-version: "3.13"
      - run: uv build
      - uses: pypa/gh-action-pypi-publish@<SHA-PYPI-PUBLISH>  # release/v1
```

- [ ] **Step 4: Write `release-please-config.json`**

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

- [ ] **Step 5: Write `.release-please-manifest.json`**

```json
{ ".": "0.1.0" }
```

- [ ] **Step 6: Write `commitlint.config.mjs`**

```js
export default { extends: ['@commitlint/config-conventional'] };
```

- [ ] **Step 7: Write `CHANGELOG.md` seed**

```markdown
# Changelog
```

- [ ] **Step 8: Modify `.pre-commit-config.yaml` — add the commit-msg hook**

Read the existing file first:

```bash
cat .pre-commit-config.yaml
```

Append (do not replace) the following block at the end of the existing `repos:` list. If the file doesn't have a `repos:` key (it should — prek/pre-commit uses this), stop and inspect.

Look up the current stable tag of `compilerla/conventional-pre-commit`:

```bash
git ls-remote https://github.com/compilerla/conventional-pre-commit refs/tags/'v*' | tail -1
```

Use the latest `v3.x.x` tag in the `rev:` field below. (As of 2026-05 the line is around `v3.6.x`; use whatever the lookup returns.)

```yaml
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v3.x.x        # replace with the actual tag from the lookup above
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
```

- [ ] **Step 9: Verify file syntax**

```bash
# YAML workflows
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
python -c "import yaml; yaml.safe_load(open('.pre-commit-config.yaml'))"

# JSON config files
python -m json.tool release-please-config.json > /dev/null
python -m json.tool .release-please-manifest.json > /dev/null
```

Expected: all five commands exit 0 with no output. Any failure means a typo in the corresponding file.

---

## Task 8 [agent-driven]: Lint workflows with actionlint + zizmor

**Goal:** Run the structure-aware linters from CLAUDE.md before pushing. Catches workflow bugs locally rather than after a wasted CI round-trip.

**Files:** none modified.

- [ ] **Step 1: Run actionlint**

```bash
actionlint .github/workflows/ci.yml .github/workflows/release.yml
```

Expected: no output (exit 0). Any output is a lint error to fix.

If `actionlint` is not installed: `brew install actionlint`.

- [ ] **Step 2: Run zizmor security audit**

```bash
zizmor .github/workflows/
```

Expected: no high-severity findings. If zizmor flags `unpinned-uses`, double-check Task 7 substituted SHAs everywhere. Other warnings (e.g., `excessive-permissions`) are usually false positives for this minimal pipeline — review each and either fix or document why it's acceptable.

If `zizmor` is not installed: `brew install zizmor`.

- [ ] **Step 3: Run all prek hooks against all files (smoke test)**

```bash
prek run --all-files
```

Expected: all hooks pass. The new `conventional-pre-commit` entry won't fire here (it's commit-msg stage, not pre-commit stage). The existing hooks should all be green.

---

## Task 9 [agent-driven]: Install the new prek hook stage and verify

**Goal:** Ensure local commits will trigger the conventional-pre-commit validation.

**Files:** modifies `.git/hooks/commit-msg`.

- [ ] **Step 1: Install both hook stages**

```bash
prek install --hook-type pre-commit --hook-type commit-msg
```

Expected: confirmation that both hooks are installed.

- [ ] **Step 2: Smoke-test the hook on a known-bad message**

```bash
echo "this is not conventional" > /tmp/jh-bad-msg.txt
prek run conventional-pre-commit --commit-msg-filename /tmp/jh-bad-msg.txt
echo "exit code: $?"
```

Expected: hook fails (exit code nonzero). Output mentions the message doesn't match Conventional Commits.

- [ ] **Step 3: Smoke-test the hook on a known-good message**

```bash
echo "chore: smoke test for hook" > /tmp/jh-good-msg.txt
prek run conventional-pre-commit --commit-msg-filename /tmp/jh-good-msg.txt
echo "exit code: $?"
```

Expected: hook passes (exit code 0).

- [ ] **Step 4: Cleanup**

```bash
rm /tmp/jh-bad-msg.txt /tmp/jh-good-msg.txt
```

---

## Task 10 [user-driven]: Configure GitHub repo settings

**Goal:** Force rebase-merge-only and create the `pypi` Environment that the release workflow expects. Can be done in parallel with Task 7-9.

**Files:** none in repo.

- [ ] **Step 1: Merge strategy**

`github.com/yo61/jobhound` → Settings → General → scroll to "Pull Requests":

- ☐ Allow merge commits (uncheck)
- ☐ Allow squash merging (uncheck)
- ☑ Allow rebase merging (check)
- ☑ Automatically delete head branches (check)

Click "Save" if prompted; some sections save automatically.

- [ ] **Step 2: Create the `pypi` Environment**

Settings → Environments → "New environment". Name: `pypi`.

In the environment config page:
- Deployment branches and tags → "Selected branches and tags" → "Add deployment branch or tag rule" → branch name pattern: `main`.
- Do **not** add any secrets (OIDC handles auth).
- Save.

- [ ] **Step 3: Verify**

`gh api repos/yo61/jobhound/environments` should list `pypi`.
`gh api repos/yo61/jobhound | jq '.allow_rebase_merge, .allow_merge_commit, .allow_squash_merge'` should return `true`, `false`, `false`.

---

## Task 11 [agent-driven]: Commit the pipeline files and open the first PR

**Goal:** Submit the release pipeline as the first PR through the new flow. CI runs for the first time here, producing the status-check names that branch protection needs.

**Files:** modifies nothing further; commits Task 7's outputs.

- [ ] **Step 1: Stage and commit**

```bash
git add .github/workflows/ci.yml .github/workflows/release.yml \
        release-please-config.json .release-please-manifest.json \
        commitlint.config.mjs CHANGELOG.md \
        .pre-commit-config.yaml
git status --short
```

Expected: 7 files staged (`A` for the new files, `M` for `.pre-commit-config.yaml`).

```bash
git commit -m "chore: add release pipeline (release-please + PyPI OIDC)"
```

The `commit-msg` hook installed in Task 9 validates this message. `chore:` is conventional, so it passes.

- [ ] **Step 2: Push the branch**

```bash
git push -u origin chore/release-pipeline
```

- [ ] **Step 3: Open the PR**

```bash
gh pr create \
  --title "chore: add release pipeline (release-please + PyPI OIDC)" \
  --body "$(cat <<'EOF'
Implements the design at docs/specs/2026-05-13-semantic-release-design.md.

## Summary
- CI workflow (lint, format-check, typecheck, tests on PR + push to main)
- Commit-message validation (commitlint on every commit in the PR)
- Release workflow (release-please + OIDC PyPI publish)
- Local commit-msg hook (conventional-pre-commit)

## Test plan
- [ ] CI green on this PR
- [ ] After merge: release.yml fires, opens no Release PR (this is a chore: commit)
- [ ] Subsequent feat: smoke test (separate PR) opens Release PR for v0.2.0
EOF
)"
```

- [ ] **Step 4: Wait for CI and observe results**

```bash
gh pr checks --watch
```

Expected: both `check` and `commitlint` jobs go green. The `commitlint` job runs because this is a `pull_request` event; the `check` job runs both as `pull_request` (now) and again later when this PR's commits land on `main`.

If `commitlint` fails: this is unexpected because the commit message is conventional. Inspect the action's logs — most likely a config-file path mismatch in `ci.yml`.

If `check` fails: same as any other CI failure; fix locally, push, re-watch.

- [ ] **Step 5: Capture the status-check names for Task 12**

```bash
gh pr checks --json name,state
```

Record the exact `name` values. Expected: `check` and `commitlint`. These are the names Task 12 uses in branch protection.

---

## Task 12 [user-driven]: Configure branch protection on `main`

**Goal:** Block direct pushes to `main` and require both CI jobs to pass before any PR can merge.

**Files:** none in repo.

- [ ] **Step 1: Add the ruleset**

`github.com/yo61/jobhound` → Settings → Rules → Rulesets → "New branch ruleset".

- **Name:** `main protection`
- **Enforcement status:** Active
- **Target branches:** Include default branch (`main`)
- **Restrict deletions:** ☑
- **Block force pushes:** ☑
- **Require a pull request before merging:** ☑
  - Required approvals: `0` (solo project)
  - ☑ Dismiss stale pull request approvals when new commits are pushed (defensive)
  - ☑ Require approval of the most recent reviewable push (defensive; harmless at 0 reviewers)
- **Require status checks to pass:** ☑
  - ☑ Require branches to be up to date before merging
  - Add status checks: search for and add `check` and `commitlint` (from Task 11.5).
- **Block force pushes:** ☑ (likely auto-checked from Step 2)

Save the ruleset.

- [ ] **Step 2: Verify**

```bash
gh api repos/yo61/jobhound/rules/branches/main
```

Expected: lists rules including `required_status_checks` with both check names, and `pull_request` with required reviewers count of 0.

---

## Task 13 [user-driven + agent-driven]: End-to-end verification

**Goal:** Prove the pipeline works: a `feat:` commit produces a Release PR that, when merged, ships to PyPI.

**Files:** transient — a no-op `feat:` commit; reverted after verification.

- [ ] **Step 1 [user]: Merge the Task 11 PR**

In the GitHub UI (or `gh pr merge --rebase --delete-branch`). Use rebase-merge (it's the only option, per Task 10).

- [ ] **Step 2 [agent]: Verify the release workflow ran but produced no Release PR**

```bash
gh run list --workflow=release.yml --limit 5
```

Expected: the latest run completed successfully and the `release-please` job's `release_created` output is `false`. No Release PR opened (because the merged commit was `chore:`, which doesn't bump versions).

```bash
gh pr list --state open --search 'release-please'
```

Expected: empty.

- [ ] **Step 3 [agent]: Create the smoke-test branch with a no-op feat: commit**

```bash
git switch main
git pull --rebase
git switch -c feat/smoke-release-pipeline

# Add a trivial no-op feature marker file
echo "release pipeline verification 2026-05-13" > docs/.release-smoke
git add docs/.release-smoke
git commit -m "feat: verify release pipeline end-to-end"
git push -u origin feat/smoke-release-pipeline
gh pr create \
  --title "feat: verify release pipeline end-to-end" \
  --body "Smoke test for the release pipeline; this is a no-op marker file. Yank v0.2.0 from PyPI after verification."
```

- [ ] **Step 4 [agent]: Wait for CI green, then merge**

```bash
gh pr checks --watch
```

Expected: both jobs green.

```bash
gh pr merge --rebase --delete-branch
```

- [ ] **Step 5 [agent]: Wait for the Release PR to appear**

```bash
sleep 30
gh pr list --search 'release-please' --json number,title,headRefName
```

Expected: one PR titled something like `chore(main): release 0.2.0` from a `release-please--` branch.

If no Release PR after 2 minutes: inspect `gh run list --workflow=release.yml --limit 1` for failures. Common cause: the `release-please-action` couldn't write to the repo because branch protection denied it. The required-status-checks rule should allow the action's PR-creation operation (it doesn't push to `main` directly; it opens a PR like any other contributor).

- [ ] **Step 6 [user]: Review and merge the Release PR**

In the GitHub UI, review the auto-generated `CHANGELOG.md` entry and the bump from `0.1.0` → `0.2.0` in `pyproject.toml`. Merge with rebase.

- [ ] **Step 7 [agent]: Verify the publish job ran and PyPI received the release**

```bash
RUN_ID=$(gh run list --workflow=release.yml --limit 1 --json databaseId --jq '.[0].databaseId')
gh run view "$RUN_ID"
gh run view "$RUN_ID" --log-failed 2>/dev/null || echo "no failures"
```

Expected: `gh run view` shows both `release-please` and `publish` jobs completed successfully. `publish` ran because `release_created` was `true`. If you want the full success log, drop `--log-failed`.

```bash
curl -s https://pypi.org/pypi/jobhound/json | python -m json.tool | head -20
```

Expected: the JSON shows version `0.2.0` (and possibly `0.1.0` if also published, though it shouldn't have been).

- [ ] **Step 8 [agent]: Verify installability from a clean venv**

```bash
mkdir -p /tmp/jh-pypi-verify && cd /tmp/jh-pypi-verify
uv venv
uv pip install jobhound==0.2.0
.venv/bin/jh --version
cd - && rm -rf /tmp/jh-pypi-verify
```

Expected: `jh --version` prints `0.2.0`.

- [ ] **Step 9 [user]: Yank the smoke release from PyPI (it shipped a marker file, not a real change)**

`pypi.org` → log in → manage `jobhound` → release `0.2.0` → "Yank". PyPI hides it from default installers; existing pins continue to work.

- [ ] **Step 10 [agent]: Remove the smoke marker file**

```bash
git switch -c chore/remove-release-smoke main
git pull --rebase origin main   # get the Release PR's commits
git rm docs/.release-smoke
git commit -m "chore: remove release pipeline smoke marker"
git push -u origin chore/remove-release-smoke
gh pr create --title "chore: remove release pipeline smoke marker" \
             --body "Cleanup after the end-to-end verification."
gh pr checks --watch
gh pr merge --rebase --delete-branch
```

This is a `chore:` so it doesn't trigger another release. The smoke artefact is gone; the pipeline is verified.

---

## Done definition

The implementation is complete when all of these are true:

1. `git log --format='%s' | grep -vE '^(feat|fix|chore|docs|refactor|test|build|ci|perf|style|revert)(\(.+\))?!?: .+'` returns empty (all commits conventional).
2. `gh api repos/yo61/jobhound` returns `"allow_rebase_merge": true, "allow_merge_commit": false, "allow_squash_merge": false`.
3. `gh api repos/yo61/jobhound/rules/branches/main` lists `check` and `commitlint` as required status checks.
4. `pypi.org/project/jobhound/` exists with at least one release.
5. `uv pip install jobhound` from a clean venv works and `jh --version` runs.
6. Local: `prek run conventional-pre-commit --commit-msg-filename <bad-msg>` rejects non-conventional messages.

## Follow-ups out of this plan

Tracked in `~/.claude/projects/.../memory/project_jh_cli.md`:

- Phase 2: add `jobhound` formula to `yo61/homebrew-tap` (requires this plan's done state).
- Phase 3: add `jh export` (JSON output) and `jh show <slug>` commands.
- Phase 4: adapt `~/Documents/Projects/Job Hunting 2026-04/` scripts to consume `jh` via the Phase 3 commands.
