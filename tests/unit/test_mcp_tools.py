"""Unit tests for MCP server tool handlers + schema emission (SRS 12)."""
import asyncio

import pytest

from mcp_server.blender_cinematic_mcp import tools as T
from mcp_server.blender_cinematic_mcp.security import ServerContext
from mcp_server.blender_cinematic_mcp.server import build_server


@pytest.fixture
def ctx(tmp_path):
    return ServerContext(workspace_root=tmp_path)


def test_server_builds_with_schemas(ctx):
    mcp, _ = build_server(ctx)
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert "preflight_system_check" in names
    assert "scene_apply_recipe" in names
    sample = next(t for t in tools if t.name == "preflight_system_check")
    props = set((sample.inputSchema.get("properties") or {}).keys())
    assert {"project_dir", "requested_profile"} <= props


def test_resources_and_prompts(ctx):
    mcp, _ = build_server(ctx)
    prompts = asyncio.run(mcp.list_prompts())
    assert len(prompts) == 6
    res = asyncio.run(mcp.list_resources())
    assert any("docs://" in str(r.uri) for r in res)


def test_validate_manifest_tool(ctx):
    assert T.h_scene_validate_manifest(ctx, {"task_id": "t", "brief": "b", "output_mode": "still"})["valid"]
    assert not T.h_scene_validate_manifest(ctx, {"task_id": "t", "brief": "", "output_mode": "x"})["valid"]


def test_create_workspace_and_policy(ctx):
    res = T.h_project_create_scene_workspace(ctx, "demo", {"task_id": "t", "brief": "b", "output_mode": "still"})
    assert res["ok"]
    assert T.h_security_policy(ctx)["policy"]["structured_operations_only"] is True


def test_complexity_gate_blocks_bomb(ctx):
    T.h_project_create_scene_workspace(ctx, "demo", {"task_id": "t", "brief": "b", "output_mode": "still"})
    bomb = {"operations": [
        {"op": "create_mesh_primitive", "type": "uv_sphere", "name": "s"},
        {"op": "add_subdivision", "target": "s", "levels": 8},
    ]}
    res = T.h_scene_apply_recipe(ctx, "demo", bomb)
    assert res["error"] == "complexity_budget"


def test_invalid_recipe_rejected(ctx):
    T.h_project_create_scene_workspace(ctx, "demo", {"task_id": "t", "brief": "b", "output_mode": "still"})
    res = T.h_scene_apply_recipe(ctx, "demo", {"operations": [{"op": "evil"}]})
    assert res["error"] == "invalid_recipe"


def test_web_validate_glb_tool_handles_missing(ctx, tmp_path):
    res = T.h_web_validate_glb(ctx, str(tmp_path / "nope.glb"))
    assert res["ok"] is False        # missing file -> invalid
    assert res["errors"]             # reports parse failure
