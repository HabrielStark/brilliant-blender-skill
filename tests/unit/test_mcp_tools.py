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
    uris = {str(r.uri) for r in res}
    assert any("docs://" in str(u) for u in uris)
    # every playbook in references/ must be reachable - an unreachable doc is
    # a capability agents cannot discover
    assert "docs://procedural-modeling-recipes" in uris
    assert "docs://animation-camera-paths" in uris
    assert "docs://composition-rubric" in uris
    assert "docs://index" in uris
    # worked task recipes must be reachable — the exemplars a weak model adapts
    assert "examples://index" in uris
    assert "examples://product_hero_watch" in uris


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


def test_scene_verifier_brief_emits_fresh_eyes_prompt(ctx):
    """The verifier-brief tool must package brief + ledger + image paths into
    a dispatchable prompt — the semantic gate must be a tool, not folklore."""
    T.h_project_create_scene_workspace(ctx, "demo", {
        "task_id": "t", "brief": "a desk with a lamp",
        "output_mode": "still",
        "success_criteria": {"required_parts": ["desk", "lamp"]},
    })
    res = T.h_scene_verifier_brief(ctx, "demo")
    assert res["ok"]
    p = res["verifier_prompt"]
    assert "a desk with a lamp" in p
    assert "desk, lamp" in p
    assert "VERDICT" in p and "unidentifiable" in p
    assert res["image_paths"]  # default orbit set when none passed


def test_scene_critique_tool_returns_op_ready_diagnoses(ctx, tmp_path):
    """The critique handler must translate a render + inspection into
    ordered diagnoses with suggested ops — not just raw numbers."""
    import numpy as np
    from PIL import Image
    # near-black render: the classic "black slab" defect
    arr = np.full((64, 64, 4), 8, dtype=np.uint8)
    arr[..., 3] = 255
    p = tmp_path / "preview.png"
    Image.fromarray(arr, "RGBA").save(p)
    inspection = {"objects": [
        {"name": "hero", "collection": "SUBJECT", "in_camera_frame": True,
         "screen_coverage": 0.4, "world_location": [0, 0, 0.5],
         "screen_bbox": [0.3, 0.3, 0.7, 0.7]},
    ], "materials": [], "world": {"strength": 0.05}}
    res = T.h_scene_critique(ctx, inspection, image_path=str(p))
    assert res["ok"] and res["diagnoses"]
    top = res["diagnoses"][0]
    assert top["severity"] == "fail"
    assert top["ops"] and all("op" in o for o in top["ops"])
    # suggested ops must be real allowlisted operations, not advice
    from blender_cinematic.recipes import validate_recipe
    assert validate_recipe({"operations": top["ops"]}).passed


def test_scene_verifier_ops_parses_and_validates(ctx):
    """Verifier prose -> structured ops: only allowlisted, schema-valid ops
    survive; junk is dropped with reasons."""
    T.h_project_create_scene_workspace(ctx, "demo",
                                       {"task_id": "t", "brief": "b", "output_mode": "still"})
    report = """VERDICT: FAIL
ledger:
  window: missing
  lamp: placeholder
defects (ordered by visual impact):
  1. no windows — hero — lit facade cells
```json
{"verdict": "FAIL", "defects": [
  {"part": "window", "defect": "no windows", "view": "hero",
   "suggested_ops": [
     {"op": "adjust_world", "strength": 0.4},
     {"op": "run_arbitrary_python", "code": "import bpy"},
     {"op": "create_mesh_primitive"}
   ]}
]}
```"""
    res = T.h_scene_verifier_ops(ctx, report)
    assert res["ok"] and res["verdict"] == "FAIL"
    assert res["ledger"] == {"window": "missing", "lamp": "placeholder"}
    assert [o["op"] for o in res["ops"]] == ["adjust_world"]
    assert len(res["dropped_ops"]) == 2  # unknown op + missing required param


def test_scene_verifier_ops_handles_bare_json_and_no_json(ctx):
    bare = 'VERDICT: PASS\nsome prose {"verdict": "PASS", "defects": [{"part": "x", "defect": "d", "view": "hero", "suggested_ops": [{"op": "delete_object", "name": "stale"}]}]}'
    res = T.h_scene_verifier_ops(ctx, bare)
    assert res["verdict"] == "PASS"
    assert [o["op"] for o in res["ops"]] == ["delete_object"]
    empty = T.h_scene_verifier_ops(ctx, "VERDICT: FAIL\nno json at all")
    assert empty["verdict"] == "FAIL" and empty["ops"] == [] and empty["defects"] == []


def test_scene_verifier_ops_resolves_name_hints(ctx):
    """A vision-only verifier can't see object names — name_hint must resolve
    to exactly one scene object or the op drops with a proper error."""
    T.h_project_create_scene_workspace(ctx, "demo",
                                       {"task_id": "t", "brief": "b", "output_mode": "still"})
    report = '''VERDICT: FAIL
```json
{"defects": [
  {"part": "lantern", "defect": "floating hook", "view": "all",
   "suggested_ops": [{"op": "delete_object", "name_hint": "lantern handle"}]},
  {"part": "pot", "defect": "hovering", "view": "back",
   "suggested_ops": [{"op": "set_object_transform", "name_hint": "big plant pot", "location": [0,0,0]}]},
  {"part": "x", "defect": "ghost", "view": "v4",
   "suggested_ops": [{"op": "delete_object", "name_hint": "zzz nothing"}]}
]}
```'''
    res = T.h_scene_verifier_ops(
        ctx, report,
        object_names=["lantern_handle", "plant_c_pot", "patio_floor"])
    kept = {o["op"]: o for o in res["ops"]}
    assert kept["delete_object"]["name"] == "lantern_handle"
    assert kept["set_object_transform"]["target"] == "plant_c_pot"
    assert len(res["dropped_ops"]) == 1  # unresolvable hint drops cleanly


def test_scene_verifier_ops_merges_class_routing(ctx):
    """Class-tagged defect lines route to template ops/plans even without
    suggested_ops — the mechanical + planning layers merge."""
    T.h_project_create_scene_workspace(ctx, "demo",
                                       {"task_id": "t", "brief": "b", "output_mode": "still"})
    report = """VERDICT: FAIL
ledger:
  chair: placeholder
defects (ordered by visual impact):
  1. [class:lighting] scene too dark — hero — needs warm fill — affects: scene
  2. [class:placeholder] chair is a cube — profile — needs real anatomy — affects: chair
```json
{"verdict": "FAIL", "defects": []}
```"""
    res = T.h_scene_verifier_ops(ctx, report)
    assert res["ok"] and res["verdict"] == "FAIL"
    assert any(o["op"] == "adjust_world" for o in res["ops"])  # lighting class
    assert any(o["op"] == "add_light" for o in res["ops"])
    # placeholder without inspection resolves no target -> rebuild plan
    assert res["plans"] and "anatomy" in res["plans"][0]
