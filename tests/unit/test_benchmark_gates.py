from PIL import Image

from benchmarks.runners.run_benchmarks import (
    animation_frame_delta_metrics,
    camera_sampled_location_delta,
    count_craft_role_objects,
    count_curved_detail_objects,
    count_emissive_materials,
    count_geometry_detail_objects,
    count_position_layers,
    count_rich_linked_materials,
    count_sampled_moving_objects,
    count_smooth_objects,
    count_visible_objects,
    eval_defect_failures,
    geometry_detail_roles,
    material_feature_set,
    material_image_texture_roles,
    material_names_for_objects,
    missing_craft_roles,
    missing_geometry_detail_roles,
    missing_material_node_name_substrings,
    missing_named_parts,
    named_part_total_coverage,
    named_part_visible_objects,
    resolve_task_path,
    total_particle_count,
    visual_style_tag_failures,
)


def test_count_position_layers_uses_axis_and_tolerance():
    objects = [
        {"location": [0, 0, 0.0]},
        {"location": [0, 0, 0.05]},
        {"location": [0, 0, 1.0]},
        {"location": [0, 0, 2.1]},
    ]

    assert count_position_layers(objects, axis="z", tolerance=0.2) == 3


def test_count_position_layers_supports_corridor_depth_axis():
    objects = [
        {"location": [0, -5.4, 1]},
        {"location": [0, -5.1, 1]},
        {"location": [0, -3.8, 1]},
        {"location": [0, -1.2, 1]},
        {"location": [0, 2.4, 1]},
    ]

    assert count_position_layers(objects, axis="y", tolerance=0.45) == 4


def test_count_visible_objects_requires_camera_frame_and_coverage():
    objects = [
        {"in_camera_frame": True, "screen_coverage": 0.02},
        {"in_camera_frame": True, "screen_coverage": 0.0001},
        {"in_camera_frame": False, "screen_coverage": 0.4},
    ]

    assert count_visible_objects(objects, min_coverage=0.001) == 1


def test_count_smooth_objects_counts_smoothed_forms():
    objects = [{"smooth": True}, {"smooth": False}, {"smooth": True}]

    assert count_smooth_objects(objects) == 2


def test_count_curved_detail_objects_rejects_low_poly_blocks():
    objects = [
        {"name": "petal_outer_block_01", "smooth": False, "faces": 6},
        {"name": "leaf_base_block_01", "smooth": True, "faces": 6},
        {"name": "fold_soft_curved_01", "smooth": True, "faces": 48},
        {"name": "petal_soft_curved_01", "smooth": True, "faces": 72},
    ]

    assert count_curved_detail_objects(objects, min_faces=24) == 2


def test_count_craft_role_objects_supports_non_mesh_visual_detail():
    objects = [
        {"name": "logo_text", "type": "FONT", "craft_role": "text_label"},
        {"name": "side_cable", "type": "CURVE", "craft_role": "curve_tube"},
        {"name": "plain_cube", "type": "MESH", "craft_role": None},
    ]

    assert count_craft_role_objects(objects) == 2
    assert count_craft_role_objects(objects, required_roles=["curve_tube"]) == 1
    assert missing_craft_roles(objects, ["text_label", "curve_tube", "grille_slat"]) == ["grille_slat"]


def test_geometry_detail_roles_require_recipe_specific_visual_output():
    objects = [
        {"name": "wall_plate_01", "type": "MESH", "gn_role": "panel_wall_plate"},
        {"name": "cable_01", "type": "CURVE", "gn_role": "cable_curve"},
        {"name": "empty_marker", "type": "EMPTY", "gn_role": "panel_wall_plate"},
        {"name": "plain_mesh", "type": "MESH", "gn_role": ""},
    ]
    geometry_nodes = [{"detail_roles": "panel_wall_plate,cable_curve"}]

    assert geometry_detail_roles(objects, geometry_nodes) == {"panel_wall_plate", "cable_curve"}
    assert count_geometry_detail_objects(objects) == 2
    assert count_geometry_detail_objects(objects, required_roles=["panel_wall_plate"]) == 1
    assert missing_geometry_detail_roles(objects, geometry_nodes, ["panel_wall_plate", "bolt_head"]) == ["bolt_head"]


def test_missing_named_parts_matches_semantic_substrings():
    objects = [
        {"name": "pcb_trace_01"},
        {"name": "case_screw_04"},
        {"name": "battery_contact_gold"},
    ]

    assert missing_named_parts(objects, ["trace", "screw", "contact"]) == []
    assert missing_named_parts(objects, ["trace", "label"]) == ["label"]


def test_named_parts_accept_domain_aliases_for_product_language():
    objects = [
        {"name": "raised_sapphire_crystal_disc", "in_camera_frame": True, "screen_coverage": 0.02},
        {"name": "applied_gold_hour_index_01", "in_camera_frame": True, "screen_coverage": 0.01},
        {"name": "case_bevel_warm_edge_glint_01", "in_camera_frame": True, "screen_coverage": 0.004},
    ]

    assert missing_named_parts(objects, ["glass", "marker", "highlight"]) == []
    visible = named_part_visible_objects(objects, ["glass", "marker", "highlight"], min_coverage=0.001)
    assert [obj["name"] for obj in visible] == [
        "raised_sapphire_crystal_disc",
        "applied_gold_hour_index_01",
        "case_bevel_warm_edge_glint_01",
    ]


def test_named_part_visible_objects_rejects_offscreen_and_micro_keyword_parts():
    objects = [
        {"name": "monolith_core", "in_camera_frame": True, "screen_coverage": 0.12},
        {"name": "screen_micro_tick", "in_camera_frame": True, "screen_coverage": 0.00005},
        {"name": "antenna_tip", "in_camera_frame": False, "screen_coverage": 0.01},
        {"name": "plain_visible_panel", "in_camera_frame": True, "screen_coverage": 0.004},
    ]

    visible = named_part_visible_objects(
        objects,
        ["monolith", "screen", "antenna", "panel"],
        min_coverage=0.001,
    )

    assert [obj["name"] for obj in visible] == ["monolith_core", "plain_visible_panel"]
    assert named_part_total_coverage(objects, ["monolith", "screen", "panel"], min_coverage=0.001) == 0.124


def test_material_feature_set_splits_declared_procedural_features():
    materials = [
        {"procedural_features": "noise_bump,noise_color_ramp"},
        {"procedural_features": "checker_texture"},
        {"procedural_features": ""},
    ]

    assert material_feature_set(materials) == {
        "noise_bump",
        "noise_color_ramp",
        "checker_texture",
    }


def test_material_image_texture_roles_splits_declared_roles():
    materials = [
        {"image_texture_roles": "base_color,displacement"},
        {"image_texture_roles": "roughness"},
        {"image_texture_roles": ""},
    ]

    assert material_image_texture_roles(materials) == {"base_color", "displacement", "roughness"}


def test_material_node_name_substrings_and_rich_graph_counts():
    materials = [
        {
            "node_count": 14,
            "link_count": 12,
            "node_names": ["NG_Label_EdgeWearAO", "NG_Label_RoughnessRamp", "NG_Label_Mapping"],
        },
        {
            "node_count": 5,
            "link_count": 3,
            "node_names": ["Principled BSDF"],
        },
    ]

    assert missing_material_node_name_substrings(
        materials,
        ["EdgeWearAO", "RoughnessRamp", "Mapping"],
    ) == []
    assert missing_material_node_name_substrings(materials, ["ScanlineWave"]) == ["ScanlineWave"]
    assert count_rich_linked_materials(materials, min_nodes=8, min_links=6) == 1


def test_material_names_for_objects_collects_unique_assigned_materials():
    objects = [
        {"materials": ["fabric", "trim"]},
        {"materials": ["fabric"]},
        {"materials": []},
    ]

    assert material_names_for_objects(objects) == {"fabric", "trim"}


def test_particle_and_emissive_gate_helpers():
    particles = [{"count": "120"}, {"count": 30}, {"count": None}]
    materials = [{"has_emission": True}, {"has_emission": False}, {"has_emission": True}]

    assert total_particle_count(particles) == 150
    assert count_emissive_materials(materials) == 2


def test_sampled_animation_motion_helpers_require_actual_motion():
    animation = {
        "sampled_objects": [
            {"name": "static", "max_location_delta": 0.0, "max_rotation_delta": 0.0},
            {"name": "turning", "max_location_delta": 0.0, "max_rotation_delta": 3.14},
            {"name": "moving", "max_location_delta": 2.5, "max_rotation_delta": 0.0},
        ],
        "camera_sampled_motion": {"name": "camera", "max_location_delta": 3.6},
    }

    assert count_sampled_moving_objects(animation, min_location_delta=0.1, min_rotation_delta=0.5) == 2
    assert camera_sampled_location_delta(animation) == 3.6


def test_animation_frame_delta_metrics_compare_rendered_frames(tmp_path):
    bright = tmp_path / "bright.png"
    dark = tmp_path / "dark.png"
    Image.new("RGBA", (32, 32), (220, 220, 230, 255)).save(bright)
    Image.new("RGBA", (32, 32), (8, 10, 12, 255)).save(dark)

    metrics = animation_frame_delta_metrics([bright, dark])

    assert metrics["frame_count"] == 2
    assert metrics["max_mean_rgb_delta"] > 0.05
    assert metrics["max_changed_pixel_ratio"] > 0.1


def test_resolve_task_path_accepts_repo_relative_reference():
    path = resolve_task_path("benchmarks/references/reference_match.png")

    assert path is not None
    assert path.name == "reference_match.png"
    assert path.is_absolute()


def test_visual_style_tag_failures_enforce_task_intent():
    failures = visual_style_tag_failures(
        ["very_dark", "blue_cyan_bias", "dark_blue_cyan"],
        {
            "forbid_visual_style_tags": ["very_dark", "dark_blue_cyan"],
            "require_visual_style_tags": ["warm_red_bias"],
        },
    )

    assert "forbidden visual style tags present: dark_blue_cyan, very_dark" in failures
    assert "required visual style tags missing: warm_red_bias" in failures


def test_eval_defect_failures_can_forbid_task_specific_warnings():
    failures = eval_defect_failures(
        [
            "premium render: antenna_tip has no bevel/subsurf/smooth",
            "55 tiny objects; consider instancing/merging",
        ],
        {"forbid_eval_defect_substrings": ["no bevel/subsurf/smooth"]},
    )

    assert failures == [
        "forbidden eval defect present: premium render: antenna_tip has no bevel/subsurf/smooth"
    ]


def test_reference_match_image_is_large_enough_for_visual_fidelity():
    path = resolve_task_path("benchmarks/references/reference_match.png")
    assert path is not None

    with Image.open(path) as image:
        assert image.size[0] >= 480
        assert image.size[1] >= 270
