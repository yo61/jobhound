# Decision: create opportunities by scraping a job-posting URL

## Decision

Add a feature to create an opportunity from a single job-posting URL,
triggered by `jh new --url <url>` (CLI) and a `create_from_url` MCP tool.
Four choices, all grounded in a live probe of two real LinkedIn postings on
2026-07-01 (`/jobs/view/4383908452`, `/jobs/view/4431949667`):

1. **Extraction runs in jobhound (Python), via a per-site extractor
   registry** — not in the agent, and not with a single generic strategy.
   LinkedIn gets a custom extractor reading `og:title`/`<title>`
   (`"{company} hiring {role} in {location} | LinkedIn"`),
   `<link rel="canonical">`/`og:url`, and `div.show-more-less-html__markup`.
   ATS sites (Greenhouse, Lever, Workday, Ashby) use a generic `JobPosting`
   JSON-LD extractor. Hostname selects the extractor.

2. **Fetching is two-tier: unauthenticated HTTP GET first, persistent
   Playwright browser profile as fallback.** Tier 1 (`httpx`, browser
   User-Agent) handles the common case with no login and no browser binary.
   Tier 2 (headless Playwright against a saved profile) engages only on an
   auth wall / rate-limit, or for sites that gate their postings.

3. **CLI trigger is a `--url` flag with an explicit `jh browser login`** —
   not a positional URL and not auto-login on first fetch. `jh browser
   status` reports session validity; a read-only `browser_status` MCP tool
   mirrors it. There is deliberately no `browser_login` MCP tool.

4. **Duplicate detection keys on the page's own canonical URL** (or the
   trailing numeric job ID parsed from it), not the URL the user pasted.

Full design: `docs/superpowers/specs/2026-07-01-url-job-scraping-design.md`.

## Context

Opportunities are currently created by hand (`jh new --company --role`).
Job postings carry that data already, so scraping a URL removes retyping and
keeps the source material attached. The desired UX is dual-surface: "add this
job: `<url>`" to the agent, or `jh new --url <url>` in a plain terminal with
no LLM present.

The original brainstorm (same day) made two assumptions that a live probe
disproved for LinkedIn — the first target site:

- **"Every job site publishes a schema.org `JobPosting` JSON-LD block for
  Google Jobs SEO."** Both probed LinkedIn pages contained **zero**
  `application/ld+json` blocks. LinkedIn hydrates from its own data model.
- **"LinkedIn requires authentication to read a posting."** A plain `curl`
  with a browser User-Agent, no cookies, returned HTTP 200 with no auth wall
  and the full company/role/location + 4–7 KB JD body.

A third probe finding settled a deferred question: the full email-alert URL
(with `trk`/`refId`/`trackingId`) and the bare `/jobs/view/<id>` produced
identical extracted data and the same canonical URL — tracking params are
inert, and LinkedIn hands us the normalized URL via `rel="canonical"`.

## Alternatives considered

**Extraction — (a) agent-driven scraping.** Let the LLM read the page and
fill fields. Rejected: the CLI must work standalone with no LLM attached, and
LLM extraction is non-deterministic and untestable. **(b) Single generic
JSON-LD strategy for all sites.** The brainstorm's plan. Rejected once the
probe showed LinkedIn emits no JSON-LD — it would return nothing on the very
first target. **(c) Per-site registry with a generic JSON-LD default
(chosen).** LinkedIn custom, ATS sites via JSON-LD, hostname routing. Keeps
"add a JSON-LD site" nearly free while handling LinkedIn correctly.

**Fetch — (a) always authenticate via Playwright.** The brainstorm's plan.
Rejected: the guest view needs no auth, so mandatory login and a mandatory
browser binary are cost with no benefit for the common path. **(b)
unauthenticated only.** Rejected: LinkedIn rate-limits aggressively;
datacenter IPs and sustained use will hit an auth wall, and gated sites exist.
**(c) two-tier, HTTP first then Playwright fallback (chosen).** Lightest for
the common case, robust when the cheap path fails.

**Login command — (a) auto-login on first fetch.** Convenient in a terminal,
but a headed 2FA login cannot run under the non-interactive MCP server — the
`create_from_url` tool would hang or fail opaquely. **(b) explicit `jh
browser login`, CLI-only (chosen).** The only shape that works identically for
CLI and MCP: the fetch path checks the session and returns an actionable "run
`jh browser login`" error rather than blocking.

**CLI trigger — positional `jh new <url>`** was rejected because `jh new` is
otherwise all-flag and a bare positional reintroduces URL-vs-company token
ambiguity; `--url` composes cleanly with the override flags.

**Dedup key — the raw input URL** was rejected because two share links to the
same posting would create duplicates; the page's canonical URL is stable.

## Reasoning

The probe is the decisive input. Designing from the brainstorm assumptions
would have shipped a JSON-LD extractor that returns nothing on LinkedIn and a
mandatory login step that isn't needed. Grounding each choice in observed
behaviour — no JSON-LD, no auth needed, inert params — inverted two "locked"
decisions before any code was written, and produced reusable test fixtures
(the two probed pages) as a side effect.

The registry-plus-two-tier shape also keeps jobhound's existing principles:
the domain stays pure, the network lives behind adapters, extractors are pure
functions over HTML, and the base install stays light (Playwright optional).

## Trade-offs accepted

- **A new optional dependency surface.** `httpx` in the base install; the
  `browser` extra pulls Playwright + a Chromium binary. Justified: `httpx`
  is small and the browser is opt-in, engaged only on fallback.
- **Scraper fragility.** LinkedIn's `og:`/markup structure can change without
  notice, breaking the custom extractor. Mitigated by pinning the two probed
  pages as fixtures and failing loudly (populate `missing`, don't guess).
- **Anti-bot uncertainty.** The guest view was reachable from a residential
  request on 2026-07-01; datacenter IPs or sustained rate may still be walled.
  The tier-2 fallback exists for this, but its real-world trigger frequency is
  unknown until the feature is used.
- **Per-site maintenance for non-JSON-LD sites.** Each such site needs a
  custom extractor. Accepted: JSON-LD sites remain a cheap registry entry;
  only LinkedIn-class sites cost custom code.

## Supersedes

None as a prior file. This decision **overrides two assumptions from the
same-day brainstorm** captured in
`docs/superpowers/specs/2026-07-01-url-job-scraping-design.md` (Sections
"Findings from live probe" and "Decision doc"): that LinkedIn exposes
`JobPosting` JSON-LD, and that authentication is always required. The spec
already reflects the corrected design.

## Outcome

- This file records the four choices and their rationale.
- The design spec's "Decision doc" section points back here.
- Implementation proceeds per the spec's 7-commit PR sequence, starting with
  `infrastructure/fetch/http_fetch.py` and `application/extract/`.
- MCP-surface naming for `create_from_url` / `browser_status` follows the
  existing verb-first snake_case convention; no change to the pending
  CLI↔MCP alignment decision.
