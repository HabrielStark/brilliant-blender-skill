"""Bridge command validation (no bpy import -> unit-testable).

The localhost bridge must validate every incoming command before touching
Blender. Structured operations only; the action and every recipe op must be in
the allowlist. Mirrors the core allowlist (kept in sync by tests).
"""

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


def validate_command(cmd, safety_mode="strict"):
    """Return an error string if invalid, else None."""
    if not isinstance(cmd, dict):
        return "command must be a JSON object"
    action = cmd.get("action")
    if action not in ALLOWED_ACTIONS:
        return f"action not allowed: {action!r}"
    if action in ("render_preview", "render_final", "export_glb"):
        output = cmd.get("output")
        if not isinstance(output, str) or not output.strip():
            return f"{action}.output must be a non-empty string path"
    if action == "apply_recipe":
        recipe = cmd.get("recipe") or {}
        ops = recipe.get("operations")
        if not isinstance(ops, list):
            return "recipe.operations must be a list"
        for o in ops:
            if not isinstance(o, dict) or o.get("op") not in ALLOWED_OPS:
                return f"operation not allowed: {o.get('op') if isinstance(o, dict) else o!r}"
    return None
