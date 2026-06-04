"""Render budget clamps used before touching Blender render settings."""

MAX_RENDER_DIMENSION = 4096
MAX_PREVIEW_DIMENSION = 2048
MAX_RENDER_SAMPLES = 1024
MAX_PREVIEW_SAMPLES = 128


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _clamp(value, lower, upper):
    return max(lower, min(upper, value))


def _safe_resolution(value, default, max_dimension):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return list(default)
    width = _clamp(_safe_int(value[0], default[0]), 1, max_dimension)
    height = _clamp(_safe_int(value[1], default[1]), 1, max_dimension)
    return [width, height]


def sanitize_render_budget(budget, preview=False):
    """Clamp caller-provided render budget values to non-explosive bounds."""
    budget = dict(budget or {})
    res_key = "preview_resolution" if preview else "final_resolution"
    default = [1280, 720] if preview else [1920, 1080]
    max_dimension = MAX_PREVIEW_DIMENSION if preview else MAX_RENDER_DIMENSION
    max_samples = MAX_PREVIEW_SAMPLES if preview else MAX_RENDER_SAMPLES
    budget[res_key] = _safe_resolution(budget.get(res_key), default, max_dimension)
    budget["samples"] = _clamp(_safe_int(budget.get("samples", 64), 64), 8, max_samples)
    return budget
