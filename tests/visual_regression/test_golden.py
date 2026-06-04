"""Visual regression (SRS 17.3): deterministic small render + SSIM tolerance.

Renders the same tiny scene twice and asserts the two renders are structurally
near-identical (SSIM high). Does not require pixel-perfect cross-GPU output.
"""
import pytest

from blender_cinematic import runner
from blender_cinematic.imaging import image_sanity, render_sanity_issues, ssim
from blender_cinematic.workspace import task_workspace

pytestmark = [pytest.mark.blender, pytest.mark.slow]

BUDGET = {"selected_engine": "EEVEE", "preview_engine": "EEVEE", "device": "CPU",
          "preview_resolution": [256, 256], "final_resolution": [256, 256],
          "samples": 16, "quality_profile": "safe_laptop"}

RECIPE = {"operations": [
    {"op": "ensure_standard_collections"},
    {"op": "create_mesh_primitive", "type": "plane", "name": "golden_ground", "size": 6, "collection": "ENVIRONMENT"},
    {"op": "create_mesh_primitive", "type": "cube", "name": "golden_device_body", "size": 2, "collection": "SUBJECT"},
    {"op": "apply_transform", "target": "golden_device_body", "scale": True},
    {"op": "add_bevel_modifier", "target": "golden_device_body", "width": 0.08, "segments": 3},
    {"op": "create_mesh_primitive", "type": "cube", "name": "golden_front_panel", "size": 1,
        "location": [0, -1.03, 0.08], "scale": [0.7, 0.025, 0.42], "collection": "SUBJECT"},
    {"op": "apply_transform", "target": "golden_front_panel", "scale": True},
    {"op": "add_bevel_modifier", "target": "golden_front_panel", "width": 0.025, "segments": 2},
    {"op": "create_linear_markers", "name_prefix": "golden_panel_tick", "start": [-0.42, -1.07, 0.22],
        "step": [0.14, 0, 0], "count": 7, "size": [0.055, 0.018, 0.15], "collection": "SUBJECT"},
    {"op": "create_radial_markers", "name_prefix": "golden_corner_screw", "center": [0, -1.08, 0.08],
        "radius": 0.68, "count": 6, "size": [0.045, 0.045, 0.018], "collection": "SUBJECT"},
    {"op": "create_material", "schema": {"name": "golden_body_red", "preset": "matte_plastic",
        "target_objects": ["golden_device_body"], "pbr": {"base_color": [0.8, 0.1, 0.1, 1], "roughness": 0.5}}},
    {"op": "create_material", "schema": {"name": "golden_panel_dark", "preset": "rubber_dark",
        "target_objects": ["golden_front_panel"], "pbr": {"base_color": [0.035, 0.035, 0.04, 1], "roughness": 0.7}}},
    {"op": "create_material", "schema": {"name": "golden_detail_warm", "preset": "emissive_neon",
        "target_objects": ["golden_panel_tick_01", "golden_panel_tick_02", "golden_panel_tick_03",
            "golden_panel_tick_04", "golden_panel_tick_05", "golden_panel_tick_06", "golden_panel_tick_07",
            "golden_corner_screw_01", "golden_corner_screw_02", "golden_corner_screw_03",
            "golden_corner_screw_04", "golden_corner_screw_05", "golden_corner_screw_06"],
        "pbr": {"base_color": [1.0, 0.68, 0.28, 1], "emission_color": [1.0, 0.48, 0.16, 1],
            "emission_strength": 0.35}}},
    {"op": "create_material", "schema": {"name": "golden_ground_mat", "preset": "stone_concrete",
        "target_objects": ["golden_ground"], "pbr": {"base_color": [0.42, 0.42, 0.4, 1], "roughness": 0.84}}},
    {"op": "create_lighting_rig", "schema": {"lighting_rig": "three_point_soft",
        "lights": [{"name": "key", "type": "AREA", "power": 500, "size": 5, "position_role": "front_left_high"}],
        "world": {"color": [0.05, 0.05, 0.06], "strength": 0.5}}},
    {"op": "create_camera", "schema": {"camera_name": "cam", "preset": "hero_low_angle",
        "target": "golden_device_body", "location": [3, -3, 2], "lens": {"focal_length_mm": 50}}},
    {"op": "set_scene_metadata", "data": {"final_camera": "cam"}},
]}


def _render(blender_exe, base, name):
    out = base / "iterations" / f"{name}.png"
    res = runner.run_job(runner.build_job("full_pipeline", base, base / "final" / f"{name}.blend",
                                          budget=BUDGET, recipe=RECIPE, output={"image": str(out)}),
                         blender_exe, 240)
    assert res["ok"], res
    assert out.exists()
    return out


def test_deterministic_render_is_stable(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "golden")
    a = _render(blender_exe, base, "a")
    b = _render(blender_exe, base, "b")
    assert render_sanity_issues(image_sanity(a)) == []
    score = ssim(a, b)
    assert score > 0.97, f"renders drifted: SSIM={score}"
