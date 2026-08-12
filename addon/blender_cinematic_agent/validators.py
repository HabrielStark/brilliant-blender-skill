"""Bridge command validation (no bpy import -> unit-testable).

The localhost bridge must validate every incoming command before touching
Blender. Structured operations only; the action and every recipe op must be in
the allowlist. Mirrors the core allowlist (kept in sync by tests).
"""

import math

ALLOWED_ACTIONS = (
    "ping", "initialize", "apply_recipe", "inspect",
    "render_preview", "render_final", "export_glb",
)

ALLOWED_OPS = (
    "ensure_standard_collections", "create_collection", "set_scene_metadata",
    "create_mesh_primitive", "add_modifier", "add_bevel_modifier", "add_subdivision",
    "add_array_modifier", "set_object_transform", "apply_transform", "set_smooth_shading",
    "set_origin", "move_to_collection", "parent_objects", "assign_material",
    "create_material", "create_camera", "create_lighting_rig", "add_light",
    "create_geometry_nodes", "create_radial_markers", "create_linear_markers",
    "create_text_label", "create_decal_plane", "create_curve_tube",
    "create_fastener_pattern", "create_panel_cutlines", "create_grille",
    "create_surface_microdetails",
    "create_organic_surface_details", "create_organic_fluted_body",
    "create_faceted_hero_body", "create_energy_burst_streaks",
    "create_animation", "create_vfx", "apply_post",
    "create_rig", "add_constraint",
)

# These limits are deliberately independent of Blender and are checked before a
# command is queued on Blender's main thread.  They are generous compared with
# the repository's production recipes, but prevent a valid operation name from
# being used as a carrier for an unbounded JSON tree or an obviously dangerous
# geometry request.
MAX_RECIPE_OPERATIONS = 1024
MAX_RECIPE_DEPTH = 32
MAX_RECIPE_NODES = 50_000
MAX_RECIPE_CONTAINER_ITEMS = 4096
MAX_RECIPE_STRING_LENGTH = 65_536

MAX_TEXT_LABEL_CHARS = 160
MAX_CURVE_TUBE_POINTS = 64

# Keep these values aligned with the pure-Python recipe validator.  The bridge
# cannot import that package in every add-on installation, so it retains a
# small, explicit last-line-of-defence table.
OPERATION_INTEGER_LIMITS = {
    "add_subdivision": {
        "levels": (0, 8),
        "render_levels": (0, 8),
    },
    "add_array_modifier": {"count": (1, 1000)},
    "add_bevel_modifier": {"segments": (0, 64)},
    "create_radial_markers": {"count": (1, 96)},
    "create_linear_markers": {"count": (1, 128)},
    "create_fastener_pattern": {"count": (1, 256)},
    "create_panel_cutlines": {"count": (1, 256)},
    "create_grille": {"count": (1, 256)},
    "create_surface_microdetails": {"count": (1, 256)},
    "create_organic_surface_details": {
        "count": (1, 96),
        "segments_u": (3, 16),
        "segments_v": (3, 18),
    },
    "create_energy_burst_streaks": {
        "count": (1, 160),
        "segments": (3, 32),
    },
    "create_organic_fluted_body": {
        "segments": (12, 160),
        "rings": (4, 80),
        "lobes": (0, 32),
        "subdivision_levels": (0, 8),
    },
    "create_faceted_hero_body": {
        "segments": (8, 128),
        "rings": (4, 64),
    },
}

GENERIC_MODIFIER_INTEGER_LIMITS = {
    "SUBSURF": {"levels": (0, 8), "render_levels": (0, 8)},
    "ARRAY": {"count": (1, 1000)},
    "BEVEL": {"segments": (0, 64)},
}


def _validate_recipe_shape(recipe):
    """Validate a JSON-shaped recipe with bounded, non-recursive traversal."""
    stack = [(recipe, 0)]
    nodes = 0
    while stack:
        value, depth = stack.pop()
        nodes += 1
        if nodes > MAX_RECIPE_NODES:
            return f"recipe exceeds maximum node count of {MAX_RECIPE_NODES}"
        if depth > MAX_RECIPE_DEPTH:
            return f"recipe exceeds maximum nesting depth of {MAX_RECIPE_DEPTH}"

        if isinstance(value, dict):
            if len(value) > MAX_RECIPE_CONTAINER_ITEMS:
                return (
                    "recipe object exceeds maximum item count of "
                    f"{MAX_RECIPE_CONTAINER_ITEMS}"
                )
            for key, child in value.items():
                if not isinstance(key, str):
                    return "recipe object keys must be strings"
                if len(key) > MAX_RECIPE_STRING_LENGTH:
                    return (
                        "recipe key exceeds maximum string length of "
                        f"{MAX_RECIPE_STRING_LENGTH}"
                    )
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            if len(value) > MAX_RECIPE_CONTAINER_ITEMS:
                return (
                    "recipe list exceeds maximum item count of "
                    f"{MAX_RECIPE_CONTAINER_ITEMS}"
                )
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, str):
            if len(value) > MAX_RECIPE_STRING_LENGTH:
                return (
                    "recipe string exceeds maximum length of "
                    f"{MAX_RECIPE_STRING_LENGTH}"
                )
        elif isinstance(value, float):
            if not math.isfinite(value):
                return "recipe numbers must be finite"
        elif value is None or isinstance(value, (bool, int)):
            continue
        else:
            return f"recipe contains non-JSON value of type {type(value).__name__}"
    return None


def _operation_params(operation):
    """Return parameters exactly as ``builders.apply_recipe`` will see them."""
    nested = operation.get("params")
    flat = {key: value for key, value in operation.items() if key not in ("op", "params")}
    if nested is None:
        return flat
    if flat:
        return {**flat, "params": nested}
    return nested


def _validate_integer_limits(op_name, params, index):
    limits = OPERATION_INTEGER_LIMITS.get(op_name, {})
    for field, (minimum, maximum) in limits.items():
        if field not in params:
            continue
        value = params[field]
        if isinstance(value, bool) or not isinstance(value, int):
            return f"operation {index}.{field} must be an integer"
        if value < minimum or value > maximum:
            return (
                f"operation {index}.{field} must be between "
                f"{minimum} and {maximum}"
            )

    if op_name == "add_modifier":
        modifier_limits = GENERIC_MODIFIER_INTEGER_LIMITS.get(params.get("modifier"), {})
        modifier_params = params.get("params")
        if isinstance(modifier_params, dict):
            for field, (minimum, maximum) in modifier_limits.items():
                if field not in modifier_params:
                    continue
                value = modifier_params[field]
                if isinstance(value, bool) or not isinstance(value, int):
                    return f"operation {index}.params.{field} must be an integer"
                if value < minimum or value > maximum:
                    return (
                        f"operation {index}.params.{field} must be between "
                        f"{minimum} and {maximum}"
                    )
    return None


def _validate_operation_budget(op_name, params, index):
    error = _validate_integer_limits(op_name, params, index)
    if error:
        return error
    if op_name == "create_text_label":
        text = params.get("text")
        if isinstance(text, str) and len(text) > MAX_TEXT_LABEL_CHARS:
            return (
                f"operation {index}.text exceeds maximum length of "
                f"{MAX_TEXT_LABEL_CHARS}"
            )
    if op_name == "create_curve_tube":
        points = params.get("points")
        if isinstance(points, list) and len(points) > MAX_CURVE_TUBE_POINTS:
            return (
                f"operation {index}.points exceeds maximum item count of "
                f"{MAX_CURVE_TUBE_POINTS}"
            )
    return None


def validate_command(cmd, safety_mode="strict"):
    """Return an error string if invalid, else None."""
    if not isinstance(cmd, dict):
        return "command must be a JSON object"
    action = cmd.get("action")
    if not isinstance(action, str):
        return "action must be a string"
    if action not in ALLOWED_ACTIONS:
        return f"action not allowed: {action[:80]!r}"
    if action in ("render_preview", "render_final", "export_glb"):
        output = cmd.get("output")
        if not isinstance(output, str) or not output.strip():
            return f"{action}.output must be a non-empty string path"
    if action == "apply_recipe":
        recipe = cmd.get("recipe", {})
        if not isinstance(recipe, dict):
            return "recipe must be a JSON object"
        ops = recipe.get("operations")
        if not isinstance(ops, list):
            return "recipe.operations must be a list"
        if len(ops) > MAX_RECIPE_OPERATIONS:
            return (
                "recipe.operations exceeds maximum item count of "
                f"{MAX_RECIPE_OPERATIONS}"
            )
        error = _validate_recipe_shape(recipe)
        if error:
            return error
        for index, operation in enumerate(ops):
            if not isinstance(operation, dict):
                return f"operation {index} must be a JSON object"
            op_name = operation.get("op")
            if not isinstance(op_name, str):
                return f"operation {index}.op must be a string"
            if op_name not in ALLOWED_OPS:
                return f"operation not allowed at index {index}: {op_name[:80]!r}"
            nested_params = operation.get("params")
            if nested_params is not None and not isinstance(nested_params, dict):
                return f"operation {index}.params must be a JSON object"
            params = _operation_params(operation)
            error = _validate_operation_budget(op_name, params, index)
            if error:
                return error
    return None
