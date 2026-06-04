#!/usr/bin/env python
# ruff: noqa: E402
"""Benchmark runner (SRS 16 / 45).

Executes a benchmark task's recipe through real Blender, inspects, lints, scores
against the rubric, applies the task's checks, and emits a structured result.
With ``--baseline`` it also runs the task's naive recipe to demonstrate the
skill's measurable improvement over unstructured "dump some primitives" output.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from blender_cinematic import runner
from blender_cinematic.budget import compute_budget
from blender_cinematic.evaluation import score_iteration
from blender_cinematic.glb import validate_glb
from blender_cinematic.imaging import (
    frame_visual_delta,
    image_sanity,
    palette_from_names,
    palette_similarity,
    reference_fidelity_metrics,
    salient_palette,
    ssim,
)
from blender_cinematic.linters import lint_scene
from blender_cinematic.preflight import collect_hardware_report
from blender_cinematic.visual_review import style_tags_for_preview
from blender_cinematic.workspace import WorkspaceResolver, task_workspace

TASKS_DIR = ROOT / "benchmarks" / "tasks"
RESULTS_DIR = ROOT / "benchmarks" / "results"
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}
VISUAL_OBJECT_TYPES = {"MESH", "CURVE", "FONT"}
PART_NAME_ALIASES = {
    "glass": ("glass", "sapphire", "crystal"),
    "marker": ("marker", "index", "indices", "indice", "hash"),
    "highlight": ("highlight", "catchlight", "glint"),
    "reflection": ("reflection", "reflect", "catchlight", "glint"),
}


def load_tasks():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(TASKS_DIR.glob("*.json"))}


def resolve_task_path(path: str | None) -> Path | None:
    if not path:
        return None
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return (ROOT / candidate).resolve()


def _budget(profile, project_dir, blender_exe):
    report = collect_hardware_report(project_dir, blender_exe)
    b = compute_budget(report, profile)
    # keep benchmark renders cheap regardless of hardware
    b["preview_resolution"] = [480, 270]
    b["final_resolution"] = [640, 360]
    b["samples"] = min(b.get("samples", 32), 24)
    b["selected_engine"] = "EEVEE"
    b["preview_engine"] = "EEVEE"
    return b


def count_position_layers(objects, axis="z", tolerance=0.25):
    """Count separated object-location bands along an axis for exploded/layout gates."""
    idx = AXIS_INDEX.get(str(axis).lower(), 2)
    values = []
    for obj in objects:
        loc = obj.get("location") or []
        if len(loc) > idx:
            try:
                values.append(float(loc[idx]))
            except (TypeError, ValueError):
                continue
    if not values:
        return 0
    values.sort()
    layers = [values[0]]
    for value in values[1:]:
        if abs(value - layers[-1]) > float(tolerance):
            layers.append(value)
    return len(layers)


def count_visible_objects(objects, min_coverage=0.0):
    return sum(
        1
        for obj in objects
        if obj.get("in_camera_frame") and float(obj.get("screen_coverage", 0.0) or 0.0) >= float(min_coverage)
    )


def count_smooth_objects(objects):
    return sum(1 for obj in objects if obj.get("smooth"))


def count_craft_role_objects(objects, required_roles=None):
    roles = {str(role) for role in (required_roles or [])}
    count = 0
    for obj in objects:
        role = obj.get("craft_role")
        if not role:
            continue
        if roles and str(role) not in roles:
            continue
        count += 1
    return count


def missing_craft_roles(objects, required_roles):
    present = {str(obj.get("craft_role")) for obj in objects if obj.get("craft_role")}
    return sorted(str(role) for role in (required_roles or []) if str(role) not in present)


def geometry_detail_roles(objects, geometry_nodes=None):
    roles = set()
    for obj in objects:
        role = obj.get("gn_role")
        if role:
            roles.add(str(role))
    for node_group in geometry_nodes or []:
        raw = str(node_group.get("detail_roles") or "")
        for role in raw.split(","):
            role = role.strip()
            if role:
                roles.add(role)
    return roles


def count_geometry_detail_objects(objects, required_roles=None):
    roles = {str(role) for role in (required_roles or [])}
    count = 0
    for obj in objects:
        role = obj.get("gn_role")
        if not role:
            continue
        if roles and str(role) not in roles:
            continue
        if obj.get("type") not in VISUAL_OBJECT_TYPES:
            continue
        count += 1
    return count


def missing_geometry_detail_roles(objects, geometry_nodes, required_roles):
    present = geometry_detail_roles(objects, geometry_nodes)
    return sorted(str(role) for role in (required_roles or []) if str(role) not in present)


def count_curved_detail_objects(objects, keywords=("petal", "leaf", "fold"), min_faces=24):
    count = 0
    needles = tuple(str(k).lower() for k in keywords)
    for obj in objects:
        name = str(obj.get("name", "")).lower()
        if not any(needle in name for needle in needles):
            continue
        if not obj.get("smooth"):
            continue
        if int(obj.get("faces", 0) or 0) < int(min_faces):
            continue
        count += 1
    return count


def missing_named_parts(objects, required_parts):
    names = [str(obj.get("name", "")).lower() for obj in objects]
    missing = []
    for part in required_parts or []:
        needles = PART_NAME_ALIASES.get(str(part).lower(), (str(part).lower(),))
        if not any(any(needle in name for needle in needles) for name in names):
            missing.append(str(part))
    return missing


def _matches_named_part(name, required_parts):
    for part in required_parts or []:
        needles = PART_NAME_ALIASES.get(str(part).lower(), (str(part).lower(),))
        if any(needle in name for needle in needles):
            return True
    return False


def named_part_visible_objects(objects, required_parts, min_coverage=0.0):
    """Return distinct visible objects that carry required semantic part names.

    This prevents a benchmark from being satisfied by offscreen or microscopic
    keyword objects that exist only to game `require_named_parts`.
    """
    visible = []
    seen = set()
    for obj in objects:
        name = str(obj.get("name", "")).lower()
        if not _matches_named_part(name, required_parts):
            continue
        if not obj.get("in_camera_frame"):
            continue
        if float(obj.get("screen_coverage", 0.0) or 0.0) < float(min_coverage):
            continue
        key = obj.get("name") or id(obj)
        if key in seen:
            continue
        seen.add(key)
        visible.append(obj)
    return visible


def named_part_total_coverage(objects, required_parts, min_coverage=0.0):
    return sum(
        float(obj.get("screen_coverage", 0.0) or 0.0)
        for obj in named_part_visible_objects(objects, required_parts, min_coverage)
    )


def material_feature_set(materials):
    features = set()
    for mat in materials:
        raw = str(mat.get("procedural_features") or "")
        for feature in raw.split(","):
            feature = feature.strip()
            if feature:
                features.add(feature)
    return features


def material_image_texture_roles(materials):
    roles = set()
    for mat in materials:
        raw = str(mat.get("image_texture_roles") or "")
        for role in raw.split(","):
            role = role.strip()
            if role:
                roles.add(role)
    return roles


def material_node_name_matches(materials):
    names = set()
    for mat in materials:
        for node_name in mat.get("node_names") or []:
            text = str(node_name).strip()
            if text:
                names.add(text)
    return names


def missing_material_node_name_substrings(materials, required):
    node_names = material_node_name_matches(materials)
    missing = []
    for needle in required or []:
        wanted = str(needle)
        if not any(wanted in node_name for node_name in node_names):
            missing.append(wanted)
    return sorted(missing)


def count_rich_linked_materials(materials, *, min_nodes=8, min_links=6):
    return sum(
        1
        for mat in materials
        if int(mat.get("node_count", 0) or 0) >= int(min_nodes)
        and int(mat.get("link_count", 0) or 0) >= int(min_links)
    )


def material_names_for_objects(objects):
    return {
        mat
        for obj in objects
        for mat in (obj.get("materials") or [])
    }


def visual_collection_objects(inspection, collection):
    return [
        obj for obj in inspection.get("objects", [])
        if obj.get("collection") == collection and obj.get("type") in VISUAL_OBJECT_TYPES
    ]


def mesh_collection_objects(inspection, collection):
    return [
        obj for obj in inspection.get("objects", [])
        if obj.get("collection") == collection and obj.get("type") == "MESH"
    ]


def count_emissive_materials(materials):
    return sum(1 for mat in materials if mat.get("has_emission"))


def total_particle_count(particles):
    total = 0
    for particle_system in particles:
        try:
            total += int(particle_system.get("count", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def count_sampled_moving_objects(animation, min_location_delta=0.01, min_rotation_delta=0.1):
    count = 0
    for item in (animation or {}).get("sampled_objects") or []:
        loc = float(item.get("max_location_delta", 0.0) or 0.0)
        rot = float(item.get("max_rotation_delta", 0.0) or 0.0)
        if loc >= float(min_location_delta) or rot >= float(min_rotation_delta):
            count += 1
    return count


def camera_sampled_location_delta(animation):
    camera_motion = (animation or {}).get("camera_sampled_motion") or {}
    return float(camera_motion.get("max_location_delta", 0.0) or 0.0)


def animation_frame_delta_metrics(frame_paths):
    if len(frame_paths) < 2:
        return {
            "frame_count": len(frame_paths),
            "pairs": [],
            "max_mean_rgb_delta": 0.0,
            "max_changed_pixel_ratio": 0.0,
        }
    pairs = []
    for a, b in zip(frame_paths, frame_paths[1:]):
        delta = frame_visual_delta(a, b)
        pairs.append({
            "from": str(a),
            "to": str(b),
            **delta,
        })
    return {
        "frame_count": len(frame_paths),
        "frames": [str(path) for path in frame_paths],
        "pairs": pairs,
        "max_mean_rgb_delta": max(pair["mean_rgb_delta"] for pair in pairs),
        "max_changed_pixel_ratio": max(pair["changed_pixel_ratio"] for pair in pairs),
    }


def render_animation_frame_proof(base, blend, budget, blender_exe, animation, checks):
    if not (
        checks.get("min_animation_frame_delta")
        or checks.get("min_animation_changed_pixel_ratio")
        or checks.get("require_animation_frame_proof")
    ):
        return None
    fs = int(animation.get("frame_start", 1) or 1)
    fe = int(animation.get("frame_end", fs) or fs)
    mid = int(round((fs + fe) / 2))
    frames = sorted({fs, mid, fe})
    frame_paths = []
    for frame in frames:
        out_path = base / "iterations" / f"animation_frame_{frame:04d}.png"
        result = runner.run_job(
            runner.build_job(
                "render_preview",
                base,
                blend,
                budget=budget,
                render={"frame": frame},
                output={"image": str(out_path)},
            ),
            blender_exe,
            300,
        )
        if result.get("ok") and out_path.exists():
            frame_paths.append(out_path)
    metrics = animation_frame_delta_metrics(frame_paths)
    metrics["requested_frames"] = frames
    return metrics


def visual_style_tag_failures(style_tags, checks):
    failures = []
    tags = set(style_tags or [])
    forbidden = sorted(tags & set(checks.get("forbid_visual_style_tags") or []))
    if forbidden:
        failures.append(f"forbidden visual style tags present: {', '.join(forbidden)}")
    required = sorted(set(checks.get("require_visual_style_tags") or []) - tags)
    if required:
        failures.append(f"required visual style tags missing: {', '.join(required)}")
    return failures


def eval_defect_failures(defects, checks):
    failures = []
    forbidden = [str(item).lower() for item in checks.get("forbid_eval_defect_substrings") or []]
    if not forbidden:
        return failures
    for defect in defects or []:
        defect_text = str(defect)
        defect_lower = defect_text.lower()
        if any(needle in defect_lower for needle in forbidden):
            failures.append(f"forbidden eval defect present: {defect_text}")
    return failures


def run_recipe(task, recipe, mode, blender_exe, out_root):
    t0 = time.time()
    manifest = task["manifest"]
    profile = task.get("profile", "balanced")
    resolver, base = task_workspace(out_root, f"{task['id']}_{mode}")
    resolver.write_text(base / "scene_manifest.json", json.dumps(manifest, indent=2))
    budget = _budget(profile, base, blender_exe)
    preview = base / "iterations" / "iter_01_preview.png"
    glb = base / "final" / "export_final.glb"
    out = {"image": str(preview)}
    wants_web = manifest.get("output_mode") in ("web_asset", "interactive_web")
    if wants_web:
        out["glb"] = str(glb)
    job = runner.build_job(
        "full_pipeline",
        base,
        base / "final" / "scene.blend",
        manifest=manifest,
        budget=budget,
        recipe=recipe,
        output=out,
    )
    blend = base / "final" / "scene.blend"
    pipe = runner.run_job(job, blender_exe, timeout=600)
    insp = runner.run_job(
        runner.build_job("inspect", base, blend),
        blender_exe,
        180,
    ).get("inspection", {})
    # interactive_web: generate the scroll integration + camera path, then record it.
    if manifest.get("output_mode") == "interactive_web":
        from blender_cinematic.webgen import generate_integration
        segs = [
            {
                "from_scroll": 0.0,
                "to_scroll": 0.5,
                "camera_from_frame": 1,
                "camera_to_frame": 60,
                "text_section": "intro",
            },
            {
                "from_scroll": 0.5,
                "to_scroll": 1.0,
                "camera_from_frame": 61,
                "camera_to_frame": 120,
                "text_section": "reveal",
            },
        ]
        samples = [
            {"position": [0, -7, 2.2], "target": [0, 0, 1.6]},
            {"position": [4, -5, 3], "target": [0, 0, 1.6]},
        ]
        written = generate_integration(
            base / "web-demo",
            resolver,
            scroll_segments=segs,
            scroll_samples=samples,
        )
        insp["camera_path_json"] = written.get("camera_path")
    lint = lint_scene(insp, manifest, budget)
    metrics = image_sanity(preview) if preview.exists() else None
    visual_style_tags = style_tags_for_preview(str(preview)) if preview.exists() else ["missing_preview"]
    checks = task.get("checks", {})
    reference_metrics = None
    palette_similarity_value = None
    expected_palette = palette_from_names(((manifest.get("style") or {}).get("palette") or []))
    reference_path = resolve_task_path(task.get("reference_image") or checks.get("reference_image"))
    if preview.exists() and reference_path and reference_path.exists():
        palette_similarity_value = palette_similarity(salient_palette(preview, k=8), salient_palette(reference_path, k=8))
        reference_metrics = {
            "ssim": ssim(preview, reference_path),
            "palette_similarity": palette_similarity_value,
            "reference_image": str(reference_path),
            **reference_fidelity_metrics(preview, reference_path),
        }
    elif preview.exists() and expected_palette:
        palette_similarity_value = palette_similarity(salient_palette(preview, k=8), expected_palette)
    web_ok = None
    glb_validation = None
    if wants_web and glb.exists():
        glb_validation = validate_glb(glb, manifest.get("constraints", {}).get("max_glb_mb"))
        web_ok = glb_validation.get("ok")
    ev = score_iteration(1, insp, lint, metrics, manifest, budget,
                         reference_metrics=reference_metrics, web_load_ok=web_ok)
    resolver.write_text(base / "iterations" / "iter_01_eval.json", json.dumps(ev.to_dict(), indent=2))

    failures = list(ev.hard_fail_reasons)
    failures.extend(visual_style_tag_failures(visual_style_tags, checks))
    failures.extend(eval_defect_failures(ev.defects, checks))
    if not pipe.get("ok"):
        failures.append(f"pipeline failed: {pipe.get('error', 'unknown_error')}")
    if ev.total < checks.get("min_score", 80):
        failures.append(f"score {ev.total} < min {checks.get('min_score', 80)}")
    subject_objects = visual_collection_objects(insp, "SUBJECT")
    subject_mesh_objects = mesh_collection_objects(insp, "SUBJECT")
    environment_objects = visual_collection_objects(insp, "ENVIRONMENT")
    max_coverage = max((o.get("screen_coverage", 0) for o in subject_objects), default=0)
    if checks.get("max_subject_coverage") is not None and max_coverage > checks["max_subject_coverage"]:
        failures.append(
            f"subject coverage {max_coverage:.2f} > max {checks['max_subject_coverage']:.2f}"
        )
    if checks.get("min_subject_objects") is not None and len(subject_objects) < checks["min_subject_objects"]:
        failures.append(
            f"subject objects {len(subject_objects)} < min {checks['min_subject_objects']}"
        )
    if checks.get("min_visible_subject_objects") is not None:
        min_visible_coverage = checks.get("min_visible_subject_coverage", 0.0)
        visible = count_visible_objects(subject_objects, min_visible_coverage)
        if visible < checks["min_visible_subject_objects"]:
            failures.append(
                f"visible subject objects {visible} < min {checks['min_visible_subject_objects']}"
            )
    if checks.get("max_offscreen_subject_objects") is not None:
        offscreen = sum(1 for o in subject_objects if not o.get("in_camera_frame"))
        if offscreen > checks["max_offscreen_subject_objects"]:
            failures.append(
                f"offscreen subject objects {offscreen} > max {checks['max_offscreen_subject_objects']}"
            )
    if checks.get("min_subject_depth_layers") is not None:
        layers = count_position_layers(
            subject_objects,
            axis=checks.get("subject_depth_axis", "z"),
            tolerance=checks.get("subject_depth_tolerance", 0.25),
        )
        if layers < checks["min_subject_depth_layers"]:
            failures.append(
                f"subject depth layers {layers} < min {checks['min_subject_depth_layers']}"
            )
    if checks.get("require_named_parts"):
        missing = missing_named_parts(subject_objects, checks["require_named_parts"])
        if missing:
            failures.append(f"missing named subject parts: {', '.join(missing)}")
        named_part_min_coverage = checks.get("min_named_part_object_coverage", 0.0)
        named_visible = named_part_visible_objects(
            subject_objects,
            checks["require_named_parts"],
            named_part_min_coverage,
        )
        if checks.get("min_distinct_named_part_objects") is not None:
            if len(named_visible) < checks["min_distinct_named_part_objects"]:
                failures.append(
                    "distinct visible named-part objects "
                    f"{len(named_visible)} < min {checks['min_distinct_named_part_objects']}"
                )
        if checks.get("min_named_part_total_coverage") is not None:
            coverage = named_part_total_coverage(
                subject_objects,
                checks["require_named_parts"],
                named_part_min_coverage,
            )
            if coverage < checks["min_named_part_total_coverage"]:
                failures.append(
                    f"named-part total coverage {coverage:.4f} < min {checks['min_named_part_total_coverage']:.4f}"
                )
    if checks.get("min_subject_total_faces") is not None:
        faces = sum(int(o.get("faces", 0) or 0) for o in subject_mesh_objects)
        if faces < checks["min_subject_total_faces"]:
            failures.append(
                f"subject faces {faces} < min {checks['min_subject_total_faces']}"
            )
    if checks.get("min_subject_modifiers") is not None:
        modifiers = sum(len(o.get("modifiers") or []) for o in subject_mesh_objects)
        if modifiers < checks["min_subject_modifiers"]:
            failures.append(
                f"subject modifiers {modifiers} < min {checks['min_subject_modifiers']}"
            )
    if checks.get("min_smooth_subject_objects") is not None:
        smooth = count_smooth_objects(subject_mesh_objects)
        if smooth < checks["min_smooth_subject_objects"]:
            failures.append(
                f"smooth subject objects {smooth} < min {checks['min_smooth_subject_objects']}"
            )
    if checks.get("min_craft_detail_objects") is not None:
        craft = count_craft_role_objects(
            subject_objects,
            required_roles=checks.get("require_craft_roles"),
        )
        if craft < checks["min_craft_detail_objects"]:
            failures.append(
                f"craft detail objects {craft} < min {checks['min_craft_detail_objects']}"
            )
    if checks.get("require_craft_roles"):
        missing = missing_craft_roles(subject_objects, checks["require_craft_roles"])
        if missing:
            failures.append(f"missing craft roles: {', '.join(missing)}")
    if checks.get("min_curved_detail_objects") is not None:
        curved = count_curved_detail_objects(
            subject_mesh_objects,
            keywords=checks.get("curved_detail_keywords", ("petal", "leaf", "fold")),
            min_faces=checks.get("curved_detail_min_faces", 24),
        )
        if curved < checks["min_curved_detail_objects"]:
            failures.append(
                f"curved detail objects {curved} < min {checks['min_curved_detail_objects']}"
            )
    if checks.get("min_environment_objects") is not None and len(environment_objects) < checks["min_environment_objects"]:
        failures.append(
            f"environment objects {len(environment_objects)} < min {checks['min_environment_objects']}"
        )
    if checks.get("min_visible_environment_objects") is not None:
        min_visible_coverage = checks.get("min_visible_environment_coverage", 0.0)
        visible = count_visible_objects(environment_objects, min_visible_coverage)
        if visible < checks["min_visible_environment_objects"]:
            failures.append(
                f"visible environment objects {visible} < min {checks['min_visible_environment_objects']}"
            )
    if checks.get("max_offscreen_environment_objects") is not None:
        offscreen = sum(1 for o in environment_objects if not o.get("in_camera_frame"))
        if offscreen > checks["max_offscreen_environment_objects"]:
            failures.append(
                f"offscreen environment objects {offscreen} > max {checks['max_offscreen_environment_objects']}"
            )
    if checks.get("min_environment_depth_layers") is not None:
        layers = count_position_layers(
            environment_objects,
            axis=checks.get("environment_depth_axis", checks.get("subject_depth_axis", "z")),
            tolerance=checks.get("environment_depth_tolerance", checks.get("subject_depth_tolerance", 0.25)),
        )
        if layers < checks["min_environment_depth_layers"]:
            failures.append(
                f"environment depth layers {layers} < min {checks['min_environment_depth_layers']}"
            )
    if checks.get("require_environment_named_parts"):
        missing = missing_named_parts(environment_objects, checks["require_environment_named_parts"])
        if missing:
            failures.append(f"missing named environment parts: {', '.join(missing)}")
    environment_material_names = material_names_for_objects(environment_objects)
    if checks.get("min_environment_materials") is not None and len(environment_material_names) < checks["min_environment_materials"]:
        failures.append(
            f"environment materials {len(environment_material_names)} < min {checks['min_environment_materials']}"
        )
    material_names = material_names_for_objects(subject_objects)
    if checks.get("min_subject_materials") is not None and len(material_names) < checks["min_subject_materials"]:
        failures.append(
            f"subject materials {len(material_names)} < min {checks['min_subject_materials']}"
        )
    material_info = {m.get("name"): m for m in insp.get("materials", [])}
    subject_material_info = [material_info[name] for name in material_names if name in material_info]
    if checks.get("min_subject_material_node_count") is not None:
        max_nodes = max((m.get("node_count", 0) for m in subject_material_info), default=0)
        if max_nodes < checks["min_subject_material_node_count"]:
            failures.append(
                f"subject material node count {max_nodes} < min {checks['min_subject_material_node_count']}"
            )
    if checks.get("min_subject_material_link_count") is not None:
        max_links = max((m.get("link_count", 0) for m in subject_material_info), default=0)
        if max_links < checks["min_subject_material_link_count"]:
            failures.append(
                f"subject material link count {max_links} < min {checks['min_subject_material_link_count']}"
            )
    if checks.get("min_rich_linked_subject_materials") is not None:
        rich_count = count_rich_linked_materials(
            subject_material_info,
            min_nodes=checks.get("rich_material_min_nodes", 8),
            min_links=checks.get("rich_material_min_links", 6),
        )
        if rich_count < checks["min_rich_linked_subject_materials"]:
            failures.append(
                "rich linked subject materials "
                f"{rich_count} < min {checks['min_rich_linked_subject_materials']}"
            )
    if checks.get("min_subject_procedural_materials") is not None:
        procedural_count = sum(1 for m in subject_material_info if m.get("procedural_features"))
        if procedural_count < checks["min_subject_procedural_materials"]:
            failures.append(
                f"subject procedural materials {procedural_count} < min {checks['min_subject_procedural_materials']}"
            )
    if checks.get("require_subject_material_features"):
        features = material_feature_set(subject_material_info)
        missing = sorted(set(checks["require_subject_material_features"]) - features)
        if missing:
            failures.append(f"missing subject material features: {', '.join(missing)}")
    if checks.get("require_subject_material_node_name_substrings"):
        missing = missing_material_node_name_substrings(
            subject_material_info,
            checks["require_subject_material_node_name_substrings"],
        )
        if missing:
            failures.append(f"missing subject material node names: {', '.join(missing)}")
    if checks.get("require_subject_image_texture_roles"):
        image_roles = material_image_texture_roles(subject_material_info)
        missing = sorted(set(checks["require_subject_image_texture_roles"]) - image_roles)
        if missing:
            failures.append(f"missing subject image texture roles: {', '.join(missing)}")
    if checks.get("min_emissive_materials") is not None:
        emissive = count_emissive_materials(insp.get("materials", []))
        if emissive < checks["min_emissive_materials"]:
            failures.append(
                f"emissive materials {emissive} < min {checks['min_emissive_materials']}"
            )
    particles = insp.get("particles") or []
    if checks.get("min_particle_systems") is not None and len(particles) < checks["min_particle_systems"]:
        failures.append(
            f"particle systems {len(particles)} < min {checks['min_particle_systems']}"
        )
    if checks.get("min_total_particles") is not None:
        total_particles = total_particle_count(particles)
        if total_particles < checks["min_total_particles"]:
            failures.append(
                f"total particles {total_particles} < min {checks['min_total_particles']}"
            )
    if checks.get("min_palette_similarity") is not None:
        sim = palette_similarity_value if palette_similarity_value is not None else 0.0
        if sim < checks["min_palette_similarity"]:
            failures.append(
                f"palette similarity {sim:.2f} < min {checks['min_palette_similarity']:.2f}"
            )
    if checks.get("min_reference_ssim") is not None:
        sim = (reference_metrics or {}).get("ssim", 0.0)
        if sim < checks["min_reference_ssim"]:
            failures.append(
                f"reference SSIM {sim:.2f} < min {checks['min_reference_ssim']:.2f}"
            )
    if checks.get("min_reference_saliency_iou") is not None:
        value = (reference_metrics or {}).get("saliency_iou", 0.0)
        if value < checks["min_reference_saliency_iou"]:
            failures.append(
                f"reference saliency IoU {value:.2f} < min {checks['min_reference_saliency_iou']:.2f}"
            )
    if checks.get("min_reference_edge_iou") is not None:
        value = (reference_metrics or {}).get("edge_iou", 0.0)
        if value < checks["min_reference_edge_iou"]:
            failures.append(
                f"reference edge IoU {value:.2f} < min {checks['min_reference_edge_iou']:.2f}"
            )
    if checks.get("max_reference_center_delta") is not None:
        value = (reference_metrics or {}).get("saliency_center_delta", 1.0)
        if value > checks["max_reference_center_delta"]:
            failures.append(
                f"reference center delta {value:.3f} > max {checks['max_reference_center_delta']:.3f}"
            )
    if checks.get("max_reference_coverage_delta") is not None:
        value = (reference_metrics or {}).get("saliency_coverage_delta", 1.0)
        if value > checks["max_reference_coverage_delta"]:
            failures.append(
                f"reference coverage delta {value:.3f} > max {checks['max_reference_coverage_delta']:.3f}"
            )
    if checks.get("max_reference_brightness_delta") is not None:
        value = (reference_metrics or {}).get("mean_brightness_delta", 1.0)
        if value > checks["max_reference_brightness_delta"]:
            failures.append(
                f"reference brightness delta {value:.3f} > max {checks['max_reference_brightness_delta']:.3f}"
            )
    if checks.get("max_reference_contrast_delta") is not None:
        value = (reference_metrics or {}).get("contrast_delta", 1.0)
        if value > checks["max_reference_contrast_delta"]:
            failures.append(
                f"reference contrast delta {value:.3f} > max {checks['max_reference_contrast_delta']:.3f}"
            )
    if checks.get("require_reference_image") and not (reference_path and reference_path.exists()):
        failures.append("reference image required but missing")
    if checks.get("require_glb") and not (glb.exists() and web_ok):
        failures.append("GLB missing or failed validation")
    if checks.get("require_animation") and insp.get("animation", {}).get("has_action") is not True:
        failures.append("animation required but no keyframes")
    if checks.get("require_glb_animation") and (glb_validation or {}).get("info", {}).get("animations", 0) < 1:
        failures.append("GLB animation clip required but none exported")
    anim = insp.get("animation", {}) or {}
    if checks.get("min_animation_frames") is not None:
        frame_count = int(anim.get("frame_end", 0)) - int(anim.get("frame_start", 0)) + 1
        if frame_count < checks["min_animation_frames"]:
            failures.append(
                f"animation frames {frame_count} < min {checks['min_animation_frames']}"
            )
    if checks.get("min_keyframed_objects") is not None:
        keyed = len(anim.get("keyframed_objects") or [])
        if keyed < checks["min_keyframed_objects"]:
            failures.append(
                f"keyframed objects {keyed} < min {checks['min_keyframed_objects']}"
            )
    animation_frame_proof = render_animation_frame_proof(base, blend, budget, blender_exe, anim, checks)
    if checks.get("require_animation_frame_proof") and not animation_frame_proof:
        failures.append("animation frame proof required but not generated")
    if animation_frame_proof and checks.get("min_animation_frame_delta") is not None:
        delta = float(animation_frame_proof.get("max_mean_rgb_delta", 0.0) or 0.0)
        if delta < checks["min_animation_frame_delta"]:
            failures.append(
                f"animation frame delta {delta:.4f} < min {checks['min_animation_frame_delta']:.4f}"
            )
    if animation_frame_proof and checks.get("min_animation_changed_pixel_ratio") is not None:
        changed = float(animation_frame_proof.get("max_changed_pixel_ratio", 0.0) or 0.0)
        if changed < checks["min_animation_changed_pixel_ratio"]:
            failures.append(
                "animation changed pixel ratio "
                f"{changed:.4f} < min {checks['min_animation_changed_pixel_ratio']:.4f}"
            )
    if checks.get("min_sampled_moving_objects") is not None:
        moving = count_sampled_moving_objects(
            anim,
            checks.get("sampled_motion_min_location_delta", 0.01),
            checks.get("sampled_motion_min_rotation_delta", 0.1),
        )
        if moving < checks["min_sampled_moving_objects"]:
            failures.append(
                f"sampled moving objects {moving} < min {checks['min_sampled_moving_objects']}"
            )
    if checks.get("min_sampled_rotation_radians") is not None:
        rot = float(anim.get("max_sampled_rotation_delta", 0.0) or 0.0)
        if rot < checks["min_sampled_rotation_radians"]:
            failures.append(
                f"sampled rotation delta {rot:.2f} < min {checks['min_sampled_rotation_radians']:.2f}"
            )
    if checks.get("min_sampled_location_delta") is not None:
        loc = float(anim.get("max_sampled_location_delta", 0.0) or 0.0)
        if loc < checks["min_sampled_location_delta"]:
            failures.append(
                f"sampled location delta {loc:.2f} < min {checks['min_sampled_location_delta']:.2f}"
            )
    if checks.get("require_camera_animated") and anim.get("camera_animated") is not True:
        failures.append("camera animation required but active camera is not keyframed")
    if checks.get("min_camera_sampled_location_delta") is not None:
        camera_delta = camera_sampled_location_delta(anim)
        if camera_delta < checks["min_camera_sampled_location_delta"]:
            failures.append(
                f"camera sampled location delta {camera_delta:.2f} < min {checks['min_camera_sampled_location_delta']:.2f}"
            )
    if checks.get("require_camera_path"):
        camera_path = insp.get("camera_path_json")
        if not camera_path or not Path(camera_path).exists():
            failures.append("camera path required but not generated")
    camera_path = insp.get("camera_path_json")
    if camera_path and Path(camera_path).exists():
        cp = json.loads(Path(camera_path).read_text(encoding="utf-8"))
        samples = cp.get("samples") or []
        if checks.get("min_camera_path_samples") is not None and len(samples) < checks["min_camera_path_samples"]:
            failures.append(
                f"camera path samples {len(samples)} < min {checks['min_camera_path_samples']}"
            )
        if checks.get("min_camera_path_distance") is not None and len(samples) >= 2:
            first = samples[0].get("position") or [0, 0, 0]
            last = samples[-1].get("position") or first
            dist = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, last)))
            if dist < checks["min_camera_path_distance"]:
                failures.append(
                    f"camera path distance {dist:.2f} < min {checks['min_camera_path_distance']:.2f}"
                )
    geometry_nodes = insp.get("geometry_nodes") or []
    if checks.get("min_geometry_node_groups") is not None and len(geometry_nodes) < checks["min_geometry_node_groups"]:
        failures.append(
            f"geometry-node groups {len(geometry_nodes)} < min {checks['min_geometry_node_groups']}"
        )
    if checks.get("require_geometry_seed"):
        seeded = [gn for gn in geometry_nodes if gn.get("seed") is not None]
        if len(seeded) < len(geometry_nodes):
            failures.append("geometry-node seed required but missing")
    if checks.get("min_geometry_node_count") is not None:
        max_nodes = max((gn.get("node_count", 0) for gn in geometry_nodes), default=0)
        if max_nodes < checks["min_geometry_node_count"]:
            failures.append(
                f"geometry-node count {max_nodes} < min {checks['min_geometry_node_count']}"
            )
    if checks.get("min_geometry_link_count") is not None:
        max_links = max((gn.get("link_count", 0) for gn in geometry_nodes), default=0)
        if max_links < checks["min_geometry_link_count"]:
            failures.append(
                f"geometry-node links {max_links} < min {checks['min_geometry_link_count']}"
            )
    if checks.get("min_geometry_detail_objects") is not None:
        detail_count = count_geometry_detail_objects(
            insp.get("objects", []),
            required_roles=checks.get("require_geometry_detail_roles"),
        )
        if detail_count < checks["min_geometry_detail_objects"]:
            failures.append(
                f"geometry-node detail objects {detail_count} < min {checks['min_geometry_detail_objects']}"
            )
    if checks.get("require_geometry_detail_roles"):
        missing = missing_geometry_detail_roles(
            insp.get("objects", []),
            geometry_nodes,
            checks["require_geometry_detail_roles"],
        )
        if missing:
            failures.append(f"missing geometry-node detail roles: {', '.join(missing)}")
    technical = max(0, 100 - 10 * len(lint.errors))
    return {
        "task_id": task["id"], "mode": mode,
        "pass": not failures and not ev.hard_fail,
        "visual_score": ev.total, "technical_score": technical,
        "runtime_seconds": round(time.time() - t0, 1),
        "iterations": 1,
        "artifacts": [str(preview) if preview.exists() else None, str(glb) if glb.exists() else None],
        "visual_style_tags": visual_style_tags,
        "reference_metrics": reference_metrics,
        "palette_similarity": palette_similarity_value,
        "animation_frame_proof": animation_frame_proof,
        "failures": failures,
    }


def run_task(task, blender_exe, out_root, with_baseline):
    results = {"skill_plus_tools": run_recipe(task, task["recipe"], "skill_plus_tools", blender_exe, out_root)}
    if with_baseline and task.get("baseline_recipe"):
        results["baseline_no_skill"] = run_recipe(task, task["baseline_recipe"], "baseline_no_skill",
                                                   blender_exe, out_root)
    if with_baseline:
        for idx, adversarial in enumerate(task.get("adversarial_baselines") or [], start=1):
            mode = f"adversarial_slop_{adversarial.get('id') or idx}"
            results[mode] = run_recipe(task, adversarial["recipe"], mode, blender_exe, out_root)
    return results


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run benchmark tasks")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tasks", default=None, help="comma-separated task ids (default: all)")
    ap.add_argument("--profile", default=None, help="override profile")
    ap.add_argument("--baseline", action="store_true", help="also run naive baseline for contrast")
    ap.add_argument("--blender", default=None)
    ap.add_argument("--out", default=str(ROOT / "artifacts" / "benchmarks"))
    args = ap.parse_args(argv)

    tasks = load_tasks()
    if args.list:
        for tid, t in tasks.items():
            print(f"{tid:24} [{t.get('category','?'):10}] {t.get('title','')}")
        return 0

    selected = args.tasks.split(",") if args.tasks else list(tasks)
    from blender_cinematic.blender import locate_blender
    blender_exe = locate_blender(args.blender)
    if not blender_exe:
        print("ERROR: Blender not found; benchmarks need Blender to render.")
        return 1

    results_resolver = WorkspaceResolver([RESULTS_DIR.parent])
    results_resolver.ensure_dir(RESULTS_DIR)
    summary = []
    for tid in selected:
        task = tasks.get(tid)
        if not task:
            print(f"unknown task: {tid}")
            continue
        if args.profile:
            task["profile"] = args.profile
        res = run_task(task, blender_exe, args.out, args.baseline)
        results_resolver.write_text(RESULTS_DIR / f"{tid}.json", json.dumps(res, indent=2))
        summary.append(res)
        skill = res["skill_plus_tools"]
        line = f"{tid:24} skill={'PASS' if skill['pass'] else 'FAIL'} score={skill['visual_score']}"
        if "baseline_no_skill" in res:
            b = res["baseline_no_skill"]
            line += f" | baseline={'PASS' if b['pass'] else 'FAIL'} score={b['visual_score']}"
        adversarial = [v for k, v in res.items() if k.startswith("adversarial_slop_")]
        if adversarial:
            failed = sum(1 for r in adversarial if not r["pass"])
            line += f" | adversarial={failed}/{len(adversarial)} FAIL"
        print(line)
    results_resolver.write_text(RESULTS_DIR / "summary.json", json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
