# Decision: Migrate to MCP Python SDK v2 and bound the constraint

## Decision
Move the `[mcp]` extra from `mcp>=1.0` to `mcp>=2.0,<3`, rename
`FastMCP` to `MCPServer` throughout `src/jobhound/mcp/`, and make
`_require_mcp_sdk()` check for the symbol it actually needs rather than
for the presence of the `mcp` package.

## Context
`mcp` 2.0.0 shipped 2026-07-28 and renames the high-level server class:
`mcp.server.fastmcp.FastMCP` becomes `mcp.server.MCPServer`. The
decorator API, `mcp.types`, and the `ClientSession`/`stdio_client` test
layering are unchanged, so the migration is a rename rather than a
rewrite.

This surfaced as a live defect, not a planned upgrade. The extra
declared `mcp>=1.0` with **no upper bound**, so from 2026-07-28 every
fresh `pip install 'jobhound[mcp]'` resolved to 2.0.0, and both entry
points died:

```
$ jh-mcp
ModuleNotFoundError: No module named 'mcp.server.fastmcp'   (server.py:35)
```

`uv.lock` pinned 1.28.0, so CI, the dev venv, and the whole test suite
stayed green throughout. The breakage existed only for people
installing the published package — verified by installing
`jobhound==0.17.0` from PyPI into a clean venv.

`_require_mcp_sdk()` did not catch it either: its bare `import mcp`
succeeds on 2.x, so users got a raw traceback instead of the intended
guidance.

## Alternatives considered

**(a) Ship `mcp>=1.28.1,<2` first as a patch, migrate later.** Restores
working installs within minutes and picks up the 1.28.1 security fix;
upstream recommends exactly this for projects not ready to move. Two
releases instead of one. Rejected by Robin in favour of migrating
directly — the migration turned out to be an eight-file rename, so the
interim release would have been obsolete within the hour.

**(b) Pin `mcp==1.28.1` and stay on v1.** Rejected: upstream put 1.x in
maintenance mode on 2026-07-28, security fixes only. Deferring the move
accrues cost without avoiding it.

**(c) Migrate to `mcp>=2.0,<3` (chosen).** One release, one PR, and it
lands on the line that receives features.

## Reasoning
The ceiling matters as much as the migration. `<3` means the next major
cannot silently break published installs the way 2.0.0 did; Dependabot
will propose the bump as an individual major PR (per the grouping added
in #144) rather than users discovering it at install time.

Tightening the guard to `from mcp.server import MCPServer` closes the
same defect class in the other direction: an environment holding mcp
1.x now gets the actionable message rather than an opaque ImportError
from `build_server()`.

## Trade-offs accepted

- **No support for mcp 1.x.** Anyone pinned to the v1 line cannot use
  jobhound's MCP server. Acceptable: v1 is maintenance-only, and the
  extra is opt-in.
- **`<3` will need a deliberate bump.** A future major requires a code
  review rather than resolving automatically. That is the point.
- **The `docs/plans/` and `docs/specs/` files still say `FastMCP`.**
  Left as written — they are dated records of past design work, not
  live documentation.

## Verification
- 841 tests pass (838 existing + 3 new guard tests); ruff and ty clean.
- The four `tests/mcp/test_server_integration.py` stdio tests were the
  exact failures under 2.0.0 before the rename, and pass after.
- New guard tests were mutation-checked: restoring the old
  `import mcp` body makes `test_require_mcp_sdk_exits_when_sdk_too_old`
  fail.
- End-to-end, the case the test suite structurally cannot cover: built
  the wheel, installed it with `[mcp]` into a clean venv, confirmed it
  resolved mcp 2.0.0, and drove a real stdio MCP handshake against the
  installed `jh-mcp` — 52 tools registered.

## Follow-up
Nothing in CI exercises the *resolved dependency range*; the lockfile
means tests only ever see pinned versions. That gap is what let this
reach PyPI. A periodic job that installs the built wheel from its
declared constraints and smoke-tests `jh-mcp` would close it. Not done
here — raised as its own piece of work.

## Supersedes
Nothing. The `[mcp]` extra was introduced unbounded in the Phase 4 MCP
work (`docs/specs/2026-05-14-phase4-mcp-design.md`), which did not
consider an upper bound.
