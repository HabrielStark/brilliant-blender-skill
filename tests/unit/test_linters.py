"""Unit tests for the linter suite (SRS 11, 32.8, 33.7, 34.7, 35.6, 36.5, 37.3)."""
from blender_cinematic.constants import REQUIRED_COLLECTIONS
from blender_cinematic.linters import (
    is_default_name,
    lint_animation,
    lint_camera,
    lint_geometry,
    lint_materials,
    lint_naming,
    lint_scene,
    lint_spatial_relationships,
)


def _good_scene():
    return {
        "collections": list(REQUIRED_COLLECTIONS),
        "objects": [{
            "name": "watch_case", "type": "MESH", "collection": "SUBJECT", "faces": 4200,
            "materials": ["brushed_titanium"], "scale": [1, 1, 1], "smooth": True,
            "modifiers": [{"type": "BEVEL", "show_render": True}],
            "in_camera_frame": True, "screen_coverage": 0.6,
            "non_manifold": False, "flipped_normals": False,
        }],
        "active_camera": {"name": "camera_hero", "lens_mm": 70, "dof": True,
                          "focus_target": "watch_case", "inside_geometry": False},
        "cameras": ["camera_hero"],
        "lights": [{"name": "key_soft", "type": "AREA", "energy": 450, "color": [1, 1, 1]}],
        "materials": [{"name": "brushed_titanium", "metallic": 1.0, "roughness": 0.34,
                       "users": 1, "is_default": False, "node_count": 12}],
        "metadata": {"final_camera": "camera_hero"},
    }


def test_is_default_name():
    assert is_default_name("Cube.001")
    assert is_default_name("Sphere")
    assert is_default_name("Material.004")
    assert not is_default_name("watch_case_beveled")


def test_good_scene_passes():
    res = lint_scene(_good_scene(), manifest={"output_mode": "still", "style": {"mood": "premium"}})
    assert res.passed, [i.message for i in res.errors]


def test_broken_scene_errors():
    broken = {
        "collections": ["Collection"],
        "objects": [{"name": "Cube.001", "type": "MESH", "collection": "SUBJECT",
                     "faces": 6, "materials": [], "scale": [2, 2, 2], "in_camera_frame": False}],
        "active_camera": None, "cameras": [], "lights": [],
        "materials": [{"name": "Material.001", "is_default": True, "users": 1}],
        "animation": {}, "render": {},
    }
    res = lint_scene(broken, manifest={"output_mode": "web_asset",
                                       "target": {"final_format": ["glb"]},
                                       "constraints": {"max_glb_mb": 10}})
    codes = {i.code for i in res.errors}
    assert "camera.none" in codes
    assert "lighting.none" in codes
    assert "material.default" in codes
    assert "mesh.unapplied_scale" in codes
    assert not res.passed


def test_camera_dof_without_target_errors():
    s = _good_scene()
    s["active_camera"]["focus_target"] = None
    assert any(i.code == "camera.dof_target" for i in lint_camera(s).errors)


def test_camera_overcrop_is_error():
    s = _good_scene()
    s["objects"][0]["screen_coverage"] = 0.995
    assert any(i.code == "camera.subject_cut" for i in lint_camera(s).errors)


def test_camera_errors_when_hero_part_is_offscreen():
    s = _good_scene()
    s["objects"].append({
        "name": "perfume_cap_brushed_metal",
        "type": "MESH",
        "collection": "SUBJECT",
        "faces": 64,
        "materials": ["brushed_titanium"],
        "in_camera_frame": False,
        "screen_coverage": 0.0,
    })
    res = lint_camera(s)
    assert any(i.code == "camera.subject_part_hidden" for i in res.errors)


def test_web_glass_without_fallback_errors():
    s = _good_scene()
    s["materials"].append({"name": "glass", "web_unsafe": True, "has_fallback": False, "users": 1})
    res = lint_materials(s, manifest={"output_mode": "web_asset", "target": {"final_format": ["glb"]}})
    assert any(i.code == "material.web_fallback" for i in res.errors)


def test_geometry_unbaked_for_web_errors():
    s = _good_scene()
    s["geometry_nodes"] = [{"name": "GN_Panels", "seed": 1, "applied": False,
                            "generated_faces": 1000, "visible_from_camera": True}]
    res = lint_geometry(s, manifest={"output_mode": "web_asset", "target": {"final_format": ["glb"]}})
    assert any(i.code == "geometry.unbaked" for i in res.errors)


def test_animation_requested_without_keyframes_errors():
    s = _good_scene()
    s["animation"] = {"has_action": False, "keyframed_objects": []}
    res = lint_animation(s, manifest={"output_mode": "animation", "target": {"final_format": ["mp4"]}})
    assert any(i.code == "animation.missing" for i in res.errors)


def test_interactive_web_static_camera_path_errors():
    s = _good_scene()
    s["animation"] = {"has_action": True, "keyframed_objects": ["camera_hero"], "camera_animated": True}
    s["camera_path_json"] = {
        "schema": "camera_path/0.1",
        "segments": [{"from_scroll": 0.0, "to_scroll": 1.0}],
        "samples": [
            {"position": [1.0, -4.0, 2.0]},
            {"position": [1.0, -4.0, 2.0]},
        ],
    }
    res = lint_animation(s, manifest={"output_mode": "interactive_web"})
    assert any(i.code == "animation.scroll_path_static" for i in res.errors)


def test_interactive_web_moving_camera_path_passes():
    s = _good_scene()
    s["animation"] = {"has_action": True, "keyframed_objects": ["camera_hero"], "camera_animated": True}
    s["camera_path_json"] = {
        "schema": "camera_path/0.1",
        "segments": [{"from_scroll": 0.0, "to_scroll": 1.0}],
        "samples": [
            {"position": [5.0, -6.0, 3.0]},
            {"position": [2.0, -3.0, 2.0]},
        ],
    }
    res = lint_animation(s, manifest={"output_mode": "interactive_web"})
    assert not [i for i in res.errors if i.code.startswith("animation.scroll_path")]


def test_attached_detail_far_from_subject_errors():
    s = _good_scene()
    s["objects"] = [
        {
            "name": "watch_body_beveled",
            "type": "MESH",
            "collection": "SUBJECT",
            "faces": 4200,
            "materials": ["brushed_titanium"],
            "location": [0, 0, 0],
            "dimensions": [2.0, 2.0, 0.5],
        },
        {
            "name": "watch_label_logo_plate",
            "type": "MESH",
            "collection": "SUBJECT",
            "faces": 24,
            "materials": ["brushed_titanium"],
            "location": [4.0, 0, 0],
            "dimensions": [0.24, 0.08, 0.03],
        },
    ]
    res = lint_spatial_relationships(s, manifest={"brief": "premium product watch hero"})
    assert any(i.code == "spatial.floating_part" for i in res.errors)


def test_attached_detail_gate_allows_exploded_scene():
    s = _good_scene()
    s["objects"] = [
        {
            "name": "device_body_cutaway",
            "type": "MESH",
            "collection": "SUBJECT",
            "location": [0, 0, 0],
            "dimensions": [2.0, 2.0, 0.5],
        },
        {
            "name": "battery_contact_ring",
            "type": "MESH",
            "collection": "SUBJECT",
            "location": [4.0, 0, 0],
            "dimensions": [0.24, 0.08, 0.03],
        },
    ]
    res = lint_spatial_relationships(s, manifest={"brief": "technical exploded view"})
    assert not [i for i in res.errors if i.code == "spatial.floating_part"]


def test_reflection_contact_streak_is_not_attachment_part():
    s = _good_scene()
    s["objects"] = [
        {
            "name": "product_body_beveled",
            "type": "MESH",
            "collection": "SUBJECT",
            "location": [0, 0, 1.0],
            "dimensions": [2.0, 1.0, 1.0],
        },
        {
            "name": "reflection_contact_streak_white",
            "type": "MESH",
            "collection": "SUBJECT",
            "location": [0, -0.3, 0.05],
            "dimensions": [0.4, 0.04, 0.01],
        },
    ]
    res = lint_spatial_relationships(s, manifest={"brief": "premium product with contact reflection"})
    assert not [i for i in res.errors if i.code == "spatial.floating_part"]


def test_naming_warns_default_object():
    s = _good_scene()
    s["objects"].append({"name": "Cylinder.003", "type": "MESH", "collection": "ENVIRONMENT"})
    assert any(i.code == "naming.object" for i in lint_naming(s).issues)
