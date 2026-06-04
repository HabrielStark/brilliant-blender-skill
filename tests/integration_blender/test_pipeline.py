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
    assert hero_motion["sample_count"] == 3
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
