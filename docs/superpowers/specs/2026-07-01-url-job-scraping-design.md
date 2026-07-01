# Design: create an opportunity from a job-posting URL

**Status:** Design approved 2026-07-01. Implementation pending.
**Related decision:** proposed `decisions/2026-07-01-url-job-scraping.md` (see Section "Decision doc").
**Convention:** follows `decisions/2026-06-07-cli-verb-object-convention.md`.

## Summary

Add a way to create an opportunity by scraping a job-posting URL. Target UX:

- In Claude: "add this job: `<url>`" → MCP tool.
- In a plain terminal: `jh new --url <url>`.

LinkedIn is the first supported site; the design is extensible to any site
that publishes a schema.org `JobPosting` block.

Extraction runs **inside jobhound (Python)**, not in the agent, so the CLI
works standalone with no LLM attached. The extractor reads the
`<script type="application/ld+json">` `JobPosting` JSON-LD that job sites
maintain for Google Jobs SEO — far more stable than per-site CSS selectors.
Authenticated fetching uses a **persistent Playwright browser profile**:
the user logs in once (headed), and later fetches run headless against that
saved session. jobhound never sees the password.

## Goals

- `jh new --url <url>` creates a `prospect` opportunity from a single URL,
  with no LLM in the loop.
- The MCP `create_from_url` tool wraps the same underlying function, so CLI
  and agent stay in sync.
- Adding a site that publishes JSON-LD is nearly free — no per-site scraping
  code. Only sites without JSON-LD need a custom fallback extractor.
- Authentication is a one-time interactive step; jobhound stores only the
  browser session, never credentials.
- Scraped fields can be corrected or augmented at creation via the existing
  override flags (`--priority`, `--role`, …).
- The base install stays light: Playwright is an optional `browser` extra,
  mirroring the existing `mcp` extra.

## Non-goals

- Scraping sites without JSON-LD in the first cut. The generic extractor is
  the whole first release; a per-site fallback registry is the extensibility
  seam, not initial scope.
- Bypassing anti-bot measures or CAPTCHAs. If a site blocks the headless
  fetch, the design surfaces a clear error and stops — no evasion.
- Storing credentials. jobhound persists only Playwright's `user_data_dir`.
- Re-scraping / refresh of an existing opportunity. First cut refuses on a
  duplicate posting URL (see Open questions). A `--refresh` path is future
  work.
- Positional `jh new <url>`. The trigger is the `--url` flag (see Components).

## Architecture overview

```
┌──────────────────────────────────────────────────────────────────────┐
│  CLI (commands/new.py --url,      MCP (mcp/tools/lifecycle.py)         │
│       commands/browser.py)         create_from_url, browser_status     │
└───────────────────────┬───────────────────────────┬───────────────────┘
                        │                           │
                        ▼                           ▼
              ┌───────────────────────────────────────────────┐
              │  application/scrape_service.py  (use case)    │
              │   fetch → extract → build Opportunity →       │
              │   lifecycle_service.create → write JD file,   │
              │   set posting link, set scalars               │
              └───────┬──────────────┬──────────────┬─────────┘
                      │              │              │
                      ▼              ▼              ▼
        ┌─────────────────────┐ ┌──────────────┐ ┌────────────────────┐
        │ infrastructure/     │ │ application/ │ │ application/       │
        │ browser_fetch.py    │ │ jobposting.py│ │ lifecycle_service, │
        │ (Playwright adapter)│ │ (JSON-LD →   │ │ file_service,      │
        │  fetch(url)→html/ld │ │  ScrapedJob) │ │ relation_service   │
        └─────────────────────┘ └──────────────┘ │ (existing)         │
                                                  └────────────────────┘
```

The layering mirrors the existing DDD split (see
`decisions/2026-05-11-ddd-refactor.md`): the domain stays pure, the fetch
adapter is the only Playwright-aware code, and the application service
orchestrates the pipeline over existing services.

## Components

### `infrastructure/browser_fetch.py` (new — Playwright adapter)

The only module that imports Playwright. Guarded so the base install without
the `browser` extra gives an actionable error rather than an `ImportError`.

Responsibilities:

- `fetch(url) -> FetchResult` — launch a **headless** persistent context at
  the profile `user_data_dir`, navigate, and return the page's raw HTML plus
  any `application/ld+json` script contents pulled via `page.evaluate`
  (so no separate HTML-parser dependency — bs4/selectolax not needed).
- `login(site) -> None` — launch a **headed** persistent context at the
  site's login URL and block until the user closes the window / a logged-in
  signal is detected. Interactive; CLI-only.
- `session_status(site) -> SessionStatus` — cheap check of whether the
  profile exists and looks logged in (e.g. presence of the profile dir +
  a lightweight authenticated probe), plus last-used time. Read-only.

Profile location: a Playwright `user_data_dir` under the XDG data dir
(alongside the existing jobhound data root), one dir per site.

Detection of the "logged in" state is site-specific and lives behind the
site registry (below), keeping this adapter generic.

### `application/jobposting.py` (new — JSON-LD → ScrapedJob)

Pure function, no I/O, unit-testable against captured HTML fixtures.

- `extract(html: str, ld_blocks: list[str]) -> ScrapedJob` — parse the
  `JobPosting` JSON-LD, mapping schema.org fields to a `ScrapedJob`
  dataclass: `title` (→ role), `hiringOrganization.name` (→ company),
  `jobLocation` (→ location), `baseSalary` (→ comp range), `description`
  (→ JD body, HTML→Markdown), plus the canonical posting `url`.
- Tolerant of missing/partial data: returns a `ScrapedJob` with whatever
  was found and a list of `missing` field names. The service decides
  whether that's enough to proceed (see below).

### `application/scrape_service.py` (new — orchestration)

The use case tying it together. One public entry point shared by CLI and MCP:

```
def create_from_url(
    repo, store, url, *, overrides: ScrapeOverrides
) -> CreateFromUrlResult
```

Algorithm:

1. Resolve site from URL hostname via the registry. Unknown host → the
   generic JSON-LD path.
2. `browser_fetch.fetch(url)` → HTML + LD blocks. If no valid session,
   raise `SessionRequiredError(site)` (actionable: "run `jh browser login`").
3. `jobposting.extract(...)` → `ScrapedJob`.
4. Duplicate check: refuse if any existing opp already has a `posting` link
   equal to the canonical URL (see Open questions). Raise `DuplicatePostingError`.
5. Build an `Opportunity` from `ScrapedJob` + `overrides` (overrides win).
   Company and role are required; if either is missing after overrides,
   raise `IncompleteScrapeError` listing what's missing.
6. `lifecycle_service.create(repo, opp)` → creates the opp dir.
7. `file_service.write(store, slug, "job-description.md", jd_body)` — the
   scraped JD as source material. `job-description.md` is a plain free-form
   file (not under a protected dir), so this is a clean "Case 1" create in
   `file_service`. Kept separate from `research.md` (the user's own analysis).
8. `relation_service.set_link(..., "posting", url)` — the posting URL as a
   named link.
9. `source` scalar set to the site name (e.g. "LinkedIn"); `location` and
   `comp_range` scalars set from the scrape when present.

Return a `CreateFromUrlResult` carrying the slug, the list of scraped vs.
overridden fields, and any `missing` fields — so both adapters can report
"created X; couldn't determine comp range" honestly.

### `commands/new.py` (edit — add `--url`)

Add a `--url` flag. When present, `run` delegates to
`scrape_service.create_from_url` instead of building the `Opportunity` from
`--company`/`--role` directly. Override flags (`--role`, `--priority`,
`--source`, …) remain available and are passed through as `ScrapeOverrides`;
they correct or augment scraped values.

Rationale for a flag, not positional `jh new <url>`: `jh new` is already
all-flag; a bare positional would reintroduce the URL-vs-company token
ambiguity the CLI convention avoids; and a flag composes cleanly with the
override flags.

Error handling mirrors the existing pattern in `commands/file.py`: translate
`SessionRequiredError`, `DuplicatePostingError`, `IncompleteScrapeError`, and
the "browser extra not installed" case into friendly stderr messages + a
non-zero exit.

### `commands/browser.py` (new — `jh browser` group)

A new object group per the `jh <object> <verb>` convention:

- `jh browser login [--site linkedin]` — headed one-time login. Calls
  `browser_fetch.login`. CLI-only; never an MCP tool (interactive, blocking,
  needs a TTY/display — impossible under a detached MCP server).
- `jh browser status [--site linkedin]` — prints whether a valid session
  exists and when it was last used. Calls `browser_fetch.session_status`.

Registered in `cli.py` under `object_group`, alongside the other object
groups.

### `mcp/tools/lifecycle.py` (extend)

- `create_from_url(url, **overrides)` — wraps `scrape_service.create_from_url`.
  On `SessionRequiredError`, returns a structured, actionable error telling
  the agent to have the user run `jh browser login` in a terminal (the agent
  cannot perform an interactive headed login itself).
- `browser_status(site)` — read-only wrapper over
  `browser_fetch.session_status`, so the agent can pre-check before
  attempting a scrape.

There is deliberately **no** `browser_login` MCP tool: a headed, human-in-the-
loop 2FA login cannot run in the non-interactive MCP context. This asymmetry
is why auto-login on first fetch was rejected in favour of an explicit
CLI-only command.

### `pyproject.toml` (edit — `browser` extra)

Add `browser = ["playwright>=1.4"]` to `[project.optional-dependencies]`,
mirroring the existing `mcp` extra. `playwright install chromium` remains a
documented post-install step (the browser binary is not a Python dependency).

## Site registry — the extensibility seam

A small mapping from hostname → `SiteAdapter` describing:

- login URL,
- "logged in" detection predicate,
- optional custom extractor for sites without usable JSON-LD.

LinkedIn is the first entry. The default (unknown host) uses the generic
JSON-LD extractor and a generic "profile dir exists" session heuristic.
Adding a JSON-LD site is a registry entry, not new scraping code.

## Data mapping (confirmed during brainstorming)

| Scraped field                 | Destination                                  |
| ----------------------------- | -------------------------------------------- |
| `title`                       | `role` scalar (`meta.toml`)                  |
| `hiringOrganization.name`     | `company` scalar (`meta.toml`) + slug        |
| `jobLocation`                 | `location` scalar (`meta.toml`)              |
| `baseSalary`                  | `comp_range` scalar (`meta.toml`)            |
| `description` (full JD body)  | `job-description.md` via the file store      |
| canonical posting `url`       | `posting` link                               |
| site name                     | `source` scalar (`meta.toml`)                |

`job-description.md` is source material and stays distinct from `research.md`
(the user's own analysis). Both are ordinary free-form files.

## Testing strategy

- `jobposting.extract` — pure unit tests over captured HTML fixtures:
  a complete LinkedIn `JobPosting`, a partial one (missing salary/location),
  malformed JSON-LD, and no JSON-LD at all (→ `missing` populated). Property
  test the HTML→Markdown description conversion for idempotence on plain text.
- `scrape_service.create_from_url` — with a fake `BrowserFetch` returning
  fixture HTML (mock the network boundary only): happy path, missing
  company/role → `IncompleteScrapeError`, duplicate posting URL →
  `DuplicatePostingError`, no session → `SessionRequiredError`. Assert the
  JD file, `posting` link, and scalars all land.
- CLI `jh new --url` — override flags win over scraped values; friendly
  errors for each failure; "browser extra missing" message when Playwright
  is absent.
- `browser_fetch` — not unit-tested against live LinkedIn. A thin smoke test
  behind an opt-in marker (real network, real profile) documents the manual
  verification path; CI stays hermetic.

## Documentation

- README: a "Add a job from a URL" section covering `jh browser login` (one
  time), `jh new --url`, and the `browser` extra + `playwright install`.
- CHANGELOG: new feature entry (additive, non-breaking).

## Decision doc

Add `decisions/2026-07-01-url-job-scraping.md` recording the three locked
choices and their rejected alternatives:

1. **Extraction in Python via JSON-LD**, not agent-driven CSS scraping —
   so the CLI works with no LLM, and site support is stable and cheap.
2. **Persistent Playwright profile for auth**, not credential storage or
   cookie juggling — jobhound never sees the password.
3. **`jh new --url` flag + explicit `jh browser login`**, not positional
   URL and not auto-login-on-first-fetch — the flag avoids token ambiguity;
   the explicit login is the only shape that works under both CLI and the
   non-interactive MCP context.

## PR sequencing (ordered commits, likely one PR)

1. `pyproject` `browser` extra + `infrastructure/browser_fetch.py` skeleton
   with the extra-missing guard.
2. `application/jobposting.py` + extraction unit tests and fixtures.
3. `application/scrape_service.py` + service tests (faked fetch).
4. `commands/new.py --url` + `commands/browser.py` + CLI wiring in `cli.py`.
5. `mcp/tools/lifecycle.py` `create_from_url` + `browser_status`.
6. README + CHANGELOG + decision doc.

## Open questions resolved during brainstorming

- **Data mapping** → Split: JD file + `posting` link + scalars (confirmed).
- **Browser command surface** → `jh browser login` + `jh browser status`,
  with a read-only `browser_status` MCP tool; no `browser_login` MCP tool
  (confirmed).
- **Auto-login vs explicit login** → explicit, because auto-login cannot run
  under the non-interactive MCP server (resolved).

## Open questions deferred to implementation

- **Duplicate detection key**: exact canonical-URL match on the `posting`
  link is the first cut. Normalisation (stripping tracking params, resolving
  `linkedin.com/jobs/view/<id>`) may be needed if the same posting appears
  under varying URLs.
- **Anti-bot resilience**: what LinkedIn returns to a headless persistent
  context in practice, and whether a headed-fallback fetch is warranted, is
  an empirical question for implementation.
- **`missing`-field UX**: whether an incomplete scrape (has company+role but
  no comp/location) should create-with-warning or prompt is a CLI-ergonomics
  call to settle when the flow is real.
