"""All structural linters (SRS 11, 32.8, 33.7, 34.7, 35.6, 36.5, 37.3, 39.5, 40.5).

Linters consume a *scene-inspection dict* (the contract produced by the add-on's
``scene_inspector`` and documented in ``docs/blender-addon.md``) plus an optional
manifest dict and render budget. They never import ``bpy``; that is what lets the
whole evaluation run on CI without Blender. Each returns a :class:`CheckResult`.

Inspection contract (keys are optional; linters degrade gracefully):
    collections: list[str]
    objects: [{name,type,collection,faces,verts,modifiers:[{type,show_render}],
               materials:[str],scale:[3],dimensions:[3],visible,smooth,
               in_camera_frame,screen_coverage,non_manifold,flipped_normals}]
    active_camera: {name,lens_mm,dof,focus_target,inside_geometry,clip_end} | None
    cameras: [str]
    lights: [{name,type,energy,color:[3]}]
    materials: [{name,metallic,roughness,node_count,users,has_emission,
                 has_transmission,is_default,web_unsafe,has_fallback}]
    node_groups: [str]
    geometry_nodes: [{name,seed,target,applied,generated_faces,visible_from_camera}]
    animation: {has_action,frame_start,frame_end,fps,keyframed_objects:[str],
                markers:[str],loop,loop_match,camera_animated}
    particles: [{object,count,cache_present}]
    compositor: {use_nodes,node_names:[str],bloom,raw_render_saved}
    render: {engine,resolution:[2],samples,volumetric,view_transform}
    metadata: {final_camera,...}
    camera_path_json: str | None
    missing_files: [str]
"""
from __future__ import annotations

import math
import re

from .constants import DEFAULT_NAME_TOKENS, REQUIRED_COLLECTIONS
from .results import CheckResult, error, info, merge, warn

_DEFAULT_SUFFIX = re.compile(r".*\.\d{3}$")
_IMPORTANT = {"SUBJECT", "EXPORT"}
_HERO_PART_TOKENS = {
    "base",
    "bezel",
    "blade",
    "body",
    "button",
    "cap",
    "crown",
    "dial",
    "face",
    "handle",
    "label",
    "lens",
    "logo",
    "neck",
    "nozzle",
    "plinth",
    "screen",
    "strap",
    "wheel",
}
_ATTACHMENT_PART_TOKENS = {
    "bezel",
    "button",
    "cap",
    "contact",
    "crown",
    "dial",
    "face",
    "handle",
    "label",
    "lens",
    "logo",
    "neck",
    "nozzle",
    "rim",
    "screen",
    "strap",
}
_DETACHED_INTENT_TOKENS = {
    "abstract",
    "burst",
    "exploded",
    "floating",
    "orbit",
    "orbital",
    "particle",
    "scatter",
    "suspended",
}
_VISUAL_EFFECT_PART_TOKENS = {
    "highlight",
    "reflection",
    "shadow",
    "specular",
    "streak",
    "swatch",
}


def is_default_name(name: str) -> bool:
    if not name:
        return True
    low = name.strip().lower()
    if _DEFAULT_SUFFIX.match(low):
        return True
    return any(low == tok or low.startswith(tok + ".") or low == tok.replace(" ", "") for tok in DEFAULT_NAME_TOKENS)


def _m(manifest) -> dict:
    return manifest or {}


def _wants_web(manifest: dict) -> bool:
    fmt = (((manifest or {}).get("target") or {}).get("final_format")) or []
    return (manifest or {}).get("output_mode") in ("web_asset", "interactive_web") or any(
        f in ("glb", "gltf") for f in fmt
    )


def _wants_animation(manifest: dict) -> bool:
    fmt = (((manifest or {}).get("target") or {}).get("final_format")) or []
    return (manifest or {}).get("output_mode") in ("animation", "interactive_web") or "mp4" in fmt


def _premium(manifest: dict) -> bool:
    mood = (((manifest or {}).get("style") or {}).get("mood") or "").lower()
    return any(w in mood for w in ("premium", "cinematic", "luxury", "sharp", "hero"))


def _name_tokens(name: str) -> set[str]:
    return {p for p in re.split(r"[^a-z0-9]+", (name or "").lower()) if p}


def _is_hero_part_name(name: str) -> bool:
    return bool(_name_tokens(name) & _HERO_PART_TOKENS)


def _is_attachment_part_name(name: str) -> bool:
    tokens = _name_tokens(name)
    if tokens & (_DETACHED_INTENT_TOKENS | _VISUAL_EFFECT_PART_TOKENS):
        return False
    return bool(tokens & _ATTACHMENT_PART_TOKENS)


def _manifest_allows_detached_parts(manifest: dict) -> bool:
    text = str(manifest or {}).lower()
    return any(token in text for token in _DETACHED_INTENT_TOKENS)


def _bbox(obj: dict):
    loc = obj.get("location") or []
    dims = obj.get("dimensions") or []
    if len(loc) < 3 or len(dims) < 3:
        return None
    try:
        center = [float(v) for v in loc[:3]]
        half = [abs(float(v)) / 2.0 for v in dims[:3]]
    except (TypeError, ValueError):
        return None
    if max(half, default=0.0) <= 1e-6:
        return None
    return tuple((center[idx] - half[idx], center[idx] + half[idx]) for idx in range(3))


def _bbox_gap(a, b) -> float:
    axis_gaps = []
    for (amin, amax), (bmin, bmax) in zip(a, b):
        axis_gaps.append(max(0.0, bmin - amax, amin - bmax))
    return math.sqrt(sum(gap * gap for gap in axis_gaps))


def _camera_path_distance(camera_path) -> tuple[int, float, bool]:
    if not isinstance(camera_path, dict):
        return 0, 0.0, False
    samples = camera_path.get("samples")
    if not isinstance(samples, list):
        return 0, 0.0, bool(camera_path.get("segments"))
    positions = [
        sample.get("position")
        for sample in samples
        if isinstance(sample, dict) and isinstance(sample.get("position"), list) and len(sample["position"]) >= 3
    ]
    if len(positions) < 2:
        return len(positions), 0.0, bool(camera_path.get("segments"))
    first = positions[0][:3]
    last = positions[-1][:3]
    try:
        distance = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(first, last)))
    except (TypeError, ValueError):
        return len(positions), 0.0, bool(camera_path.get("segments"))
    return len(positions), distance, bool(camera_path.get("segments"))


_LIST_FIELDS = ("objects", "materials", "lights", "cameras", "node_groups",
                "geometry_nodes", "particles", "collections")
_DICT_FIELDS = ("animation", "render", "metadata", "compositor", "world")


def _normalize(inspection) -> dict:
    """Coerce an inspection dict to safe types so linters never crash on junk."""
    if not isinstance(inspection, dict):
        return {f: [] for f in _LIST_FIELDS}
    out = dict(inspection)
    for f in _LIST_FIELDS:
        v = out.get(f)
        out[f] = [x for x in v if x is not None] if isinstance(v, list) else []
    out["objects"] = [o for o in out["objects"] if isinstance(o, dict)]
    out["materials"] = [m for m in out["materials"] if isinstance(m, dict)]
    out["lights"] = [light for light in out["lights"] if isinstance(light, dict)]
    out["geometry_nodes"] = [g for g in out["geometry_nodes"] if isinstance(g, dict)]
    out["particles"] = [p for p in out["particles"] if isinstance(p, dict)]
    for f in ("collections", "cameras", "node_groups"):
        out[f] = [str(x) for x in out[f] if not isinstance(x, (dict, list))]
    for f in _DICT_FIELDS:
        v = out.get(f)
        out[f] = v if isinstance(v, dict) else {}
    cam = out.get("active_camera")
    out["active_camera"] = cam if isinstance(cam, dict) else None
    return out


# --------------------------------------------------------------------------- #
def lint_naming(inspection: dict, manifest: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("naming")
    for obj in inspection.get("objects", []):
        name = obj.get("name", "")
        if is_default_name(name):
            sev = error if obj.get("collection") in _IMPORTANT else warn
            r.add(sev("naming.object", f"object has default/auto name: {name!r}", name))
    for mat in inspection.get("materials", []):
        if is_default_name(mat.get("name", "")):
            r.add(error("naming.material", f"material has default name: {mat.get('name')!r}"))
    for ng in inspection.get("node_groups", []):
        if is_default_name(ng):
            r.add(warn("naming.node_group", f"node group has default name: {ng!r}"))
    if not r.issues:
        r.add(info("naming.ok", "object/material/node-group names are intentional"))
    return r


def lint_materials(inspection: dict, manifest: dict | None = None, budget: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("materials")
    m = _m(manifest)
    objs = inspection.get("objects", [])
    mats = inspection.get("materials", [])
    important = [o for o in objs if o.get("collection") in _IMPORTANT and o.get("type") == "MESH"]
    for o in important:
        if not o.get("materials"):
            r.add(error("material.missing", f"important object has no material: {o.get('name')}", o.get("name")))
    by_name = {mt.get("name"): mt for mt in mats}
    for mt in mats:
        name = mt.get("name")
        if mt.get("is_default"):
            r.add(error("material.default", f"default/grey material used: {name}", name))
        rough = mt.get("roughness")
        metal = mt.get("metallic")
        for label, val in (("roughness", rough), ("metallic", metal)):
            if val is not None and not (0.0 <= float(val) <= 1.0):
                r.add(error("material.value", f"{label} out of [0,1]: {val} ({name})", name))
        if mt.get("users", 1) == 0:
            r.add(warn("material.unused", f"material not assigned to any object: {name}", name))
        if _wants_web(m) and mt.get("web_unsafe") and not mt.get("has_fallback"):
            r.add(error("material.web_fallback",
                        f"web export: material {name} uses unsupported features without fallback", name))
        cap = (budget or {}).get("texture_cap")
        tex = mt.get("max_texture_resolution")
        if cap and tex and tex > cap:
            r.add(error("material.texture_cap", f"texture {tex}px exceeds profile cap {cap} ({name})", name))
        nc = mt.get("node_count")
        if _wants_web(m) and nc and nc > 60:
            r.add(warn("material.web_complexity", f"material {name} has {nc} nodes; heavy for web", name))
    # all important objects share one material without explicit reason
    used = {mn for o in important for mn in (o.get("materials") or [])}
    if len(important) >= 3 and len(used) == 1:
        r.add(warn("material.monotone", "all key objects use one material; add variation"))
    # metallic material needs bevels/lighting to read
    has_light = bool(inspection.get("lights"))
    for o in important:
        for mn in (o.get("materials") or []):
            mt = by_name.get(mn, {})
            if (mt.get("metallic") or 0) >= 0.7:
                has_bevel = any(mod.get("type") == "BEVEL" for mod in o.get("modifiers", []))
                if not has_bevel and not has_light:
                    r.add(warn("material.metal_unreadable",
                               f"metallic {mn} on {o.get('name')} lacks bevel+light to reveal it", o.get("name")))
    return r


def lint_geometry(inspection: dict, manifest: dict | None = None, budget: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("geometry")
    m = _m(manifest)
    subject_faces = sum(o.get("faces", 0) for o in inspection.get("objects", []) if o.get("collection") == "SUBJECT")
    for gn in inspection.get("geometry_nodes", []):
        name = gn.get("name", "")
        gen = gn.get("generated_faces", 0)
        budget_faces = gn.get("max_generated_faces", (budget or {}).get("max_generated_faces", 200000))
        if gen and gen > budget_faces:
            r.add(error("geometry.face_budget", f"{name} generates {gen} faces > budget {budget_faces}", name))
        if is_default_name(name):
            r.add(warn("geometry.name", f"geometry-node group has default name: {name!r}", name))
        if gn.get("seed") is None:
            r.add(warn("geometry.seed", f"geometry-node group {name} has no logged seed", name))
        if gn.get("visible_from_camera") is False:
            r.add(warn("geometry.invisible", f"geometry-node result {name} is invisible from camera", name))
        if _wants_web(m) and gn.get("applied") is False:
            r.add(error("geometry.unbaked", f"web export: {name} not applied/baked before export", name))
        if subject_faces and gen and gen > subject_faces * 8:
            r.add(warn("geometry.dominates", f"procedural detail {name} dominates the subject", name))
    # too many tiny loose objects instead of instances
    tiny = [o for o in inspection.get("objects", []) if 0 < o.get("faces", 0) <= 12]
    if len(tiny) > 40:
        r.add(warn("geometry.loose_objects", f"{len(tiny)} tiny objects; consider instancing/merging"))
    return r


def lint_camera(inspection: dict, manifest: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("camera")
    m = _m(manifest)
    cam = inspection.get("active_camera")
    if not cam:
        r.add(error("camera.none", "no active camera in scene"))
        return r
    if is_default_name(cam.get("name", "")):
        r.add(warn("camera.name", f"active camera has default name: {cam.get('name')!r}"))
    if cam.get("dof") and not cam.get("focus_target"):
        r.add(error("camera.dof_target", "DOF enabled but no focus target set"))
    if cam.get("inside_geometry"):
        r.add(error("camera.inside_geometry", "camera is inside geometry"))
    subjects = [o for o in inspection.get("objects", []) if o.get("collection") == "SUBJECT"]
    if subjects:
        visible = [o for o in subjects if o.get("in_camera_frame", True)]
        if not visible:
            r.add(error("camera.subject_hidden", "no SUBJECT object is inside the camera frame"))
        offscreen_hero_parts = [
            o.get("name")
            for o in subjects
            if o.get("in_camera_frame") is False and _is_hero_part_name(o.get("name", ""))
        ]
        if visible and offscreen_hero_parts:
            shown = ", ".join(str(n) for n in offscreen_hero_parts[:4])
            suffix = "" if len(offscreen_hero_parts) <= 4 else f" (+{len(offscreen_hero_parts) - 4} more)"
            r.add(error("camera.subject_part_hidden",
                        f"important SUBJECT parts outside camera frame: {shown}{suffix}"))
        cov = max((o.get("screen_coverage", 0) for o in subjects), default=0)
        if 0 < cov < 0.05:
            r.add(warn("camera.subject_tiny", f"subject coverage only {cov:.0%}; too small"))
        if cov > 0.98:
            r.add(error("camera.subject_cut", f"subject coverage {cov:.0%}; likely cut off"))
        if _wants_web(m) and cov > 0.85:
            r.add(warn("camera.mobile_unsafe", f"coverage {cov:.0%} risks mobile crop; leave margin"))
    cams = inspection.get("cameras", [])
    if len(cams) > 1 and not (inspection.get("metadata") or {}).get("final_camera"):
        r.add(warn("camera.final_unspecified", "multiple cameras but metadata.final_camera not set"))
    return r


def lint_lighting(inspection: dict, manifest: dict | None = None, budget: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("lighting")
    lights = inspection.get("lights", [])
    world_strength = (inspection.get("world") or {}).get("strength", 0)
    if not lights and not world_strength:
        r.add(error("lighting.none", "scene has no lights and no world illumination"))
    default_only = lights and all(is_default_name(light.get("name", "")) for light in lights)
    if default_only:
        r.add(error("lighting.default", "only default-named lights present; choose a lighting rig"))
    strong = [light for light in lights if (light.get("energy") or 0) > 2000]
    if len(strong) >= 3:
        r.add(warn("lighting.overpowered", f"{len(strong)} very high-power lights may blow out the render"))
    if inspection.get("render", {}).get("volumetric") and budget and not budget.get("volumetrics_allowed", True):
        r.add(error("lighting.volumetric_budget", "volumetric lighting enabled but disallowed by profile"))
    return r


def lint_animation(inspection: dict, manifest: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("animation")
    m = _m(manifest)
    anim = inspection.get("animation") or {}
    wants = _wants_animation(m)
    if wants and not anim.get("has_action") and not anim.get("keyframed_objects"):
        r.add(error("animation.missing", "animation requested but no keyframes/actions exist"))
        return r
    if not anim.get("has_action") and not anim.get("keyframed_objects"):
        return r  # no animation, none requested
    fs, fe = anim.get("frame_start", 1), anim.get("frame_end", 250)
    if fe <= fs:
        r.add(error("animation.range", f"invalid frame range {fs}..{fe}"))
    if fs == 1 and fe == 250 and not anim.get("markers"):
        r.add(warn("animation.default_range", "frame range looks like the untouched default 1..250"))
    if anim.get("camera_animated") and not inspection.get("active_camera"):
        r.add(error("animation.camera_unassigned", "camera animated but no active camera assigned"))
    if anim.get("loop") and anim.get("loop_match") is False:
        r.add(warn("animation.loop_mismatch", "loop requested but first/last frames differ"))
    if _wants_web(m) and anim.get("has_action") and inspection.get("exported_clips") == []:
        r.add(error("animation.glb_clip", "GLB requested but no animation clip exported"))
    if m.get("output_mode") == "interactive_web":
        camera_path = inspection.get("camera_path_json")
        if not camera_path:
            r.add(error("animation.scroll_path", "scroll-linked web requested but no camera_path.json generated"))
        elif isinstance(camera_path, dict):
            sample_count, distance, has_segments = _camera_path_distance(camera_path)
            if not has_segments:
                r.add(error("animation.scroll_path_segments", "scroll camera path has no timeline segments"))
            if sample_count < 2:
                r.add(error("animation.scroll_path_samples", "scroll camera path needs at least two sampled positions"))
            elif distance < 0.25:
                r.add(error("animation.scroll_path_static", f"scroll camera path is static ({distance:.2f} units)"))
    frames = (fe - fs)
    if frames >= 60 and not anim.get("markers"):
        r.add(warn("animation.markers", "complex animation lacks timeline markers"))
    return r


def lint_mesh(inspection: dict, manifest: dict | None = None, budget: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("mesh")
    m = _m(manifest)
    premium = _premium(m)
    for o in inspection.get("objects", []):
        if o.get("type") != "MESH":
            continue
        name = o.get("name")
        mods = o.get("modifiers", [])
        if o.get("flipped_normals"):
            r.add(error("mesh.normals", f"flipped/broken normals: {name}", name))
        if o.get("non_manifold"):
            r.add(warn("mesh.non_manifold", f"non-manifold artifacts (check booleans): {name}", name))
        scale = o.get("scale") or [1, 1, 1]
        if _wants_web(m) and any(abs(s - 1.0) > 0.01 for s in scale):
            r.add(error("mesh.unapplied_scale", f"unapplied scale {scale} with export requested: {name}", name))
        for mod in mods:
            if mod.get("show_render") is False:
                r.add(warn("mesh.modifier_hidden", f"modifier {mod.get('type')} disabled in render: {name}", name))
        if premium and o.get("collection") in _IMPORTANT:
            has_bevel = any(mod.get("type") in ("BEVEL", "SUBSURF") for mod in mods)
            if not has_bevel and not o.get("smooth"):
                r.add(warn("mesh.sharp_edges", f"premium render: {name} has no bevel/subsurf/smooth", name))
    return r


def lint_spatial_relationships(inspection: dict, manifest: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("spatial")
    if _manifest_allows_detached_parts(_m(manifest)):
        return r
    subjects = [
        obj
        for obj in inspection.get("objects", [])
        if obj.get("type") == "MESH" and obj.get("collection") == "SUBJECT" and _bbox(obj)
    ]
    if len(subjects) < 2:
        return r
    for detail in [obj for obj in subjects if _is_attachment_part_name(obj.get("name", ""))]:
        detail_box = _bbox(detail)
        if not detail_box:
            continue
        gaps = [
            _bbox_gap(detail_box, anchor_box)
            for anchor in subjects
            if anchor is not detail and (anchor_box := _bbox(anchor))
        ]
        if not gaps:
            continue
        nearest = min(gaps)
        try:
            dims = [abs(float(v)) for v in (detail.get("dimensions") or [0, 0, 0])[:3]]
        except (TypeError, ValueError):
            dims = [0, 0, 0]
        tolerance = max(0.12, min(0.25, max(dims, default=0.0) * 0.35))
        if nearest > tolerance:
            r.add(error(
                "spatial.floating_part",
                f"attached detail appears physically detached: {detail.get('name')} (nearest gap {nearest:.2f})",
                detail.get("name"),
            ))
    return r


def lint_vfx(inspection: dict, manifest: dict | None = None, budget: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("vfx")
    m = _m(manifest)
    profile = (budget or {}).get("quality_profile", m.get("quality_profile", "balanced"))
    cap = {"safe_laptop": 200, "balanced": 2000, "cinematic": 20000, "ultra_4k": 100000}.get(profile, 2000)
    for p in inspection.get("particles", []):
        cnt = p.get("count", 0)
        if cnt > cap:
            r.add(error("vfx.particle_budget", f"particle count {cnt} exceeds {profile} cap {cap}", p.get("object")))
        if p.get("cache_present") is False and cnt > 0:
            r.add(warn("vfx.cache_missing", f"simulation cache missing for {p.get('object')}", p.get("object")))
        if _wants_web(m) and cnt > 0:
            r.add(warn("vfx.web_particles", f"particle system on {p.get('object')} may not survive GLB export", p.get("object")))
    if inspection.get("render", {}).get("volumetric") and profile == "safe_laptop":
        r.add(error("vfx.volumetric_weak_hw", "volumetrics requested on safe_laptop profile"))
    return r


def lint_compositor(inspection: dict, manifest: dict | None = None) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("compositor")
    comp = inspection.get("compositor") or {}
    if not comp.get("use_nodes"):
        return r
    if comp.get("raw_render_saved") is False:
        r.add(warn("compositor.no_raw", "compositor active but no raw render saved for comparison"))
    bloom = comp.get("bloom")
    if isinstance(bloom, (int, float)) and bloom > 0.8:
        r.add(warn("compositor.overbloom", f"bloom level {bloom} is excessive"))
    for n in comp.get("node_names", []):
        if is_default_name(n):
            r.add(info("compositor.node_name", f"compositor node has generic name: {n}"))
    if (manifest or {}).get("output_mode") in ("benchmark",) and comp.get("post_preset") == "neon_bloom":
        r.add(warn("compositor.tech_conflict", "heavy post preset conflicts with technical visualization"))
    return r


def lint_collections(inspection: dict) -> CheckResult:
    inspection = _normalize(inspection)
    r = CheckResult("collections")
    present = set(inspection.get("collections", []))
    for required in REQUIRED_COLLECTIONS:
        if required not in present:
            r.add(warn("collection.missing", f"recommended collection missing: {required}"))
    return r


def lint_scene(inspection: dict, manifest: dict | None = None, budget: dict | None = None) -> CheckResult:
    """Aggregate every linter into one scene-level CheckResult (SRS 12.4 evaluate.scene_lint)."""
    inspection = _normalize(inspection)
    parts = [
        lint_collections(inspection),
        lint_naming(inspection, manifest),
        lint_camera(inspection, manifest),
        lint_lighting(inspection, manifest, budget),
        lint_materials(inspection, manifest, budget),
        lint_geometry(inspection, manifest, budget),
        lint_spatial_relationships(inspection, manifest),
        lint_mesh(inspection, manifest, budget),
        lint_animation(inspection, manifest),
        lint_vfx(inspection, manifest, budget),
        lint_compositor(inspection, manifest),
    ]
    if not inspection.get("objects"):
        parts.append(CheckResult("scene", [error("scene.empty", "scene contains no objects")]))
    return merge("scene_lint", parts)
