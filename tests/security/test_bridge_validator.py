"""Security test: bridge command validator + allowlist sync (SRS 13, 18)."""
import importlib.util
import math
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


@pytest.mark.parametrize("recipe", [
    [],
    "not an object",
    {"operations": ["not an object"]},
    {"operations": [{"op": ["not", "a", "string"]}]},
    {"operations": [{"op": "create_mesh_primitive", "params": []}]},
])
def test_malformed_recipe_shapes_are_rejected_without_raising(v, recipe):
    assert v.validate_command({"action": "apply_recipe", "recipe": recipe}) is not None


def test_recipe_operation_count_is_bounded(v):
    at_limit = [{"op": "ensure_standard_collections"}] * v.MAX_RECIPE_OPERATIONS
    assert v.validate_command({
        "action": "apply_recipe", "recipe": {"operations": at_limit},
    }) is None

    over_limit = at_limit + [{"op": "ensure_standard_collections"}]
    error = v.validate_command({
        "action": "apply_recipe", "recipe": {"operations": over_limit},
    })
    assert str(v.MAX_RECIPE_OPERATIONS) in error


def test_recipe_nesting_and_container_width_are_bounded(v):
    nested = "leaf"
    for _ in range(v.MAX_RECIPE_DEPTH + 1):
        nested = [nested]
    deep = {"operations": [{"op": "set_scene_metadata", "data": nested}]}
    assert "nesting depth" in v.validate_command({"action": "apply_recipe", "recipe": deep})

    wide = {
        "operations": [{
            "op": "set_scene_metadata",
            "data": list(range(v.MAX_RECIPE_CONTAINER_ITEMS + 1)),
        }],
    }
    assert "item count" in v.validate_command({"action": "apply_recipe", "recipe": wide})


def test_recipe_strings_node_count_and_non_finite_numbers_are_bounded(v):
    long_string = "x" * (v.MAX_RECIPE_STRING_LENGTH + 1)
    long_recipe = {"operations": [{"op": "set_scene_metadata", "data": {"x": long_string}}]}
    assert "string" in v.validate_command({"action": "apply_recipe", "recipe": long_recipe})

    shared = list(range(v.MAX_RECIPE_CONTAINER_ITEMS))
    node_bomb = {"operations": [
        {"op": "set_scene_metadata", "data": shared}
        for _ in range((v.MAX_RECIPE_NODES // len(shared)) + 1)
    ]}
    assert "node count" in v.validate_command({"action": "apply_recipe", "recipe": node_bomb})

    for value in (math.inf, -math.inf, math.nan):
        non_finite = {"operations": [{"op": "set_scene_metadata", "data": {"x": value}}]}
        assert "finite" in v.validate_command({"action": "apply_recipe", "recipe": non_finite})


@pytest.mark.parametrize(("operation", "field"), [
    ({"op": "add_subdivision", "target": "hero", "levels": 9}, "levels"),
    ({"op": "add_array_modifier", "target": "hero", "count": 1001}, "count"),
    ({"op": "create_energy_burst_streaks", "name_prefix": "s", "count": 161}, "count"),
    ({
        "op": "add_modifier", "target": "hero", "modifier": "SUBSURF",
        "params": {"render_levels": 9},
    }, "render_levels"),
])
def test_expensive_operation_parameters_are_rejected(v, operation, field):
    error = v.validate_command({
        "action": "apply_recipe", "recipe": {"operations": [operation]},
    })
    assert field in error


def test_expensive_operation_parameters_accept_documented_limits(v):
    operations = [
        {"op": "add_subdivision", "target": "hero", "levels": 8, "render_levels": 8},
        {"op": "add_array_modifier", "target": "hero", "count": 1000},
        {"op": "create_curve_tube", "name": "curve", "points": [[0, 0, 0]] * v.MAX_CURVE_TUBE_POINTS},
        {"op": "create_text_label", "name": "label", "text": "x" * v.MAX_TEXT_LABEL_CHARS},
    ]
    assert v.validate_command({
        "action": "apply_recipe", "recipe": {"operations": operations},
    }) is None


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
