"""MCP server construction and entry point."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from jobhound.infrastructure.config import load_config
from jobhound.infrastructure.paths import paths_from_config
from jobhound.infrastructure.repository import OpportunityRepository

if TYPE_CHECKING:
    from mcp.server import MCPServer


def _require_mcp_sdk() -> None:
    try:
        from mcp.server import MCPServer  # noqa: F401
    except ImportError as exc:
        print(
            "jh: the MCP server requires the [mcp] extra with mcp>=2.0.\n"
            "Install with: pip install 'jobhound[mcp]'\n"
            "Or for zero-install discovery: uvx --from jobhound jh-mcp",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def build_server() -> MCPServer:
    """Build an MCPServer with all tools registered.

    Lazy-imports the SDK so the package is usable without the [mcp] extra.
    """
    _require_mcp_sdk()
    from mcp.server import MCPServer

    cfg = load_config()
    paths = paths_from_config(cfg)
    repo = OpportunityRepository(paths, cfg)

    app = MCPServer(name="jobhound")

    from jobhound.mcp.tools import reads

    reads.register(app, repo)
    from jobhound.mcp.tools import files

    files.register(app, repo)
    from jobhound.mcp.tools import lifecycle

    lifecycle.register(app, repo)
    from jobhound.mcp.tools import fields

    fields.register(app, repo)
    from jobhound.mcp.tools import relations

    relations.register(app, repo)
    from jobhound.mcp.tools import ops

    ops.register(app, repo)

    return app


def main() -> None:
    """Run the server on stdio. Used by `jh mcp` and the `jh-mcp` script."""
    app = build_server()
    app.run()


if __name__ == "__main__":
    main()
