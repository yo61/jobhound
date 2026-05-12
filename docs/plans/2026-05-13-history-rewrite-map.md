# History Rewrite Map — 53 → 51 commits

Generated 2026-05-13 from `git log --reverse main`.

Note on commit count drift:
- The plan body assumed 50 commits.
- Two more landed before execution started: `20d6d0a` (the spec) and
  `5aa53ad` (the plan itself) — both clearly `docs:`. Appended as rows
  51 and 52.
- One more landed when this map was committed: `443bba9` (the map +
  plan-count alignment commit). Appended as row 53.

Row 53 references this very commit. The map commit was amended in place
once row 53 was added so the artifact remains self-referential without
introducing yet another commit-and-row cycle.

User-requested adjustment 2026-05-13: row 9 (`f3a4b20`) is split into two
commits (action `EDIT`) — see "Splitting f3a4b20" section below.

**Legend:**
- **REWORD** — keep commit, change subject only.
- **SQUASH-PREV** — merge into the immediately previous commit. In `git rebase -i`, mark the line `fixup` (drop the original message) or `squash` (combine messages).
- **EDIT** — pause the rebase on this commit; split into two or more commits by hand, then `git rebase --continue`.
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
| 9 | `f3a4b20` | EDIT (split) | → 9a `refactor: switch XDG resolution to xdg-base-dirs library`<br>→ 9b `feat: add Opportunity dataclass` |
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
| 51 | `20d6d0a` | REWORD | `docs: add semantic release & PyPI publishing design spec` |
| 52 | `5aa53ad` | REWORD | `docs: add semantic release implementation plan` |
| 53 | `443bba9`† | REWORD | `docs: add history rewrite map and align plan commit counts` |

† The SHA shown for row 53 is the pre-amend value. Adding row 53 amended the
map commit, changing its SHA. During rebase, this row is whatever commit `main`
points at — match by subject, not SHA.

**Result:** 53 → 51 commits (3 squashes in the cyclopts cluster, plus 1 split of `f3a4b20`).

## Splitting `f3a4b20`

The original commit changes 6 files for two unrelated reasons:

| File | Belongs to commit 9a (XDG refactor) | Belongs to commit 9b (Opportunity) |
|---|:-:|:-:|
| `pyproject.toml` (adds `xdg-base-dirs>=6`) | ✓ | |
| `uv.lock` (lockfile update for new dep) | ✓ | |
| `src/jobhound/config.py` (removes 27 lines of inline XDG helpers; imports from `xdg_base_dirs`) | ✓ | |
| `src/jobhound/paths.py` (imports `xdg_cache_home`/`xdg_state_home` from library) | ✓ | |
| `src/jobhound/opportunities.py` (new file, 97 lines) | | ✓ |
| `tests/test_opportunities.py` (new file, 88 lines) | | ✓ |

The two splits are independent at the file level — no file straddles the boundary.

**How to perform the split during rebase.** When `git rebase -i` reaches the
`edit` line for `f3a4b20` it pauses with HEAD pointing at that commit. Then:

```bash
# Un-commit the changes (working tree keeps them)
git reset HEAD~

# Commit A: the XDG refactor
git add pyproject.toml uv.lock src/jobhound/config.py src/jobhound/paths.py
git commit -m "refactor: switch XDG resolution to xdg-base-dirs library"

# Commit B: the Opportunity feature
git add src/jobhound/opportunities.py tests/test_opportunities.py
git commit -m "feat: add Opportunity dataclass"

# Verify nothing was left behind
git status                 # expect: nothing to commit, working tree clean

# Resume the rebase
git rebase --continue
```

The commit-msg hook (installed in Plan Task 9) is not yet active during
Plan Task 2, so the two new messages do not need pre-validation; the
post-rebase regex check in Plan Task 2 Step 4 catches malformed subjects.

**Bodies and trailers:** `git rebase -i` preserves commit bodies and trailers (e.g., the existing `Co-Authored-By:` lines on commits 19-22, 31-44) untouched when you use `reword`. With `fixup` the previous commit's body is kept and the squashed commits' subjects + bodies are discarded; with `squash` you get to merge bodies interactively. For the cyclopts cluster the recommendation is `fixup` — the follow-up commits' bodies describe transient iterations, not durable rationale.

**Editor template:** the resulting `git rebase -i --root` todo list will be:

```
reword 365be4b chore: initialize jobhound package
... (lines 2–8 all reword) ...
edit   f3a4b20 (split into refactor: switch XDG resolution... + feat: add Opportunity...)
... (lines 10–18 all reword) ...
reword ac8d346 refactor: switch CLI framework from typer to cyclopts
fixup  fa06312
fixup  096159d
fixup  fe2ceea
reword ed3bca9 docs: convert remaining plan snippets from typer to cyclopts
... (lines 24–52 all reword) ...
```

When `reword` opens the editor, replace the entire subject line with the "New subject" from the table. Save and close. The rebase continues.

## Optional: pre-baked rebase todo

If you want to skip the manual `pick → reword/fixup` conversion, save the
following as `/tmp/jh-rebase-todo.txt` and run:

```bash
GIT_SEQUENCE_EDITOR="cp /tmp/jh-rebase-todo.txt" git rebase -i --root
```

`git rebase -i` is then non-interactive at the todo step; each `reword` will
still open the editor for the new subject (or you can pre-stage messages with
`GIT_EDITOR` pointing at a script that writes the right message per commit).

```
reword 365be4b chore: initialize jobhound package
reword 626c5df docs: add jh-cli design spec and implementation plan
reword 61aa7c8 build: bound uv_build version in build-system requires
reword 0fa8358 build: add dev Taskfile and pre-commit hooks
reword 2b855f2 test: add smoke test for project layout
reword ae54bc5 feat: add Config loader with XDG-strict paths
reword 6c5af00 feat: add Paths dataclass
reword 12175dc chore: remove pytest pythonpath workaround
edit   f3a4b20 (split into 9a refactor + 9b feat — see "Splitting f3a4b20")
reword e922bdc feat: add meta.toml read/write/validate
reword 54e5438 feat: add slug resolver
reword b537637 feat: add auto-commit helper
reword 89c4303 feat: add prompt helpers and date parser
reword b614d34 feat: add typer app skeleton and shared test fixture
reword 9576541 feat: add jh new command
reword 3c6080b feat: add jh apply command and transitions module
reword 70d957e chore: revert chflags workaround (repo moved out of iCloud Documents)
reword 37b924c feat: add jh log command
reword ac8d346 refactor: switch CLI framework from typer to cyclopts
fixup  fa06312
fixup  096159d
fixup  fe2ceea
reword ed3bca9 docs: convert remaining plan snippets from typer to cyclopts
reword 630e7c6 feat: add jh withdraw, ghost, accept, decline commands
reword 04e0cac feat: add jh note, priority, tag commands
reword 5f6fe9c feat: add jh link and contact commands
reword f74c9b7 feat: add jh list command
reword 3d68698 feat: add jh edit command with validation loop
reword 5a4b7a0 feat: add jh archive, delete, sync commands
reword a3a78d6 docs: add DDD refactor plan
reword 0190278 refactor: add OpportunityRepository
reword d44baab refactor: migrate apply/note/tag/priority/link/contact to OpportunityRepository
reword 0d6f1ae refactor: migrate log and terminal-status verbs to OpportunityRepository
reword f27450e refactor: migrate new/archive/delete/edit/list to OpportunityRepository
reword 903f13f refactor: push state-transition behaviour onto Opportunity entity
reword 33db122 refactor: push field-shaped behaviour onto Opportunity entity
reword 5be5afa refactor: add Status enum with transition tables
reword 9c74e82 refactor: use Status enum for Opportunity.status
reword 8f4c8d8 refactor: add Priority enum
reword a46716d refactor: add Slug value object
reword c28afe1 refactor: add Contact value object
reword 8bbe231 refactor: drop dead target_status parameter from run_transition
reword 97c82b1 refactor: remove unused Opportunity.path field
reword d101bc4 test: assert date fields directly instead of via isoformat()
reword b6a5263 docs: seed quality/criteria.md from DDD refactor review findings
reword 5c94da4 docs: log DDD refactor decision
reword 39d9b71 fix: drop None values from opportunity links at parse time
reword 0af779b chore: add one-shot yaml-to-toml migration script
reword cc16925 docs: add post-refactor housekeeping plan
reword 52cc67f docs: log YAML-to-TOML migration decision
reword 20d6d0a docs: add semantic release & PyPI publishing design spec
reword 5aa53ad docs: add semantic release implementation plan
reword 443bba9 docs: add history rewrite map and align plan commit counts
```
