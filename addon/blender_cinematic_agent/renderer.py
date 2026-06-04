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
