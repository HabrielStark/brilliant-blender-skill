"""Headless Blender integration tests (SRS 17.2). Auto-skip without Blender."""
import base64
import math

import pytest

from blender_cinematic import runner
from blender_cinematic.glb import validate_glb
from blender_cinematic.imaging import image_sanity, render_sanity_issues
from blender_cinematic.linters import lint_scene
from blender_cinematic.workspace import task_workspace

pytestmark = pytest.mark.blender

PREVIEW_BUDGET = {"selected_engine": "EEVEE", "preview_engine": "EEVEE", "device": "CPU",
                  "preview_resolution": [320, 180], "final_resolution": [640, 360],
                  "samples": 16, "quality_profile": "balanced"}

TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFElEQVR4nGP8z8Dwn4GBgYGJAQoAHxcC"
    "AqGfS4QAAAAASUVORK5CYII="
)

BASE_RECIPE = [
    {"op": "ensure_standard_collections"},
    {"op": "create_mesh_primitive", "type": "plane", "name": "ground", "size": 12, "collection": "ENVIRONMENT"},
    {"op": "create_mesh_primitive", "type": "uv_sphere", "name": "hero_core", "size": 2, "collection": "SUBJECT"},
    {"op": "set_smooth_shading", "target": "hero_core", "smooth": True},
    {"op": "add_bevel_modifier", "target": "hero_core", "width": 0.02, "segments": 2},
    {"op": "create_material", "schema": {
        "name": "metal_body",
        "preset": "brushed_metal",
        "target_objects": ["hero_core"],
        "pbr": {"base_color": [0.1, 0.12, 0.18, 1], "metallic": 1.0, "roughness": 0.3},
        "procedural": {
            "noise": True,
            "noise_scale": 48,
            "bump_strength": 0.03,
            "color_ramp": {
                "noise_scale": 24,
                "detail": 8,
                "colors": [[0.04, 0.05, 0.07, 1], [0.32, 0.42, 0.6, 1]],
            },
        },
    }},
    {"op": "create_lighting_rig", "schema": {"lighting_rig": "studio_product_large_softbox",
        "lights": [{"name": "key_soft", "type": "AREA", "power": 600, "size": 6, "position_role": "front_left_high"},
                   {"name": "rim_cold", "type": "AREA", "power": 200, "size": 2, "color": [0.4, 0.6, 1.0], "position_role": "rim"}],
        "world": {"color": [0.02, 0.02, 0.03], "strength": 0.4}}},
    {"op": "create_camera", "schema": {"camera_name": "camera_hero", "preset": "macro_product",
        "target": "hero_core", "location": [5.2, -6.5, 3.2],
        "lens": {"focal_length_mm": 50, "dof": True, "focus_target": "hero_core"}}},
    {"op": "set_scene_metadata", "data": {"final_camera": "camera_hero"}},
]


def test_full_pipeline_builds_renders_exports(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "itest")
    preview = base / "iterations" / "iter_01_preview.png"
    glb = base / "final" / "export_final.glb"
    job = runner.build_job("full_pipeline", base, base / "final" / "scene.blend",
                           manifest={"task_id": "itest", "output_mode": "web_asset"},
                           budget=PREVIEW_BUDGET, recipe={"operations": BASE_RECIPE},
                           output={"image": str(preview), "glb": str(glb)})
    res = runner.run_job(job, blender_exe, timeout=300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]
    assert preview.exists() and glb.exists()
    assert render_sanity_issues(image_sanity(preview)) == []
    v = validate_glb(glb, max_mb=20)
    assert v["ok"], v
    assert v["info"]["meshes"] >= 2


def test_full_pipeline_without_camera_returns_ok_false(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "missing_camera")
    blend = base / "final" / "scene.blend"
    res = runner.run_job(
        runner.build_job(
            "full_pipeline",
            base,
            blend,
            budget=PREVIEW_BUDGET,
            recipe={"operations": [{"op": "ensure_standard_collections"}]},
            output={"image": str(base / "iterations" / "iter_01_preview.png")},
        ),
        blender_exe,
        timeout=300,
    )
    assert res["ok"] is False
    assert res["render"]["error"] == "no active camera"


def test_inspect_feeds_linters(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "itest2")
    blend = base / "final" / "scene.blend"
    runner.run_job(runner.build_job("full_pipeline", base, blend,
                                    budget=PREVIEW_BUDGET, recipe={"operations": BASE_RECIPE},
                                    output={"image": str(base / "iterations" / "p.png")}), blender_exe, 300)
    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)
    inspection = insp["inspection"]
    assert inspection["active_camera"]["name"] == "camera_hero"
    metal_body = next(m for m in inspection["materials"] if m["name"] == "metal_body")
    assert metal_body["node_count"] >= 6
    assert "noise_color_ramp" in metal_body["procedural_features"]
    assert "noise_bump" in metal_body["procedural_features"]
    lint = lint_scene(inspection, {"output_mode": "still", "style": {"mood": "premium"}})
    assert not lint.errors, [i.message for i in lint.errors]


def test_authored_shader_stack_builds_real_nodes_and_texture(blender_exe, tmp_path):
    texture_path = tmp_path / "label_checker_source.png"
    texture_path.write_bytes(base64.b64decode(TINY_PNG))
    _, base = task_workspace(tmp_path, "shader_stack")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_material", "schema": {
            "name": "hero_authored_shader_stack",
            "preset": "brushed_metal",
            "target_objects": ["hero_core"],
            "pbr": {"base_color": [0.18, 0.2, 0.22, 1], "metallic": 1.0, "roughness": 0.34},
            "procedural": {
                "noise": True,
                "noise_scale": 64,
                "bump_strength": 0.026,
                "color_ramp": {
                    "noise_scale": 26,
                    "detail": 10,
                    "colors": [[0.05, 0.06, 0.07, 1], [0.42, 0.48, 0.58, 1]],
                },
                "checker": {"scale": 18, "colors": [[0.03, 0.035, 0.04, 1], [0.82, 0.76, 0.58, 1]]},
                "wave": {"scale": 54, "distortion": 1.1, "bump_strength": 0.018},
                "roughness_variation": {
                    "noise_scale": 42,
                    "detail": 11,
                    "min_roughness": 0.18,
                    "max_roughness": 0.76,
                },
                "edge_wear": "heavy",
                "scanlines": True,
                "scanline_scale": 90,
                "scanline_strength": 0.2,
                "anisotropic": 0.8,
                "anisotropic_rotation": 0.18,
                "image_textures": [
                    {"path": str(texture_path), "role": "base_color", "color_space": "sRGB",
                     "projection": "uv", "repeat": [1.0, 1.0], "offset": [0.0, 0.0]},
                    {"generated": "microprint_label", "role": "displacement", "color_space": "Non-Color",
                     "projection": "generated", "repeat": [3.0, 2.0], "strength": 0.7},
                ],
            },
        }},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]

    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    mat = next(m for m in insp["materials"] if m["name"] == "hero_authored_shader_stack")
    features = set(mat["procedural_features"].split(","))
    assert {
        "noise_bump",
        "noise_color_ramp",
        "checker_texture",
        "wave_bump",
        "roughness_variation",
        "edge_wear_heavy",
        "scanlines",
        "anisotropic_brush",
        "image_texture_base_color",
        "image_texture_displacement",
    }.issubset(features)
    assert mat["node_count"] >= 25
    assert mat["link_count"] >= 22
    assert "NG_hero_authored_shader_stack_EdgeWearAO" in mat["node_names"]
    assert "NG_hero_authored_shader_stack_ScanlineWave" in mat["node_names"]
    assert "NG_hero_authored_shader_stack_RoughnessRamp" in mat["node_names"]
    assert set(mat["image_texture_roles"].split(",")) == {"base_color", "displacement"}
    assert str(texture_path) not in insp["missing_files"]
    lint = lint_scene(insp, {"output_mode": "still", "style": {"mood": "premium material study"}})
    assert not lint.errors, [i.message for i in lint.errors]


def test_turntable_animation_in_glb(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "anim")
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_animation", "schema": {"animation_name": "spin", "mode": "turntable",
            "frame_start": 1, "frame_end": 24, "fps": 24, "targets": ["hero_core"],
            "export": {"include_in_glb": True, "clip_name": "Turntable"}}},
    ]}
    glb = base / "final" / "anim.glb"
    res = runner.run_job(runner.build_job("full_pipeline", base, base / "final" / "scene.blend",
                                          budget=PREVIEW_BUDGET, recipe=recipe,
                                          output={"image": str(base / "iterations" / "p.png"), "glb": str(glb)}),
                         blender_exe, 300)
    assert res["ok"], res
    anim_ops = [o for o in res["operations"] if o.get("op") == "create_animation"]
    assert anim_ops and anim_ops[0]["keyed"] == ["hero_core"]
    insp = runner.run_job(
        runner.build_job("inspect", base, base / "final" / "scene.blend"),
        blender_exe,
        120,
    )["inspection"]
    anim = insp["animation"]
    assert anim["moving_object_count"] >= 1
    assert anim["max_sampled_rotation_delta"] >= 3.0
    hero_motion = next(o for o in anim["sampled_objects"] if o["name"] == "hero_core")
    assert hero_motion["sample_count"] == 5  # quarter-phase sampling
    v = validate_glb(glb)
    assert v["info"]["animations"] >= 1, v


def test_turntable_animation_orbits_assembly_parts(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "anim_orbit")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_mesh_primitive", "type": "cube", "name": "hero_side_badge_left",
         "size": 0.2, "location": [-1.0, 0.0, 0.9], "collection": "SUBJECT"},
        {"op": "create_mesh_primitive", "type": "cube", "name": "hero_side_badge_right",
         "size": 0.2, "location": [1.0, 0.0, 0.9], "collection": "SUBJECT"},
        {"op": "create_animation", "schema": {"animation_name": "assembly_spin", "mode": "turntable",
            "frame_start": 1, "frame_end": 24, "fps": 24,
            "targets": ["hero_core", "hero_side_badge_left", "hero_side_badge_right"],
            "export": {"include_in_glb": True, "clip_name": "AssemblyTurntable"}}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]

    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    sampled = {o["name"]: o for o in insp["animation"]["sampled_objects"]}
    assert sampled["hero_side_badge_left"]["max_location_delta"] >= 1.8
    assert sampled["hero_side_badge_right"]["max_location_delta"] >= 1.8
    assert sampled["hero_core"]["max_rotation_delta"] >= 3.0


def test_loop_idle_produces_seamless_subtle_motion(blender_exe, tmp_path):
    """loop_idle must actually keyframe a gentle sway that returns to rest."""
    _, base = task_workspace(tmp_path, "anim_idle")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_animation", "schema": {"animation_name": "idle",
            "mode": "loop_idle", "frame_start": 1, "frame_end": 48, "fps": 24,
            "targets": ["hero_core"], "params": {"sway_degrees": 8.0}}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe),
        blender_exe, 300)
    assert res["ok"], res
    insp = runner.run_job(runner.build_job("inspect", base, blend),
                          blender_exe, 120)["inspection"]
    anim = insp["animation"]
    assert anim["moving_object_count"] >= 1
    hero = next(o for o in anim["sampled_objects"] if o["name"] == "hero_core")
    # 8deg sway -> ~0.14rad delta at quarter frames; rests at fs/fe
    assert 0.1 < hero["max_rotation_delta"] < 0.35
    assert hero["sample_count"] == 5


def test_geometry_node_recipe_dispatch_is_inspectable(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "gn_recipe")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_geometry_nodes", "schema": {
            "node_group_name": "GN_TestPanelWall",
            "recipe": "GN_PanelWall",
            "target_object": "ground",
            "inputs": {"panel_count": 18, "panel_depth": 0.04, "seed": 11},
            "export_policy": {"max_generated_faces": 8000},
        }},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]

    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    gn = next(g for g in insp["geometry_nodes"] if g["name"] == "GN_TestPanelWall")
    assert gn["recipe"] == "GN_PanelWall"
    assert gn["seed"] == 11
    assert gn["generated_faces"] == 18
    assert gn["detail_count"] == 18
    assert "panel_wall_plate" in gn["detail_roles"]
    assert gn["node_count"] >= 6
    assert gn["link_count"] >= 5
    generated = [o for o in insp["objects"] if o.get("gn_recipe") == "GN_PanelWall"]
    assert len(generated) == 18
    assert {o.get("gn_role") for o in generated} == {"panel_wall_plate"}
    assert all(o["materials"] for o in generated)


def test_geometry_node_recipes_create_distinct_visual_detail_roles(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "gn_distinct")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_geometry_nodes", "schema": {
            "node_group_name": "GN_TestCableBundle",
            "recipe": "GN_CableBundle",
            "target_object": "hero_core",
            "inputs": {"cable_count": 4, "cable_radius": 0.025, "seed": 21},
            "export_policy": {"max_generated_faces": 8000},
        }},
        {"op": "create_geometry_nodes", "schema": {
            "node_group_name": "GN_TestOrbitalRings",
            "recipe": "GN_OrbitalRings",
            "target_object": "hero_core",
            "inputs": {"ring_count": 3, "ring_size": 0.02, "seed": 22},
            "export_policy": {"max_generated_faces": 8000},
        }},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]

    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    cable_group = next(g for g in insp["geometry_nodes"] if g["name"] == "GN_TestCableBundle")
    ring_group = next(g for g in insp["geometry_nodes"] if g["name"] == "GN_TestOrbitalRings")
    assert "cable_curve" in cable_group["detail_roles"]
    assert "orbital_ring" in ring_group["detail_roles"]
    cable_details = [o for o in insp["objects"] if o.get("gn_role") == "cable_curve"]
    ring_details = [o for o in insp["objects"] if o.get("gn_role") == "orbital_ring"]
    assert len(cable_details) == 4
    assert len(ring_details) == 3
    assert {o["type"] for o in cable_details} == {"CURVE"}
    assert {o["type"] for o in ring_details} == {"MESH"}


def test_craft_detail_ops_create_real_blender_objects(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "craft_details")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_material", "schema": {
            "name": "label_white",
            "preset": "glossy_plastic",
            "pbr": {"base_color": [0.92, 0.9, 0.82, 1], "roughness": 0.24},
        }},
        {"op": "create_material", "schema": {
            "name": "trim_dark",
            "preset": "rubber_dark",
            "pbr": {"base_color": [0.025, 0.026, 0.03, 1], "roughness": 0.7},
            "procedural": {"noise": True, "noise_scale": 34, "bump_strength": 0.012},
        }},
        {"op": "create_decal_plane", "name": "hero_label_decal_plate",
         "location": [0, -1.08, 0.24], "rotation": [76, 0, 0], "size": [0.9, 0.28, 0.012],
         "collection": "SUBJECT", "material": "trim_dark", "parent": "hero_core"},
        {"op": "create_text_label", "name": "hero_brand_label_text", "text": "BCAS",
         "location": [0, -1.095, 0.25], "rotation": [76, 0, 0], "size": 0.16,
         "collection": "SUBJECT", "material": "label_white", "parent": "hero_core"},
        {"op": "create_curve_tube", "name": "hero_side_cable_tube",
         "points": [[-0.9, -0.75, 0.2], [-1.2, -0.32, 0.64], [-0.72, 0.18, 0.94]],
         "bevel_depth": 0.022, "resolution": 3, "collection": "SUBJECT",
         "material": "trim_dark", "parent": "hero_core"},
        {"op": "create_fastener_pattern", "name_prefix": "hero_cover_screw", "pattern": "radial",
         "center": [0, -1.11, 0.24], "radius": 0.43, "count": 6, "size": 0.06,
         "rotation": [76, 0, 0], "collection": "SUBJECT", "material": "label_white",
         "parent": "hero_core"},
        {"op": "create_panel_cutlines", "name_prefix": "hero_panel_seam",
         "start": [-0.42, -1.12, 0.42], "step": [0.21, 0, 0], "count": 5,
         "size": [0.15, 0.012, 0.012], "rotation": [76, 0, 0],
         "collection": "SUBJECT", "material": "trim_dark", "parent": "hero_core"},
        {"op": "create_grille", "name_prefix": "hero_front_vent",
         "start": [-0.24, -1.13, -0.08], "step": [0.08, 0, 0], "count": 7,
         "slat_size": [0.035, 0.28, 0.018], "rotation": [76, 0, 0],
         "collection": "SUBJECT", "material": "trim_dark", "parent": "hero_core"},
        {"op": "create_surface_microdetails", "name_prefix": "hero_surface_wear_microline",
         "pattern": "linear", "start": [-0.36, -1.125, 0.52], "step": [0.14, 0, -0.018],
         "direction": [1, 0, 0], "count": 4, "length": 0.11, "bevel_depth": 0.004,
         "waviness": 0.006, "rotation": [76, 0, 0], "collection": "SUBJECT",
         "material": "label_white", "parent": "hero_core"},
        {"op": "create_radial_markers", "name_prefix": "hero_dial_index_marker",
         "center": [0, -1.125, 0.24], "radius": 0.26, "count": 4,
         "size": [0.025, 0.08, 0.014], "collection": "SUBJECT",
         "material": "label_white", "parent": "hero_core", "role": "hour_marker"},
        {"op": "create_linear_markers", "name_prefix": "hero_trim_stitch_marker",
         "start": [-0.18, -1.13, -0.22], "step": [0.12, 0, 0], "count": 4,
         "size": [0.025, 0.055, 0.014], "rotation": [76, 0, 0],
         "collection": "SUBJECT", "material": "label_white", "parent": "hero_core",
         "role": "trim_stitch"},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]
    assert render_sanity_issues(image_sanity(base / "iterations" / "p.png")) == []

    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    objects = {o["name"]: o for o in insp["objects"]}
    assert objects["hero_brand_label_text"]["type"] == "FONT"
    assert objects["hero_brand_label_text"]["craft_role"] == "text_label"
    assert "label_white" in objects["hero_brand_label_text"]["materials"]
    assert objects["hero_side_cable_tube"]["type"] == "CURVE"
    assert objects["hero_side_cable_tube"]["craft_role"] == "curve_tube"
    fasteners = [o for o in insp["objects"] if o["craft_role"] == "fastener"]
    cutlines = [o for o in insp["objects"] if o["craft_role"] == "panel_cutline"]
    grille = [o for o in insp["objects"] if o["craft_role"] == "grille_slat"]
    microdetails = [o for o in insp["objects"] if o["craft_role"] == "surface_microdetail"]
    hour_markers = [o for o in insp["objects"] if o["craft_role"] == "hour_marker"]
    trim_stitches = [o for o in insp["objects"] if o["craft_role"] == "trim_stitch"]
    assert len(fasteners) == 6
    assert len(cutlines) == 5
    assert len(grille) == 7
    assert len(microdetails) == 4
    assert len(hour_markers) == 4
    assert len(trim_stitches) == 4
    assert all(o["type"] == "MESH" and o["materials"] for o in fasteners + cutlines + grille)
    assert all(o["type"] == "MESH" and o["materials"] for o in hour_markers + trim_stitches)
    assert all(o["type"] == "CURVE" and o["materials"] for o in microdetails)
    assert all(o["craft_source"] == "hero_core" for o in fasteners + cutlines + grille)
    assert all(o["craft_source"] == "hero_core" for o in hour_markers + trim_stitches)
    assert all(o["craft_source"] == "hero_core" for o in microdetails)


def test_scroll_linked_animation_writes_camera_path_metadata(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "scroll_anim")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_animation", "schema": {
            "animation_name": "ScrollCameraMove",
            "mode": "scroll_linked",
            "frame_start": 1,
            "frame_end": 90,
            "fps": 24,
            "targets": ["hero_core"],
            "camera": {
                "name": "camera_hero",
                "start_location": [5.2, -6.5, 3.2],
                "end_location": [2.8, -3.6, 2.4],
                "dof_target": "hero_core",
            },
            "export": {"include_in_glb": True, "clip_name": "ScrollCameraMove"},
        }},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        manifest={"task_id": "scroll", "output_mode": "interactive_web"},
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    anim_ops = [o for o in res["operations"] if o.get("op") == "create_animation"]
    assert anim_ops and anim_ops[0]["camera_path"] is True

    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    camera_obj = next(o for o in insp["objects"] if o["name"] == "camera_hero")
    assert camera_obj["location"] == pytest.approx([5.2, -6.5, 3.2], abs=0.001)
    path = insp["camera_path_json"]
    assert path["schema"] == "camera_path/0.1"
    assert len(path["samples"]) >= 9
    first = path["samples"][0]["position"]
    last = path["samples"][-1]["position"]
    distance = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, last)))
    assert distance >= 3.0
    assert insp["animation"]["camera_animated"] is True
    assert insp["animation"]["camera_sampled_motion"]["max_location_delta"] >= 3.0
    lint = lint_scene(insp, {"output_mode": "interactive_web"})
    assert not [i for i in lint.errors if i.code == "animation.scroll_path"]


def test_organic_fluted_body_builder_survives_blender_pipeline(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "organic_body")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "create_mesh_primitive", "type": "plane", "name": "ground", "size": 8, "collection": "ENVIRONMENT"},
        {"op": "create_organic_fluted_body", "name": "organic_fluted_soft_body",
         "location": [0, 0, 0.35], "radius": 0.58, "height": 1.25,
         "segments": 48, "rings": 14, "lobes": 9, "waist": 0.2,
         "rim_wave": 0.12, "twist_degrees": 36, "collection": "SUBJECT"},
        {"op": "create_material", "schema": {"name": "organic_body_skin", "preset": "matte_plastic",
            "target_objects": ["organic_fluted_soft_body"],
            "pbr": {"base_color": [0.52, 0.28, 0.32, 1], "roughness": 0.68},
            "procedural": {"noise": True, "noise_scale": 24, "bump_strength": 0.02}}},
        {"op": "create_material", "schema": {"name": "petal_soft_test", "preset": "matte_plastic",
            "pbr": {"base_color": [0.72, 0.38, 0.48, 1], "roughness": 0.68}}},
        {"op": "create_organic_surface_details", "name_prefix": "organic_test_petal_surface",
         "pattern": "radial", "center": [0, 0, 1.25], "radius": 0.42, "count": 5,
         "length": 0.32, "width": 0.11, "curl": 0.045, "bend": 0.02,
         "collection": "SUBJECT", "material": "petal_soft_test"},
        {"op": "create_lighting_rig", "schema": {"lighting_rig": "organic_softbox",
            "lights": [{"name": "key_soft", "type": "AREA", "power": 400, "size": 5,
                        "position_role": "front_left_high"}],
            "world": {"color": [0.04, 0.035, 0.03], "strength": 0.35}}},
        {"op": "create_camera", "schema": {"camera_name": "camera_organic", "preset": "macro_product",
            "target": "organic_fluted_soft_body", "look_at": [0, 0, 0.95],
            "location": [3.6, -5.0, 2.3],
            "lens": {"focal_length_mm": 55, "dof": True, "focus_target": "organic_fluted_soft_body"}}},
        {"op": "set_scene_metadata", "data": {"final_camera": "camera_organic"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]
    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    body = next(o for o in insp["objects"] if o["name"] == "organic_fluted_soft_body")
    assert body["faces"] >= 48 * 14
    assert body["smooth"] is True
    assert len(body["modifiers"]) >= 2
    assert "organic_body_skin" in body["materials"]
    petals = [o for o in insp["objects"] if o["name"].startswith("organic_test_petal_surface_")]
    assert len(petals) == 5
    assert all(o["craft_role"] == "organic_surface" for o in petals)


def test_energy_burst_streak_builder_survives_blender_pipeline(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "energy_streaks")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "create_mesh_primitive", "type": "uv_sphere", "name": "energy_core",
         "size": 0.5, "location": [0, 0, 1.2], "collection": "SUBJECT"},
        {"op": "create_material", "schema": {"name": "trail_violet_noise_emissive",
            "preset": "emissive_neon",
            "pbr": {"base_color": [0.54, 0.28, 1.0, 1],
                    "emission_color": [0.54, 0.28, 1.0, 1], "emission_strength": 1.2}}},
        {"op": "create_energy_burst_streaks", "name_prefix": "energy_trail_ribbon",
         "center": [0, 0, 1.2], "count": 6, "radius_min": 0.1, "radius_max": 0.2,
         "length_min": 0.3, "length_max": 0.52, "width": 0.03, "thickness": 0.004,
         "curl": 0.05, "fan_degrees": 140, "angle_degrees": 10, "segments": 10,
         "seed": 7, "collection": "SUBJECT", "material": "trail_violet_noise_emissive"},
        {"op": "create_lighting_rig", "schema": {"lighting_rig": "vfx_test_light",
            "lights": [{"name": "key_soft", "type": "AREA", "power": 220, "size": 4,
                        "position_role": "front_left_high"}],
            "world": {"color": [0.02, 0.02, 0.035], "strength": 0.3}}},
        {"op": "create_camera", "schema": {"camera_name": "camera_energy", "target": "energy_core",
            "look_at": [0, 0, 1.2], "location": [2.5, -4.5, 2.0],
            "lens": {"focal_length_mm": 58, "dof": True, "focus_target": "energy_core"}}},
        {"op": "set_scene_metadata", "data": {"final_camera": "camera_energy"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]
    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    streaks = [o for o in insp["objects"] if o["name"].startswith("energy_trail_ribbon_")]
    assert len(streaks) == 6
    assert all(o["faces"] >= 20 for o in streaks)
    assert all(o["smooth"] is True for o in streaks)
    assert all(len(o["modifiers"]) >= 2 for o in streaks)
    assert all(o["craft_role"] == "energy_streak" for o in streaks)


def test_faceted_hero_body_builder_survives_blender_pipeline(blender_exe, tmp_path):
    _, base = task_workspace(tmp_path, "faceted_hero")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "create_mesh_primitive", "type": "plane", "name": "stage", "size": 8, "collection": "ENVIRONMENT"},
        {"op": "create_material", "schema": {"name": "hero_dark_chrome_facets", "preset": "brushed_metal",
            "pbr": {"base_color": [0.045, 0.05, 0.06, 1], "metallic": 1.0, "roughness": 0.22},
            "procedural": {"noise": True, "noise_scale": 70, "bump_strength": 0.018}}},
        {"op": "create_faceted_hero_body", "name": "hero_faceted_luxury_body",
         "location": [0, 0, 1.15], "radius": 0.82, "height": 1.55,
         "segments": 40, "rings": 16, "facet_twist_degrees": 16,
         "shoulder": 0.62, "waist": 0.22, "facet_depth": 0.06,
         "bevel_width": 0.014, "collection": "SUBJECT", "material": "hero_dark_chrome_facets"},
        {"op": "create_lighting_rig", "schema": {"lighting_rig": "faceted_hero_test",
            "lights": [{"name": "key_strip", "type": "AREA", "power": 520, "size": 4,
                        "position_role": "front_left_high"}],
            "world": {"color": [0.03, 0.032, 0.04], "strength": 0.35}}},
        {"op": "create_camera", "schema": {"camera_name": "camera_faceted", "preset": "hero_low_angle",
            "target": "hero_faceted_luxury_body", "look_at": [0, 0, 1.18],
            "location": [3.6, -5.0, 2.2],
            "lens": {"focal_length_mm": 60, "dof": True, "focus_target": "hero_faceted_luxury_body"}}},
        {"op": "set_scene_metadata", "data": {"final_camera": "camera_faceted"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline",
        base,
        blend,
        budget=PREVIEW_BUDGET,
        recipe=recipe,
        output={"image": str(base / "iterations" / "p.png")},
    ), blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]
    insp = runner.run_job(runner.build_job("inspect", base, blend), blender_exe, 120)["inspection"]
    hero = next(o for o in insp["objects"] if o["name"] == "hero_faceted_luxury_body")
    assert hero["faces"] >= 40 * 16
    assert hero["smooth"] is False
    assert len(hero["modifiers"]) >= 2
    assert "hero_dark_chrome_facets" in hero["materials"]
    assert hero["flipped_normals"] is False


def test_in_pipeline_inspection_and_parented_data_api_object(blender_exe, tmp_path):
    """Regression: in-pipeline inspection must see evaluated transforms (no stale
    depsgraph), and data-API objects (FONT) parented to a moved object must keep
    their authored world position instead of collapsing to the parent origin."""
    _, base = task_workspace(tmp_path, "inspect_fresh")
    blend = base / "final" / "scene.blend"
    inspect_path = base / "iterations" / "iter_01_inspect.json"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_mesh_primitive", "type": "cube", "name": "mount_post",
         "size": 0.4, "location": [2.0, 0.0, 1.0], "collection": "SUBJECT"},
        {"op": "apply_transform", "target": "mount_post", "location": True},
        {"op": "create_text_label", "name": "badge_text", "text": "OK",
         "location": [3.0, 0.0, 2.0], "size": 0.3, "extrude": 0.01,
         "collection": "SUBJECT", "parent": "mount_post"},
    ]}
    res = runner.run_job(
        runner.build_job("full_pipeline", base, blend,
                         manifest={"task_id": "itest", "output_mode": "still"},
                         budget=PREVIEW_BUDGET, recipe=recipe,
                         output={"image": str(base / "iterations" / "p.png"),
                                 "inspect": str(inspect_path)}),
        blender_exe, timeout=300)
    assert res["ok"], res
    inspection = res["inspection"]
    badge = next(o for o in inspection["objects"] if o["name"] == "badge_text")
    assert badge["world_location"] == pytest.approx([3.0, 0.0, 2.0], abs=0.05)
    # In-pipeline inspection must produce evaluated camera-space bounds, not
    # the garbage/inverted boxes a stale depsgraph yields.
    boxes = [o["screen_bbox"] for o in inspection["objects"]
             if o["in_camera_frame"] and o.get("screen_bbox")]
    assert boxes, "expected camera-visible objects"
    for b in boxes:
        assert b[0] <= b[2] and b[1] <= b[3]
    assert inspect_path.exists()


def test_add_modifier_resolves_object_name_params(blender_exe, tmp_path):
    """Object-typed modifier params (BOOLEAN.object etc.) accept object names."""
    _, base = task_workspace(tmp_path, "mod_objref")
    blend = base / "final" / "scene.blend"
    glb = base / "final" / "export_final.glb"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_mesh_primitive", "type": "cube", "name": "boolean_cutter",
         "size": 0.8, "location": [0.6, 0, 1.0], "collection": "SUBJECT"},
        {"op": "add_modifier", "target": "hero_core", "modifier": "BOOLEAN",
         "params": {"object": "boolean_cutter", "operation": "DIFFERENCE"}},
        {"op": "add_modifier", "target": "hero_core", "modifier": "MIRROR",
         "params": {"use_axis[0]": True}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe,
        output={"glb": str(glb)}), blender_exe, 300)
    assert res["ok"], res
    ops = res["operations"]
    assert not [o for o in ops if o.get("error")], ops
    bool_op = next(o for o in ops if o.get("modifier") == "Boolean")
    assert bool_op["params"].get("object") == "boolean_cutter"
    # Boolean result is evaluated and reported healthy.
    health = bool_op.get("boolean")
    assert health and health.get("non_manifold_edges") == 0, health
    # The auto-hidden cutter must not leak into the GLB export.
    assert glb.exists()
    node_names = validate_glb(glb, max_mb=20)["info"].get("node_names") or []
    assert not any("boolean_cutter" in (n or "") for n in node_names)


def test_generalist_utility_ops_end_to_end(blender_exe, tmp_path):
    """Exercise the ops no benchmark task uses: collection/parent/origin/
    transform/array/constraint — they must work, not just validate."""
    _, base = task_workspace(tmp_path, "util_ops")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_collection", "name": "DETAILS"},
        {"op": "create_mesh_primitive", "type": "cube", "name": "chip_detail",
         "size": 0.2, "location": [1.2, 0, 1.0], "collection": "SUBJECT"},
        {"op": "move_to_collection", "target": "chip_detail", "collection": "DETAILS"},
        {"op": "parent_objects", "child": "chip_detail", "parent": "hero_core"},
        {"op": "set_origin", "target": "chip_detail", "mode": "ORIGIN_GEOMETRY"},
        {"op": "set_object_transform", "target": "chip_detail",
         "location": [1.0, 0, 1.0], "rotation": [0, 0, 15]},
        {"op": "add_array_modifier", "target": "chip_detail", "count": 3,
         "offset": [0.3, 0, 0]},
        {"op": "add_constraint", "target": "hero_core", "constraint": "COPY_LOCATION",
         "params": {"target": "ground"}},
        {"op": "add_constraint", "target": "camera_hero", "constraint": "TRACK_TO",
         "params": {"target": "hero_core"}},
        {"op": "create_rig", "schema": {"rig_name": "probe_rig", "controls": [
            {"name": "CTRL_probe", "type": "empty", "drives": []}],
         "drivers": [
            {"target": "chip_detail.location.z", "driver": "CTRL_probe.location.y"},
            {"target": "ghost.location.z", "driver": "CTRL_probe.location.y"}]}},
        {"op": "set_object_transform", "target": "CTRL_probe",
         "location": [0, 3.5, 0]},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe),
        blender_exe, 300)
    assert res["ok"], res
    assert not [o for o in res["operations"] if o.get("error")], res["operations"]
    rig = next(o for o in res["operations"] if o.get("rig") == "probe_rig")
    assert rig["drivers"] == ["chip_detail.location.z"]
    assert rig["driver_errors"][0]["driver"] == "ghost.location.z"
    # driver must actually evaluate: chip follows the control's y onto its z
    insp = runner.run_job(runner.build_job("inspect", base, blend),
                          blender_exe, 120)["inspection"]
    chip = next(o for o in insp["objects"] if o["name"] == "chip_detail")
    parent = next(o for o in insp["objects"] if o["name"] == "hero_core")
    assert chip["world_location"][2] - parent["world_location"][2] == \
        pytest.approx(3.5, abs=0.2)


def test_export_policy_and_animation_export_flags(blender_exe, tmp_path):
    """apply_before_glb=False exports raw base geometry; keep_modifier_in_
    blend=False bakes GN into the mesh; include_in_glb controls clip export."""
    from blender_cinematic.glb import inspect_glb
    _, base = task_workspace(tmp_path, "export_policy")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "create_mesh_primitive", "type": "cube", "name": "raw_host",
         "size": 1.0, "location": [2.0, 0, 1.0], "collection": "SUBJECT"},
        {"op": "create_mesh_primitive", "type": "cube", "name": "bake_host",
         "size": 1.0, "location": [-2.0, 0, 1.0], "collection": "SUBJECT"},
        {"op": "create_geometry_nodes", "schema": {
            "node_group_name": "GN_Raw", "recipe": "GN_RockScatter",
            "target_object": "raw_host",
            "inputs": {"rock_count": 30, "rock_size": 0.08, "seed": 5},
            "export_policy": {"apply_before_glb": False,
                              "keep_modifier_in_blend": True}}},
        {"op": "create_geometry_nodes", "schema": {
            "node_group_name": "GN_Bake", "recipe": "GN_RockScatter",
            "target_object": "bake_host",
            "inputs": {"rock_count": 30, "rock_size": 0.08, "seed": 6},
            "export_policy": {"apply_before_glb": True,
                              "keep_modifier_in_blend": False}}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe,
        output={"glb": str(base / "final" / "scene.glb")}),
        blender_exe, 300)
    assert res["ok"], res
    gn = [o for o in res["operations"] if o.get("recipe") == "GN_RockScatter"]
    assert any(o.get("baked_in_blend") for o in gn)
    # bake_host: modifier applied -> plain mesh with the scattered faces baked in
    insp = runner.run_job(runner.build_job("inspect", base, blend),
                          blender_exe, 120)["inspection"]
    bake = next(o for o in insp["objects"] if o["name"] == "bake_host")
    raw = next(o for o in insp["objects"] if o["name"] == "raw_host")
    assert bake.get("modifiers") == []
    assert bake["faces"] > 100 > raw["faces"]  # baked scatter vs live cube
    raw_faces = inspect_glb(base / "final" / "scene.glb")["mesh_total_faces"]

    # control: same scene but raw_host exports WITH modifiers applied
    _, base2 = task_workspace(tmp_path, "export_policy_ctrl")
    blend2 = base2 / "final" / "scene.blend"
    recipe["operations"][-2]["schema"]["export_policy"]["apply_before_glb"] = True
    res2 = runner.run_job(runner.build_job(
        "full_pipeline", base2, blend2, budget=PREVIEW_BUDGET, recipe=recipe,
        output={"glb": str(base2 / "final" / "scene.glb")}),
        blender_exe, 300)
    assert res2["ok"], res2
    baked_faces = inspect_glb(base2 / "final" / "scene.glb")["mesh_total_faces"]
    # raw-only export must carry far fewer faces than the applied export
    assert baked_faces > raw_faces + 500, (raw_faces, baked_faces)


def test_animation_include_in_glb_flag_controls_clip_export(blender_exe, tmp_path):
    """include_in_glb=False must actually exclude the animation from the GLB."""
    from blender_cinematic.glb import inspect_glb
    for include in (True, False):
        _, base = task_workspace(tmp_path, f"anim_glb_{include}")
        blend = base / "final" / "scene.blend"
        recipe = {"operations": BASE_RECIPE + [
            {"op": "create_animation", "schema": {
                "animation_name": "Spin", "mode": "turntable",
                "frame_start": 1, "frame_end": 48, "fps": 24,
                "targets": ["hero_core"],
                "export": {"include_in_glb": include, "clip_name": "Spin"}}},
        ]}
        res = runner.run_job(runner.build_job(
            "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe,
            output={"glb": str(base / "final" / "scene.glb")}),
            blender_exe, 300)
        assert res["ok"], res
        glb = inspect_glb(base / "final" / "scene.glb")
        assert (glb["animations"] > 0) == include, (include, glb)


def test_add_modifier_boolean_missing_cutter_errors(blender_exe, tmp_path):
    """A BOOLEAN with a missing/invalid operand fails cleanly, no dead modifier."""
    _, base = task_workspace(tmp_path, "mod_bool_neg")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": BASE_RECIPE + [
        {"op": "add_modifier", "target": "hero_core", "modifier": "BOOLEAN",
         "params": {"object": "no_such_cutter", "operation": "DIFFERENCE"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe),
        blender_exe, 300)
    ops = res["operations"]
    err = [o for o in ops if "operand not found" in str(o.get("error", ""))]
    assert err, ops


def test_light_look_at_and_target_aim_the_light(blender_exe, tmp_path):
    """Lights declared with look_at / target must actually rotate toward the
    point/object — position_role alone left every AREA light pointing down -Z."""
    _, base = task_workspace(tmp_path, "light_aim")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "create_mesh_primitive", "type": "cube", "name": "aim_cube",
         "size": 1.0, "location": [0, 0, 1.0], "collection": "SUBJECT"},
        {"op": "create_lighting_rig", "schema": {"lighting_rig": "aim_test",
            "lights": [
                # on -Y axis aiming at origin: -Z must track to +Y -> rot (pi/2,0,0)
                {"name": "aimed_look_at", "type": "AREA", "power": 100,
                 "location": [0, -5, 0], "look_at": [0, 0, 0]},
                {"name": "aimed_target", "type": "AREA", "power": 100,
                 "location": [0, -5, 0], "target": "aim_cube"},
                {"name": "unaimed", "type": "AREA", "power": 100,
                 "location": [0, -5, 0]},
            ]}},
        {"op": "create_camera", "schema": {"camera_name": "camera_aim",
            "target": "aim_cube", "location": [0, -6, 1.5]}},
        {"op": "set_scene_metadata", "data": {"final_camera": "camera_aim"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe),
        blender_exe, 300)
    assert res["ok"], res
    insp = runner.run_job(runner.build_job("inspect", base, blend),
                          blender_exe, 120)["inspection"]
    lights = {l["name"]: l for l in insp["lights"]}
    aimed = lights["aimed_look_at"]["rotation"]
    assert aimed[0] == pytest.approx(math.pi / 2, abs=0.02)
    assert abs(aimed[1]) < 0.02 and abs(aimed[2]) < 0.02
    # target= resolves the object's location — cube sits 1m above origin so
    # the -Z axis pitches past horizontal: rot_x = atan2(dy, -dz).
    tgt = lights["aimed_target"]["rotation"]
    assert tgt[0] == pytest.approx(math.atan2(5.0, -1.0), abs=0.02)
    # unaimed light keeps identity rotation (points straight down -Z)
    un = lights["unaimed"]["rotation"]
    assert all(abs(v) < 1e-4 for v in un), un


def test_subject_screen_coverage_drives_camera_distance(blender_exe, tmp_path):
    """composition.subject_screen_coverage is a *linear* extent contract: the
    target's max screen-bbox side must land at the declared fraction."""
    _, base = task_workspace(tmp_path, "cam_cov")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "create_mesh_primitive", "type": "cube", "name": "cov_cube",
         "size": 2.0, "location": [0, 0, 1.0], "collection": "SUBJECT"},
        {"op": "create_camera", "schema": {"camera_name": "camera_cov",
            "target": "cov_cube", "location": [0, -12, 1.0],
            "look_at": [0, 0, 1.0],
            "composition": {"subject_screen_coverage": 0.55}}},
        {"op": "set_scene_metadata", "data": {"final_camera": "camera_cov"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe),
        blender_exe, 300)
    assert res["ok"], res
    insp = runner.run_job(runner.build_job("inspect", base, blend),
                          blender_exe, 120)["inspection"]
    cube = next(o for o in insp["objects"] if o["name"] == "cov_cube")
    bb = cube["screen_bbox"]
    extent = max(bb[2] - bb[0], bb[3] - bb[1])
    assert extent == pytest.approx(0.55, abs=0.06)


def test_adjust_ops_patch_lights_materials_and_expose_world(blender_exe, tmp_path):
    """adjust_light / adjust_material must mutate the live scene — these are
    the levers the critique layer emits — and the inspector must report
    world + base_color so diagnoses can fire."""
    _, base = task_workspace(tmp_path, "adjust_ops")
    blend = base / "final" / "scene.blend"
    recipe = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "adjust_world", "strength": 0.4},
        {"op": "create_mesh_primitive", "type": "cube", "name": "adj_cube",
         "size": 1.0, "location": [0, 0, 0.5], "collection": "SUBJECT"},
        {"op": "create_material", "schema": {"name": "adj_body",
            "preset": "glossy_plastic",
            "pbr": {"base_color": [0.9, 0.2, 0.1, 1.0], "metallic": 0.0,
                    "roughness": 0.3},
            "target_objects": ["adj_cube"]}},
        {"op": "add_light", "schema": {"name": "adj_key", "type": "AREA",
            "power": 200, "size": 2.0, "location": [3, -3, 4]}},
        # the actual adjustments under test:
        {"op": "adjust_light", "name": "adj_key", "power_scale": 0.5,
         "look_at": [0, 0, 0.5]},
        {"op": "adjust_material", "material": "adj_body",
         "pbr": {"metallic": 0.9, "base_color": [0.02, 0.02, 0.03, 1.0]}},
        {"op": "create_camera", "schema": {"camera_name": "camera_adj",
            "target": "adj_cube", "location": [0, -6, 1.5]}},
        {"op": "set_scene_metadata", "data": {"final_camera": "camera_adj"}},
    ]}
    res = runner.run_job(runner.build_job(
        "full_pipeline", base, blend, budget=PREVIEW_BUDGET, recipe=recipe),
        blender_exe, 300)
    assert res["ok"], res
    insp = runner.run_job(runner.build_job("inspect", base, blend),
                          blender_exe, 120)["inspection"]
    light = next(l for l in insp["lights"] if l["name"] == "adj_key")
    assert light["energy"] == pytest.approx(100.0, rel=0.01)
    # aimed at the cube: rotate the light's -Z axis by the reported euler and
    # check it points from (3,-3,4) to (0,0,0.5) -> direction (-3,3,-3.5)
    x, y, z = light["rotation"]
    vx = -math.sin(y) * math.cos(x) * math.cos(z) - math.sin(x) * math.sin(z)
    vy = -math.sin(z) * math.sin(y) * math.cos(x) + math.cos(z) * math.sin(x)
    vz = -math.cos(y) * math.cos(x)
    n = math.sqrt(3 ** 2 + 3 ** 2 + 3.5 ** 2)
    assert vx == pytest.approx(-3 / n, abs=0.02)
    assert vy == pytest.approx(3 / n, abs=0.02)
    assert vz == pytest.approx(-3.5 / n, abs=0.02)
    mat = next(m for m in insp["materials"] if m["name"] == "adj_body")
    assert mat["metallic"] == pytest.approx(0.9, abs=0.01)
    assert mat["base_color"][0] == pytest.approx(0.02, abs=0.01)
    assert insp["world"] is not None
    assert insp["world"]["strength"] == pytest.approx(0.4, abs=0.01)


def test_critique_loop_converges_on_broken_scene(blender_exe, tmp_path):
    """The weak-model loop, mechanised: start from a scene with no camera and
    near-black lighting, then apply the top fail diagnosis each round —
    inspect -> diagnose -> apply suggested ops -> re-render. Converging to
    zero fail diagnoses with a visible subject proves the critique carries
    enough judgment to iterate without an operator's eye."""
    from blender_cinematic.critique import diagnose

    _, base = task_workspace(tmp_path, "critique_loop")
    blend = base / "final" / "scene.blend"
    broken = {"operations": [
        {"op": "ensure_standard_collections"},
        {"op": "create_mesh_primitive", "type": "cube", "name": "hero",
         "size": 2.0, "location": [0, 0, 1.0], "collection": "SUBJECT"},
        {"op": "create_material", "schema": {"name": "hero_mat",
            "preset": "glossy_plastic",
            "pbr": {"base_color": [0.2, 0.25, 0.35, 1.0], "roughness": 0.4},
            "target_objects": ["hero"]}},
        {"op": "adjust_world", "strength": 0.03},
    ]}
    res = runner.run_job(runner.build_job(
        "initialize_blend", base, blend), blender_exe, 300)
    assert res["ok"], res
    res = runner.run_job(runner.build_job(
        "apply_recipe", base, blend, recipe=broken), blender_exe, 300)
    assert res["ok"], res

    preview = base / "iterations" / "critique_preview.png"
    history = []
    for _round in range(5):
        insp = runner.run_job(runner.build_job(
            "inspect", base, blend, output={}), blender_exe, 180)["inspection"]
        metrics = None
        if insp.get("active_camera"):
            runner.run_job(runner.build_job(
                "render_preview", base, blend, budget=PREVIEW_BUDGET,
                output={"image": str(preview)}), blender_exe, 300)
            metrics = image_sanity(preview) if preview.exists() else None
        lint = lint_scene(insp, None)
        diags = diagnose(insp, image_metrics=metrics,
                         render_path=preview if preview.exists() else None,
                         lint=lint)
        fails = [d for d in diags if d["severity"] == "fail"]
        history.append({"round": _round,
                        "fails": [d["code"] for d in fails]})
        if not fails:
            break
        ops = [o for o in fails[0]["ops"] if o.get("op")]
        if not ops:
            break
        applied = runner.run_job(runner.build_job(
            "apply_recipe", base, blend, recipe={"operations": ops}),
            blender_exe, 300)
        assert applied["ok"], applied

    print("\ncritique loop:", history)
    assert preview.exists(), history
    final_metrics = image_sanity(preview)
    assert final_metrics["pct_near_black"] < 0.6, history
    assert not fails, history
