"""Structured scene-operation allowlist (SRS 12.4 ``scene.apply_recipe``).

Only operations in :data:`OPERATION_SPECS` may run. This is the security
boundary that replaces "execute arbitrary Python": the agent emits a recipe of
named operations with typed parameters, the core validates them, and only the
add-on's matching builder runs inside Blender. A complexity estimator (SRS
19.4) lets us reject geometry/particle bombs before touching Blender.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .results import CheckResult, error, warn
from .schemas import (
    AnimationSchema,
    CameraSchema,
    GeometryNodeSchema,
    LightingSchema,
    MaterialSchema,
    PostManifest,
    RigManifest,
    VfxSchema,
)

PRIMITIVES = ("cube", "uv_sphere", "ico_sphere", "cylinder", "cone", "plane", "torus", "circle")
MODIFIERS = (
    "BEVEL", "SUBSURF", "ARRAY", "MIRROR", "SOLIDIFY", "WEIGHTED_NORMAL",
    "DECIMATE", "TRIANGULATE", "SHRINKWRAP", "BOOLEAN", "CURVE", "WIREFRAME",
)

# Rough face counts for primitives (default Blender resolution).
_PRIM_FACES = {
    "cube": 6, "plane": 1, "circle": 32, "uv_sphere": 960, "ico_sphere": 320,
    "cylinder": 96, "cone": 64, "torus": 576,
}
MAX_SUBDIVISION_LEVEL = 8
MAX_ARRAY_COUNT = 1000
MAX_BEVEL_SEGMENTS = 64
MAX_ORGANIC_SURFACE_COUNT = 96
ORGANIC_SURFACE_FACES = 96
MAX_ENERGY_STREAK_COUNT = 160
MAX_ENERGY_STREAK_SEGMENTS = 32
MAX_ORGANIC_BODY_SEGMENTS = 160
MAX_ORGANIC_BODY_RINGS = 80
ORGANIC_FLUTED_BODY_MODIFIERS = 2
MAX_FACETED_HERO_SEGMENTS = 128
MAX_FACETED_HERO_RINGS = 64
FACETED_HERO_BODY_MODIFIERS = 2
MAX_TEXT_LABELS = 64
MAX_TEXT_LABEL_CHARS = 160
MAX_DECAL_PLANES = 128
MAX_CURVE_TUBE_POINTS = 64
MAX_FASTENER_COUNT = 256
MAX_PANEL_CUTLINE_COUNT = 256
MAX_GRILLE_SLAT_COUNT = 256
MAX_SURFACE_MICRODETAIL_COUNT = 256


def _spec(required: dict[str, type], optional: dict[str, type] | None = None,
          category: str = "geometry") -> dict:
    return {"required": required, "optional": optional or {}, "category": category}


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def _numeric_guard(result: CheckResult, loc: str, code: str, label: str, value, low: int, high: int) -> None:
    if not isinstance(value, int):
        return
    if value < low or value > high:
        result.add(error(code, f"{label} must be between {low} and {high}", loc))


OPERATION_SPECS: dict[str, dict] = {
    "ensure_standard_collections": _spec({}, {}, "scene"),
    "create_collection": _spec({"name": str}, {"parent": str}, "scene"),
    "set_scene_metadata": _spec({"data": dict}, {}, "scene"),
    "create_mesh_primitive": _spec(
        {"type": str, "name": str},
        {"location": list, "rotation": list, "scale": list, "size": (int, float), "collection": str},
    ),
    "add_modifier": _spec({"target": str, "modifier": str}, {"params": dict}),
    "add_bevel_modifier": _spec({"target": str, "width": (int, float)}, {"segments": int}),
    "add_subdivision": _spec({"target": str}, {"levels": int, "render_levels": int}),
    "add_array_modifier": _spec({"target": str, "count": int}, {"offset": list}),
    "set_object_transform": _spec({"target": str}, {"location": list, "rotation": list, "scale": list}),
    "apply_transform": _spec({"target": str}, {"location": bool, "rotation": bool, "scale": bool}),
    "set_smooth_shading": _spec({"target": str, "smooth": bool}, {}),
    "set_origin": _spec({"target": str}, {"mode": str}),
    "move_to_collection": _spec({"target": str, "collection": str}, {}),
    "parent_objects": _spec({"child": str, "parent": str}, {}),
    "assign_material": _spec({"target": str, "material": str}, {}, "material"),
    "create_material": _spec({"schema": dict}, {}, "material"),
    "create_camera": _spec({"schema": dict}, {}, "camera"),
    "create_lighting_rig": _spec({"schema": dict}, {}, "lighting"),
    "add_light": _spec({"schema": dict}, {"collection": str}, "lighting"),
    "create_geometry_nodes": _spec({"schema": dict}, {}, "geometry"),
    "create_radial_markers": _spec(
        {"name_prefix": str},
        {
            "center": list,
            "radius": (int, float),
            "count": int,
            "size": list,
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
        },
    ),
    "create_linear_markers": _spec(
        {"name_prefix": str},
        {"start": list, "step": list, "count": int, "size": list, "rotation": list, "collection": str,
         "material": str, "parent": str, "role": str},
    ),
    "create_text_label": _spec(
        {"name": str, "text": str},
        {
            "location": list,
            "rotation": list,
            "scale": list,
            "size": (int, float),
            "align_x": str,
            "align_y": str,
            "extrude": (int, float),
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
        },
        "detail",
    ),
    "create_decal_plane": _spec(
        {"name": str},
        {
            "location": list,
            "rotation": list,
            "size": list,
            "collection": str,
            "material": str,
            "parent": str,
            "bevel_width": (int, float),
            "role": str,
        },
        "detail",
    ),
    "create_curve_tube": _spec(
        {"name": str, "points": list},
        {
            "bevel_depth": (int, float),
            "resolution": int,
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
        },
        "detail",
    ),
    "create_fastener_pattern": _spec(
        {"name_prefix": str},
        {
            "center": list,
            "radius": (int, float),
            "count": int,
            "size": (int, float),
            "pattern": str,
            "start": list,
            "step": list,
            "rotation": list,
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
        },
        "detail",
    ),
    "create_panel_cutlines": _spec(
        {"name_prefix": str},
        {
            "start": list,
            "step": list,
            "count": int,
            "size": list,
            "rotation": list,
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
        },
        "detail",
    ),
    "create_grille": _spec(
        {"name_prefix": str},
        {
            "start": list,
            "step": list,
            "count": int,
            "slat_size": list,
            "rotation": list,
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
        },
        "detail",
    ),
    "create_surface_microdetails": _spec(
        {"name_prefix": str},
        {
            "pattern": str,
            "center": list,
            "start": list,
            "step": list,
            "direction": list,
            "radius": (int, float),
            "count": int,
            "length": (int, float),
            "bevel_depth": (int, float),
            "waviness": (int, float),
            "phase_degrees": (int, float),
            "rotation": list,
            "collection": str,
            "material": str,
            "parent": str,
            "role": str,
            "seed": int,
        },
        "detail",
    ),
    "create_organic_surface_details": _spec(
        {"name_prefix": str},
        {
            "pattern": str,
            "center": list,
            "start": list,
            "step": list,
            "radius": (int, float),
            "count": int,
            "length": (int, float),
            "width": (int, float),
            "thickness": (int, float),
            "curl": (int, float),
            "bend": (int, float),
            "tilt_degrees": (int, float),
            "twist_degrees": (int, float),
            "phase_degrees": (int, float),
            "rotation": list,
            "segments_u": int,
            "segments_v": int,
            "taper": (int, float),
            "collection": str,
            "material": str,
            "role": str,
        },
    ),
    "create_energy_burst_streaks": _spec(
        {"name_prefix": str},
        {
            "center": list,
            "count": int,
            "radius_min": (int, float),
            "radius_max": (int, float),
            "length_min": (int, float),
            "length_max": (int, float),
            "width": (int, float),
            "thickness": (int, float),
            "curl": (int, float),
            "fan_degrees": (int, float),
            "angle_degrees": (int, float),
            "angle_jitter_degrees": (int, float),
            "tilt_degrees": (int, float),
            "z_jitter": (int, float),
            "segments": int,
            "seed": int,
            "collection": str,
            "material": str,
            "role": str,
        },
    ),
    "create_organic_fluted_body": _spec(
        {"name": str},
        {
            "location": list,
            "rotation": list,
            "scale": list,
            "radius": (int, float),
            "height": (int, float),
            "segments": int,
            "rings": int,
            "lobes": int,
            "waist": (int, float),
            "rim_wave": (int, float),
            "twist_degrees": (int, float),
            "cap_bottom": bool,
            "smooth": bool,
            "subdivision_levels": int,
            "collection": str,
            "material": str,
        },
    ),
    "create_faceted_hero_body": _spec(
        {"name": str},
        {
            "location": list,
            "rotation": list,
            "scale": list,
            "radius": (int, float),
            "height": (int, float),
            "segments": int,
            "rings": int,
            "facet_twist_degrees": (int, float),
            "shoulder": (int, float),
            "waist": (int, float),
            "crown_height": (int, float),
            "pavilion_height": (int, float),
            "facet_depth": (int, float),
            "cap_top": bool,
            "cap_bottom": bool,
            "bevel_width": (int, float),
            "collection": str,
            "material": str,
        },
    ),
    "create_animation": _spec({"schema": dict}, {}, "animation"),
    "create_vfx": _spec({"schema": dict}, {}, "vfx"),
    "create_rig": _spec({"schema": dict}, {}, "rig"),
    "apply_post": _spec({"schema": dict}, {}, "compositor"),
    "add_constraint": _spec({"target": str, "constraint": str}, {"params": dict}),
}

ALLOWED_OPS = tuple(OPERATION_SPECS)

NESTED_SCHEMA_BY_OP = {
    "create_material": MaterialSchema,
    "create_camera": CameraSchema,
    "create_lighting_rig": LightingSchema,
    "add_light": LightingSchema,
    "create_geometry_nodes": GeometryNodeSchema,
    "create_animation": AnimationSchema,
    "create_vfx": VfxSchema,
    "create_rig": RigManifest,
    "apply_post": PostManifest,
}


class RecipeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    op: str
    # Remaining fields are operation-specific; captured generically and
    # validated against OPERATION_SPECS by validate_recipe().
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("op")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in OPERATION_SPECS:
            raise ValueError(f"operation {v!r} is not in the allowlist {ALLOWED_OPS}")
        return v


class Recipe(BaseModel):
    model_config = ConfigDict(extra="forbid")
    operations: list[RecipeOperation] = Field(default_factory=list)


def _coerce(raw: dict) -> Recipe:
    """Accept either {op, ...flat params} or {op, params:{...}} per operation."""
    ops = []
    for item in raw.get("operations", []):
        if not isinstance(item, dict) or "op" not in item:
            raise ValueError("each operation needs an 'op' field")
        op = item["op"]
        nested_params = item.get("params")
        flat_params = {k: v for k, v in item.items() if k not in ("op", "params")}
        if nested_params is None:
            params = flat_params
        elif flat_params:
            params = {**flat_params, "params": nested_params}
        else:
            params = nested_params
        ops.append({"op": op, "params": params})
    return Recipe(operations=ops)


def _validate_nested_schema(result: CheckResult, op: str, params: dict[str, Any], loc: str) -> None:
    model = NESTED_SCHEMA_BY_OP.get(op)
    if model is None:
        return
    schema = params.get("schema")
    if not isinstance(schema, dict):
        return
    try:
        if op == "add_light":
            model(lights=[schema])
        else:
            model(**schema)
    except Exception as exc:
        result.add(error("recipe.schema_invalid", f"{op} schema invalid: {exc}", loc))


def validate_recipe(raw: dict) -> CheckResult:
    """Validate a recipe dict against the allowlist and per-op param specs."""
    result = CheckResult(name="recipe")
    try:
        recipe = _coerce(raw)
    except Exception as exc:
        result.add(error("recipe.parse", str(exc)))
        return result

    for idx, opn in enumerate(recipe.operations):
        spec = OPERATION_SPECS[opn.op]
        loc = f"operations[{idx}].{opn.op}"
        for key, typ in spec["required"].items():
            if key not in opn.params:
                result.add(error("recipe.missing_param", f"missing required param '{key}'", loc))
            elif not isinstance(opn.params[key], typ):
                result.add(error("recipe.bad_type",
                                 f"param '{key}' must be {getattr(typ,'__name__',typ)}", loc))
        for key in opn.params:
            if key not in spec["required"] and key not in spec["optional"]:
                result.add(warn("recipe.unknown_param", f"unknown param '{key}' for {opn.op}", loc))
        _validate_nested_schema(result, opn.op, opn.params, loc)
        if opn.op == "create_mesh_primitive":
            t = opn.params.get("type")
            if t is not None and t not in PRIMITIVES:
                result.add(error("recipe.bad_primitive", f"unknown primitive '{t}'", loc))
        if opn.op == "add_modifier":
            m = opn.params.get("modifier")
            if m is not None and m not in MODIFIERS:
                result.add(error("recipe.bad_modifier", f"unknown modifier '{m}'", loc))
        if opn.op == "add_subdivision":
            _numeric_guard(
                result,
                loc,
                "recipe.subdivision_budget",
                "levels",
                opn.params.get("levels", 1),
                0,
                MAX_SUBDIVISION_LEVEL,
            )
            _numeric_guard(
                result,
                loc,
                "recipe.subdivision_budget",
                "render_levels",
                opn.params.get("render_levels", opn.params.get("levels", 1)),
                0,
                MAX_SUBDIVISION_LEVEL,
            )
        if opn.op == "add_array_modifier":
            _numeric_guard(
                result,
                loc,
                "recipe.array_budget",
                "count",
                opn.params.get("count"),
                1,
                MAX_ARRAY_COUNT,
            )
        if opn.op == "add_bevel_modifier":
            _numeric_guard(
                result,
                loc,
                "recipe.bevel_budget",
                "segments",
                opn.params.get("segments", 1),
                0,
                MAX_BEVEL_SEGMENTS,
            )
        if opn.op == "create_radial_markers":
            _numeric_guard(
                result,
                loc,
                "recipe.marker_budget",
                "count",
                opn.params.get("count", 12),
                1,
                96,
            )
        if opn.op == "create_linear_markers":
            _numeric_guard(
                result,
                loc,
                "recipe.marker_budget",
                "count",
                opn.params.get("count", 8),
                1,
                128,
            )
        if opn.op == "create_text_label":
            text = opn.params.get("text", "")
            if isinstance(text, str) and len(text) > MAX_TEXT_LABEL_CHARS:
                result.add(
                    error(
                        "recipe.text_budget",
                        f"text label must be at most {MAX_TEXT_LABEL_CHARS} characters",
                        loc,
                    )
                )
        if opn.op == "create_decal_plane":
            size = opn.params.get("size", [1.0, 0.25, 0.01])
            if isinstance(size, list) and len(size) not in (2, 3):
                result.add(error("recipe.decal_shape", "size must have 2 or 3 numeric components", loc))
        if opn.op == "create_curve_tube":
            points = opn.params.get("points", [])
            if not isinstance(points, list) or len(points) < 2 or len(points) > MAX_CURVE_TUBE_POINTS:
                result.add(
                    error(
                        "recipe.curve_tube_budget",
                        f"points length must be between 2 and {MAX_CURVE_TUBE_POINTS}",
                        loc,
                    )
                )
            elif any(not isinstance(point, list) or len(point) != 3 for point in points):
                result.add(error("recipe.curve_tube_shape", "each point must be a 3-component list", loc))
        if opn.op == "create_fastener_pattern":
            _numeric_guard(
                result,
                loc,
                "recipe.fastener_budget",
                "count",
                opn.params.get("count", 8),
                1,
                MAX_FASTENER_COUNT,
            )
        if opn.op == "create_panel_cutlines":
            _numeric_guard(
                result,
                loc,
                "recipe.panel_cutline_budget",
                "count",
                opn.params.get("count", 8),
                1,
                MAX_PANEL_CUTLINE_COUNT,
            )
        if opn.op == "create_grille":
            _numeric_guard(
                result,
                loc,
                "recipe.grille_budget",
                "count",
                opn.params.get("count", 8),
                1,
                MAX_GRILLE_SLAT_COUNT,
            )
        if opn.op == "create_surface_microdetails":
            _numeric_guard(
                result,
                loc,
                "recipe.surface_microdetail_budget",
                "count",
                opn.params.get("count", 12),
                1,
                MAX_SURFACE_MICRODETAIL_COUNT,
            )
        if opn.op == "create_organic_surface_details":
            _numeric_guard(
                result,
                loc,
                "recipe.organic_surface_budget",
                "count",
                opn.params.get("count", 8),
                1,
                MAX_ORGANIC_SURFACE_COUNT,
            )
        if opn.op == "create_energy_burst_streaks":
            _numeric_guard(
                result,
                loc,
                "recipe.energy_streak_budget",
                "count",
                opn.params.get("count", 24),
                1,
                MAX_ENERGY_STREAK_COUNT,
            )
            _numeric_guard(
                result,
                loc,
                "recipe.energy_streak_budget",
                "segments",
                opn.params.get("segments", 12),
                3,
                MAX_ENERGY_STREAK_SEGMENTS,
            )
        if opn.op == "create_organic_fluted_body":
            _numeric_guard(
                result,
                loc,
                "recipe.organic_body_budget",
                "segments",
                opn.params.get("segments", 64),
                12,
                MAX_ORGANIC_BODY_SEGMENTS,
            )
            _numeric_guard(
                result,
                loc,
                "recipe.organic_body_budget",
                "rings",
                opn.params.get("rings", 18),
                4,
                MAX_ORGANIC_BODY_RINGS,
            )
            _numeric_guard(
                result,
                loc,
                "recipe.organic_body_budget",
                "lobes",
                opn.params.get("lobes", 8),
                0,
                32,
            )
        if opn.op == "create_faceted_hero_body":
            _numeric_guard(
                result,
                loc,
                "recipe.faceted_hero_budget",
                "segments",
                opn.params.get("segments", 48),
                8,
                MAX_FACETED_HERO_SEGMENTS,
            )
            _numeric_guard(
                result,
                loc,
                "recipe.faceted_hero_budget",
                "rings",
                opn.params.get("rings", 18),
                4,
                MAX_FACETED_HERO_RINGS,
            )
    return result


def estimate_complexity(raw: dict, budget_faces: int = 2_000_000) -> dict:
    """Estimate object/face/modifier counts before touching Blender (SRS 19.4)."""
    try:
        recipe = _coerce(raw)
    except Exception:
        return {"objects": 0, "faces": 0, "modifiers": 0, "within_budget": True, "notes": ["unparsable"]}

    objects = faces = modifiers = 0
    notes: list[str] = []
    base_faces: dict[str, int] = {}  # object name -> base faces, for modifier scaling
    for opn in recipe.operations:
        p = opn.params
        if opn.op == "create_mesh_primitive":
            objects += 1
            f = _PRIM_FACES.get(str(p.get("type", "cube")), 12)
            base_faces[str(p.get("name", f"obj{objects}"))] = f
            faces += f
        elif opn.op in ("add_modifier", "add_bevel_modifier", "add_subdivision", "add_array_modifier"):
            modifiers += 1
            tgt = str(p.get("target"))
            cur = base_faces.get(tgt, 100)
            if opn.op == "add_subdivision":
                lv = _safe_int(p.get("levels", 1), 1)
                if lv < 0 or lv > MAX_SUBDIVISION_LEVEL:
                    add = max(0, budget_faces + 1 - faces)
                    notes.append(f"subdivision level {lv} outside supported range 0..{MAX_SUBDIVISION_LEVEL}")
                else:
                    add = cur * (4 ** lv) - cur
            elif opn.op == "add_array_modifier":
                count = _safe_int(p.get("count", 2), 2)
                if count < 1 or count > MAX_ARRAY_COUNT:
                    add = max(0, budget_faces + 1 - faces)
                    notes.append(f"array count {count} outside supported range 1..{MAX_ARRAY_COUNT}")
                else:
                    add = cur * (count - 1)
            elif opn.op == "add_bevel_modifier":
                add = int(cur * 0.5)
            else:
                add = int(cur * 1.0)
            faces += max(0, add)
            base_faces[tgt] = cur + max(0, add)
        elif opn.op == "create_geometry_nodes":
            schema = p.get("schema") if isinstance(p.get("schema"), dict) else {}
            ep = schema.get("export_policy") if isinstance(schema.get("export_policy"), dict) else {}
            gen = _safe_int(ep.get("max_generated_faces", 50000), 50000)
            faces += gen
            notes.append(f"geometry-nodes max {gen} faces")
        elif opn.op == "create_radial_markers":
            count = _safe_int(p.get("count", 12), 12)
            if count < 1 or count > 96:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"radial marker count {count} outside supported range 1..96")
            else:
                objects += count
                faces += 6 * count
        elif opn.op == "create_linear_markers":
            count = _safe_int(p.get("count", 8), 8)
            if count < 1 or count > 128:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"linear marker count {count} outside supported range 1..128")
            else:
                objects += count
                faces += 6 * count
        elif opn.op == "create_text_label":
            text = str(p.get("text", ""))
            if len(text) > MAX_TEXT_LABEL_CHARS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"text label length {len(text)} exceeds {MAX_TEXT_LABEL_CHARS}")
            else:
                objects += 1
                faces += max(24, len(text) * 16)
        elif opn.op == "create_decal_plane":
            objects += 1
            faces += 6
            modifiers += 1 if float(p.get("bevel_width", 0.006) or 0) > 0 else 0
        elif opn.op == "create_curve_tube":
            points = p.get("points") if isinstance(p.get("points"), list) else []
            if len(points) < 2 or len(points) > MAX_CURVE_TUBE_POINTS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"curve tube point count {len(points)} outside supported range 2..{MAX_CURVE_TUBE_POINTS}")
            else:
                objects += 1
                faces += max(16, len(points) * 24)
        elif opn.op == "create_fastener_pattern":
            count = _safe_int(p.get("count", 8), 8)
            if count < 1 or count > MAX_FASTENER_COUNT:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"fastener count {count} outside supported range 1..{MAX_FASTENER_COUNT}")
            else:
                objects += count
                faces += 96 * count
                modifiers += count
        elif opn.op == "create_panel_cutlines":
            count = _safe_int(p.get("count", 8), 8)
            if count < 1 or count > MAX_PANEL_CUTLINE_COUNT:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"panel cutline count {count} outside supported range 1..{MAX_PANEL_CUTLINE_COUNT}")
            else:
                objects += count
                faces += 6 * count
                modifiers += count
        elif opn.op == "create_grille":
            count = _safe_int(p.get("count", 8), 8)
            if count < 1 or count > MAX_GRILLE_SLAT_COUNT:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"grille slat count {count} outside supported range 1..{MAX_GRILLE_SLAT_COUNT}")
            else:
                objects += count
                faces += 6 * count
                modifiers += count
        elif opn.op == "create_surface_microdetails":
            count = _safe_int(p.get("count", 12), 12)
            if count < 1 or count > MAX_SURFACE_MICRODETAIL_COUNT:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(
                    "surface microdetail count "
                    f"{count} outside supported range 1..{MAX_SURFACE_MICRODETAIL_COUNT}"
                )
            else:
                objects += count
                faces += 48 * count
        elif opn.op == "create_organic_surface_details":
            count = _safe_int(p.get("count", 8), 8)
            if count < 1 or count > MAX_ORGANIC_SURFACE_COUNT:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(
                    f"organic surface count {count} outside supported range 1..{MAX_ORGANIC_SURFACE_COUNT}"
                )
            else:
                objects += count
                modifiers += count * 2
                faces += ORGANIC_SURFACE_FACES * count
        elif opn.op == "create_energy_burst_streaks":
            count = _safe_int(p.get("count", 24), 24)
            segments = _safe_int(p.get("segments", 12), 12)
            if count < 1 or count > MAX_ENERGY_STREAK_COUNT:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"energy streak count {count} outside supported range 1..{MAX_ENERGY_STREAK_COUNT}")
            elif segments < 3 or segments > MAX_ENERGY_STREAK_SEGMENTS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(
                    f"energy streak segments {segments} outside supported range 3..{MAX_ENERGY_STREAK_SEGMENTS}"
                )
            else:
                objects += count
                modifiers += count * 2
                faces += count * segments * 2
        elif opn.op == "create_organic_fluted_body":
            segments = _safe_int(p.get("segments", 64), 64)
            rings = _safe_int(p.get("rings", 18), 18)
            if segments < 12 or segments > MAX_ORGANIC_BODY_SEGMENTS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(
                    f"organic body segments {segments} outside supported range 12..{MAX_ORGANIC_BODY_SEGMENTS}"
                )
            elif rings < 4 or rings > MAX_ORGANIC_BODY_RINGS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"organic body rings {rings} outside supported range 4..{MAX_ORGANIC_BODY_RINGS}")
            else:
                objects += 1
                modifiers += ORGANIC_FLUTED_BODY_MODIFIERS
                faces += segments * rings + segments
        elif opn.op == "create_faceted_hero_body":
            segments = _safe_int(p.get("segments", 48), 48)
            rings = _safe_int(p.get("rings", 18), 18)
            if segments < 8 or segments > MAX_FACETED_HERO_SEGMENTS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(
                    f"faceted hero segments {segments} outside supported range 8..{MAX_FACETED_HERO_SEGMENTS}"
                )
            elif rings < 4 or rings > MAX_FACETED_HERO_RINGS:
                faces += max(0, budget_faces + 1 - faces)
                notes.append(f"faceted hero rings {rings} outside supported range 4..{MAX_FACETED_HERO_RINGS}")
            else:
                objects += 1
                modifiers += FACETED_HERO_BODY_MODIFIERS
                faces += segments * rings + segments * 2
        elif opn.op == "create_vfx":
            schema = p.get("schema") if isinstance(p.get("schema"), dict) else {}
            params = schema.get("params") if isinstance(schema.get("params"), dict) else {}
            pc = params.get("particle_count", 0)
            if isinstance(pc, int) and pc > 5000:
                notes.append(f"high particle count {pc}")

    within = faces <= budget_faces
    if not within:
        notes.append(f"estimated faces {faces} exceed budget {budget_faces}")
    return {"objects": objects, "faces": faces, "modifiers": modifiers,
            "within_budget": within, "budget_faces": budget_faces, "notes": notes}
