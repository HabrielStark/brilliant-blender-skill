"""Unit tests for the recipe allowlist + complexity estimator (SRS 12.4, 19.4)."""
from blender_cinematic.recipes import estimate_complexity, validate_recipe


def test_valid_recipe_passes():
    r = {"operations": [
        {"op": "create_mesh_primitive", "type": "cube", "name": "base"},
        {"op": "add_bevel_modifier", "target": "base", "width": 0.05, "segments": 4},
        {"op": "assign_material", "target": "base", "material": "m"},
    ]}
    assert validate_recipe(r).passed


def test_hybrid_operation_params_keep_flat_required_fields():
    r = {"operations": [
        {"op": "create_mesh_primitive", "type": "cube", "name": "base"},
        {
            "op": "add_modifier",
            "target": "base",
            "modifier": "WEIGHTED_NORMAL",
            "params": {"keep_sharp": True},
        },
    ]}

    assert validate_recipe(r).passed


def test_nested_material_schema_validates_authored_shader_features():
    r = {"operations": [{
        "op": "create_material",
        "schema": {
            "name": "hero_authored_shader",
            "preset": "glossy_plastic",
            "pbr": {"base_color": [0.2, 0.4, 0.7, 1], "roughness": 0.22},
            "procedural": {
                "noise": True,
                "color_ramp": {
                    "noise_scale": 18,
                    "detail": 8,
                    "colors": [[0.02, 0.05, 0.08, 1], [0.45, 0.7, 1.0, 1]],
                },
                "checker": {
                    "scale": 18,
                    "colors": [[0.02, 0.02, 0.025, 1], [0.9, 0.92, 0.88, 1]],
                },
                "wave": {"scale": 24, "distortion": 2.0, "bump_strength": 0.035},
            },
        },
    }]}

    assert validate_recipe(r).passed


def test_nested_schema_errors_are_recipe_errors_not_silent_warnings():
    r = {"operations": [{
        "op": "create_material",
        "schema": {
            "name": "bad_shader",
            "preset": "glossy_plastic",
            "pbr": {"base_color": [1.4, 0.2, 0.3, 1]},
        },
    }]}

    res = validate_recipe(r)

    assert not res.passed
    assert any(i.code == "recipe.schema_invalid" for i in res.issues)


def test_nested_geometry_and_scroll_animation_schema_are_validated():
    r = {"operations": [
        {
            "op": "create_geometry_nodes",
            "schema": {
                "node_group_name": "GN_TestPanels",
                "recipe": "GN_PanelWall",
                "target_object": "wall",
                "inputs": {"panel_count": 12, "panel_depth": 0.05, "seed": 7},
            },
        },
        {
            "op": "create_animation",
            "schema": {
                "animation_name": "ScrollCam",
                "mode": "scroll_linked",
                "frame_start": 1,
                "frame_end": 90,
                "camera": {
                    "name": "camera_scroll",
                    "start_location": [0, -7, 2.0],
                    "end_location": [0, -3, 2.7],
                },
                "export": {"include_in_glb": True, "clip_name": "ScrollCam"},
            },
        },
    ]}

    assert validate_recipe(r).passed


def test_unknown_op_rejected():
    r = {"operations": [{"op": "run_shell", "cmd": "rm -rf /"}]}
    res = validate_recipe(r)
    assert not res.passed
    assert any("parse" in i.code or "allowlist" in i.message for i in res.issues)


def test_missing_required_param():
    r = {"operations": [{"op": "create_mesh_primitive", "type": "cube"}]}  # missing name
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.missing_param" for i in res.issues)


def test_bad_primitive_and_modifier():
    r = {"operations": [
        {"op": "create_mesh_primitive", "type": "banana", "name": "x"},
        {"op": "add_modifier", "target": "x", "modifier": "NOPE"},
    ]}
    res = validate_recipe(r)
    codes = {i.code for i in res.issues}
    assert "recipe.bad_primitive" in codes
    assert "recipe.bad_modifier" in codes


def test_complexity_scales_with_subdivision():
    r = {"operations": [
        {"op": "create_mesh_primitive", "type": "cube", "name": "c"},
        {"op": "add_subdivision", "target": "c", "levels": 3},
    ]}
    est = estimate_complexity(r)
    assert est["objects"] == 1
    assert est["faces"] == 6 * (4 ** 3)
    assert est["within_budget"]


def test_complexity_budget_exceeded():
    r = {"operations": [
        {"op": "create_mesh_primitive", "type": "uv_sphere", "name": "s"},
        {"op": "add_subdivision", "target": "s", "levels": 8},
    ]}
    est = estimate_complexity(r, budget_faces=1_000_000)
    assert not est["within_budget"]


def test_extreme_numeric_recipe_params_rejected_and_estimator_safe():
    r = {"operations": [
        {"op": "create_mesh_primitive", "type": "cube", "name": "c"},
        {"op": "add_subdivision", "target": "c", "levels": 1_000_000},
        {"op": "add_array_modifier", "target": "c", "count": 1_000_000},
    ]}
    res = validate_recipe(r)
    assert not res.passed
    codes = {i.code for i in res.issues}
    assert "recipe.subdivision_budget" in codes
    assert "recipe.array_budget" in codes
    est = estimate_complexity(r)
    assert not est["within_budget"]
    assert est["faces"] <= 2_000_001


def test_radial_markers_are_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_radial_markers", "name_prefix": "dial_marker", "center": [0, 0, 0.75],
         "radius": 0.8, "count": 12, "size": [0.05, 0.16, 0.02], "collection": "SUBJECT",
         "material": "face_marking_emissive"}
    ]}
    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 12
    assert est["faces"] == 72


def test_radial_marker_count_guard():
    r = {"operations": [
        {"op": "create_radial_markers", "name_prefix": "dial_marker", "count": 1000}
    ]}
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.marker_budget" for i in res.issues)


def test_linear_markers_are_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_linear_markers", "name_prefix": "strap_ridge", "start": [0, -1, 0.4],
         "step": [0, -0.2, 0], "count": 6, "size": [0.45, 0.035, 0.025],
         "rotation": [0, 0, 0], "collection": "SUBJECT", "material": "rubber_edge"}
    ]}
    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 6
    assert est["faces"] == 36


def test_linear_marker_count_guard():
    r = {"operations": [
        {"op": "create_linear_markers", "name_prefix": "strap_ridge", "count": 10_000}
    ]}
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.marker_budget" for i in res.issues)


def test_organic_surface_details_are_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_organic_surface_details", "name_prefix": "petal_soft", "pattern": "radial",
         "center": [0, 0, 1.2], "radius": 0.7, "count": 10, "length": 0.6,
         "width": 0.24, "curl": 0.08, "bend": 0.025, "collection": "SUBJECT",
         "material": "petal_gradient_soft"}
    ]}
    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 10
    assert est["faces"] == 960
    assert est["modifiers"] == 20


def test_organic_surface_count_guard():
    r = {"operations": [
        {"op": "create_organic_surface_details", "name_prefix": "petal_soft", "count": 10_000}
    ]}
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.organic_surface_budget" for i in res.issues)


def test_energy_burst_streaks_are_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_energy_burst_streaks", "name_prefix": "energy_trail_ribbon",
         "center": [0, 0, 1.2], "count": 18, "radius_min": 0.12, "radius_max": 0.32,
         "length_min": 0.28, "length_max": 0.72, "width": 0.032, "curl": 0.06,
         "fan_degrees": 180, "angle_degrees": 12, "segments": 12, "seed": 42,
         "collection": "SUBJECT", "material": "trail_violet_noise_emissive"}
    ]}
    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 18
    assert est["faces"] == 18 * 12 * 2
    assert est["modifiers"] == 36


def test_energy_burst_streak_numeric_guards():
    r = {"operations": [
        {"op": "create_energy_burst_streaks", "name_prefix": "energy_trail_ribbon",
         "count": 10_000, "segments": 1000}
    ]}
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.energy_streak_budget" for i in res.issues)
    est = estimate_complexity(r)
    assert not est["within_budget"]


def test_organic_fluted_body_is_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_organic_fluted_body", "name": "organic_fluted_soft_body",
         "location": [0, 0, 0.52], "radius": 0.7, "height": 1.35,
         "segments": 64, "rings": 18, "lobes": 9, "waist": 0.18,
         "rim_wave": 0.1, "twist_degrees": 24, "collection": "SUBJECT",
         "material": "organic_body_skin"}
    ]}
    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 1
    assert est["faces"] == 64 * 18 + 64
    assert est["modifiers"] == 2


def test_organic_fluted_body_numeric_guards():
    r = {"operations": [
        {"op": "create_organic_fluted_body", "name": "organic_fluted_soft_body",
         "segments": 10_000, "rings": 10_000, "lobes": 100}
    ]}
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.organic_body_budget" for i in res.issues)
    est = estimate_complexity(r)
    assert not est["within_budget"]


def test_faceted_hero_body_is_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_faceted_hero_body", "name": "hero_faceted_luxury_body",
         "location": [0, 0, 1.4], "radius": 0.82, "height": 1.58,
         "segments": 48, "rings": 18, "facet_twist_degrees": 18,
         "shoulder": 0.6, "waist": 0.28, "facet_depth": 0.06,
         "collection": "SUBJECT", "material": "hero_dark_chrome_facets"}
    ]}
    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 1
    assert est["faces"] == 48 * 18 + 48 * 2
    assert est["modifiers"] == 2


def test_faceted_hero_body_numeric_guards():
    r = {"operations": [
        {"op": "create_faceted_hero_body", "name": "hero_faceted_luxury_body",
         "segments": 10_000, "rings": 10_000}
    ]}
    res = validate_recipe(r)
    assert not res.passed
    assert any(i.code == "recipe.faceted_hero_budget" for i in res.issues)
    est = estimate_complexity(r)
    assert not est["within_budget"]


def test_craft_detail_ops_are_allowlisted_and_budgeted():
    r = {"operations": [
        {"op": "create_text_label", "name": "brand_text", "text": "BCAS",
         "location": [0, -1, 0.4], "rotation": [75, 0, 0], "size": 0.14,
         "collection": "SUBJECT", "material": "label_white"},
        {"op": "create_decal_plane", "name": "brand_plate", "location": [0, -1, 0.35],
         "rotation": [75, 0, 0], "size": [0.7, 0.22, 0.012],
         "collection": "SUBJECT", "material": "trim_dark"},
        {"op": "create_curve_tube", "name": "side_cable", "points": [
            [-0.8, -0.6, 0.2], [-1.0, -0.2, 0.55], [-0.7, 0.2, 0.8],
        ], "bevel_depth": 0.018, "collection": "SUBJECT", "material": "rubber_dark"},
        {"op": "create_fastener_pattern", "name_prefix": "cover_screw", "pattern": "radial",
         "center": [0, -1, 0.28], "radius": 0.36, "count": 6, "size": 0.055,
         "rotation": [75, 0, 0], "collection": "SUBJECT", "material": "trim_dark"},
        {"op": "create_panel_cutlines", "name_prefix": "panel_seam", "start": [-0.4, -1, 0.2],
         "step": [0.2, 0, 0], "count": 5, "size": [0.16, 0.012, 0.01],
         "rotation": [75, 0, 0], "collection": "SUBJECT", "material": "trim_dark"},
        {"op": "create_grille", "name_prefix": "front_vent", "start": [-0.2, -1.02, 0.05],
         "step": [0.08, 0, 0], "count": 6, "slat_size": [0.035, 0.26, 0.018],
         "rotation": [75, 0, 0], "collection": "SUBJECT", "material": "trim_dark"},
        {"op": "create_surface_microdetails", "name_prefix": "brushed_edge_wear",
         "pattern": "linear", "start": [-0.32, -1.04, 0.52], "step": [0.12, 0, 0],
         "direction": [1, 0, 0], "count": 4, "length": 0.08, "bevel_depth": 0.003,
         "waviness": 0.006, "rotation": [75, 0, 0], "collection": "SUBJECT",
         "material": "label_white"},
    ]}

    assert validate_recipe(r).passed
    est = estimate_complexity(r)
    assert est["objects"] == 24
    assert est["faces"] >= 6 * 96
    assert est["modifiers"] >= 18
    assert est["within_budget"]


def test_marker_ops_accept_parent_and_craft_role_metadata():
    r = {"operations": [
        {
            "op": "create_radial_markers",
            "name_prefix": "dial_applied_index",
            "center": [0, 0, 0.8],
            "radius": 0.7,
            "count": 12,
            "size": [0.04, 0.14, 0.02],
            "collection": "SUBJECT",
            "material": "warm_gold",
            "parent": "dial_plate",
            "role": "hour_marker",
        },
        {
            "op": "create_linear_markers",
            "name_prefix": "upper_strap_left_stitch",
            "start": [-0.18, 1.1, 0.43],
            "step": [0, 0.18, 0],
            "count": 8,
            "size": [0.02, 0.06, 0.014],
            "collection": "SUBJECT",
            "material": "cream_thread",
            "parent": "strap_upper",
            "role": "strap_stitch",
        },
    ]}

    assert validate_recipe(r).passed


def test_craft_detail_numeric_guards():
    r = {"operations": [
        {"op": "create_text_label", "name": "too_long", "text": "X" * 161},
        {"op": "create_curve_tube", "name": "too_many_points",
         "points": [[0, 0, 0] for _ in range(65)]},
        {"op": "create_fastener_pattern", "name_prefix": "too_many_fasteners", "count": 257},
        {"op": "create_panel_cutlines", "name_prefix": "too_many_cutlines", "count": 257},
        {"op": "create_grille", "name_prefix": "too_many_slats", "count": 257},
        {"op": "create_surface_microdetails", "name_prefix": "too_many_microdetails", "count": 257},
    ]}

    res = validate_recipe(r)

    assert not res.passed
    codes = {i.code for i in res.issues}
    assert "recipe.text_budget" in codes
    assert "recipe.curve_tube_budget" in codes
    assert "recipe.fastener_budget" in codes
    assert "recipe.panel_cutline_budget" in codes
    assert "recipe.grille_budget" in codes
    assert "recipe.surface_microdetail_budget" in codes
    assert not estimate_complexity(r)["within_budget"]
