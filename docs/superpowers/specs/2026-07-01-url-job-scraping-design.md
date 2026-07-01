# Design: create an opportunity from a job-posting URL

**Status:** Design approved 2026-07-01. Implementation pending.
**Related decision:** proposed `decisions/2026-07-01-url-job-scraping.md` (see Section "Decision doc").
**Convention:** follows `decisions/2026-06-07-cli-verb-object-convention.md`.

## Summary

Add a way to create an opportunity by scraping a job-posting URL. Target UX:

- In Claude: "add this job: `<url>`" → MCP tool.
- In a plain terminal: `jh new --url <url>`.

LinkedIn is the first supported site; the design is extensible to any site
via a per-site extractor registry.

Extraction runs **inside jobhound (Python)**, not in the agent, so the CLI
works standalone with no LLM attached. Fetching is **two-tier**: a cheap
unauthenticated HTTP GET first, falling back to a **persistent Playwright
browser profile** only when the site returns an auth wall or rate-limits.
The user logs in once (headed) if and when the fallback is needed; jobhound
never sees the password.

## Findings from live probe (2026-07-01)

The original brainstorm assumed every job site publishes a schema.org
`JobPosting` JSON-LD block for Google Jobs SEO, and that LinkedIn requires
authentication. A live probe of two real LinkedIn postings
(`/jobs/view/4383908452`, `/jobs/view/4431949667`) disproved both for
LinkedIn specifically:

1. **No JSON-LD.** Both pages contained zero `application/ld+json` blocks.
   LinkedIn hydrates from its own data model, not schema.org markup.
2. **No auth needed for the common path.** Plain `curl` with a browser
   User-Agent, no cookies, returned HTTP 200 with no auth wall — full
   company, role, location, canonical URL, and the complete 4–7 KB JD body.
3. **Tracking params are inert.** The full email-alert URL (with
   `trk`/`refId`/`trackingId`) and the bare `/jobs/view/<id>` produced
   identical extracted data and the same canonical URL. LinkedIn exposes a
   `<link rel="canonical">` / `og:url` pointing at the normalized form
   (`…/jobs/view/<role-slug>-<id>`).

What LinkedIn exposes cleanly and consistently:

| Signal                                   | Yields                          |
| ---------------------------------------- | ------------------------------- |
| `<title>` / `og:title`                   | `"{company} hiring {role} in {location} \| LinkedIn"` |
| `<link rel="canonical">` / `og:url`      | normalized posting URL (dedup key) |
| `div.show-more-less-html__markup`        | full JD body                    |
| `og:description` / meta description      | JD summary (truncated)          |

Consequence: LinkedIn is a **custom-extractor** case, not the generic
JSON-LD case. The generic JSON-LD extractor is retained for **ATS sites**
(Greenhouse, Lever, Workday, Ashby), which do emit `JobPosting` JSON-LD —
that remains the cheap-to-extend seam. But the first extractor written is
LinkedIn-specific.

## Goals

- `jh new --url <url>` creates a `prospect` opportunity from a single URL,
  with no LLM in the loop.
- The MCP `create_from_url` tool wraps the same underlying function, so CLI
  and agent stay in sync.
- The common LinkedIn path needs no login and no browser binary — a plain
  HTTP fetch suffices.
- Auth (persistent Playwright profile) is a **fallback**, engaged only on an
  auth wall / rate-limit, or for sites that gate their postings.
- Adding an ATS site that publishes JSON-LD is a registry entry, not new
  scraping code.
- Scraped fields can be corrected or augmented at creation via override
  flags (`--priority`, `--role`, …).
- The base install stays light: Playwright is an optional `browser` extra,
  mirroring the existing `mcp` extra. HTTP fetch uses `httpx` (already a
  transitive dep candidate) in the base install.

## Non-goals

- Scraping sites with neither JSON-LD nor a registered custom extractor in
  the first cut. Such a URL yields a clear "unsupported site" error.
- Bypassing anti-bot measures or CAPTCHAs. If both fetch tiers fail, the
  design surfaces an actionable error and stops — no evasion.
- Storing credentials. jobhound persists only Playwright's `user_data_dir`.
- Re-scraping / refresh of an existing opportunity. First cut refuses on a
  duplicate canonical URL. A `--refresh` path is future work.
- Positional `jh new <url>`. The trigger is the `--url` flag.

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
              │  fetch(2-tier) → resolve extractor → extract  │
              │  → dedup on canonical → build Opportunity →   │
              │  create → write JD file, set link, set scalars│
              └────┬──────────────────┬─────────────────┬─────┘
                   │                  │                 │
                   ▼                  ▼                 ▼
     ┌──────────────────────┐ ┌───────────────────┐ ┌────────────────────┐
     │ infrastructure/fetch │ │ application/       │ │ application/       │
     │  http_fetch (tier 1) │ │ extract/           │ │ lifecycle_service, │
     │  browser_fetch(tier 2│ │  linkedin.py       │ │ file_service,      │
     │  Playwright fallback) │ │  jsonld.py (ATS)  │ │ relation_service   │
     │  → FetchResult(html)  │ │  registry         │ │ (existing)         │
     └──────────────────────┘ └───────────────────┘ └────────────────────┘
```

Layering mirrors the existing DDD split (`decisions/2026-05-11-ddd-refactor.md`):
domain stays pure; the fetch adapters are the only network-aware code;
extractors are pure functions over HTML; the application service orchestrates.

## Components

### `infrastructure/fetch/http_fetch.py` (new — tier 1)

Plain unauthenticated fetch. `fetch(url) -> FetchResult` issues an `httpx`
GET with a browser User-Agent, follows redirects, and returns the final URL
plus raw HTML. Detects an auth wall / rate-limit (HTTP 401/403/429, or a
known interstitial `pageKey`) and raises `AuthWallError` so the service can
escalate to tier 2. No browser binary required.

### `infrastructure/fetch/browser_fetch.py` (new — tier 2, Playwright)

The only module that imports Playwright. Guarded so the base install without
the `browser` extra raises an actionable error rather than `ImportError`.
Engaged only on tier-1 escalation or for gated sites.

- `fetch(url) -> FetchResult` — headless persistent context at the profile
  `user_data_dir`; returns final URL + rendered HTML.
- `login(site) -> None` — **headed** persistent context at the site's login
  URL; blocks until logged in. Interactive; CLI-only.
- `session_status(site) -> SessionStatus` — profile exists + looks logged in
  + last-used time. Read-only.

Profile: a Playwright `user_data_dir` under the XDG data dir, one per site.

### `application/extract/` (new — HTML → ScrapedJob)

Pure functions, no I/O, unit-tested against captured HTML fixtures. A
`ScrapedJob` dataclass carries `company`, `role`, `location`, `comp_range`,
`jd_body`, `canonical_url`, and a `missing` list of absent field names.

- `linkedin.py::extract(html) -> ScrapedJob` — parses `og:title`/`<title>`
  via the `"{company} hiring {role} in {location} | LinkedIn"` pattern, the
  `<link rel="canonical">` / `og:url` for the normalized URL, and
  `div.show-more-less-html__markup` for the JD body (HTML→Markdown).
- `jsonld.py::extract(html) -> ScrapedJob` — the generic path for ATS sites:
  parses the `JobPosting` JSON-LD (`title`, `hiringOrganization.name`,
  `jobLocation`, `baseSalary`, `description`, `url`).
- `registry.py` — maps hostname → extractor + which fetch tier to try first
  + login metadata. `linkedin.com` → `linkedin` extractor, tier-1 first.
  Unknown host → `jsonld` extractor, tier-1 first. LinkedIn login metadata
  is retained for the rare tier-2 escalation.

Extractors are tolerant of partial data: they populate `missing`; the
service decides whether that is enough to proceed.

### `application/scrape_service.py` (new — orchestration)

```
def create_from_url(
    repo, store, url, *, overrides: ScrapeOverrides
) -> CreateFromUrlResult
```

Algorithm:

1. Resolve site + extractor + fetch order from the registry (hostname).
2. **Fetch, two-tier**: `http_fetch.fetch(url)`; on `AuthWallError` and if
   the site supports it, `browser_fetch.fetch(url)`. If tier 2 has no valid
   session, raise `SessionRequiredError(site)` ("run `jh browser login`").
3. `extractor.extract(html)` → `ScrapedJob`.
4. **Dedup on the page's own `canonical_url`** (not the input URL — tracking
   params are inert). Refuse if any existing opp has a `posting` link equal
   to it. Raise `DuplicatePostingError`.
5. Build an `Opportunity` from `ScrapedJob` + `overrides` (overrides win).
   Company and role required; if either missing after overrides, raise
   `IncompleteScrapeError` listing what's missing.
6. `lifecycle_service.create(repo, opp)`.
7. `file_service.write(store, slug, "job-description.md", jd_body)` — the
   scraped JD as source material (a plain free-form file → clean "Case 1"
   create; kept separate from `research.md` = the user's own analysis).
8. `relation_service.set_link(..., "posting", canonical_url)` — store the
   **canonical** URL, not the raw input.
9. `source` scalar → site name (e.g. "LinkedIn"); `location`, `comp_range`
   scalars set from the scrape when present.

Return a `CreateFromUrlResult` with the slug, scraped-vs-overridden fields,
`missing` fields, and which fetch tier was used — so both adapters report
honestly ("created X via guest fetch; couldn't determine comp range").

### `commands/new.py` (edit — add `--url`)

Add a `--url` flag. When present, `run` delegates to
`scrape_service.create_from_url` instead of building the `Opportunity` from
`--company`/`--role`. Override flags pass through as `ScrapeOverrides`.
A flag (not positional `jh new <url>`) avoids the URL-vs-company token
ambiguity and composes with the override flags. Error handling mirrors
`commands/file.py`: friendly stderr + non-zero exit for `SessionRequiredError`,
`DuplicatePostingError`, `IncompleteScrapeError`, unsupported-site, and the
"browser extra not installed" case.

### `commands/browser.py` (new — `jh browser` group)

Per the `jh <object> <verb>` convention:

- `jh browser login [--site linkedin]` — headed one-time login (tier-2
  fallback). CLI-only; never an MCP tool (interactive, blocking, needs a
  display — impossible under a detached MCP server).
- `jh browser status [--site linkedin]` — prints session validity + last-used
  time.

Registered under `object_group` in `cli.py`.

### `mcp/tools/lifecycle.py` (extend)

- `create_from_url(url, **overrides)` — wraps the service. On
  `SessionRequiredError`, returns a structured, actionable error telling the
  agent to have the user run `jh browser login` in a terminal.
- `browser_status(site)` — read-only wrapper over `session_status`, so the
  agent can pre-check before a scrape that might need the fallback.

No `browser_login` MCP tool: a headed, human-in-the-loop 2FA login cannot run
in the non-interactive MCP context.

### `pyproject.toml` (edit)

- `browser = ["playwright>=1.4"]` in `[project.optional-dependencies]`,
  mirroring the `mcp` extra. `playwright install chromium` stays a documented
  post-install step.
- Ensure `httpx` is a base dependency for tier-1 fetch.

## Data mapping (confirmed)

| Scraped field        | Destination                              |
| -------------------- | ---------------------------------------- |
| role                 | `role` scalar (`meta.toml`)              |
| company              | `company` scalar (`meta.toml`) + slug    |
| location             | `location` scalar (`meta.toml`)          |
| comp_range           | `comp_range` scalar (`meta.toml`)        |
| jd_body (full JD)    | `job-description.md` via the file store  |
| **canonical_url**    | `posting` link                           |
| site name            | `source` scalar (`meta.toml`)            |

`job-description.md` is source material, distinct from `research.md`. Dedup
keys on `canonical_url` (or the trailing numeric job ID parsed from it).

## Testing strategy

- Extractors — pure unit tests over captured fixtures (the two probed
  LinkedIn pages are ready-made fixtures): complete posting, partial
  (missing salary/location → `missing` populated), and a full-params-vs-bare
  URL pair asserting identical output + canonical URL. Generic `jsonld`
  extractor tested against an ATS fixture and a malformed/absent-JSON-LD case.
- `scrape_service.create_from_url` — with fake fetchers returning fixture
  HTML (mock the network boundary only): tier-1 happy path; tier-1 auth wall
  → tier-2 escalation; tier-2 no session → `SessionRequiredError`; duplicate
  canonical → `DuplicatePostingError`; missing company/role →
  `IncompleteScrapeError`. Assert JD file, `posting` link, and scalars land.
- CLI `jh new --url` — override flags win; friendly errors; "browser extra
  missing" only surfaces when tier-2 is actually reached.
- `browser_fetch` — not unit-tested against live LinkedIn; an opt-in smoke
  test (real network/profile) documents manual verification. CI stays
  hermetic. `http_fetch` similarly gated behind an opt-in network marker.

## Documentation

- README: "Add a job from a URL" — `jh new --url`, when `jh browser login`
  is needed (rate-limited/gated), and the `browser` extra + `playwright
  install`.
- CHANGELOG: new feature entry (additive, non-breaking).

## Decision doc

Add `decisions/2026-07-01-url-job-scraping.md` recording:

1. **Per-site extractor registry, Python-side**, not agent-driven scraping —
   CLI works with no LLM. LinkedIn uses a custom og:/title/markup extractor
   (no JSON-LD, per live probe); ATS sites use the generic JSON-LD extractor.
   *Supersedes the brainstorm assumption that LinkedIn exposes JSON-LD.*
2. **Two-tier fetch**: unauthenticated HTTP GET first, persistent Playwright
   profile as fallback — the LinkedIn guest view needs no auth (per probe),
   so login is demoted from mandatory to fallback. *Supersedes the "always
   authenticate via Playwright" brainstorm decision.*
3. **`jh new --url` flag + explicit `jh browser login`**, not positional URL
   and not auto-login — flag avoids token ambiguity; explicit login is the
   only shape that works under both CLI and the non-interactive MCP context.
4. **Dedup on the page's canonical URL**, not the input URL — tracking params
   are inert and LinkedIn supplies the normalized form.

## PR sequencing (ordered commits, likely one PR)

1. `infrastructure/fetch/http_fetch.py` (tier 1) + `httpx` base dep.
2. `application/extract/` — `linkedin.py`, `jsonld.py`, `registry.py`,
   `ScrapedJob`, with unit tests + the two probed pages as fixtures.
3. `application/scrape_service.py` + service tests (faked fetchers).
4. `pyproject` `browser` extra + `infrastructure/fetch/browser_fetch.py`
   (tier-2 fallback) with the extra-missing guard.
5. `commands/new.py --url` + `commands/browser.py` + `cli.py` wiring.
6. `mcp/tools/lifecycle.py` `create_from_url` + `browser_status`.
7. README + CHANGELOG + decision doc.

## Open questions resolved

- **Data mapping** → Split: JD file + `posting` link + scalars.
- **Browser command surface** → `jh browser login` + `jh browser status`,
  read-only `browser_status` MCP tool; no `browser_login` MCP tool.
- **Auto-login vs explicit login** → explicit; auto-login cannot run under
  the non-interactive MCP server.
- **JSON-LD assumption** → false for LinkedIn (live probe); LinkedIn gets a
  custom extractor, generic JSON-LD retained for ATS sites.
- **Auth required?** → no for the LinkedIn guest view (live probe); auth is a
  fallback tier.
- **Duplicate detection key** → the page's canonical URL / trailing job ID.

## Open questions deferred to implementation

- **Anti-bot resilience over time**: the guest view was reachable from a
  residential-style request on 2026-07-01. Datacenter IPs and sustained rate
  may still hit the auth wall — the tier-2 fallback exists precisely for
  this, but its real-world trigger frequency is unknown until used.
- **`missing`-field UX**: whether an incomplete scrape (company+role but no
  comp/location) should create-with-warning or prompt is a CLI-ergonomics
  call to settle when the flow is real.
- **Comp-range parsing**: LinkedIn rarely exposes structured salary; when the
  JD body mentions a range in prose, first cut leaves `comp_range` unset
  rather than guessing.
