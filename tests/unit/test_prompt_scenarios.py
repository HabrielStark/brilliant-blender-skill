import json

from benchmarks.runners.run_prompt_scenarios import (
    evaluate_live_agent_run,
    evaluate_static_contract,
    extract_json_object,
    load_scenarios,
    load_tasks,
    recipe_features,
    run_live_agent_runs,
    run_prompt_scenarios,
)


def test_current_prompt_scenario_fixtures_pass_static_contract(tmp_path):
    summary = run_prompt_scenarios(render=False, out=tmp_path / "prompt_scenarios")

    assert summary["acceptance_level"] == "static_prompt_fixture_contract"
    assert summary["scenario_count"] >= 3
    assert summary["passed"] == summary["scenario_count"]
    assert summary["live_agent_runs"] == 0
    assert (tmp_path / "prompt_scenarios" / "prompt_scenarios_summary.json").exists()


def test_static_contract_rejects_keyword_named_default_slop():
    scenarios = load_scenarios()
    scenario = dict(scenarios["reference_match_prompt"])
    scenario["contract"] = dict(scenario["contract"])
    scenario["contract"]["min_operations"] = 4
    recipe = {
        "operations": [
            {"op": "ensure_standard_collections"},
            {
                "op": "create_mesh_primitive",
                "type": "cube",
                "name": "Cube",
                "collection": "SUBJECT",
            },
            {
                "op": "create_mesh_primitive",
                "type": "cube",
                "name": "body_inset_rim_highlight_groove_reflection_lens_sensor_bevel_fake",
                "collection": "SUBJECT",
            },
            {
                "op": "create_camera",
                "schema": {"camera_name": "camera_fake", "target": "Cube"},
            },
            {
                "op": "create_lighting_rig",
                "schema": {"lighting_rig": "flat", "lights": []},
            },
            {
                "op": "create_material",
                "schema": {
                    "name": "Material",
                    "target_objects": ["Cube"],
                    "pbr": {"base_color": [0, 0, 0, 1]},
                },
            },
        ]
    }

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    failures = "\n".join(result["failures"])
    assert "default object/material names present" in failures
    assert "craft operations" in failures
    assert "procedural materials" in failures
    assert "emissive materials" in failures


def test_recipe_features_count_material_texture_and_craft_signals():
    tasks = load_tasks()
    recipe = tasks["shader_texture_material_study"]["recipe"]

    features = recipe_features(recipe)

    assert features["craft_operation_count"] >= 1
    assert features["material_count"] >= 8
    assert features["procedural_material_count"] >= 4
    assert features["material_craft_signal_count"] >= 11
    assert {"base_color", "displacement"} <= set(features["image_texture_roles"])
    assert "image_textures" in features["procedural_keys"]


def test_recipe_features_count_material_params_on_generated_detail_targets():
    recipe = {"operations": [
        {
            "op": "create_material",
            "schema": {
                "name": "cream_thread",
                "preset": "matte_plastic",
                "pbr": {"base_color": [1, 0.9, 0.7, 1]},
            },
        },
        {
            "op": "create_linear_markers",
            "name_prefix": "strap_stitch",
            "count": 3,
            "material": "cream_thread",
        },
        {
            "op": "create_text_label",
            "name": "dial_logo_text",
            "text": "A",
            "material": "cream_thread",
        },
    ]}

    features = recipe_features(recipe)

    assert features["material_target_count"] == 4


def test_static_contract_accepts_highlight_alias_group():
    scenario = {
        "id": "highlight_alias",
        "contract": {
            "min_operations": 1,
            "require_name_terms": ["watch"],
            "require_name_term_groups": [["highlight", "catchlight", "glint"]],
        },
    }
    recipe = {"operations": [
        {
            "op": "create_decal_plane",
            "name": "watch_case_bevel_warm_catchlight",
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert result["static_pass"]


def test_static_contract_rejects_forbidden_reference_name_terms():
    scenario = {
        "id": "forbid_name_terms",
        "contract": {
            "min_operations": 1,
            "forbid_name_terms": ["occlusion"],
        },
    }
    recipe = {"operations": [
        {
            "op": "create_decal_plane",
            "name": "right_lens_black_occlusion_patch",
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "forbidden semantic name terms present: occlusion" in "\n".join(result["failures"])


def test_prompt_scenario_summary_is_json_serializable(tmp_path):
    summary = run_prompt_scenarios(["product_watch_prompt"], render=False, out=tmp_path)

    encoded = json.dumps(summary)

    assert "product_watch_prompt" in encoded
    assert summary["passed"] == 1


def test_extract_json_object_accepts_fenced_raw_agent_output():
    raw = '```json\n{"metadata":{"claim_level":"live_agent_raw_output"},"recipe":{"operations":[]}}\n```'

    parsed = extract_json_object(raw)

    assert parsed["metadata"]["claim_level"] == "live_agent_raw_output"


def test_live_agent_run_archive_passes_static_contract(tmp_path):
    tasks = load_tasks()
    scenarios = load_scenarios()
    scenario = scenarios["product_watch_prompt"]
    raw_output = {
        "metadata": {
            "agent_label": "unit-test-live-agent",
            "skill_path": "SKILL.md",
            "generated_at_note": "unit test deterministic archive",
            "claim_level": "live_agent_raw_output",
        },
        "prompt": scenario["prompt"],
        "recipe": tasks["product_hero_watch"]["recipe"],
    }
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "watch_live_unit.json").write_text(
        json.dumps(
            {
                "id": "watch_live_unit",
                "scenario_id": "product_watch_prompt",
                "source_agent": "unit-test",
                "model": "deterministic-fixture",
                "created_at": "2026-06-04",
                "raw_output": json.dumps(raw_output),
            }
        ),
        encoding="utf-8",
    )

    summary = run_live_agent_runs(["watch_live_unit"], render=False, out=tmp_path / "out", runs_dir=runs_dir)

    assert summary["acceptance_level"] == "live_agent_static_contract"
    assert summary["live_agent_runs"] == 1
    assert summary["passed"] == 1


def test_live_agent_run_rejects_missing_metadata_and_recipe():
    scenarios = load_scenarios()
    tasks = load_tasks()

    result = evaluate_live_agent_run(
        {"id": "bad", "raw_output": "{}"},
        scenarios["product_watch_prompt"],
        tasks,
        render=False,
        blender_exe=None,
        out_root="unused",
    )

    assert not result["pass"]
    failures = "\n".join(result["failures"])
    assert "metadata.claim_level" in failures
    assert "parsed recipe object is required" in failures


def test_static_contract_rejects_unresolved_late_material_references():
    scenario = {
        "id": "late_material",
        "contract": {
            "min_operations": 1,
            "forbid_unresolved_late_material_references": True,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_linear_markers",
            "name_prefix": "late_marker",
            "count": 2,
            "material": "late_named_shader",
        },
        {
            "op": "create_material",
            "schema": {
                "name": "late_named_shader",
                "preset": "matte_plastic",
                "pbr": {"base_color": [1, 1, 1, 1]},
            },
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "material referenced before creation" in "\n".join(result["failures"])


def test_static_contract_allows_late_material_when_generated_objects_are_assigned():
    scenario = {
        "id": "late_material_assigned",
        "contract": {
            "min_operations": 1,
            "forbid_unresolved_late_material_references": True,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_linear_markers",
            "name_prefix": "late_marker",
            "count": 2,
            "material": "late_named_shader",
        },
        {
            "op": "create_material",
            "schema": {
                "name": "late_named_shader",
                "preset": "matte_plastic",
                "pbr": {"base_color": [1, 1, 1, 1]},
            },
        },
        {"op": "assign_material", "target": "late_marker_01", "material": "late_named_shader"},
        {"op": "assign_material", "target": "late_marker_02", "material": "late_named_shader"},
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert result["static_pass"]


def test_static_contract_rejects_text_label_role_that_hides_logo_from_rubric():
    scenario = {
        "id": "text_role",
        "contract": {
            "min_operations": 1,
            "require_text_label_role": True,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_text_label",
            "name": "applied_watch_logo",
            "text": "AURUM",
            "role": "applied_dial_logo",
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "create_text_label must keep craft role text_label" in "\n".join(result["failures"])


def test_static_contract_rejects_strap_stitches_outside_strap_width():
    scenario = {
        "id": "strap_width",
        "contract": {
            "min_operations": 1,
            "forbid_strap_surface_detail_outside_width": True,
            "strap_surface_detail_keywords": ["stitch"],
            "strap_surface_detail_margin": 0.04,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_mesh_primitive",
            "type": "cube",
            "name": "upper_watch_strap",
            "size": 1,
            "location": [0, 1.8, 0.4],
            "scale": [0.42, 1.4, 0.08],
            "collection": "SUBJECT",
        },
        {
            "op": "create_linear_markers",
            "name_prefix": "upper_strap_left_stitch",
            "start": [-0.36, 1.2, 0.45],
            "step": [0, 0.2, 0],
            "count": 4,
            "size": [0.025, 0.075, 0.018],
            "collection": "SUBJECT",
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "strap surface detail outside strap width" in "\n".join(result["failures"])


def test_static_contract_allows_centered_strap_markers():
    scenario = {
        "id": "strap_width_centered",
        "contract": {
            "min_operations": 1,
            "forbid_strap_surface_detail_outside_width": True,
            "strap_surface_detail_keywords": ["stitch"],
        },
    }
    recipe = {"operations": [
        {
            "op": "create_mesh_primitive",
            "type": "cube",
            "name": "upper_watch_strap",
            "size": 1,
            "location": [0, 1.8, 0.4],
            "scale": [0.42, 1.4, 0.08],
            "collection": "SUBJECT",
        },
        {
            "op": "create_linear_markers",
            "name_prefix": "upper_strap_center_stitch",
            "start": [0.18, 1.2, 0.45],
            "step": [0, 0.2, 0],
            "count": 4,
            "size": [0.025, 0.075, 0.018],
            "collection": "SUBJECT",
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert result["static_pass"]


def test_static_contract_rejects_too_tight_product_camera_composition():
    scenario = {
        "id": "tight_camera",
        "contract": {
            "min_operations": 1,
            "max_subject_screen_coverage": 0.68,
            "min_camera_safe_margin": 0.12,
            "max_camera_look_at_y": 0.1,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_camera",
            "schema": {
                "camera_name": "macro_too_tight",
                "target": "watch_case",
                "composition": {
                    "subject_screen_coverage": 0.74,
                    "safe_margin": 0.11,
                },
                "look_at": [0, 0.28, 0.4],
            },
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    failures = "\n".join(result["failures"])
    assert "camera subject_screen_coverage too tight" in failures
    assert "camera safe_margin too small" in failures
    assert "camera look_at y too high for full subject" in failures


def test_static_contract_rejects_too_loose_reference_camera_composition():
    scenario = {
        "id": "loose_reference_camera",
        "contract": {
            "min_operations": 1,
            "min_subject_screen_coverage": 0.60,
            "require_camera_composition": True,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_camera",
            "schema": {
                "camera_name": "reference_too_wide",
                "target": "dark_product_body",
                "composition": {
                    "subject_screen_coverage": 0.48,
                    "safe_margin": 0.24,
                },
            },
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "camera subject_screen_coverage too loose" in "\n".join(result["failures"])


def test_static_contract_rejects_reference_camera_long_lens_crop_risk():
    scenario = {
        "id": "long_reference_lens",
        "contract": {
            "min_operations": 1,
            "max_camera_focal_length_mm": 60,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_camera",
            "schema": {
                "camera_name": "reference_long_lens",
                "target": "dark_product_body",
                "composition": {
                    "subject_screen_coverage": 0.68,
                    "safe_margin": 0.15,
                },
                "lens": {
                    "focal_length_mm": 76,
                },
            },
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "camera focal length too long for full reference subject" in "\n".join(result["failures"])


def test_static_contract_rejects_missing_required_operation_count():
    scenario = {
        "id": "op_count",
        "contract": {
            "min_operations": 1,
            "min_operation_counts": {"set_smooth_shading": 2},
        },
    }
    recipe = {"operations": [
        {"op": "set_smooth_shading", "target": "dial", "smooth": True},
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "operation set_smooth_shading count 1 < min 2" in "\n".join(result["failures"])


def test_static_contract_rejects_forbidden_operation_count_over_maximum():
    scenario = {
        "id": "op_max",
        "contract": {
            "min_operations": 1,
            "max_operation_counts": {"parent_objects": 0},
        },
    }
    recipe = {"operations": [
        {"op": "parent_objects", "child": "lens_glint", "parent": "body_shell"},
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "operation parent_objects count 1 > max 0" in "\n".join(result["failures"])


def test_static_contract_rejects_missing_camera_composition_metadata():
    scenario = {
        "id": "camera_composition",
        "contract": {
            "min_operations": 1,
            "require_camera_composition": True,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_camera",
            "schema": {
                "camera_name": "camera_without_composition",
                "target": "hero_product",
            },
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "camera composition metadata missing" in "\n".join(result["failures"])


def test_recipe_features_count_animation_contract_signals():
    tasks = load_tasks()
    recipe = tasks["turntable_animation"]["recipe"]

    features = recipe_features(recipe)

    assert features["animation_count"] >= 1
    assert features["animation_frame_span_max"] >= 120
    assert features["animation_target_count_max"] >= 10
    assert features["animation_glb_export_count"] >= 1
    assert features["looping_animation_count"] >= 1


def test_static_contract_rejects_static_product_for_animation_prompt():
    scenario = {
        "id": "animation_required",
        "contract": {
            "min_operations": 1,
            "require_animation": True,
            "min_animation_frames": 120,
            "min_animation_targets": 10,
            "require_glb_animation": True,
            "require_looping_animation": True,
        },
    }
    recipe = {"operations": [
        {"op": "create_mesh_primitive", "type": "cylinder", "name": "product_body"},
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    failures = "\n".join(result["failures"])
    assert "required animation missing" in failures
    assert "animation frames 0 < min 120" in failures
    assert "animation target objects 0 < min 10" in failures
    assert "required GLB animation export missing" in failures
    assert "required looping animation missing" in failures


def test_static_contract_rejects_nonstandard_collections():
    scenario = {
        "id": "collection_names",
        "contract": {
            "min_operations": 1,
            "forbid_nonstandard_collections": True,
        },
    }
    recipe = {"operations": [
        {
            "op": "create_mesh_primitive",
            "type": "cube",
            "name": "hero_detail",
            "collection": "DETAIL",
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert not result["static_pass"]
    assert "nonstandard collection names present: DETAIL" in "\n".join(result["failures"])


def test_static_contract_accepts_required_craft_op_group_alternative():
    scenario = {
        "id": "craft_group",
        "contract": {
            "min_operations": 1,
            "required_craft_op_groups": [["create_radial_markers", "create_linear_markers"]],
        },
    }
    recipe = {"operations": [
        {
            "op": "create_linear_markers",
            "name_prefix": "visible_cap_ridge",
            "count": 4,
        },
    ]}

    result = evaluate_static_contract(scenario, recipe)

    assert result["static_pass"]
