"""Unit tests for every schema + its validation rules (SRS 8.2, 17.1)."""
import pytest
from pydantic import ValidationError

from blender_cinematic.schemas import (
    AnimationSchema,
    CameraSchema,
    GeometryNodeSchema,
    LightingSchema,
    MaterialSchema,
    PostManifest,
    RigManifest,
    SceneManifest,
    ScrollTimeline,
    VfxSchema,
)


def _web_manifest(**over):
    base = dict(task_id="t", brief="b", output_mode="web_asset",
                target={"final_format": ["blend", "glb"], "web_runtime": "react-three-fiber"},
                constraints={"max_glb_mb": 20})
    base.update(over)
    return SceneManifest(**base)


def test_manifest_valid():
    m = SceneManifest(task_id="t1", brief="cinematic watch", output_mode="still")
    assert m.quality_profile == "auto"
    assert not m.wants_web()


def test_manifest_web_valid():
    assert _web_manifest().wants_web()


@pytest.mark.parametrize("kw", [
    dict(brief="   "),                                   # empty brief
    dict(output_mode="nope"),                            # unknown mode
    dict(max_iterations=20),                             # > cap without override
])
def test_manifest_invalid(kw):
    base = dict(task_id="t", brief="b", output_mode="still")
    base.update(kw)
    with pytest.raises(ValidationError):
        SceneManifest(**base)


def test_manifest_override_allows_high_iterations():
    m = SceneManifest(task_id="t", brief="b", output_mode="still",
                      max_iterations=20, user_override_max_iterations=True)
    assert m.max_iterations == 20


def test_manifest_web_requires_glb_mb_and_runtime():
    with pytest.raises(ValidationError):
        SceneManifest(task_id="t", brief="b", output_mode="web_asset")
    with pytest.raises(ValidationError):
        SceneManifest(task_id="t", brief="b", output_mode="web_asset",
                      target={"final_format": ["glb"], "web_runtime": "three"})  # no max_glb_mb


def test_material_presets_and_colors():
    MaterialSchema(name="m", preset="brushed_metal")
    with pytest.raises(ValidationError):
        MaterialSchema(name="m", preset="not_a_preset")
    with pytest.raises(ValidationError):
        MaterialSchema(name="m", pbr={"base_color": [2.0, 0, 0, 1]})  # out of range


def test_material_procedural_shader_features_are_typed():
    m = MaterialSchema(
        name="authored_shader",
        procedural={
            "noise": True,
            "color_ramp": {
                "noise_scale": 18,
                "detail": 8,
                "low_position": 0.15,
                "high_position": 0.95,
                "colors": [[0.02, 0.08, 0.1, 1], [0.7, 0.9, 0.85, 1]],
            },
            "checker": {
                "scale": 12,
                "colors": [[0.04, 0.04, 0.05, 1], [0.88, 0.9, 0.86, 1]],
            },
            "wave": {"scale": 32, "distortion": 1.5, "bump_strength": 0.02},
            "edge_wear": "medium",
            "scanlines": True,
            "scanline_scale": 96,
            "scanline_strength": 0.22,
            "anisotropic": 0.75,
            "anisotropic_rotation": 0.2,
            "roughness_variation": {
                "noise_scale": 42,
                "detail": 10,
                "min_roughness": 0.18,
                "max_roughness": 0.72,
            },
        },
    )

    assert m.procedural.color_ramp is not None
    assert m.procedural.checker is not None
    assert m.procedural.wave is not None
    assert m.procedural.edge_wear == "medium"
    assert m.procedural.scanlines is True
    assert m.procedural.roughness_variation is not None
    assert m.procedural.anisotropic == 0.75


def test_material_image_texture_mapping_is_typed():
    m = MaterialSchema(
        name="mapped_texture",
        procedural={
            "image_textures": [{
                "generated": "checker_label",
                "role": "base_color",
                "projection": "generated",
                "repeat": [2.0, 3.0],
                "offset": [0.1, 0.2],
                "rotation_degrees": 12,
            }]
        },
    )

    tex = m.procedural.image_textures[0]
    assert tex.generated == "checker_label"
    assert tex.projection == "generated"
    assert tex.repeat == [2.0, 3.0]
    assert tex.offset == [0.1, 0.2]


def test_material_procedural_shader_feature_validation():
    with pytest.raises(ValidationError):
        MaterialSchema(
            name="bad_ramp",
            procedural={
                "color_ramp": {
                    "low_position": 0.8,
                    "high_position": 0.2,
                    "colors": [[0.1, 0.1, 0.1, 1], [0.9, 0.9, 0.9, 1]],
                }
            },
        )
    with pytest.raises(ValidationError):
        MaterialSchema(
            name="bad_checker",
            procedural={"checker": {"colors": [[0.1, 0.1, 0.1, 1]]}},
        )
    with pytest.raises(ValidationError):
        MaterialSchema(
            name="bad_roughness_range",
            procedural={
                "roughness_variation": {
                    "min_roughness": 0.9,
                    "max_roughness": 0.2,
                }
            },
        )
    with pytest.raises(ValidationError):
        MaterialSchema(name="missing_image_source", procedural={"image_textures": [{"role": "base_color"}]})
    with pytest.raises(ValidationError):
        MaterialSchema(
            name="bad_image_repeat",
            procedural={"image_textures": [{"generated": "checker_label", "repeat": [1.0, 0.0]}]},
        )


def test_camera_dof_requires_focus_target():
    with pytest.raises(ValidationError):
        CameraSchema(camera_name="c", lens={"dof": True})
    CameraSchema(camera_name="c", lens={"dof": True, "focus_target": "x"})


def test_animation_range_and_curve_alias():
    with pytest.raises(ValidationError):
        AnimationSchema(animation_name="a", frame_start=10, frame_end=5)
    a = AnimationSchema(animation_name="a",
                        curves={"rotation_z": {"from": 0, "to": 6.28, "interpolation": "linear"}})
    assert a.frame_count == 120
    assert a.curves["rotation_z"].from_value == 0
    fly = AnimationSchema(
        animation_name="fly",
        mode="scroll_linked",
        camera={"name": "camera_scroll", "start_location": [0, -7, 2], "end_location": [0, -3, 2.6]},
        params={"distance": 1.2},
    )
    assert fly.camera.end_location == [0, -3, 2.6]


def test_scroll_timeline_no_overlap():
    ScrollTimeline(segments=[{"from_scroll": 0, "to_scroll": 0.5,
                              "camera_from_frame": 1, "camera_to_frame": 40}])
    with pytest.raises(ValidationError):
        ScrollTimeline(segments=[
            {"from_scroll": 0, "to_scroll": 0.5, "camera_from_frame": 1, "camera_to_frame": 40},
            {"from_scroll": 0.3, "to_scroll": 0.6, "camera_from_frame": 41, "camera_to_frame": 90},
        ])


def test_vfx_particle_count_validation():
    VfxSchema(vfx_name="v", target="core", params={"particle_count": 100})
    with pytest.raises(ValidationError):
        VfxSchema(vfx_name="v", target="core", params={"particle_count": -5})


def test_lighting_geometry_post_rig_smoke():
    LightingSchema(lighting_rig="three_point_soft",
                   lights=[{"name": "key", "type": "AREA", "power": 100}])
    GeometryNodeSchema(node_group_name="GN_X", target_object="wall", inputs={"seed": 7})
    PostManifest(post_preset="cinematic_contrast")
    RigManifest(rig_name="r", controls=[{"name": "CTRL", "drives": ["a"]}])


def test_strict_extra_forbidden():
    with pytest.raises(ValidationError):
        MaterialSchema(name="m", preset="matte_plastic", bogus_field=1)


def test_geometry_seed_pulled_from_inputs():
    g = GeometryNodeSchema(node_group_name="GN_Bolts", target_object="x", inputs={"seed": 42})
    assert g.seed == 42
