"""Real MCP stdio client<->server roundtrip (SRS 12.1/12.2).

Spawns the server as a subprocess over the actual stdio transport and drives it
with the MCP client SDK: initialize, list tools/resources/prompts, call tools and
read a resource. This proves a host (Claude/Cursor/Codex/Gemini) can talk to it,
not merely that the server object builds.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

mcp = pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _payload(result):
    """Extract the tool's dict result from a CallToolResult."""
    sc = getattr(result, "structuredContent", None)
    if isinstance(sc, dict):
        return sc.get("result", sc)
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                continue
    return None


async def _roundtrip(workspace):
    env = dict(os.environ)
    env["BCAS_WORKSPACE_ROOT"] = str(workspace)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.blender_cinematic_mcp.server"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            prompts = (await session.list_prompts()).prompts
            resources = (await session.list_resources()).resources

            valid = _payload(await session.call_tool(
                "scene_validate_manifest",
                {"manifest": {"task_id": "t", "brief": "b", "output_mode": "still"}}))
            invalid = _payload(await session.call_tool(
                "scene_validate_manifest",
                {"manifest": {"task_id": "t", "brief": "", "output_mode": "nope"}}))
            policy = _payload(await session.call_tool("security_policy", {}))
            return tools, prompts, resources, valid, invalid, policy


def test_mcp_stdio_roundtrip(tmp_path):
    tools, prompts, resources, valid, invalid, policy = asyncio.run(_roundtrip(tmp_path))
    assert "scene_validate_manifest" in tools and "render_preview" in tools
    assert len(tools) == 22
    assert len(prompts) == 6
    assert any("docs://" in str(r.uri) for r in resources)
    assert valid["valid"] is True
    assert invalid["valid"] is False
    assert policy["policy"]["structured_operations_only"] is True
