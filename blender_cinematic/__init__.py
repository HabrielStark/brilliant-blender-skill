"""blender_cinematic: pure-Python core for the Blender Cinematic Agent Skill.

This package contains ZERO ``bpy`` imports. It holds schemas, validation,
hardware/profile/budget logic, the path sandbox, all linters, image metrics,
the evaluation rubric, the iteration manager and the report writer.

Blender-specific code lives in ``addon/`` and imports this package at runtime.
Keeping the two apart is what makes the core fully unit-testable without
Blender installed (SRS 26: "Separate pure Python logic from Blender-specific
bpy logic").
"""

from .constants import (
    DEFAULT_MAX_ITERATIONS,
    OUTPUT_MODES,
    PASS_THRESHOLD,
    QUALITY_PROFILES,
    REQUIRED_COLLECTIONS,
    SCHEMA_VERSION,
    SKILL_VERSION,
)

__all__ = [
    "SKILL_VERSION",
    "SCHEMA_VERSION",
    "OUTPUT_MODES",
    "QUALITY_PROFILES",
    "REQUIRED_COLLECTIONS",
    "PASS_THRESHOLD",
    "DEFAULT_MAX_ITERATIONS",
]

__version__ = SKILL_VERSION
