#!/usr/bin/env python
# ruff: noqa: E402
"""Prompt-scenario acceptance runner.

This runner validates prompt-derived recipe artifacts before optionally sending
them through the full Blender benchmark checks. It is intentionally explicit
about provenance: a prompt fixture is not a live LLM/subagent run.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from benchmarks.runners.run_benchmarks import load_tasks, run_recipe
from blender_cinematic.recipes import OPERATION_SPECS, estimate_complexity, validate_recipe
from blender_cinematic.workspace import WorkspaceResolver

SCENARIOS_DIR = ROOT / "benchmarks" / "prompt_scenarios"
LIVE_RUNS_DIR = ROOT / "benchmarks" / "live_agent_runs"
RESULTS_DIR = ROOT / "benchmarks" / "results" / "prompt_scenarios"

DEFAULT_NAME_PREFIXES = (
    "cube",
    "cube.",
    "cylinder",
    "cylinder.",
    "sphere",
    "sphere.",
    "plane",
    "plane.",
    "torus",
    "torus.",
    "material",
    "material.",
)

CRAFT_OPS = {
    "create_text_label",
    "create_decal_plane",
    "create_curve_tube",
    "create_fastener_pattern",
    "create_panel_cutlines",
    "create_grille",
    "create_surface_microdetails",
    "create_organic_surface_details",
    "create_energy_burst_streaks",
    "create_radial_markers",
    "create_linear_markers",
    "create_geometry_nodes",
    "create_organic_fluted_body",
    "create_faceted_hero_body",
}

GENERATED_NAME_OPS = {
    "create_radial_markers",
    "create_linear_markers",
    "create_fastener_pattern",
    "create_panel_cutlines",
    "create_grille",
    "create_surface_microdetails",
    "create_organic_surface_details",
    "create_energy_burst_streaks",
}

STANDARD_COLLECTIONS = {"CAMERAS", "LIGHTS", "SUBJECT", "ENVIRONMENT", "FX", "HELPERS", "EXPORT"}


def _as_float_list(value: Any, length: int, default: list[float]) -> list[float]:
    if not isinstance(value, list) or len(value) < length:
        return default[:]
    try:
        return [float(value[idx]) for idx in range(length)]
    except (TypeError, ValueError):
        return default[:]


def _marker_positions(params: dict[str, Any]) -> list[list[float]]:
    count = max(1, int(params.get("count", 1) or 1))
    start = _as_float_list(params.get("start"), 3, [0.0, 0.0, 0.0])
    step = _as_float_list(params.get("step"), 3, [0.0, 0.0, 0.0])
    return [
        [start[axis] + step[axis] * idx for axis in range(3)]
        for idx in range(count)
    ]


def _generated_object_names(op: str, params: dict[str, Any]) -> list[str]:
    if params.get("name"):
        return [_normalize_name(params["name"])]
    prefix = _normalize_name(params.get("name_prefix"))
    if prefix and op in GENERATED_NAME_OPS:
        count = int(params.get("count", 1) or 1)
        return [f"{prefix}_{idx:02d}" for idx in range(1, count + 1)]
    return []


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_scenarios(scenarios_dir: Path = SCENARIOS_DIR) -> dict[str, dict[str, Any]]:
    return {
        path.stem: _read_json(path)
        for path in sorted(scenarios_dir.glob("*.json"))
    }


def load_live_agent_runs(runs_dir: Path = LIVE_RUNS_DIR) -> dict[str, dict[str, Any]]:
    if not runs_dir.exists():
        return {}
    return {
        path.stem: _read_json(path)
        for path in sorted(runs_dir.glob("*.json"))
    }


def extract_json_object(raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, dict):
        return raw_output
    if not isinstance(raw_output, str):
        raise ValueError("raw_output must be a JSON object or a string containing one")
    text = raw_output.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("raw_output does not contain a JSON object")
    return json.loads(text[start:end + 1])


def _candidate_recipe(scenario: dict[str, Any], tasks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidate = scenario.get("candidate") or {}
    source = candidate.get("source", "benchmark_task")
    if source == "inline":
        recipe = candidate.get("recipe")
        if not isinstance(recipe, dict):
            raise ValueError(f"{scenario['id']}: inline candidate missing recipe object")
        return recipe
    if source != "benchmark_task":
        raise ValueError(f"{scenario['id']}: unsupported candidate source {source!r}")

    task_id = candidate.get("task_id") or scenario.get("task_id")
    if task_id not in tasks:
        raise ValueError(f"{scenario['id']}: unknown benchmark task {task_id!r}")
    task = tasks[task_id]
    recipe_key = candidate.get("recipe_key", "recipe")
    if recipe_key == "adversarial_baseline":
        baseline_id = candidate.get("baseline_id")
        for item in task.get("adversarial_baselines") or []:
            if item.get("id") == baseline_id:
                return item["recipe"]
        raise ValueError(f"{scenario['id']}: unknown adversarial baseline {baseline_id!r}")
    recipe = task.get(recipe_key)
    if not isinstance(recipe, dict):
        raise ValueError(f"{scenario['id']}: task {task_id!r} missing recipe key {recipe_key!r}")
    return recipe


def _operation_params(operation: dict[str, Any]) -> dict[str, Any]:
    if isinstance(operation.get("params"), dict):
        return operation["params"]
    return {k: v for k, v in operation.items() if k != "op"}


def _material_schema(params: dict[str, Any]) -> dict[str, Any]:
    schema = params.get("schema")
    return schema if isinstance(schema, dict) else {}


def _normalize_name(value: Any) -> str:
    return str(value or "").strip()


def _default_named(name: str) -> bool:
    lowered = name.lower()
    return any(lowered == prefix.rstrip(".") or lowered.startswith(prefix) for prefix in DEFAULT_NAME_PREFIXES)


def recipe_features(recipe: dict[str, Any]) -> dict[str, Any]:
    operations = recipe.get("operations") or []
    op_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    names: list[str] = []
    material_names: list[str] = []
    material_targets: set[str] = set()
    created_materials: set[str] = set()
    assigned_targets: set[str] = set()
    late_material_references: list[dict[str, Any]] = []
    procedural_materials = 0
    image_texture_roles: set[str] = set()
    procedural_keys: set[str] = set()
    emissive_materials = 0
    mesh_boxes: dict[str, dict[str, Any]] = {}
    surface_detail_paths: list[dict[str, Any]] = []
    text_label_roles: list[dict[str, str]] = []
    camera_compositions: list[dict[str, Any]] = []
    animation_ranges: list[dict[str, Any]] = []
    collection_names: set[str] = set()

    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op = str(operation.get("op") or "")
        params = _operation_params(operation)
        op_counts[op] += 1
        category_counts[OPERATION_SPECS.get(op, {}).get("category", "unknown")] += 1

        for key in ("name", "name_prefix", "target"):
            if params.get(key):
                names.append(_normalize_name(params[key]))
        names.extend(_generated_object_names(op, params))
        if params.get("collection"):
            collection_names.add(_normalize_name(params["collection"]))

        if op == "create_material":
            schema = _material_schema(params)
            mat_name = _normalize_name(schema.get("name"))
            if mat_name:
                material_names.append(mat_name)
                created_materials.add(mat_name)
            for target in schema.get("target_objects") or []:
                material_targets.add(_normalize_name(target))
            procedural = schema.get("procedural")
            if isinstance(procedural, dict) and procedural:
                procedural_materials += 1
                procedural_keys.update(str(key) for key in procedural)
                for texture in procedural.get("image_textures") or []:
                    if isinstance(texture, dict) and texture.get("role"):
                        image_texture_roles.add(str(texture["role"]))
            pbr = schema.get("pbr")
            if isinstance(pbr, dict) and pbr.get("emission_strength"):
                emissive_materials += 1
        elif op == "assign_material" and params.get("target"):
            target = _normalize_name(params["target"])
            material_targets.add(target)
            assigned_targets.add(target)
        elif params.get("material"):
            for target in _generated_object_names(op, params):
                material_targets.add(target)
            if params.get("target"):
                material_targets.add(_normalize_name(params["target"]))
            material_ref = _normalize_name(params["material"])
            if material_ref and material_ref not in created_materials:
                late_material_references.append({
                    "op": op,
                    "material": material_ref,
                    "objects": _generated_object_names(op, params),
                })
        if op == "create_mesh_primitive":
            obj_type = str(params.get("type") or "").lower()
            name = _normalize_name(params.get("name"))
            if name and obj_type == "cube":
                size = float(params.get("size", 1.0) or 1.0)
                scale = _as_float_list(params.get("scale"), 3, [1.0, 1.0, 1.0])
                center = _as_float_list(params.get("location"), 3, [0.0, 0.0, 0.0])
                half = [abs(size * scale[axis]) * 0.5 for axis in range(3)]
                mesh_boxes[name] = {"name": name, "center": center, "half": half}
        elif op == "set_object_transform" and params.get("target"):
            target = _normalize_name(params.get("target"))
            if target in mesh_boxes:
                if isinstance(params.get("location"), list):
                    mesh_boxes[target]["center"] = _as_float_list(params.get("location"), 3, mesh_boxes[target]["center"])
                if isinstance(params.get("scale"), list):
                    scale = _as_float_list(params.get("scale"), 3, [1.0, 1.0, 1.0])
                    mesh_boxes[target]["half"] = [abs(scale[axis]) * 0.5 for axis in range(3)]
        elif op in {"create_linear_markers", "create_surface_microdetails"}:
            prefix = _normalize_name(params.get("name_prefix"))
            if prefix:
                surface_detail_paths.append({
                    "op": op,
                    "name_prefix": prefix,
                    "positions": _marker_positions(params),
                    "parent": _normalize_name(params.get("parent")),
                    "role": _normalize_name(params.get("role")),
                })
        elif op == "create_text_label":
            text_name = _normalize_name(params.get("name"))
            text_label_roles.append({
                "name": text_name,
                "role": _normalize_name(params.get("role") or "text_label"),
            })
        elif op == "create_camera":
            schema = params.get("schema") if isinstance(params.get("schema"), dict) else {}
            composition = schema.get("composition") if isinstance(schema.get("composition"), dict) else {}
            lens = schema.get("lens") if isinstance(schema.get("lens"), dict) else {}
            camera_compositions.append({
                "camera_name": _normalize_name(schema.get("camera_name")),
                "subject_screen_coverage": composition.get("subject_screen_coverage"),
                "safe_margin": composition.get("safe_margin"),
                "focal_length_mm": lens.get("focal_length_mm"),
                "look_at": schema.get("look_at"),
            })
        elif op == "create_animation":
            schema = params.get("schema") if isinstance(params.get("schema"), dict) else {}
            try:
                frame_start = int(schema.get("frame_start", 1) or 1)
                frame_end = int(schema.get("frame_end", frame_start) or frame_start)
            except (TypeError, ValueError):
                frame_start = 1
                frame_end = 1
            export = schema.get("export") if isinstance(schema.get("export"), dict) else {}
            targets = schema.get("targets") if isinstance(schema.get("targets"), list) else []
            animation_ranges.append({
                "animation_name": _normalize_name(schema.get("animation_name")),
                "mode": _normalize_name(schema.get("mode")),
                "frames": max(0, frame_end - frame_start + 1),
                "target_count": len(targets),
                "include_in_glb": bool(export.get("include_in_glb")),
                "loop": bool(schema.get("loop")),
                "camera_path": bool(schema.get("camera_path")),
            })

    unique_names = sorted({name for name in names if name})
    default_names = sorted(name for name in unique_names + material_names if _default_named(name))
    unresolved_late_material_refs = []
    for ref in late_material_references:
        objects = set(ref["objects"])
        if not objects or not objects.issubset(assigned_targets):
            unresolved_late_material_refs.append(ref)
    return {
        "operation_count": len(operations),
        "operation_counts": dict(sorted(op_counts.items())),
        "category_counts": dict(sorted(category_counts.items())),
        "craft_operation_count": sum(op_counts[op] for op in CRAFT_OPS),
        "object_name_count": len(unique_names),
        "material_count": len(set(material_names)),
        "material_target_count": len(material_targets),
        "procedural_material_count": procedural_materials,
        "material_craft_signal_count": procedural_materials + len(image_texture_roles) + len(procedural_keys),
        "emissive_material_count": emissive_materials,
        "image_texture_roles": sorted(image_texture_roles),
        "procedural_keys": sorted(procedural_keys),
        "default_names": default_names,
        "unresolved_late_material_references": unresolved_late_material_refs,
        "mesh_boxes": mesh_boxes,
        "surface_detail_paths": surface_detail_paths,
        "text_label_roles": text_label_roles,
        "camera_compositions": camera_compositions,
        "animation_ranges": animation_ranges,
        "animation_count": len(animation_ranges),
        "animation_frame_span_max": max((item["frames"] for item in animation_ranges), default=0),
        "animation_target_count_max": max((item["target_count"] for item in animation_ranges), default=0),
        "animation_glb_export_count": sum(1 for item in animation_ranges if item["include_in_glb"]),
        "looping_animation_count": sum(1 for item in animation_ranges if item["loop"]),
        "camera_path_animation_count": sum(1 for item in animation_ranges if item["camera_path"]),
        "collection_names": sorted(collection_names),
        "nonstandard_collections": sorted(
            name for name in collection_names
            if name and name.upper() not in STANDARD_COLLECTIONS
        ),
        "name_corpus": " ".join((unique_names + material_names)).lower(),
    }


def _fail_if_below(failures: list[str], label: str, actual: int | float, minimum: int | float) -> None:
    if actual < minimum:
        failures.append(f"{label} {actual} < min {minimum}")


def _missing_terms(corpus: str, required: list[str]) -> list[str]:
    return sorted(term for term in (str(item).lower() for item in required or []) if term not in corpus)


def _missing_term_groups(corpus: str, required_groups: list[Any]) -> list[str]:
    missing = []
    for group in required_groups or []:
        terms = group
        if isinstance(group, dict):
            terms = group.get("any") or []
        if isinstance(terms, str):
            terms = [terms]
        normalized = [str(term).lower() for term in terms or []]
        if normalized and not any(term in corpus for term in normalized):
            missing.append("|".join(normalized))
    return sorted(missing)


def _bounds_overlap(a_center: float, a_half: float, b_center: float, b_half: float) -> bool:
    return abs(a_center - b_center) <= (a_half + b_half)


def strap_surface_detail_issues(
    features: dict[str, Any],
    *,
    keywords: list[str],
    margin: float,
) -> list[str]:
    strap_boxes = [
        box for name, box in (features.get("mesh_boxes") or {}).items()
        if "strap" in str(name).lower()
    ]
    if not strap_boxes:
        return []
    lowered_keywords = tuple(str(term).lower() for term in keywords)
    issues: list[str] = []
    for path in features.get("surface_detail_paths") or []:
        prefix = str(path.get("name_prefix") or "")
        prefix_lower = prefix.lower()
        if "strap" not in prefix_lower or not any(term in prefix_lower for term in lowered_keywords):
            continue
        positions = path.get("positions") or []
        if not positions:
            continue
        for idx, position in enumerate(positions, start=1):
            if not isinstance(position, list) or len(position) < 3:
                continue
            overlapping = [
                box for box in strap_boxes
                if _bounds_overlap(float(position[1]), 0.0, float(box["center"][1]), float(box["half"][1]))
            ]
            candidate_boxes = overlapping or strap_boxes
            within_any = any(
                abs(float(position[0]) - float(box["center"][0])) <= float(box["half"][0]) + margin
                for box in candidate_boxes
            )
            if not within_any:
                nearest = min(
                    abs(float(position[0]) - float(box["center"][0])) - float(box["half"][0])
                    for box in candidate_boxes
                )
                issues.append(
                    f"{prefix}_{idx:02d} x={float(position[0]):.3f} exceeds strap width "
                    f"(nearest overrun {nearest:.3f})"
                )
                if len(issues) >= 8:
                    break
        if len(issues) >= 8:
            break
    return issues


def evaluate_static_contract(scenario: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    contract = scenario.get("contract") or {}
    features = recipe_features(recipe)
    validation = validate_recipe(recipe)
    complexity = estimate_complexity(recipe, contract.get("max_estimated_faces", 2_000_000))
    failures: list[str] = []

    if validation.errors:
        failures.extend(f"recipe validation error: {issue.code}: {issue.message}" for issue in validation.errors)
    if contract.get("require_complexity_within_budget", True) and not complexity.get("within_budget", True):
        failures.append(f"estimated complexity exceeds budget: {complexity}")

    _fail_if_below(failures, "operations", features["operation_count"], contract.get("min_operations", 1))
    _fail_if_below(
        failures,
        "craft operations",
        features["craft_operation_count"],
        contract.get("min_craft_operations", 0),
    )
    _fail_if_below(failures, "object/name count", features["object_name_count"], contract.get("min_named_objects", 0))
    _fail_if_below(failures, "materials", features["material_count"], contract.get("min_materials", 0))
    _fail_if_below(
        failures,
        "procedural materials",
        features["procedural_material_count"],
        contract.get("min_procedural_materials", 0),
    )
    _fail_if_below(
        failures,
        "material target objects",
        features["material_target_count"],
        contract.get("min_material_target_objects", 0),
    )
    _fail_if_below(
        failures,
        "material craft signals",
        features["material_craft_signal_count"],
        contract.get("min_material_craft_signals", 0),
    )
    _fail_if_below(
        failures,
        "emissive materials",
        features["emissive_material_count"],
        contract.get("min_emissive_materials", 0),
    )

    for op in contract.get("required_ops") or []:
        if features["operation_counts"].get(op, 0) < 1:
            failures.append(f"required operation missing: {op}")
    for op, minimum in (contract.get("min_operation_counts") or {}).items():
        actual = features["operation_counts"].get(op, 0)
        if actual < int(minimum):
            failures.append(f"operation {op} count {actual} < min {int(minimum)}")
    for op, maximum in (contract.get("max_operation_counts") or {}).items():
        actual = features["operation_counts"].get(op, 0)
        if actual > int(maximum):
            failures.append(f"operation {op} count {actual} > max {int(maximum)}")
    for op in contract.get("required_craft_ops") or []:
        if features["operation_counts"].get(op, 0) < 1:
            failures.append(f"required craft operation missing: {op}")
    for group in contract.get("required_craft_op_groups") or []:
        ops = group.get("any") if isinstance(group, dict) else group
        if isinstance(ops, str):
            ops = [ops]
        candidates = [str(op) for op in ops or []]
        if candidates and not any(features["operation_counts"].get(op, 0) > 0 for op in candidates):
            failures.append(f"required craft operation group missing: {'|'.join(candidates)}")

    missing_terms = _missing_terms(features["name_corpus"], contract.get("require_name_terms") or [])
    if missing_terms:
        failures.append(f"required semantic name terms missing: {', '.join(missing_terms)}")
    forbidden_terms = sorted(
        term for term in (str(item).lower() for item in contract.get("forbid_name_terms") or [])
        if term and term in features["name_corpus"]
    )
    if forbidden_terms:
        failures.append(f"forbidden semantic name terms present: {', '.join(forbidden_terms)}")
    missing_term_groups = _missing_term_groups(
        features["name_corpus"],
        contract.get("require_name_term_groups") or [],
    )
    if missing_term_groups:
        failures.append(f"required semantic name term groups missing: {', '.join(missing_term_groups)}")

    missing_texture_roles = sorted(
        set(contract.get("require_image_texture_roles") or []) - set(features["image_texture_roles"])
    )
    if missing_texture_roles:
        failures.append(f"required image texture roles missing: {', '.join(missing_texture_roles)}")

    missing_proc_keys = sorted(set(contract.get("require_procedural_keys") or []) - set(features["procedural_keys"]))
    if missing_proc_keys:
        failures.append(f"required procedural keys missing: {', '.join(missing_proc_keys)}")

    if contract.get("forbid_default_names", True) and features["default_names"]:
        failures.append(f"default object/material names present: {', '.join(features['default_names'])}")
    if contract.get("forbid_nonstandard_collections", False) and features["nonstandard_collections"]:
        formatted = ", ".join(features["nonstandard_collections"][:8])
        if len(features["nonstandard_collections"]) > 8:
            formatted += f" (+{len(features['nonstandard_collections']) - 8} more)"
        failures.append(f"nonstandard collection names present: {formatted}")
    if contract.get("forbid_unresolved_late_material_references", False):
        refs = features["unresolved_late_material_references"]
        if refs:
            formatted = ", ".join(f"{ref['op']}->{ref['material']}" for ref in refs[:6])
            if len(refs) > 6:
                formatted += f" (+{len(refs) - 6} more)"
            failures.append(f"material referenced before creation without generated-object assignment: {formatted}")
    if contract.get("require_text_label_role", False):
        wrong_roles = [
            item for item in features["text_label_roles"]
            if item["role"] != "text_label"
        ]
        if wrong_roles:
            formatted = ", ".join(f"{item['name']}->{item['role']}" for item in wrong_roles[:6])
            if len(wrong_roles) > 6:
                formatted += f" (+{len(wrong_roles) - 6} more)"
            failures.append(f"create_text_label must keep craft role text_label: {formatted}")
    if contract.get("forbid_strap_surface_detail_outside_width", False):
        issues = strap_surface_detail_issues(
            features,
            keywords=contract.get("strap_surface_detail_keywords") or ["stitch", "grain", "hole"],
            margin=float(contract.get("strap_surface_detail_margin", 0.04)),
        )
        if issues:
            formatted = ", ".join(issues[:6])
            if len(issues) > 6:
                formatted += f" (+{len(issues) - 6} more)"
            failures.append(f"strap surface detail outside strap width: {formatted}")
    if contract.get("max_subject_screen_coverage") is not None:
        max_coverage = float(contract["max_subject_screen_coverage"])
        too_tight = [
            camera for camera in features["camera_compositions"]
            if camera.get("subject_screen_coverage") is not None
            and float(camera["subject_screen_coverage"]) > max_coverage
        ]
        if too_tight:
            formatted = ", ".join(
                f"{camera['camera_name']}={float(camera['subject_screen_coverage']):.2f}"
                for camera in too_tight[:6]
            )
            failures.append(f"camera subject_screen_coverage too tight: {formatted} > {max_coverage:.2f}")
    if contract.get("min_subject_screen_coverage") is not None:
        min_coverage = float(contract["min_subject_screen_coverage"])
        too_loose = [
            camera for camera in features["camera_compositions"]
            if camera.get("subject_screen_coverage") is not None
            and float(camera["subject_screen_coverage"]) < min_coverage
        ]
        if too_loose:
            formatted = ", ".join(
                f"{camera['camera_name']}={float(camera['subject_screen_coverage']):.2f}"
                for camera in too_loose[:6]
            )
            failures.append(f"camera subject_screen_coverage too loose: {formatted} < {min_coverage:.2f}")
    if contract.get("min_camera_safe_margin") is not None:
        min_margin = float(contract["min_camera_safe_margin"])
        too_small = [
            camera for camera in features["camera_compositions"]
            if camera.get("safe_margin") is not None and float(camera["safe_margin"]) < min_margin
        ]
        if too_small:
            formatted = ", ".join(
                f"{camera['camera_name']}={float(camera['safe_margin']):.2f}"
                for camera in too_small[:6]
            )
            failures.append(f"camera safe_margin too small: {formatted} < {min_margin:.2f}")
    if contract.get("max_camera_look_at_y") is not None:
        max_y = float(contract["max_camera_look_at_y"])
        too_high = []
        for camera in features["camera_compositions"]:
            look_at = camera.get("look_at")
            if isinstance(look_at, list) and len(look_at) > 1 and float(look_at[1]) > max_y:
                too_high.append(camera)
        if too_high:
            formatted = ", ".join(
                f"{camera['camera_name']}={float(camera['look_at'][1]):.2f}"
                for camera in too_high[:6]
            )
            failures.append(f"camera look_at y too high for full subject: {formatted} > {max_y:.2f}")
    if contract.get("max_camera_focal_length_mm") is not None:
        max_focal = float(contract["max_camera_focal_length_mm"])
        too_long = [
            camera for camera in features["camera_compositions"]
            if camera.get("focal_length_mm") is not None and float(camera["focal_length_mm"]) > max_focal
        ]
        if too_long:
            formatted = ", ".join(
                f"{camera['camera_name']}={float(camera['focal_length_mm']):.1f}mm"
                for camera in too_long[:6]
            )
            failures.append(f"camera focal length too long for full reference subject: {formatted} > {max_focal:.1f}mm")
    if contract.get("require_camera_composition", False):
        missing = [
            camera for camera in features["camera_compositions"]
            if camera.get("subject_screen_coverage") is None or camera.get("safe_margin") is None
        ]
        if not features["camera_compositions"]:
            failures.append("camera composition metadata missing: no create_camera operation")
        elif missing:
            formatted = ", ".join(camera["camera_name"] or "<unnamed>" for camera in missing[:6])
            failures.append(f"camera composition metadata missing subject_screen_coverage/safe_margin: {formatted}")
    if contract.get("require_animation", False) and features["animation_count"] < 1:
        failures.append("required animation missing: create_animation")
    _fail_if_below(
        failures,
        "animation frames",
        features["animation_frame_span_max"],
        contract.get("min_animation_frames", 0),
    )
    _fail_if_below(
        failures,
        "animation target objects",
        features["animation_target_count_max"],
        contract.get("min_animation_targets", 0),
    )
    if contract.get("require_glb_animation", False) and features["animation_glb_export_count"] < 1:
        failures.append("required GLB animation export missing: create_animation export.include_in_glb")
    if contract.get("require_looping_animation", False) and features["looping_animation_count"] < 1:
        failures.append("required looping animation missing: create_animation loop=true")
    if contract.get("require_camera_path_animation", False) and features["camera_path_animation_count"] < 1:
        failures.append("required camera path animation missing: create_animation camera_path=true")

    return {
        "scenario_id": scenario["id"],
        "static_pass": not failures,
        "provenance": (scenario.get("candidate") or {}).get("provenance", "unknown"),
        "live_agent_run": (scenario.get("candidate") or {}).get("provenance") == "live_agent",
        "features": {k: v for k, v in features.items() if k != "name_corpus"},
        "complexity": complexity,
        "validation": validation.to_dict(),
        "failures": failures,
    }


def evaluate_scenario(
    scenario: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
    *,
    render: bool,
    blender_exe: str | None,
    out_root: Path,
) -> dict[str, Any]:
    recipe = _candidate_recipe(scenario, tasks)
    static = evaluate_static_contract(scenario, recipe)
    render_result = None
    if render:
        task_id = (scenario.get("candidate") or {}).get("task_id") or scenario.get("task_id")
        task = dict(tasks[task_id])
        task["recipe"] = recipe
        render_result = run_recipe(task, recipe, f"prompt_{scenario['id']}", blender_exe, out_root)
    return {
        **static,
        "title": scenario.get("title", scenario["id"]),
        "prompt": scenario.get("prompt", ""),
        "task_id": (scenario.get("candidate") or {}).get("task_id") or scenario.get("task_id"),
        "render_requested": render,
        "render_result": render_result,
        "pass": static["static_pass"] and (render_result is None or bool(render_result.get("pass"))),
    }


def evaluate_live_agent_run(
    run: dict[str, Any],
    scenario: dict[str, Any],
    tasks: dict[str, dict[str, Any]],
    *,
    render: bool,
    blender_exe: str | None,
    out_root: Path,
) -> dict[str, Any]:
    failures: list[str] = []
    run_id = str(run.get("id") or "unnamed_live_run")
    try:
        parsed = extract_json_object(run.get("raw_output"))
    except Exception as exc:
        parsed = {}
        failures.append(f"raw output parse failed: {exc}")

    metadata = parsed.get("metadata") if isinstance(parsed.get("metadata"), dict) else {}
    if metadata.get("claim_level") != "live_agent_raw_output":
        failures.append("metadata.claim_level must be live_agent_raw_output")
    for key in ("agent_label", "skill_path", "generated_at_note"):
        if not metadata.get(key):
            failures.append(f"metadata.{key} is required")

    expected_prompt = str(scenario.get("prompt") or "")
    actual_prompt = str(parsed.get("prompt") or "")
    if actual_prompt != expected_prompt:
        failures.append("parsed prompt must exactly match scenario prompt")

    recipe = parsed.get("recipe") if isinstance(parsed.get("recipe"), dict) else None
    if recipe is None:
        recipe = {"operations": []}
        failures.append("parsed recipe object is required")

    live_scenario = dict(scenario)
    live_scenario["candidate"] = {
        "source": "live_agent_archive",
        "provenance": "live_agent",
        "run_id": run_id,
        "task_id": (scenario.get("candidate") or {}).get("task_id") or scenario.get("task_id"),
    }
    static = evaluate_static_contract(live_scenario, recipe)
    render_result = None
    if render and not failures:
        task_id = live_scenario["candidate"]["task_id"]
        task = dict(tasks[task_id])
        task["recipe"] = recipe
        render_result = run_recipe(task, recipe, f"live_{run_id}", blender_exe, out_root)
    all_failures = failures + static["failures"]
    return {
        **static,
        "scenario_id": scenario["id"],
        "run_id": run_id,
        "title": run.get("title", scenario.get("title", run_id)),
        "prompt": expected_prompt,
        "task_id": live_scenario["candidate"]["task_id"],
        "archive_metadata": {
            "source_agent": run.get("source_agent"),
            "model": run.get("model"),
            "created_at": run.get("created_at"),
        },
        "parsed_metadata": metadata,
        "render_requested": render,
        "render_result": render_result,
        "failures": all_failures,
        "static_pass": static["static_pass"] and not failures,
        "live_agent_run": True,
        "provenance": "live_agent",
        "pass": static["static_pass"] and not failures and (render_result is None or bool(render_result.get("pass"))),
    }


def run_prompt_scenarios(
    selected: list[str] | None = None,
    *,
    render: bool = False,
    blender_exe: str | None = None,
    out: str | Path = ROOT / "artifacts" / "prompt_scenarios",
) -> dict[str, Any]:
    tasks = load_tasks()
    scenarios = load_scenarios()
    scenario_ids = selected or list(scenarios)
    out_root = Path(out)
    results = [
        evaluate_scenario(scenarios[scenario_id], tasks, render=render, blender_exe=blender_exe, out_root=out_root)
        for scenario_id in scenario_ids
    ]
    summary = {
        "scenario_count": len(results),
        "passed": sum(1 for result in results if result["pass"]),
        "render_requested": render,
        "acceptance_level": "prompt_fixture_plus_render" if render else "static_prompt_fixture_contract",
        "live_agent_runs": sum(1 for result in results if result.get("live_agent_run")),
        "results": results,
    }
    results_resolver = WorkspaceResolver([ROOT, out_root])
    results_resolver.ensure_dir(RESULTS_DIR)
    results_resolver.write_text(RESULTS_DIR / "summary.json", json.dumps(summary, indent=2))
    results_resolver.write_text(out_root / "prompt_scenarios_summary.json", json.dumps(summary, indent=2))
    return summary


def run_live_agent_runs(
    selected: list[str] | None = None,
    *,
    render: bool = False,
    blender_exe: str | None = None,
    out: str | Path = ROOT / "artifacts" / "live_agent_prompt_runs",
    runs_dir: str | Path = LIVE_RUNS_DIR,
) -> dict[str, Any]:
    tasks = load_tasks()
    scenarios = load_scenarios()
    runs = load_live_agent_runs(Path(runs_dir))
    run_ids = selected or list(runs)
    out_root = Path(out)
    results = []
    for run_id in run_ids:
        run = runs[run_id]
        scenario_id = run.get("scenario_id")
        if scenario_id not in scenarios:
            results.append({
                "run_id": run_id,
                "scenario_id": scenario_id,
                "pass": False,
                "static_pass": False,
                "render_requested": render,
                "render_result": None,
                "live_agent_run": True,
                "provenance": "live_agent",
                "failures": [f"unknown scenario_id: {scenario_id!r}"],
            })
            continue
        results.append(
            evaluate_live_agent_run(
                run,
                scenarios[scenario_id],
                tasks,
                render=render,
                blender_exe=blender_exe,
                out_root=out_root,
            )
        )
    summary = {
        "run_count": len(results),
        "scenario_count": len({result.get("scenario_id") for result in results}),
        "passed": sum(1 for result in results if result["pass"]),
        "render_requested": render,
        "acceptance_level": "live_agent_plus_render" if render else "live_agent_static_contract",
        "live_agent_runs": len(results),
        "results": results,
    }
    results_resolver = WorkspaceResolver([ROOT, out_root])
    results_resolver.ensure_dir(RESULTS_DIR)
    results_resolver.write_text(RESULTS_DIR / "live_summary.json", json.dumps(summary, indent=2))
    results_resolver.write_text(out_root / "live_agent_runs_summary.json", json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="list prompt scenarios")
    parser.add_argument("--scenarios", default=None, help="comma-separated scenario ids")
    parser.add_argument("--live-runs", action="store_true", help="evaluate archived live-agent raw outputs")
    parser.add_argument("--runs", default=None, help="comma-separated live-agent run ids")
    parser.add_argument("--live-runs-dir", default=str(LIVE_RUNS_DIR))
    parser.add_argument("--render", action="store_true", help="also run real Blender render benchmark checks")
    parser.add_argument("--blender", default=None, help="Blender executable override")
    parser.add_argument("--out", default=str(ROOT / "artifacts" / "prompt_scenarios"))
    args = parser.parse_args(argv)

    scenarios = load_scenarios()
    if args.list:
        if args.live_runs:
            runs = load_live_agent_runs(Path(args.live_runs_dir))
            for run_id, run in runs.items():
                print(f"{run_id:32} [live_agent] {run.get('scenario_id', '?')}")
            return 0
        for scenario_id, scenario in scenarios.items():
            provenance = (scenario.get("candidate") or {}).get("provenance", "unknown")
            print(f"{scenario_id:32} [{provenance}] {scenario.get('title', '')}")
        return 0

    selected = args.scenarios.split(",") if args.scenarios else None
    if args.render:
        from blender_cinematic.blender import locate_blender

        blender_exe = locate_blender(args.blender)
        if not blender_exe:
            print("ERROR: Blender not found; --render prompt scenarios need Blender.")
            return 1
    else:
        blender_exe = args.blender

    if args.live_runs:
        selected_runs = args.runs.split(",") if args.runs else None
        summary = run_live_agent_runs(
            selected_runs,
            render=args.render,
            blender_exe=blender_exe,
            out=args.out,
            runs_dir=args.live_runs_dir,
        )
        results = summary["results"]
    else:
        summary = run_prompt_scenarios(selected, render=args.render, blender_exe=blender_exe, out=args.out)
        results = summary["results"]
    for result in results:
        status = "PASS" if result["pass"] else "FAIL"
        render_status = "render=not_requested"
        if result["render_result"] is not None:
            render_status = f"render={'PASS' if result['render_result'].get('pass') else 'FAIL'}"
        display_id = result.get("run_id") or result.get("scenario_id")
        print(
            f"{display_id:32} {status} static={'PASS' if result['static_pass'] else 'FAIL'} "
            f"{render_status} provenance={result['provenance']}"
        )
        for failure in result["failures"]:
            print(f"  - {failure}")
        if result["render_result"] and result["render_result"].get("failures"):
            for failure in result["render_result"]["failures"]:
                print(f"  - render: {failure}")
    print(
        f"prompt scenarios: {summary['passed']}/{summary.get('scenario_count', summary.get('run_count', 0))} PASS "
        f"({summary['acceptance_level']}, live_agent_runs={summary['live_agent_runs']})"
    )
    total = summary.get("run_count", summary.get("scenario_count", 0))
    return 0 if summary["passed"] == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
