"""Integration tests over actual stdio — verify FastMCP wiring end-to-end."""

from __future__ import annotations

import json
import os
import sys
from typing import cast

import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import TextContent

from jobhound.infrastructure.paths import Paths

pytestmark = pytest.mark.asyncio


@pytest.fixture
def server_env(mcp_paths: Paths) -> dict[str, str]:
    """Environment for spawning the server subprocess.

    Points XDG_CONFIG_HOME at a temp dir containing a jh/config.toml that
    sets db_path to the test fixture's db_root, so load_config() picks up
    the test data root.
    """
    env = os.environ.copy()
    config_dir = mcp_paths.db_root.parent / "config" / "jh"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(
        f'db_path = "{mcp_paths.db_root}"\nauto_commit = true\neditor = ""\n',
    )
    env["XDG_CONFIG_HOME"] = str(mcp_paths.db_root.parent / "config")
    return env


async def test_initialize_and_list_tools(server_env: dict[str, str]) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jobhound.mcp.server"],
        env=server_env,
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = {t.name for t in tools.tools}
        # spot-check one from each module
        for expected in (
            "list_opportunities",  # reads
            "apply_to_opportunity",  # lifecycle
            "set_priority",  # fields
            "add_tag",  # relations
            "archive_opportunity",  # ops
        ):
            assert expected in tool_names, f"missing tool {expected!r}; got {sorted(tool_names)}"
        # bump + touch alias must both be registered
        assert "bump" in tool_names, f"missing 'bump'; got {sorted(tool_names)}"
        assert "touch" in tool_names, f"missing 'touch' alias; got {sorted(tool_names)}"


async def test_call_list_opportunities_over_stdio(
    server_env: dict[str, str],
) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jobhound.mcp.server"],
        env=server_env,
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool("list_opportunities", {})
        payload = json.loads(cast(TextContent, result.content[0]).text)
        assert payload["schema_version"] == 2
        assert "opportunities" in payload


async def test_call_show_opportunity_unknown_slug(
    server_env: dict[str, str],
) -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jobhound.mcp.server"],
        env=server_env,
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        result = await session.call_tool(
            "show_opportunity",
            {"slug": "nonexistent"},
        )
        payload = json.loads(cast(TextContent, result.content[0]).text)
        assert payload["error"]["code"] == "slug_not_found"


async def test_touch_alias_same_result_as_bump(
    server_env: dict[str, str],
) -> None:
    """Both `bump` and `touch` must produce a valid opportunity response."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "jobhound.mcp.server"],
        env=server_env,
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        tool_names = {t.name for t in tools.tools}
        assert "bump" in tool_names
        assert "touch" in tool_names
        result = await session.call_tool("bump", {"slug": "2026-05-acme-em"})
        payload = json.loads(cast(TextContent, result.content[0]).text)
        assert "opportunity" in payload
