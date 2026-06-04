"""Security tests for Blender-side render budget clamps."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RENDER_LIMITS = ROOT / "addon" / "blender_cinematic_agent" / "render_limits.py"


def _load_render_limits():
    spec = importlib.util.spec_from_file_location("bcas_render_limits", RENDER_LIMITS)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_render_budget_sanitizer_clamps_extreme_values():
    limits = _load_render_limits()
    budget = limits.sanitize_render_budget(
        {"final_resolution": [999999, "bad"], "samples": 999999},
        preview=False,
    )
    assert budget["final_resolution"] == [limits.MAX_RENDER_DIMENSION, 1080]
    assert budget["samples"] == limits.MAX_RENDER_SAMPLES


def test_preview_budget_sanitizer_uses_preview_caps():
    limits = _load_render_limits()
    budget = limits.sanitize_render_budget(
        {"preview_resolution": [999999, 999999], "samples": 999999},
        preview=True,
    )
    assert budget["preview_resolution"] == [limits.MAX_PREVIEW_DIMENSION, limits.MAX_PREVIEW_DIMENSION]
    assert budget["samples"] == limits.MAX_PREVIEW_SAMPLES
