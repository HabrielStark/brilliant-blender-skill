"""Security test: bridge command validator + allowlist sync (SRS 13, 18)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATORS = ROOT / "addon" / "blender_cinematic_agent" / "validators.py"
BRIDGE_PATHS = ROOT / "addon" / "blender_cinematic_agent" / "bridge_paths.py"


def _load_validators():
    # Load the module directly; the package __init__ imports bpy (unavailable here).
    spec = importlib.util.spec_from_file_location("bcas_validators", VALIDATORS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_bridge_paths():
    spec = importlib.util.spec_from_file_location("bcas_bridge_paths", BRIDGE_PATHS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def v():
    return _load_validators()


def test_unknown_action_rejected(v):
    assert v.validate_command({"action": "exec_arbitrary"}) is not None
    assert v.validate_command("not a dict") is not None


def test_known_action_ok(v):
    assert v.validate_command({"action": "ping"}) is None
    assert v.validate_command({"action": "inspect"}) is None
    assert v.validate_command({"action": "render_preview", "output": "preview.png"}) is None


def test_write_actions_require_output_path(v):
    assert v.validate_command({"action": "render_preview"}) is not None
    assert v.validate_command({"action": "render_final", "output": ""}) is not None
    assert v.validate_command({"action": "export_glb", "output": 123}) is not None


def test_recipe_op_allowlist(v):
    ok = {"action": "apply_recipe", "recipe": {"operations": [
        {"op": "create_mesh_primitive", "type": "cube", "name": "c"}]}}
    assert v.validate_command(ok) is None
    bad = {"action": "apply_recipe", "recipe": {"operations": [{"op": "run_shell"}]}}
    assert v.validate_command(bad) is not None


def test_faceted_hero_body_recipe_allowed_by_bridge(v):
    cmd = {"action": "apply_recipe", "recipe": {"operations": [
        {"op": "create_faceted_hero_body", "name": "hero_faceted_luxury_body",
         "segments": 40, "rings": 16, "collection": "SUBJECT"}
    ]}}
    assert v.validate_command(cmd) is None


def test_allowlist_in_sync_with_core(v):
    from blender_cinematic.recipes import ALLOWED_OPS as CORE_OPS
    assert set(v.ALLOWED_OPS) == set(CORE_OPS), "addon/bridge op allowlist drifted from core recipes"


def test_bridge_output_sandbox_rejects_traversal(tmp_path):
    bp = _load_bridge_paths()
    resolver = bp.BridgeWorkspaceResolver(tmp_path / "ws")
    inside = resolver.resolve_output("renders/preview.png")
    assert inside.is_relative_to(tmp_path / "ws")
    with pytest.raises(bp.BridgePathSandboxError):
        resolver.resolve_output(tmp_path / "escape.png")
