# Cookie-Reuse Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Playwright browser fetch tier with cookie reuse — read the user's existing browser session cookies and replay them with the tier-1 httpx client, gated by a user-owned config permission.

**Architecture:** The two-tier fetch shape and `coordinator` are kept; tier-2 becomes `cookie_fetch` (reads domain-scoped cookies via `browser-cookie3`, replays with httpx). Escalation is gated by a new `allow_browser_cookie_access` config field the MCP agent cannot set. A new `jh config` command sets the cookie fields. The whole Playwright layer (`browser_fetch`, `browser` extra, `jh browser`, `browser_status`) is removed.

**Tech Stack:** Python 3.11+, httpx, browser-cookie3, cyclopts, tomllib/tomli-w, pytest.

## Global Constraints

- Python `>=3.11`; line length 100; absolute imports only.
- Tools: `uv run pytest -q`, `uv run ruff check`, `uv run ruff format`, `uv run ty check src`. All must be clean before each commit.
- New dependency: `browser-cookie3>=0.20` as a **base** dependency (pin floor; run `UV_FROZEN=0 uv lock` after editing `pyproject.toml`).
- Remove the `browser` optional extra (playwright) entirely.
- Config field names (verbatim): TOML `allow_browser_cookie_access`, `cookie_browser`, `cookie_browser_profile`; CLI kebab-case `allow-browser-cookie-access`, `cookie-browser`, `cookie-browser-profile`.
- Exception names (verbatim): `BrowserCookieAccessDeniedError`, `NoBrowserSessionError`. MCP error codes: `browser_cookie_access_denied`, `no_browser_session`.
- Security invariant: cookies are read transiently, scoped to the target registrable domain, and never written to disk.
- `pytest` runs at `pre-push`, not per-commit (repo policy); run it manually before each commit.

---

## File structure

- Modify `src/jobhound/infrastructure/config.py` — add 3 fields, load-time validation, get/set helpers.
- Create `src/jobhound/commands/config.py` — `jh config get/set`.
- Modify `src/jobhound/cli.py` — register `config`, unregister `browser`.
- Modify `src/jobhound/commands/_complete.py` — completion tables: add `config`, remove `browser`.
- Modify `src/jobhound/infrastructure/fetch/base.py` — add 2 errors, remove `SessionRequiredError`.
- Create `src/jobhound/infrastructure/fetch/default_browser.py` — OS default-browser detection.
- Create `src/jobhound/infrastructure/fetch/cookie_fetch.py` — tier-2.
- Modify `src/jobhound/infrastructure/fetch/coordinator.py` — config-gated cookie escalation.
- Modify `src/jobhound/mcp/errors.py` — map new errors, drop `session_required`.
- Modify `src/jobhound/mcp/tools/lifecycle.py` — remove `browser_status` tool.
- Modify `pyproject.toml` — drop `browser` extra, add `browser-cookie3`.
- Delete `src/jobhound/infrastructure/fetch/browser_fetch.py`, `src/jobhound/commands/browser.py`.
- Delete `tests/infrastructure/fetch/test_browser_fetch.py`, `tests/test_cmd_browser.py`.
- Modify `README.md`, `tests/mcp/test_tools_scrape.py`, `tests/mcp/test_server_integration.py`, `tests/infrastructure/fetch/test_coordinator.py`.
- Create `tests/test_cmd_config.py`, `tests/infrastructure/fetch/test_default_browser.py`, `tests/infrastructure/fetch/test_cookie_fetch.py`.

---

### Task 1: Config fields + load-time validation

**Files:**
- Modify: `src/jobhound/infrastructure/config.py`
- Test: `tests/infrastructure/test_config.py` (create if absent)

**Interfaces:**
- Produces: `Config` gains `allow_browser_cookie_access: bool = False`, `cookie_browser: str = "auto"`, `cookie_browser_profile: str | None = None`. `load_config() -> Config` reads/validates them.

- [ ] **Step 1: Write the failing test**

```python
# tests/infrastructure/test_config.py
from __future__ import annotations

from pathlib import Path

import pytest

from jobhound.infrastructure.config import load_config


def _write(cfg_home: Path, body: str) -> None:
    d = cfg_home / "jh"
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.toml").write_text(body)


def test_cookie_fields_default_when_absent(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    cfg = load_config()
    assert cfg.allow_browser_cookie_access is False
    assert cfg.cookie_browser == "auto"
    assert cfg.cookie_browser_profile is None


def test_cookie_fields_read_from_toml(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _write(
        tmp_path / "config",
        'allow_browser_cookie_access = true\ncookie_browser = "firefox"\n'
        'cookie_browser_profile = "Work"\n',
    )
    cfg = load_config()
    assert cfg.allow_browser_cookie_access is True
    assert cfg.cookie_browser == "firefox"
    assert cfg.cookie_browser_profile == "Work"


def test_allow_browser_cookie_access_must_be_bool(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    _write(tmp_path / "config", 'allow_browser_cookie_access = "yes"\n')
    with pytest.raises(ValueError):
        load_config()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infrastructure/test_config.py -q`
Expected: FAIL — `Config` has no attribute `allow_browser_cookie_access`.

- [ ] **Step 3: Implement**

Edit `src/jobhound/infrastructure/config.py`. Add fields to the dataclass:

```python
@dataclass(frozen=True)
class Config:
    """User-tunable settings for the `jh` CLI."""

    db_path: Path
    auto_commit: bool
    editor: str
    allow_browser_cookie_access: bool = False
    cookie_browser: str = "auto"
    cookie_browser_profile: str | None = None
```

In `load_config`, before the `return`, add:

```python
    allow_cookies = data.get("allow_browser_cookie_access", False)
    if not isinstance(allow_cookies, bool):
        raise ValueError(
            f"config.toml: allow_browser_cookie_access must be a boolean, got {allow_cookies!r}"
        )

    cookie_browser = data.get("cookie_browser", "auto")
    if not isinstance(cookie_browser, str):
        raise ValueError(f"config.toml: cookie_browser must be a string, got {cookie_browser!r}")

    cookie_profile = data.get("cookie_browser_profile")
    if cookie_profile is not None and not isinstance(cookie_profile, str):
        raise ValueError(
            f"config.toml: cookie_browser_profile must be a string, got {cookie_profile!r}"
        )
```

And extend the `return`:

```python
    return Config(
        db_path=db_path,
        auto_commit=auto_commit,
        editor=editor,
        allow_browser_cookie_access=allow_cookies,
        cookie_browser=cookie_browser,
        cookie_browser_profile=cookie_profile,
    )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/infrastructure/test_config.py -q && uv run ruff check src/jobhound/infrastructure/config.py && uv run ty check src`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/infrastructure/config.py tests/infrastructure/test_config.py
git commit -m "feat(config): add cookie-reuse config fields"
```

---

### Task 2: Config get/set helpers

**Files:**
- Modify: `src/jobhound/infrastructure/config.py`
- Test: `tests/infrastructure/test_config.py`

**Interfaces:**
- Consumes: `Config`, `config_file_path()`, `load_config()` (Task 1).
- Produces:
  - `SETTABLE_KEYS: dict[str, str]` — kebab CLI key → snake TOML key.
  - `config_values() -> dict[str, object]` — effective values keyed by kebab key.
  - `set_config_value(key: str, value: str) -> None` — validate + persist to `config.toml`.
  - `UnknownConfigKeyError(ValueError)`, `InvalidConfigValueError(ValueError)`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/infrastructure/test_config.py
from jobhound.infrastructure.config import (
    InvalidConfigValueError,
    UnknownConfigKeyError,
    config_values,
    set_config_value,
)


def test_set_and_read_back_bool(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    set_config_value("allow-browser-cookie-access", "true")
    assert load_config().allow_browser_cookie_access is True
    assert config_values()["allow-browser-cookie-access"] is True


def test_set_preserves_other_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    set_config_value("editor", "vim")
    set_config_value("cookie-browser", "chrome")
    assert load_config().editor == "vim"
    assert load_config().cookie_browser == "chrome"


def test_set_unknown_key_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(UnknownConfigKeyError):
        set_config_value("db-path", "/tmp/x")


def test_set_invalid_browser_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(InvalidConfigValueError):
        set_config_value("cookie-browser", "netscape")


def test_set_invalid_bool_raises(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    with pytest.raises(InvalidConfigValueError):
        set_config_value("allow-browser-cookie-access", "maybe")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infrastructure/test_config.py -q`
Expected: FAIL — `set_config_value` not importable.

- [ ] **Step 3: Implement**

Add to `src/jobhound/infrastructure/config.py` (imports at top: `import tomli_w`):

```python
KNOWN_BROWSERS: frozenset[str] = frozenset(
    {"auto", "chrome", "chromium", "brave", "edge", "firefox", "safari", "opera", "vivaldi"}
)

# CLI kebab key -> TOML snake key. db_path is intentionally omitted.
SETTABLE_KEYS: dict[str, str] = {
    "allow-browser-cookie-access": "allow_browser_cookie_access",
    "cookie-browser": "cookie_browser",
    "cookie-browser-profile": "cookie_browser_profile",
    "auto-commit": "auto_commit",
    "editor": "editor",
}
_BOOL_KEYS = {"allow-browser-cookie-access", "auto-commit"}


class UnknownConfigKeyError(ValueError):
    def __init__(self, key: str) -> None:
        allowed = ", ".join(sorted(SETTABLE_KEYS))
        super().__init__(f"unknown config key {key!r}; settable keys: {allowed}")
        self.key = key


class InvalidConfigValueError(ValueError):
    def __init__(self, key: str, value: str, reason: str) -> None:
        super().__init__(f"invalid value {value!r} for {key}: {reason}")
        self.key = key
        self.value = value


def config_values() -> dict[str, object]:
    """Effective config as a kebab-keyed dict (includes db-path, read-only)."""
    cfg = load_config()
    return {
        "db-path": str(cfg.db_path),
        "auto-commit": cfg.auto_commit,
        "editor": cfg.editor,
        "allow-browser-cookie-access": cfg.allow_browser_cookie_access,
        "cookie-browser": cfg.cookie_browser,
        "cookie-browser-profile": cfg.cookie_browser_profile,
    }


def _coerce(key: str, value: str) -> bool | str:
    if key in _BOOL_KEYS:
        if value.lower() in ("true", "1", "yes"):
            return True
        if value.lower() in ("false", "0", "no"):
            return False
        raise InvalidConfigValueError(key, value, "expected true or false")
    if key == "cookie-browser" and value not in KNOWN_BROWSERS:
        raise InvalidConfigValueError(
            key, value, f"expected one of {', '.join(sorted(KNOWN_BROWSERS))}"
        )
    return value


def set_config_value(key: str, value: str) -> None:
    """Validate `value` for `key` and persist it to config.toml (preserving other keys)."""
    if key not in SETTABLE_KEYS:
        raise UnknownConfigKeyError(key)
    coerced = _coerce(key, value)
    path = config_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, object] = {}
    if path.exists():
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    data[SETTABLE_KEYS[key]] = coerced
    with path.open("wb") as fh:
        tomli_w.dump(data, fh)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/infrastructure/test_config.py -q && uv run ruff check src/jobhound/infrastructure/config.py && uv run ty check src`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/infrastructure/config.py tests/infrastructure/test_config.py
git commit -m "feat(config): add get/set helpers for jh config"
```

---

### Task 3: `jh config` command

**Files:**
- Create: `src/jobhound/commands/config.py`
- Modify: `src/jobhound/cli.py`, `src/jobhound/commands/_complete.py`
- Test: `tests/test_cmd_config.py`

**Interfaces:**
- Consumes: `config_values`, `set_config_value`, `UnknownConfigKeyError`, `InvalidConfigValueError` (Task 2).
- Produces: `commands/config.py` exposing `app` (cyclopts App with `get`, `set`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cmd_config.py
from __future__ import annotations


def test_config_set_then_get(tmp_jh, invoke) -> None:
    r = invoke(["config", "set", "cookie-browser", "chrome"])
    assert r.exit_code == 0, r.output
    r = invoke(["config", "get", "cookie-browser"])
    assert r.exit_code == 0, r.output
    assert "chrome" in r.output


def test_config_get_all_lists_cookie_keys(tmp_jh, invoke) -> None:
    r = invoke(["config", "get"])
    assert r.exit_code == 0, r.output
    assert "allow-browser-cookie-access" in r.output


def test_config_set_unknown_key_errors(tmp_jh, invoke) -> None:
    r = invoke(["config", "set", "db-path", "/tmp/x"])
    assert r.exit_code == 1
    assert "unknown config key" in r.output.lower()
```

Note: `tmp_jh` sets `XDG_CONFIG_HOME` to a temp dir (see `tests/conftest.py`), so `config set` writes there.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cmd_config.py -q`
Expected: FAIL — no `config` command registered.

- [ ] **Step 3: Implement the command**

Create `src/jobhound/commands/config.py`:

```python
"""`jh config` — read and set jobhound configuration (config.toml)."""

from __future__ import annotations

import sys

from cyclopts import App

from jobhound.infrastructure.config import (
    InvalidConfigValueError,
    UnknownConfigKeyError,
    config_values,
    set_config_value,
)

app = App(name="config", help="Read and set jobhound configuration.")


@app.command(name="get")
def get(key: str | None = None, /) -> None:
    """Print one config value, or all of them."""
    values = config_values()
    if key is None:
        for name, value in values.items():
            print(f"{name} = {value!r}")
        return
    if key not in values:
        print(f"config: unknown config key {key!r}", file=sys.stderr)
        raise SystemExit(1)
    print(values[key])


@app.command(name="set")
def set_(key: str, value: str, /) -> None:
    """Set a config value (persisted to config.toml)."""
    try:
        set_config_value(key, value)
    except (UnknownConfigKeyError, InvalidConfigValueError) as exc:
        print(f"config: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    print(f"{key} = {value}")
```

- [ ] **Step 4: Wire into cli.py**

In `src/jobhound/cli.py`, add the import alongside the others (alphabetical, after `completion`):

```python
    from jobhound.commands.config import app as config_app
```

Register it under `utility_group` (near the `completion_app` registration):

```python
    config_app.group = utility_group
    _cyclopts_app.command(config_app)
```

- [ ] **Step 5: Update completion tables**

In `src/jobhound/commands/_complete.py`, add to `_SUB_APP_NAMES`:

```python
    "config": frozenset({"get", "set"}),
```

And add `"config"` to the `_TOP_LEVEL_COMMANDS` frozenset (alphabetically, after `"completion"`).

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_cmd_config.py tests/commands/test_cmd_complete.py -q && uv run ruff check src/jobhound/commands/config.py src/jobhound/cli.py && uv run ty check src`
Expected: PASS, clean. (The completion-table test guards drift; it must stay green.)

- [ ] **Step 7: Commit**

```bash
git add src/jobhound/commands/config.py src/jobhound/cli.py src/jobhound/commands/_complete.py tests/test_cmd_config.py
git commit -m "feat(config): add jh config get/set command"
```

---

### Task 4: New fetch errors

**Files:**
- Modify: `src/jobhound/infrastructure/fetch/base.py`
- Test: `tests/infrastructure/fetch/test_base_errors.py`

**Interfaces:**
- Produces: `BrowserCookieAccessDeniedError(FetchError)`, `NoBrowserSessionError(FetchError)` with `.browser`, `.profile`.
- Note: `SessionRequiredError` stays until Task 9 (still used by `browser_fetch`).

- [ ] **Step 1: Write the failing test**

```python
# tests/infrastructure/fetch/test_base_errors.py
from __future__ import annotations

from jobhound.infrastructure.fetch.base import (
    BrowserCookieAccessDeniedError,
    FetchError,
    NoBrowserSessionError,
)


def test_access_denied_is_fetch_error_with_actionable_message() -> None:
    exc = BrowserCookieAccessDeniedError()
    assert isinstance(exc, FetchError)
    assert "allow-browser-cookie-access" in str(exc)


def test_no_session_names_browser_and_profile() -> None:
    exc = NoBrowserSessionError("chrome", "Profile 1")
    assert isinstance(exc, FetchError)
    assert exc.browser == "chrome"
    assert exc.profile == "Profile 1"
    assert "chrome" in str(exc)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infrastructure/fetch/test_base_errors.py -q`
Expected: FAIL — names not importable.

- [ ] **Step 3: Implement**

Add to `src/jobhound/infrastructure/fetch/base.py` (after `AuthWallError`):

```python
class BrowserCookieAccessDeniedError(FetchError):
    """Tier-1 was blocked, but reading browser cookies is not permitted."""

    def __init__(self) -> None:
        super().__init__(
            "this posting needs a login; enable with "
            "`jh config set allow-browser-cookie-access true`"
        )


class NoBrowserSessionError(FetchError):
    """Cookie access is permitted, but no session cookies were found."""

    def __init__(self, browser: str, profile: str | None = None) -> None:
        where = browser + (f" (profile {profile})" if profile else "")
        super().__init__(
            f"no session cookies found in {where}; log in there, or set "
            "cookie-browser / cookie-browser-profile"
        )
        self.browser = browser
        self.profile = profile
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/infrastructure/fetch/test_base_errors.py -q && uv run ty check src`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/infrastructure/fetch/base.py tests/infrastructure/fetch/test_base_errors.py
git commit -m "feat(fetch): add cookie-tier error types"
```

---

### Task 5: Default-browser detection

**Files:**
- Create: `src/jobhound/infrastructure/fetch/default_browser.py`
- Test: `tests/infrastructure/fetch/test_default_browser.py`

**Interfaces:**
- Produces:
  - `browser_from_bundle_id(bundle_id: str) -> str | None` — maps a macOS bundle id to a browser name.
  - `detect_default_browser() -> str | None` — reads the OS default browser (macOS now; `None` elsewhere).

- [ ] **Step 1: Write the failing test**

```python
# tests/infrastructure/fetch/test_default_browser.py
from __future__ import annotations

import pytest

from jobhound.infrastructure.fetch.default_browser import browser_from_bundle_id


@pytest.mark.parametrize(
    "bundle_id, expected",
    [
        ("com.google.chrome", "chrome"),
        ("org.mozilla.firefox", "firefox"),
        ("com.apple.safari", "safari"),
        ("com.microsoft.edgemac", "edge"),
        ("com.brave.browser", "brave"),
        ("com.unknown.thing", None),
    ],
)
def test_browser_from_bundle_id(bundle_id: str, expected: str | None) -> None:
    assert browser_from_bundle_id(bundle_id) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infrastructure/fetch/test_default_browser.py -q`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

Create `src/jobhound/infrastructure/fetch/default_browser.py`:

```python
"""Detect the OS default browser (macOS supported; best-effort elsewhere)."""

from __future__ import annotations

import plistlib
import sys
from pathlib import Path

_BUNDLE_TO_BROWSER: dict[str, str] = {
    "com.google.chrome": "chrome",
    "org.mozilla.firefox": "firefox",
    "com.apple.safari": "safari",
    "com.microsoft.edgemac": "edge",
    "com.brave.browser": "brave",
    "com.operasoftware.opera": "opera",
    "com.vivaldi.vivaldi": "vivaldi",
}


def browser_from_bundle_id(bundle_id: str) -> str | None:
    """Map a macOS application bundle id to a jobhound browser name."""
    return _BUNDLE_TO_BROWSER.get(bundle_id.lower())


def _macos_default_browser() -> str | None:
    plist = (
        Path.home()
        / "Library/Preferences/com.apple.LaunchServices/com.apple.launchservices.secure.plist"
    )
    if not plist.exists():
        return "safari"  # no explicit handler set → Safari is the system default
    with plist.open("rb") as fh:
        data = plistlib.load(fh)
    for handler in data.get("LSHandlers", []):
        if handler.get("LSHandlerURLScheme") == "https":
            role = handler.get("LSHandlerRoleAll")
            return browser_from_bundle_id(role) if role else None
    return "safari"


def detect_default_browser() -> str | None:
    """Return the default browser's jobhound name, or None if undetectable."""
    if sys.platform == "darwin":
        return _macos_default_browser()
    return None
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/infrastructure/fetch/test_default_browser.py -q && uv run ruff check src/jobhound/infrastructure/fetch/default_browser.py && uv run ty check src`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/infrastructure/fetch/default_browser.py tests/infrastructure/fetch/test_default_browser.py
git commit -m "feat(fetch): detect the OS default browser"
```

---

### Task 6: `cookie_fetch` tier-2

**Files:**
- Create: `src/jobhound/infrastructure/fetch/cookie_fetch.py`
- Modify: `pyproject.toml` (add `browser-cookie3`)
- Test: `tests/infrastructure/fetch/test_cookie_fetch.py`

**Interfaces:**
- Consumes: `FetchResult`, `FetchError`, `NoBrowserSessionError` (base), `detect_default_browser` (Task 5).
- Produces: `fetch(url: str, *, browser: str, profile: str | None = None, read_cookies: CookieReader | None = None, transport: httpx.BaseTransport | None = None) -> FetchResult` where `CookieReader = Callable[[str, str, str | None], dict[str, str]]` (domain, browser, profile) → `{name: value}`.

- [ ] **Step 1: Add the dependency**

Edit `pyproject.toml` `dependencies` (add, keeping alphabetical-ish order):

```toml
    "browser-cookie3>=0.20",
```

Then run: `UV_FROZEN=0 uv lock && uv sync --quiet`
Expected: `browser-cookie3` added to `uv.lock`.

- [ ] **Step 2: Write the failing test**

```python
# tests/infrastructure/fetch/test_cookie_fetch.py
from __future__ import annotations

import httpx
import pytest

from jobhound.infrastructure.fetch import cookie_fetch
from jobhound.infrastructure.fetch.base import FetchError, NoBrowserSessionError


def _transport(handler):
    return httpx.MockTransport(handler)


def test_replays_cookies_and_returns_html() -> None:
    seen = {}

    def reader(domain, browser, profile):
        seen["domain"] = domain
        return {"li_at": "SECRET"}

    def handler(request):
        seen["cookie_header"] = request.headers.get("cookie")
        return httpx.Response(200, text="<html>authed</html>")

    result = cookie_fetch.fetch(
        "https://www.linkedin.com/jobs/view/1",
        browser="chrome",
        read_cookies=reader,
        transport=_transport(handler),
    )

    assert result.html == "<html>authed</html>"
    assert seen["domain"] == "linkedin.com"  # registrable domain, not the host
    assert "li_at=SECRET" in seen["cookie_header"]


def test_no_cookies_raises_no_browser_session() -> None:
    def reader(domain, browser, profile):
        return {}

    with pytest.raises(NoBrowserSessionError):
        cookie_fetch.fetch(
            "https://www.linkedin.com/jobs/view/1",
            browser="chrome",
            profile="Work",
            read_cookies=reader,
            transport=_transport(lambda r: httpx.Response(200, text="x")),
        )


def test_reader_failure_wrapped_as_fetch_error() -> None:
    def reader(domain, browser, profile):
        raise RuntimeError("keychain denied")

    with pytest.raises(FetchError):
        cookie_fetch.fetch(
            "https://www.linkedin.com/jobs/view/1",
            browser="chrome",
            read_cookies=reader,
            transport=_transport(lambda r: httpx.Response(200, text="x")),
        )
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/infrastructure/fetch/test_cookie_fetch.py -q`
Expected: FAIL — module not found.

- [ ] **Step 4: Implement**

Create `src/jobhound/infrastructure/fetch/cookie_fetch.py`:

```python
"""Tier-2 fetch: replay the user's existing browser session cookies via httpx.

Reads cookies scoped to the target site's registrable domain from a
configured browser/profile and replays them with the tier-1 httpx client.
The session token is used transiently and never persisted.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from jobhound.infrastructure.fetch.base import FetchError, FetchResult, NoBrowserSessionError
from jobhound.infrastructure.fetch.default_browser import detect_default_browser

CookieReader = Callable[[str, str, str | None], dict[str, str]]

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_TIMEOUT = 20.0


def _registrable_domain(host: str) -> str:
    labels = host.lower().split(".")
    return ".".join(labels[-2:]) if len(labels) >= 2 else host


def _resolve_browser(browser: str) -> str:
    if browser != "auto":
        return browser
    detected = detect_default_browser()
    if detected is None:
        raise FetchError("could not detect the default browser; set `cookie-browser`")
    return detected


def _default_read_cookies(domain: str, browser: str, profile: str | None) -> dict[str, str]:
    import browser_cookie3 as bc3  # lazy: pulls pycryptodomex

    func = getattr(bc3, browser, None)
    if func is None:
        raise FetchError(f"unsupported cookie browser: {browser!r}")
    try:
        jar = func(domain_name=domain)
    except Exception as exc:  # noqa: BLE001 — browser_cookie3 raises many types
        raise FetchError(f"could not read {browser} cookies: {exc}") from exc
    return {c.name: c.value for c in jar if c.value}


def fetch(
    url: str,
    *,
    browser: str,
    profile: str | None = None,
    read_cookies: CookieReader | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FetchResult:
    """Fetch `url` authenticated with reused browser cookies for its domain."""
    read_cookies = read_cookies or _default_read_cookies
    resolved = _resolve_browser(browser)
    domain = _registrable_domain(urlparse(url).hostname or "")

    try:
        cookies = read_cookies(domain, resolved, profile)
    except FetchError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise FetchError(f"could not read {resolved} cookies: {exc}") from exc

    if not cookies:
        raise NoBrowserSessionError(resolved, profile)

    try:
        with httpx.Client(
            transport=transport,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        ) as client:
            response = client.get(url, cookies=cookies)
    except httpx.HTTPError as exc:
        raise FetchError(f"failed to fetch {url}: {exc}") from exc

    return FetchResult(final_url=str(response.url), html=response.text)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/infrastructure/fetch/test_cookie_fetch.py -q && uv run ruff check src/jobhound/infrastructure/fetch/cookie_fetch.py && uv run ty check src`
Expected: PASS, clean.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/jobhound/infrastructure/fetch/cookie_fetch.py tests/infrastructure/fetch/test_cookie_fetch.py
git commit -m "feat(fetch): add cookie-reuse tier-2 fetch"
```

---

### Task 7: Coordinator swap + permission gate

**Files:**
- Modify: `src/jobhound/infrastructure/fetch/coordinator.py`
- Test: `tests/infrastructure/fetch/test_coordinator.py` (rewrite the escalation cases)

**Interfaces:**
- Consumes: `cookie_fetch.fetch` (Task 6), `BrowserCookieAccessDeniedError` (Task 4), `Config`/`load_config` (Task 1).
- Produces: `fetch(url, *, tier1=None, tier2=None, config=None) -> FetchResult`.

- [ ] **Step 1: Rewrite the test file**

Replace `tests/infrastructure/fetch/test_coordinator.py` with:

```python
"""Tests for the two-tier fetch coordinator (cookie tier-2, config-gated)."""

from __future__ import annotations

from pathlib import Path

import pytest

from jobhound.infrastructure.config import Config
from jobhound.infrastructure.fetch import coordinator
from jobhound.infrastructure.fetch.base import (
    AuthWallError,
    BrowserCookieAccessDeniedError,
    FetchResult,
)


def _config(*, allow: bool) -> Config:
    return Config(db_path=Path("/tmp/x"), auto_commit=True, editor="", allow_browser_cookie_access=allow)


def test_tier1_success_skips_escalation() -> None:
    calls = []

    def tier1(url):
        calls.append("t1")
        return FetchResult(final_url=url, html="guest")

    def tier2(url):
        calls.append("t2")
        return FetchResult(final_url=url, html="auth")

    result = coordinator.fetch("https://x/1", tier1=tier1, tier2=tier2, config=_config(allow=True))
    assert result.html == "guest"
    assert calls == ["t1"]


def test_auth_wall_with_permission_escalates_to_cookie_tier() -> None:
    def tier1(url):
        raise AuthWallError(url, 403)

    def tier2(url):
        return FetchResult(final_url=url, html="auth")

    result = coordinator.fetch("https://x/1", tier1=tier1, tier2=tier2, config=_config(allow=True))
    assert result.html == "auth"


def test_auth_wall_without_permission_raises_access_denied() -> None:
    called = []

    def tier1(url):
        raise AuthWallError(url, 403)

    def tier2(url):
        called.append("t2")
        return FetchResult(final_url=url, html="auth")

    with pytest.raises(BrowserCookieAccessDeniedError):
        coordinator.fetch("https://x/1", tier1=tier1, tier2=tier2, config=_config(allow=False))
    assert called == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/infrastructure/fetch/test_coordinator.py -q`
Expected: FAIL — `coordinator.fetch` has no `config` param / no gate.

- [ ] **Step 3: Implement**

Replace the body of `src/jobhound/infrastructure/fetch/coordinator.py`:

```python
"""Two-tier fetch: unauthenticated HTTP first, cookie reuse as a gated fallback.

Tier 1 (`http_fetch`) handles the common case. On an auth wall, tier 2
(`cookie_fetch`) reuses the user's browser session cookies — but only if the
user has granted `allow_browser_cookie_access`. Otherwise the auth wall is
surfaced as an actionable error.
"""

from __future__ import annotations

from collections.abc import Callable

from jobhound.infrastructure.config import Config, load_config
from jobhound.infrastructure.fetch import http_fetch
from jobhound.infrastructure.fetch.base import (
    AuthWallError,
    BrowserCookieAccessDeniedError,
    FetchResult,
)

Tier = Callable[[str], FetchResult]


def _cookie_tier(config: Config) -> Tier:
    from jobhound.infrastructure.fetch import cookie_fetch

    def tier2(url: str) -> FetchResult:
        return cookie_fetch.fetch(
            url, browser=config.cookie_browser, profile=config.cookie_browser_profile
        )

    return tier2


def fetch(
    url: str,
    *,
    tier1: Tier | None = None,
    tier2: Tier | None = None,
    config: Config | None = None,
) -> FetchResult:
    """Fetch `url`, escalating to cookie reuse on an auth wall when permitted."""
    config = config or load_config()
    tier1 = tier1 or http_fetch.fetch
    try:
        return tier1(url)
    except AuthWallError:
        if not config.allow_browser_cookie_access:
            raise BrowserCookieAccessDeniedError() from None
        tier2 = tier2 or _cookie_tier(config)
        return tier2(url)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/infrastructure/fetch/test_coordinator.py tests/application/test_scrape_service.py -q && uv run ty check src`
Expected: PASS (scrape_service tests inject their own fetch, so they are unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/infrastructure/fetch/coordinator.py tests/infrastructure/fetch/test_coordinator.py
git commit -m "feat(fetch): gate cookie escalation behind config permission"
```

---

### Task 8: MCP error mapping for the new errors

**Files:**
- Modify: `src/jobhound/mcp/errors.py`
- Modify: `tests/mcp/test_tools_scrape.py` (rewrite the session case)

**Interfaces:**
- Consumes: `BrowserCookieAccessDeniedError`, `NoBrowserSessionError` (Task 4), coordinator gate (Task 7).
- Produces: MCP error codes `browser_cookie_access_denied`, `no_browser_session`.

- [ ] **Step 1: Rewrite the scrape MCP error tests**

Replace the two error tests in `tests/mcp/test_tools_scrape.py` (`test_create_from_url_session_required_...`) with:

```python
def test_create_from_url_access_denied_returns_error(
    repo: OpportunityRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jobhound.infrastructure.config import Config
    from jobhound.infrastructure.fetch.base import AuthWallError

    def _authwall(url: str):
        raise AuthWallError(url, 403)

    _patch_tier1(monkeypatch, _authwall)
    monkeypatch.setattr(
        "jobhound.infrastructure.fetch.coordinator.load_config",
        lambda: Config(db_path=repo.paths.db_root, auto_commit=True, editor=""),
    )

    payload = json.loads(create_from_url(repo, url="https://www.linkedin.com/jobs/view/1"))
    assert payload["error"]["code"] == "browser_cookie_access_denied"


def test_create_from_url_no_session_returns_error(
    repo: OpportunityRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    from jobhound.infrastructure.config import Config
    from jobhound.infrastructure.fetch.base import AuthWallError, NoBrowserSessionError

    def _authwall(url: str):
        raise AuthWallError(url, 403)

    def _no_session(url: str):
        raise NoBrowserSessionError("chrome")

    _patch_tier1(monkeypatch, _authwall)
    monkeypatch.setattr(
        "jobhound.infrastructure.fetch.coordinator.load_config",
        lambda: Config(
            db_path=repo.paths.db_root, auto_commit=True, editor="", allow_browser_cookie_access=True
        ),
    )
    monkeypatch.setattr("jobhound.infrastructure.fetch.cookie_fetch.fetch", _no_session)

    payload = json.loads(create_from_url(repo, url="https://www.linkedin.com/jobs/view/1"))
    assert payload["error"]["code"] == "no_browser_session"
```

Remove the now-unused `SessionRequiredError` import from that test file.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/mcp/test_tools_scrape.py -q`
Expected: FAIL — codes are `internal_error` (not yet mapped).

- [ ] **Step 3: Implement the mapping**

In `src/jobhound/mcp/errors.py`, update the fetch imports:

```python
from jobhound.infrastructure.fetch.base import (
    AuthWallError,
    BrowserCookieAccessDeniedError,
    FetchError,
    NoBrowserSessionError,
)
```

Replace the `SessionRequiredError` branch (in `exception_to_response`) with:

```python
    if isinstance(exc, BrowserCookieAccessDeniedError):
        return tool_error_response("browser_cookie_access_denied", str(exc))

    if isinstance(exc, NoBrowserSessionError):
        return tool_error_response(
            "no_browser_session", str(exc), browser=exc.browser, profile=exc.profile
        )
```

(Keep the `AuthWallError` and `FetchError` branches as-is, after these two.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/mcp/test_tools_scrape.py -q && uv run ty check src`
Expected: PASS, clean.

- [ ] **Step 5: Commit**

```bash
git add src/jobhound/mcp/errors.py tests/mcp/test_tools_scrape.py
git commit -m "feat(mcp): map cookie-tier errors to actionable codes"
```

---

### Task 9: Remove the Playwright browser layer

**Files:**
- Delete: `src/jobhound/infrastructure/fetch/browser_fetch.py`, `src/jobhound/commands/browser.py`, `tests/infrastructure/fetch/test_browser_fetch.py`, `tests/test_cmd_browser.py`
- Modify: `src/jobhound/infrastructure/fetch/base.py` (remove `SessionRequiredError`), `src/jobhound/cli.py`, `src/jobhound/commands/_complete.py`, `src/jobhound/mcp/tools/lifecycle.py`, `src/jobhound/mcp/errors.py`, `src/jobhound/mcp/tools/... registration`, `pyproject.toml` (remove `browser` extra), `tests/mcp/test_server_integration.py`

**Interfaces:**
- Consumes: nothing new. Removes `browser_status`, `SessionRequiredError`, the `browser` extra, `jh browser`.

- [ ] **Step 1: Delete the modules and their tests**

```bash
git rm src/jobhound/infrastructure/fetch/browser_fetch.py \
       src/jobhound/commands/browser.py \
       tests/infrastructure/fetch/test_browser_fetch.py \
       tests/test_cmd_browser.py
```

- [ ] **Step 2: Remove `SessionRequiredError`**

In `src/jobhound/infrastructure/fetch/base.py`, delete the `SessionRequiredError` class.

- [ ] **Step 3: Unregister `jh browser`**

In `src/jobhound/cli.py`:
- delete the import `from jobhound.commands import browser as cmd_browser`
- remove `cmd_browser.app` from the `object_group` registration loop (leave the other members).

- [ ] **Step 4: Remove browser from completion tables**

In `src/jobhound/commands/_complete.py`:
- delete the `"browser": frozenset({"login", "status"}),` line from `_SUB_APP_NAMES`
- delete `"browser",` from `_TOP_LEVEL_COMMANDS`.

- [ ] **Step 5: Remove the `browser_status` MCP tool**

In `src/jobhound/mcp/tools/lifecycle.py`:
- delete the `browser_status` function
- delete its `@app.tool(name="browser_status", …)` / `_browser_status` registration block.

In `src/jobhound/mcp/errors.py`, remove the now-unused `SessionRequiredError` import (and any remaining `session_required` reference — none should remain after Task 8).

- [ ] **Step 6: Remove the `browser` extra**

In `pyproject.toml`, delete the line `browser = ["playwright>=1.55"]` from `[project.optional-dependencies]`. Then run `UV_FROZEN=0 uv lock && uv sync --quiet`.

- [ ] **Step 7: Fix the MCP integration spot-check**

In `tests/mcp/test_server_integration.py`, remove the `"browser_status",  # lifecycle (URL scraping)` line from the `for expected in (...)` tuple.

- [ ] **Step 8: Run the full suite**

Run: `uv run pytest -q && uv run ruff check src tests && uv run ty check src`
Expected: PASS, clean. Confirm no import of `browser_fetch`, `SessionRequiredError`, or `playwright` remains: `rg -n "browser_fetch|SessionRequiredError|playwright" src tests` → no hits.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(scrape): remove the Playwright browser fetch layer"
```

---

### Task 10: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the "Adding a job from a URL" section**

In `README.md`, replace the paragraph and code block covering the `browser` extra / `jh browser login` with:

```markdown
Most postings are fetched without logging in. For a posting behind a login,
let jobhound reuse the session from your browser — grant permission once:

```bash
jh config set allow-browser-cookie-access true
```

jobhound then reads the cookies for that site from your default browser
(configurable with `jh config set cookie-browser <name>` and
`cookie-browser-profile`) and replays them to fetch the posting. Cookies are
read only for the target site, used for that fetch, and never stored.
```

Remove any remaining mention of `jobhound[browser]`, `playwright install`, or `jh browser login`.

- [ ] **Step 2: Verify no stale references**

Run: `rg -n "jh browser|jobhound\[browser\]|playwright" README.md` → no hits.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs(readme): document cookie-reuse config flow"
```

---

## Notes for the implementer

- **`browser-cookie3` profile support** is limited in this first cut: `cookie_browser_profile` is passed to the reader but the default reader (`_default_read_cookies`) does not yet build per-profile cookie-file paths — profile targeting beyond the browser default is a follow-up. Keep the field and plumbing; don't block on full profile support.
- **Real `browser-cookie3` is never exercised in unit tests** — the `read_cookies` seam is always injected. A live smoke test (reading a real browser) is manual/opt-in, matching how the old Playwright path was verified.
- After Task 9, run `rg -n "browser" src/jobhound/mcp src/jobhound/commands/_complete.py` to confirm only unrelated matches (e.g. `cookie_browser`) remain.
