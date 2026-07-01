# Design: cookie-reuse fetch (replace the Playwright browser tier)

**Status:** Design approved 2026-07-02. Implementation pending.
**Implements:** #132. **Closes:** #131 (removing the `browser` extra removes the Homebrew gap).
**Supersedes:** the Playwright tier-2 from `docs/superpowers/specs/2026-07-01-url-job-scraping-design.md`.

## Summary

Replace the Playwright browser tier-2 (authenticated fetch via a headless
persistent profile) with **cookie reuse**: read the user's existing browser
session cookies and replay them with the tier-1 `httpx` client. A feasibility
spike (2026-07-02, recorded on #132) confirmed this works end to end — reading
Chrome's `li_at` token and replaying it returns authenticated LinkedIn HTML;
cookies alone suffice for HTML GETs (no CSRF/extra headers).

This removes the entire browser layer: `browser_fetch`, the optional
`browser`/Playwright extra, the `jh browser login`/`status` commands, and the
`browser_status` MCP tool. The two-tier shape stays — only tier-2's mechanism
changes.

## Goals

- Authenticated fetch with no second login and no browser binary — reuse the
  session the user already has.
- Consent that originates from the **user**, not the agent: a config permission
  the MCP caller cannot set.
- Configurable browser and profile, defaulting to the OS default browser and its
  default profile.
- The `li_at`-class session token is read transiently and never persisted.

## Non-goals

- Keeping Playwright as a deeper fallback. This is a full replacement (pre-1.0,
  no compatibility shim per "replace, don't deprecate").
- A per-use CLI/MCP flag to enable cookie access. Consent is the config
  permission only; a per-use override is deferred (YAGNI).
- Reading the whole cookie jar. Reads are scoped to the target site's
  registrable domain.
- Cross-browser session merging. One configured browser+profile is read.

## Background

The Playwright tier-2 (shipped v0.15.0) has three costs: a heavy optional extra
(Playwright + a ~150 MB Chromium the Homebrew formula can't bundle — #131), a
*second* login (`jh browser login`) duplicating the session the user already has
in their normal browser, and a profile that goes stale. Cookie reuse removes all
three: no extra, no second login, and cookies are read live each fetch so they
track the real session.

The spike also surfaced the design's central tension, which shapes the consent
model below: reading `li_at` (full account access) is security-sensitive, and on
the MCP surface the caller is an agent — so consent must not be an agent-settable
tool parameter.

## Consent model

A **user-owned config permission**, `allow_browser_cookie_access` (bool, default
`false`).

- The fetch coordinator escalates: tier-1 guest GET → on an auth wall, **if
  `allow_browser_cookie_access` is set**, tier-2 cookie fetch; **otherwise**
  raise `BrowserCookieAccessDeniedError`.
- There is **no cookie parameter** on the CLI or the MCP `create_from_url` tool.
  The agent physically cannot opt in — only the user's config can. One-time
  consent, then seamless (symmetric with the old tier's one-time `jh browser
  login`).

## Configuration

Three new fields on `Config` (read from `config.toml`; snake_case in TOML,
kebab-case on the CLI):

| TOML / CLI key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `allow_browser_cookie_access` | bool | `false` | Consent gate for reading browser cookies |
| `cookie_browser` | str | `"auto"` | Which browser; `auto` = detect OS default; or `chrome`/`firefox`/… |
| `cookie_browser_profile` | str \| null | `null` | Browser profile; `null` = the browser's default profile; e.g. `"Profile 1"` |

### `jh config` command (new)

A small generic get/set over `config.toml`, using `tomli-w` (already a
dependency) to write and `tomllib` to read, preserving unrelated keys.

- `jh config get [key]` — print one key, or all keys if omitted.
- `jh config set <key> <value>` — validated write.
- Exposes the three cookie fields plus existing `auto-commit`/`editor`.
  `db-path` is intentionally excluded: it is really a property of the *local*
  storage backend, not a flat top-level key. Restructuring config around
  backend types is a separate concern, deliberately out of scope here.
  `get`/`set` take flat kebab-case keys.
- Validation: bool for `allow-browser-cookie-access`; known-browser-or-`auto`
  for `cookie-browser`; unknown keys/values → a clear error + non-zero exit.

## Architecture

The two-tier fetch shape and the `coordinator` are retained. Tier-2's
implementation is swapped.

```
tier 1: http_fetch (unauthenticated httpx GET)      [unchanged]
   │  AuthWallError
   ▼
coordinator: allow_browser_cookie_access set?
   ├─ no  → raise BrowserCookieAccessDeniedError
   └─ yes → tier 2: cookie_fetch
                 resolve browser+profile from config
                 read domain-scoped cookies (browser_cookie3)
                 httpx GET with cookies → FetchResult
                 (no session cookie → NoBrowserSessionError)
```

### Removed

- `src/jobhound/infrastructure/fetch/browser_fetch.py`
- `[project.optional-dependencies] browser` (playwright) in `pyproject.toml`
- `src/jobhound/commands/browser.py` + its `cli.py` registration + its
  `_complete.py` completion-table entries
- the `browser_status` MCP tool in `mcp/tools/lifecycle.py`
- `SessionRequiredError` (base.py) + its `session_required` MCP error mapping
- the browser-site login-URL table in the extractor registry

### Added

- `src/jobhound/infrastructure/fetch/cookie_fetch.py` — tier-2.
- default-browser detection helper (macOS via the LaunchServices `https`
  handler, spike-proven; Linux/Windows best-effort with a clear fallback).
- `src/jobhound/commands/config.py` — the `jh config` group.
- `browser-cookie3` as a pinned base dependency (pulls `pycryptodomex`).

## Components

### `infrastructure/fetch/cookie_fetch.py`

- `fetch(url, *, browser, profile, read_cookies=<default>) -> FetchResult` —
  resolves the browser/profile (a `"auto"` browser → default-browser detection),
  reads cookies **scoped to `url`'s registrable domain**, and replays them with
  the same httpx configuration tier-1 uses (browser UA, redirects, timeout).
  `read_cookies` is the injection seam for tests; the default is a
  `browser_cookie3`-backed reader.
- Raises `NoBrowserSessionError` when no cookies are found for the domain, and
  wraps `browser_cookie3` failures (locked DB, keychain denied, browser not
  installed) as `FetchError` with the cause.

### `coordinator.py` (modified)

Tier-2 default becomes `cookie_fetch` (lazily, so nothing imports
`browser_cookie3` until needed). The escalation consults
`allow_browser_cookie_access` from config; when off it raises
`BrowserCookieAccessDeniedError` instead of escalating. Config is read via the
existing `load_config`, injectable in tests.

### Error taxonomy (`infrastructure/fetch/base.py`)

- `BrowserCookieAccessDeniedError(FetchError)` — auth wall hit, permission off.
  Message: *"this posting needs a login; enable with `jh config set
  allow-browser-cookie-access true`"*.
- `NoBrowserSessionError(FetchError)` — permitted, but no session cookie found;
  names the browser+profile and suggests logging in there or changing
  `cookie-browser`/`cookie-browser-profile`.
- `AuthWallError`, `FetchError`, `FetchResult` — unchanged. `SessionRequiredError`
  removed.

### MCP (`mcp/errors.py`, `mcp/tools/lifecycle.py`)

- Map `BrowserCookieAccessDeniedError` → `browser_cookie_access_denied` and
  `NoBrowserSessionError` → `no_browser_session`. Drop `session_required`.
- Remove the `browser_status` tool. `create_from_url` is unchanged (no new
  params — consent is config-side).

## Data flow & security invariants

- Cookies are read **transiently**, **scoped to the target registrable domain**,
  handed to the httpx request in memory, and **never written** to `meta.toml`,
  the JD file, logs, or anywhere on disk. The `li_at` token exists only for the
  duration of the fetch.
- Escalation happens only behind the user's `allow_browser_cookie_access`
  permission. The agent cannot set it.

## Testing

- **`cookie_fetch`** — inject a fake `read_cookies` + httpx `MockTransport`:
  assert the request is scoped to the target domain, browser/profile resolution,
  `NoBrowserSessionError` on empty, wrapped `FetchError` on reader failure. Real
  `browser_cookie3` is exercised only behind an opt-in marker (as the old
  Playwright smoke test was).
- **default-browser detection** — unit-test the LaunchServices plist parser
  against a fixture (pure parsing, no live system read).
- **coordinator** — gated escalation: permitted → tier-2 called; off →
  `BrowserCookieAccessDeniedError`; tier-1 success → no escalation.
- **`jh config`** — get/set round-trip on a tmp `config.toml`; validation errors;
  unrelated keys preserved on write.
- **MCP** — `create_from_url` → structured `browser_cookie_access_denied` /
  `no_browser_session` codes.
- **Deletions** — remove `test_browser_fetch.py`, `test_cmd_browser.py`, and the
  `browser_status`/`session_required` cases in the MCP tests; update
  `test_tools_scrape.py`'s session case to the new errors.

## PR sequencing (ordered commits, one PR)

1. Config: three `Config` fields + `config.toml` read/write helper.
2. `jh config` command + `cli.py` + `_complete.py` wiring.
3. `cookie_fetch` + default-browser detection + `browser-cookie3` dependency;
   new errors in `base.py`.
4. Coordinator swap to cookie tier-2 with the permission gate.
5. Remove `browser_fetch`, the `browser` extra, `jh browser`, `browser_status`,
   `SessionRequiredError`; update MCP error mapping and tests.
6. README: replace the `jh browser login` guidance with the
   `allow-browser-cookie-access` config flow.

## Decisions resolved (during brainstorming)

- Full replacement of the Playwright tier — no fallback (pre-1.0, no shim).
- `browser-cookie3` for reading cookies (broad coverage; pin it, stay defensive
  about its flakiness) — over a vendored decryptor.
- Consent = user-owned `allow_browser_cookie_access` config, not an
  agent-settable param.
- Config surface = TOML field + a `jh config get/set` command.
- Configurable `cookie_browser` (default `auto`) and `cookie_browser_profile`
  (default = default profile).
- Names: config `allow-browser-cookie-access`; exception `BrowserCookieAccessDeniedError`.

## Open / deferred

- **Cross-platform default-browser detection.** macOS is spike-proven; Linux has
  no single standard (`xdg-settings get default-web-browser` is the best bet) and
  Windows uses the registry. First cut: macOS solid, others best-effort with a
  clear "couldn't detect default browser; set `cookie-browser`" error.
- **`browser-cookie3` fragility.** It breaks periodically on browser updates and
  reads the cookie store (attack surface). Pin the version; if it proves
  unreliable, revisit the vendored-decryptor option from #132.
- **Per-use override flag.** Not built; add only if the config-only gate proves
  too coarse in practice.
