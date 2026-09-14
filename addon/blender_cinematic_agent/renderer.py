"""Render helpers (bpy): apply budget-driven settings and render a still."""
import bpy  # type: ignore

from . import bpyutil
from .render_limits import sanitize_render_budget


def apply_render_settings(budget, preview=False, film_transparent=False):
    budget = sanitize_render_budget(budget, preview)
    scene = bpy.context.scene
    r = scene.render
    logical = budget.get("preview_engine" if preview else "selected_engine", "EEVEE")
    engine_id = bpyutil.resolve_engine(logical)
    try:
        r.engine = engine_id
    except (TypeError, ValueError):
        r.engine = bpyutil.resolve_engine("EEVEE")  # Cycles truly unavailable
    res = budget.get("preview_resolution" if preview else "final_resolution", [1280, 720])
    r.resolution_x, r.resolution_y = int(res[0]), int(res[1])
    r.resolution_percentage = 100
    r.film_transparent = bool(film_transparent)
    r.image_settings.file_format = "PNG"
    samples = int(budget.get("samples", 64))
    effective_device = "CPU"
    if r.engine == "CYCLES":
        scene.cycles.samples = max(8, samples if not preview else min(64, samples))
        device = budget.get("device", "CPU")
        if device.startswith("GPU"):
            effective_device = _enable_cycles_gpu(scene, device.split("_")[-1])
        else:
            scene.cycles.device = "CPU"
    else:
        if hasattr(scene.eevee, "taa_render_samples"):
            scene.eevee.taa_render_samples = max(8, samples if not preview else 32)
    return {"engine": r.engine, "resolution": [r.resolution_x, r.resolution_y],
            "samples": samples, "device": effective_device}


def _enable_cycles_gpu(scene, backend):
    """Enable a Cycles compute backend (OPTIX/CUDA/HIP/ONEAPI/METAL) + its devices.

    Returns the device actually used ("GPU_<backend>" or "CPU" fallback).
    """
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
    except (KeyError, AttributeError):
        scene.cycles.device = "CPU"
        return "CPU"
    for cand in (backend, "OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
        try:
            prefs.compute_device_type = cand
        except (TypeError, ValueError):
            continue
        try:
            devices = prefs.get_devices_for_type(cand)
        except Exception:
            devices = []
        gpu_devices = [d for d in devices if d.type == cand]
        if gpu_devices:
            for d in prefs.devices:
                d.use = d.type == cand
            scene.cycles.device = "GPU"
            return f"GPU_{cand}"
    scene.cycles.device = "CPU"
    return "CPU"


# Orbit views for verification: (name, azimuth_deg, elevation_deg). The hero
# view is the authored preview — these exist so a verifier can see the back,
# sides, and top the hero angle hides.
MULTIVIEW_DEFAULT = (
    ("three_quarter", 45.0, 22.0),
    ("profile", 90.0, 8.0),
    ("back", 180.0, 25.0),
    ("top", 30.0, 62.0),
)


def _subject_bounds():
    scene = bpy.context.scene
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    found = False
    from mathutils import Vector
    for obj in scene.objects:
        if obj.type not in {"MESH", "CURVE", "SURFACE", "FONT", "META"}:
            continue
        coll = obj.users_collection[0].name if obj.users_collection else ""
        if coll in {"CAMERAS", "LIGHTS", "HELPERS"}:
            continue
        # bound_box is local-space; transform each corner to world
        for corner in obj.bound_box:
            w = obj.matrix_world @ Vector(corner)
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        found = True
    if not found:
        return None, None
    center = [(lo[i] + hi[i]) / 2 for i in range(3)]
    radius = (sum((hi[i] - lo[i]) ** 2 for i in range(3)) ** 0.5) / 2
    return center, max(radius, 0.5)


def render_multiview(out_paths, budget, views=None):
    """Render orbit views for visual verification without touching the scene.

    Creates a temporary camera, renders each (name, azimuth, elevation) view
    around the subject bounds, then removes it — the authored camera and the
    .blend are untouched. Returns {"views": {name: path}, "errors": [...]}.
    """
    import math
    from mathutils import Vector
    scene = bpy.context.scene
    center, radius = _subject_bounds()
    if center is None:
        return {"views": {}, "errors": ["no geometry to orbit"]}
    settings = apply_render_settings(budget or {}, preview=True,
                                     film_transparent=False)
    cam_data = bpy.data.cameras.new("bcas_multiview_cam")
    cam_data.lens = 50.0
    cam = bpy.data.objects.new("bcas_multiview_cam", cam_data)
    scene.collection.objects.link(cam)
    prev_cam = scene.camera
    scene.camera = cam
    results, errors = {}, []
    try:
        dist = radius * 2.4 + 0.5
        for name, az_deg, el_deg in (views or MULTIVIEW_DEFAULT):
            az, el = math.radians(az_deg), math.radians(el_deg)
            pos = Vector((
                center[0] + dist * math.cos(el) * math.cos(az),
                center[1] + dist * math.cos(el) * math.sin(az),
                center[2] + dist * math.sin(el)))
            cam.location = pos
            cam.rotation_euler = (Vector(center) - pos).to_track_quat("-Z", "Y").to_euler()
            path = out_paths.get(name)
            if not path:
                continue
            scene.render.filepath = path
            try:
                bpy.ops.render.render(write_still=True)
                import os
                if os.path.exists(path):
                    results[name] = path
                else:
                    errors.append(f"{name}: no file written")
            except Exception as exc:  # per-view failure must not kill the set
                errors.append(f"{name}: {exc}")
    finally:
        scene.camera = prev_cam
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
    return {"views": results, "errors": errors, "settings": settings,
            "center": center, "radius": radius}


def render_still(filepath, budget, preview=False, film_transparent=False, frame=None):
    settings = apply_render_settings(budget, preview, film_transparent)
    scene = bpy.context.scene
    if not scene.camera:
        return {"error": "no active camera", "settings": settings}
    if frame is not None:
        scene.frame_set(int(frame))
        bpy.context.view_layer.update()
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)
    import os
    ok = os.path.exists(filepath)
    return {"rendered": ok, "path": filepath, "frame": int(frame) if frame is not None else scene.frame_current,
            "settings": settings}
