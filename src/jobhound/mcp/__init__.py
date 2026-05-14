"""MCP adapter — exposes jobhound as a Model Context Protocol server.

The mcp SDK is a soft dependency (jobhound[mcp] extra). Importing this
module without the extra installed will produce a clear ImportError
on first use, not at import time.
"""

from jobhound.mcp.server import build_server, main

__all__ = ["build_server", "main"]
