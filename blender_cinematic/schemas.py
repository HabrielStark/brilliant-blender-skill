"""Pydantic v2 schemas for every structured artifact in the pipeline.

Each schema mirrors a concrete section of the SRS and carries the validation
rules described there. Schemas use ``extra="forbid"`` so unknown / injected
fields are rejected rather than silently ignored (defence in depth, SRS 18).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from .constants import (
    DEFAULT_MAX_ITERATIONS,
    SCHEMA_VERSION,
)

OutputMode = Literal[
    "still",
    "animation",
    "web_asset",
    "interactive_web",
    "reference_match",
    "scene_repair",
    "benchmark",
]
QualityProfile = Literal["auto", "safe_laptop", "balanced", "cinematic", "ultra_4k"]

Color = Annotated[list[float], Field(min_length=3, max_length=4)]
Vec3 = Annotated[list[float], Field(min_length=3, max_length=3)]
Resolution = Annotated[list[int], Field(min_length=2, max_length=2)]

WEB_MODES = ("web_asset", "interactive_web")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _check_color(v: list[float]) -> list[float]:
    if not all(isinstance(c, (int, float)) for c in v):
        raise ValueError("color components must be numbers")
    if not all(0.0 <= float(c) <= 1.0 for c in v):
        raise ValueError("color components must be within [0, 1]")
    return [float(c) for c in v]


# --------------------------------------------------------------------------- #
# Scene manifest (SRS 8)
# --------------------------------------------------------------------------- #
class Target(_Strict):
    render_resolution: Resolution = [1920, 1080]
    preview_resolution: Resolution = [1280, 720]
    final_format: list[str] = Field(default_factory=lambda: ["blend", "png"])
    web_runtime: Optional[Literal["three", "react-three-fiber", "vanilla"]] = None

    @field_validator("render_resolution", "preview_resolution")
    @classmethod
    def _positive(cls, v: list[int]) -> list[int]:
        if any(int(x) <= 0 for x in v):
            raise ValueError("resolution components must be positive")
        return [int(x) for x in v]

    @field_validator("final_format")
    @classmethod
    def _known_formats(cls, v: list[str]) -> list[str]:
        allowed = {"blend", "png", "jpg", "mp4", "sequence", "glb", "gltf", "usd", "fbx", "obj"}
        bad = [f for f in v if f not in allowed]
        if bad:
            raise ValueError(f"unknown final_format(s): {bad}")
        return v


class Style(_Strict):
    mood: str = ""
    palette: list[str] = Field(default_factory=list)
    camera_language: str = ""
    lighting_language: str = ""


class Constraints(_Strict):
    no_paid_apis: bool = True
    no_unlicensed_assets: bool = True
    safe_hardware_budget: bool = True
    max_glb_mb: Optional[float] = Field(default=None, gt=0)
    max_texture_resolution: Optional[int] = Field(default=None, gt=0)


class SuccessCriteria(_Strict):
    scene_not_empty: bool = True
    subject_visible: bool = True
    camera_framed: bool = True
    lighting_valid: bool = True
    web_export_loads: bool = False
    visual_score_min: int = Field(default=80, ge=0, le=100)


class SceneManifest(_Strict):
    """SRS 8.1 manifest + 8.2 validation rules."""

    schema_version: str = SCHEMA_VERSION
    task_id: str = Field(min_length=1)
    brief: str
    output_mode: OutputMode
    quality_profile: QualityProfile = "auto"
    max_iterations: int = Field(default=DEFAULT_MAX_ITERATIONS, ge=1)
    user_override_max_iterations: bool = False
    target: Target = Field(default_factory=Target)
    style: Style = Field(default_factory=Style)
    constraints: Constraints = Field(default_factory=Constraints)
    references: list[str] = Field(default_factory=list)
    success_criteria: SuccessCriteria = Field(default_factory=SuccessCriteria)
    seed: Optional[int] = None

    @field_validator("brief")
    @classmethod
    def _brief_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("brief must not be empty")
        return v

    @model_validator(mode="after")
    def _semantic_rules(self) -> "SceneManifest":
        # SRS 8.2: max_iterations > 10 only with explicit override.
        if self.max_iterations > DEFAULT_MAX_ITERATIONS and not self.user_override_max_iterations:
            raise ValueError(
                f"max_iterations={self.max_iterations} exceeds default cap "
                f"{DEFAULT_MAX_ITERATIONS}; set user_override_max_iterations=true to allow"
            )
        # SRS 8.2: web export requires max_glb_mb and a web runtime target.
        wants_web = self.output_mode in WEB_MODES or any(
            f in ("glb", "gltf") for f in self.target.final_format
        )
        if wants_web:
            if self.constraints.max_glb_mb is None:
                raise ValueError("web export requires constraints.max_glb_mb")
            if self.target.web_runtime is None:
                raise ValueError("web export requires target.web_runtime")
        return self

    def wants_web(self) -> bool:
        return self.output_mode in WEB_MODES or any(
            f in ("glb", "gltf") for f in self.target.final_format
        )

    def wants_animation(self) -> bool:
        return self.output_mode in ("animation", "interactive_web") or "mp4" in self.target.final_format


# --------------------------------------------------------------------------- #
# Creative scene plan (SRS 10.1)
# --------------------------------------------------------------------------- #
class Composition(_Strict):
    shot_type: str
    focal_length_mm: float = Field(gt=0)
    camera_angle: str
    foreground: str = ""
    midground: str = ""
    background: str = ""


class ExportPlan(_Strict):
    glb: bool = False
    web_runtime: Optional[str] = None


class ScenePlan(_Strict):
    subject: str = Field(min_length=1)
    composition: Composition
    modeling: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    lighting: list[str] = Field(default_factory=list)
    animation: Optional[dict] = None
    export: ExportPlan = Field(default_factory=ExportPlan)


# --------------------------------------------------------------------------- #
# Materials (SRS 32.3)
# --------------------------------------------------------------------------- #
MATERIAL_PRESETS = (
    "matte_plastic", "glossy_plastic", "brushed_metal", "painted_metal",
    "glass_clear", "frosted_glass", "emissive_neon", "rubber_dark", "fabric",
    "skin_stylized", "stone_concrete", "wood", "water_simple", "hologram",
    "metallic_roughness_pbr",
)


class PBR(_Strict):
    base_color: Color = [0.8, 0.8, 0.8, 1.0]
    metallic: float = Field(default=0.0, ge=0.0, le=1.0)
    roughness: float = Field(default=0.5, ge=0.0, le=1.0)
    clearcoat: float = Field(default=0.0, ge=0.0, le=1.0)
    alpha: float = Field(default=1.0, ge=0.0, le=1.0)
    emission_color: Optional[Color] = None
    emission_strength: float = Field(default=0.0, ge=0.0)
    transmission: float = Field(default=0.0, ge=0.0, le=1.0)
    ior: float = Field(default=1.45, ge=1.0, le=3.0)

    _v_base = field_validator("base_color")(_check_color)

    @field_validator("emission_color")
    @classmethod
    def _v_emit(cls, v):
        return _check_color(v) if v is not None else v


class ColorRampStop(_Strict):
    position: float = Field(default=0.0, ge=0.0, le=1.0)
    color: Color

    _v_color = field_validator("color")(_check_color)


class ColorRamp(_Strict):
    noise_scale: float = Field(default=18.0, gt=0)
    detail: int = Field(default=8, ge=0, le=16)
    low_position: float = Field(default=0.2, ge=0.0, le=1.0)
    high_position: float = Field(default=1.0, ge=0.0, le=1.0)
    colors: list[Color] = Field(min_length=2, max_length=8)
    stops: list[ColorRampStop] = Field(default_factory=list)

    @field_validator("colors")
    @classmethod
    def _v_colors(cls, v: list[list[float]]) -> list[list[float]]:
        return [_check_color(color) for color in v]

    @model_validator(mode="after")
    def _positions_ordered(self) -> "ColorRamp":
        if self.high_position <= self.low_position:
            raise ValueError("high_position must be greater than low_position")
        return self


class CheckerPattern(_Strict):
    scale: float = Field(default=8.0, gt=0)
    color_a: Color = [0.02, 0.02, 0.02, 1.0]
    color_b: Color = [0.9, 0.9, 0.9, 1.0]
    colors: Optional[list[Color]] = None
    accent: Optional[Color] = None

    _v_a = field_validator("color_a")(_check_color)
    _v_b = field_validator("color_b")(_check_color)

    @field_validator("colors")
    @classmethod
    def _v_colors(cls, v: list[list[float]] | None) -> list[list[float]] | None:
        if v is None:
            return v
        if len(v) != 2:
            raise ValueError("checker.colors must contain exactly two colors")
        return [_check_color(color) for color in v]

    @field_validator("accent")
    @classmethod
    def _v_accent(cls, v):
        return _check_color(v) if v is not None else v


class WavePattern(_Strict):
    scale: float = Field(default=24.0, gt=0)
    distortion: float = Field(default=0.0, ge=0.0, le=50.0)
    bump_strength: float = Field(default=0.02, ge=0.0, le=1.0)


class RoughnessVariation(_Strict):
    noise_scale: float = Field(default=36.0, gt=0)
    detail: int = Field(default=8, ge=0, le=16)
    min_roughness: float = Field(default=0.25, ge=0.0, le=1.0)
    max_roughness: float = Field(default=0.75, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _range_ordered(self) -> "RoughnessVariation":
        if self.max_roughness <= self.min_roughness:
            raise ValueError("max_roughness must be greater than min_roughness")
        return self


class ImageTexture(_Strict):
    path: Optional[str] = None
    generated: Optional[Literal["checker_label", "stripe_label", "microprint_label"]] = None
    color_space: Literal["sRGB", "Non-Color", "Linear"] = "sRGB"
    role: Literal["base_color", "roughness", "normal", "emission", "alpha", "displacement"] = "base_color"
    projection: Literal["uv", "generated", "object"] = "uv"
    repeat: list[float] = Field(default_factory=lambda: [1.0, 1.0])
    offset: list[float] = Field(default_factory=lambda: [0.0, 0.0])
    rotation_degrees: float = 0.0
    uv_map: Optional[str] = None
    strength: float = Field(default=1.0, ge=0.0, le=10.0)

    @model_validator(mode="after")
    def _source_and_mapping_ok(self) -> "ImageTexture":
        if not self.path and not self.generated:
            raise ValueError("image texture needs either path or generated")
        if len(self.repeat) != 2 or len(self.offset) != 2:
            raise ValueError("repeat and offset must each have exactly two values")
        if self.repeat[0] <= 0 or self.repeat[1] <= 0:
            raise ValueError("repeat values must be positive")
        return self


class Procedural(_Strict):
    noise: bool = False
    noise_scale: float = Field(default=10.0, gt=0)
    bump_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    edge_wear: Literal["none", "subtle", "medium", "heavy"] = "none"
    scanlines: bool = False
    scanline_scale: float = Field(default=80.0, gt=0)
    scanline_strength: float = Field(default=0.18, ge=0.0, le=1.0)
    anisotropic: float = Field(default=0.0, ge=0.0, le=1.0)
    anisotropic_rotation: float = Field(default=0.0, ge=0.0, le=1.0)
    color_ramp: Optional[ColorRamp] = None
    checker: Optional[CheckerPattern] = None
    wave: Optional[WavePattern] = None
    roughness_variation: Optional[RoughnessVariation] = None
    image_textures: list[ImageTexture] = Field(default_factory=list)

    @model_validator(mode="after")
    def _authored_shader_limit(self) -> "Procedural":
        if len(self.image_textures) > 8:
            raise ValueError("image_textures supports at most 8 texture slots")
        return self


class ExportPolicy(_Strict):
    web_safe: bool = True
    bake_if_needed: bool = True
    fallback_material: str = "metallic_roughness_pbr"


class MaterialSchema(_Strict):
    name: str = Field(min_length=1)
    preset: Literal[MATERIAL_PRESETS] = "matte_plastic"  # type: ignore[valid-type]
    target_objects: list[str] = Field(default_factory=list)
    pbr: PBR = Field(default_factory=PBR)
    procedural: Procedural = Field(default_factory=Procedural)
    export_policy: ExportPolicy = Field(default_factory=ExportPolicy)


# --------------------------------------------------------------------------- #
# Geometry nodes (SRS 33.4)
# --------------------------------------------------------------------------- #
GEOMETRY_RECIPES = (
    "GN_PanelWall", "GN_BoltDistributor", "GN_CableBundle", "GN_CityWindows",
    "GN_RockScatter", "GN_TechGreebles", "GN_LabelArrows", "GN_OrbitalRings",
    "GN_ParticleDots", "GN_VegetationLow",
)


class GeometryExportPolicy(_Strict):
    apply_before_glb: bool = True
    keep_modifier_in_blend: bool = True
    max_generated_faces: int = Field(default=120000, gt=0)


class GeometryNodeSchema(_Strict):
    node_group_name: str = Field(min_length=1)
    recipe: Optional[Literal[GEOMETRY_RECIPES]] = None  # type: ignore[valid-type]
    target_object: str = Field(min_length=1)
    purpose: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    seed: int = 0
    export_policy: GeometryExportPolicy = Field(default_factory=GeometryExportPolicy)

    @model_validator(mode="after")
    def _seed_from_inputs(self) -> "GeometryNodeSchema":
        if "seed" in self.inputs and isinstance(self.inputs["seed"], int):
            self.seed = self.inputs["seed"]
        return self


# --------------------------------------------------------------------------- #
# Camera (SRS 35.3)
# --------------------------------------------------------------------------- #
CAMERA_PRESETS = (
    "macro_product", "hero_low_angle", "orthographic_technical",
    "wide_environment", "top_down_layout", "portrait_medium",
    "scroll_hero_start", "scroll_hero_detail",
)


class CameraComposition(_Strict):
    rule: str = "rule_of_thirds_center_bias"
    subject_screen_coverage: float = Field(default=0.6, gt=0.0, le=1.0)
    safe_margin: float = Field(default=0.08, ge=0.0, le=0.5)
    leading_lines: bool = False
    ortho_scale: Optional[float] = Field(default=None, gt=0.0)


class Lens(_Strict):
    focal_length_mm: float = Field(default=50.0, gt=0)
    sensor_width_mm: float = Field(default=36.0, gt=0)
    dof: bool = False
    focus_target: Optional[str] = None
    aperture_fstop: float = Field(default=2.8, gt=0)

    @model_validator(mode="after")
    def _dof_needs_target(self) -> "Lens":
        if self.dof and not self.focus_target:
            raise ValueError("dof=true requires focus_target")
        return self


class CameraSchema(_Strict):
    camera_name: str = Field(min_length=1)
    preset: Literal[CAMERA_PRESETS] = "macro_product"  # type: ignore[valid-type]
    target: Optional[str] = None
    location: Optional[Vec3] = None
    look_at: Optional[Vec3] = None
    composition: CameraComposition = Field(default_factory=CameraComposition)
    lens: Lens = Field(default_factory=Lens)
    motion: Optional[dict] = None


# --------------------------------------------------------------------------- #
# Lighting (SRS 36.3)
# --------------------------------------------------------------------------- #
LIGHTING_RIGS = (
    "three_point_soft", "studio_product_large_softbox", "neon_cyberpunk",
    "corridor_practical_lights", "technical_clean", "dramatic_rim",
    "world_hdri_like", "low_spec_flat_safe",
    "architectural_window_soft", "aurora_web_stage", "dramatic_rim_reference_match",
    "organic_macro_soft", "premium_material_lab_bright", "vfx_energy_burst_lighting",
    "warm_repair_studio", "web_asset_product_soft",
)
LIGHT_TYPES = ("POINT", "SUN", "SPOT", "AREA")


class Light(_Strict):
    name: str = Field(min_length=1)
    type: Literal[LIGHT_TYPES] = "AREA"  # type: ignore[valid-type]
    power: float = Field(default=100.0, ge=0)
    size: float = Field(default=1.0, gt=0)
    color: Color = [1.0, 1.0, 1.0]
    position_role: str = ""
    location: Optional[Vec3] = None

    _v_color = field_validator("color")(_check_color)


class World(_Strict):
    color: Color = [0.05, 0.05, 0.05]
    strength: float = Field(default=1.0, ge=0)

    _v_color = field_validator("color")(_check_color)


class LightingSchema(_Strict):
    lighting_rig: str = Field(default="three_point_soft", min_length=1)
    lights: list[Light] = Field(default_factory=list)
    world: World = Field(default_factory=World)
    volumetric: bool = False


# --------------------------------------------------------------------------- #
# Animation (SRS 34.3 / 34.6)
# --------------------------------------------------------------------------- #
ANIMATION_MODES = (
    "turntable", "camera_flythrough", "scroll_linked", "exploded_view",
    "reveal", "loop_idle", "light_pulse", "rig_basic",
)
INTERPOLATIONS = ("linear", "ease_in_out", "ease_in", "ease_out", "hold", "bezier", "constant")


class AnimCurve(_Strict):
    from_value: float = Field(alias="from")
    to_value: float = Field(alias="to")
    interpolation: Literal[INTERPOLATIONS] = "ease_in_out"  # type: ignore[valid-type]

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AnimCamera(_Strict):
    name: str
    locked: bool = True
    dof_target: Optional[str] = None
    start_location: Optional[Vec3] = None
    end_location: Optional[Vec3] = None


class AnimExport(_Strict):
    include_in_glb: bool = False
    clip_name: str = "Action"


class AnimationSchema(_Strict):
    animation_name: str = Field(min_length=1)
    mode: Literal[ANIMATION_MODES] = "turntable"  # type: ignore[valid-type]
    frame_start: int = Field(default=1, ge=0)
    frame_end: int = Field(default=120, ge=1)
    fps: int = Field(default=24, gt=0)
    loop: bool = False
    targets: list[str] = Field(default_factory=list)
    curves: dict[str, AnimCurve] = Field(default_factory=dict)
    camera: Optional[AnimCamera] = None
    params: dict[str, Any] = Field(default_factory=dict)
    export: AnimExport = Field(default_factory=AnimExport)

    @model_validator(mode="after")
    def _range_ok(self) -> "AnimationSchema":
        if self.frame_end <= self.frame_start:
            raise ValueError("frame_end must be greater than frame_start")
        return self

    @property
    def frame_count(self) -> int:
        return self.frame_end - self.frame_start + 1


class ScrollSegment(_Strict):
    from_scroll: float = Field(ge=0.0, le=1.0)
    to_scroll: float = Field(ge=0.0, le=1.0)
    camera_from_frame: int = Field(ge=0)
    camera_to_frame: int = Field(ge=0)
    text_section: str = ""

    @model_validator(mode="after")
    def _ordered(self) -> "ScrollSegment":
        if self.to_scroll <= self.from_scroll:
            raise ValueError("to_scroll must be greater than from_scroll")
        return self


class ScrollTimeline(_Strict):
    duration_pages: float = Field(default=4.0, gt=0)
    segments: list[ScrollSegment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _segments_cover(self) -> "ScrollTimeline":
        if not self.segments:
            raise ValueError("scroll timeline needs at least one segment")
        ordered = sorted(self.segments, key=lambda s: s.from_scroll)
        for a, b in zip(ordered, ordered[1:]):
            if b.from_scroll < a.to_scroll - 1e-6:
                raise ValueError("scroll segments must not overlap")
        return self


# --------------------------------------------------------------------------- #
# VFX (SRS 39.4)
# --------------------------------------------------------------------------- #
VFX_PRESETS = (
    "simple_particles_sparks", "hologram_particles", "energy_core_shell",
    "smoke_cards", "dust_motes", "liquid_simple", "emissive_core_no_particles",
)


class VfxSchema(_Strict):
    vfx_name: str = Field(min_length=1)
    preset: Literal[VFX_PRESETS] = "energy_core_shell"  # type: ignore[valid-type]
    target: str = Field(min_length=1)
    profile: QualityProfile = "balanced"
    params: dict[str, Any] = Field(default_factory=dict)
    fallback: dict[str, str] = Field(default_factory=dict)

    @field_validator("params")
    @classmethod
    def _particle_sanity(cls, v: dict) -> dict:
        pc = v.get("particle_count")
        if pc is not None and (not isinstance(pc, int) or pc < 0):
            raise ValueError("particle_count must be a non-negative integer")
        return v


# --------------------------------------------------------------------------- #
# Compositor / post (SRS 40.3)
# --------------------------------------------------------------------------- #
POST_PRESETS = (
    "clean_product", "cinematic_contrast", "neon_bloom", "technical_flat",
    "atmospheric_depth", "website_hero",
    "interior_editorial_warm_contrast", "safe_laptop_clean_daylight",
    "technical_cutaway_crisp_bright",
)


class PostEffects(_Strict):
    bloom: str = "off"
    vignette: str = "off"
    mist: bool = False
    color_balance: str = "neutral"


class PostManifest(_Strict):
    post_preset: Literal[POST_PRESETS] = "clean_product"  # type: ignore[valid-type]
    view_transform: str = "Filmic"
    look: str = "None"
    exposure: float = 0.0
    gamma: float = Field(default=1.0, gt=0)
    effects: PostEffects = Field(default_factory=PostEffects)
    save_raw_render: bool = True


# --------------------------------------------------------------------------- #
# Rig (SRS 38.3)
# --------------------------------------------------------------------------- #
class RigControl(_Strict):
    name: str = Field(min_length=1)
    type: Literal["empty", "bone", "armature"] = "empty"
    drives: list[str] = Field(default_factory=list)


class RigDriver(_Strict):
    target: str = Field(min_length=1)
    driver: str = Field(min_length=1)


class RigManifest(_Strict):
    rig_name: str = Field(min_length=1)
    controls: list[RigControl] = Field(default_factory=list)
    drivers: list[RigDriver] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Reference match (SRS 41.3)
# --------------------------------------------------------------------------- #
class ReferenceSummary(_Strict):
    subject: str = ""
    palette: list[str] = Field(default_factory=list)
    camera: str = ""
    lighting: str = ""
    materials: list[str] = Field(default_factory=list)


class MatchTargets(_Strict):
    palette_similarity: float = Field(default=0.7, ge=0.0, le=1.0)
    composition_similarity: float = Field(default=0.7, ge=0.0, le=1.0)
    required_objects_present: bool = True
    forbidden_default_gray: bool = True


class ReferenceMatchManifest(_Strict):
    reference_summary: ReferenceSummary = Field(default_factory=ReferenceSummary)
    match_targets: MatchTargets = Field(default_factory=MatchTargets)


__all__ = [
    "SceneManifest", "Target", "Style", "Constraints", "SuccessCriteria",
    "ScenePlan", "Composition", "ExportPlan",
    "MaterialSchema", "PBR", "Procedural", "ColorRamp", "CheckerPattern",
    "WavePattern", "RoughnessVariation", "ImageTexture", "ExportPolicy", "MATERIAL_PRESETS",
    "GeometryNodeSchema", "GEOMETRY_RECIPES",
    "CameraSchema", "Lens", "CameraComposition", "CAMERA_PRESETS",
    "LightingSchema", "Light", "World", "LIGHTING_RIGS",
    "AnimationSchema", "ScrollTimeline", "ScrollSegment", "ANIMATION_MODES",
    "VfxSchema", "VFX_PRESETS",
    "PostManifest", "POST_PRESETS",
    "RigManifest", "ReferenceMatchManifest",
]
