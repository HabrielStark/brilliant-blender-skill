"""Shared constants and enumerations (single source of truth).

Values here are referenced by schemas, profiles, linters, the MCP server,
the add-on and the docs, so they must stay consistent.
"""
from __future__ import annotations

SKILL_VERSION = "0.1"
SCHEMA_VERSION = "0.1"

# SRS 6.2 / 22: task classification.
OUTPUT_MODES: tuple[str, ...] = (
    "still",
    "animation",
    "web_asset",
    "interactive_web",
    "reference_match",
    "scene_repair",
    "benchmark",
)

# SRS 9.3 quality profiles + "auto".
QUALITY_PROFILES: tuple[str, ...] = (
    "auto",
    "safe_laptop",
    "balanced",
    "cinematic",
    "ultra_4k",
)

# SRS 11.1 collections.
REQUIRED_COLLECTIONS: tuple[str, ...] = (
    "CAMERAS",
    "LIGHTS",
    "SUBJECT",
    "ENVIRONMENT",
    "FX",
    "HELPERS",
    "EXPORT",
)
OPTIONAL_COLLECTIONS: tuple[str, ...] = (
    "RIGS",
    "SIMULATION",
    "ANNOTATIONS",
    "PROXIES",
    "REFERENCE",
)

# SRS 10.2 rubric pass threshold and excellence bar.
PASS_THRESHOLD = 80
EXCELLENT_THRESHOLD = 90

# SRS 7.2 default global iteration cap.
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_MIN_ITERATIONS = 2

# SRS 43.2 per-mode iteration budgets.
ITERATION_BUDGETS: dict[str, int] = {
    "still": 3,
    "animation": 6,
    "web_asset": 6,
    "interactive_web": 10,
    "reference_match": 8,
    "scene_repair": 5,
    "benchmark": 10,
}

# SRS 19.1 default timeouts (seconds).
TIMEOUTS: dict[str, int] = {
    "preflight": 60,
    "scene_inspection": 30,
    "thumbnail_render": 120,
    "preview_render": 300,
    "final_still_render": 1800,
    "glb_export": 300,
    "web_validation": 120,
}

# SRS 10.2 rubric category -> max points (sums to 100).
RUBRIC_MAX: dict[str, int] = {
    "composition": 20,
    "lighting": 15,
    "materials": 15,
    "geometry_detail": 15,
    "camera": 10,
    "reference_fidelity": 10,
    "technical": 10,
    "performance": 5,
}

# Naming linter: tokens that mark a default/auto-generated Blender name.
DEFAULT_NAME_TOKENS: tuple[str, ...] = (
    "cube",
    "cylinder",
    "sphere",
    "cone",
    "plane",
    "torus",
    "icosphere",
    "circle",
    "untitled",
    "object",
    "empty",
    "material",
    "nodegroup",
    "node group",
    "noise texture",
    "suzanne",
    "grid",
    "monkey",
)

# Severity levels used by every linter.
SEVERITY_ERROR = "error"
SEVERITY_WARN = "warning"
SEVERITY_INFO = "info"
