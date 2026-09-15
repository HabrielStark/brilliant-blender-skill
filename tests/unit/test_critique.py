"""Unit tests for the critique layer (diagnose → suggested ops)."""
import numpy as np
from PIL import Image

from blender_cinematic.critique import diagnose
from blender_cinematic.recipes import validate_recipe


def _inspection(objects=(), materials=(), world=None, camera=True):
    return {
        "objects": list(objects),
        "materials": list(materials),
        "world": world,
        "active_camera": {"name": "cam"} if camera else None,
    }


def _subject(name, in_frame=True, coverage=0.3, loc=(0, 0, 0), bbox=None,
             dims=(1, 1, 1)):
    return {
        "name": name, "collection": "SUBJECT", "in_camera_frame": in_frame,
        "screen_coverage": coverage, "world_location": list(loc),
        "screen_bbox": bbox, "dimensions": list(dims),
    }


def _save(path, luma_value, size=(64, 64)):
    arr = np.full((*size, 4), luma_value, dtype=np.uint8)
    arr[..., 3] = 255
    Image.fromarray(arr, "RGBA").save(path)


def _save_gradient(path, dark_left=True, size=(64, 64)):
    w, h = size
    cols = np.linspace(10, 200, w, dtype=np.uint8)
    arr = np.tile(cols, (h, 1))
    if not dark_left:
        arr = np.fliplr(arr)
    rgba = np.stack([arr, arr, arr, np.full_like(arr, 255)], axis=-1)
    Image.fromarray(rgba, "RGBA").save(path)


def test_crushed_blacks_diagnosis_suggests_world_lift():
    img = {"pct_near_black": 0.8, "pct_near_white": 0.0,
           "edge_density": 0.005, "contrast": 0.03}
    diags = diagnose(_inspection(objects=[_subject("hero")]), image_metrics=img)
    top = diags[0]
    assert top["code"] == "tonal.crushed_blacks" and top["severity"] == "fail"
    assert any(o["op"] == "adjust_world" for o in top["ops"])


def test_offscreen_subjects_reframe_at_visible_centroid():
    objs = [
        _subject("hero", in_frame=True, loc=(0, 0, 0)),
        _subject("scatter", in_frame=False, loc=(20, 0, 0)),
        _subject("accent", in_frame=True, loc=(2, 0, 0)),
    ]
    diags = diagnose(_inspection(objects=objs))
    d = next(x for x in diags if x["code"] == "framing.offscreen_subjects")
    op = next(o for o in d["ops"] if o["op"] == "reframe_camera")
    # centroid of the two *visible* subjects, not all three
    assert op["look_at"][0] == 1.0


def test_metal_void_material_flagged():
    mats = [{"name": "body", "metallic": 1.0, "base_color": [0.02, 0.02, 0.03],
             "roughness": 0.2}]
    diags = diagnose(_inspection(objects=[_subject("hero")], materials=mats,
                                 world={"strength": 0.2}))
    d = next(x for x in diags if x["code"] == "material.metal_void")
    assert any(o["op"] == "adjust_material" and o.get("material") == "body"
               for o in d["ops"])


def test_bright_world_no_metal_void():
    mats = [{"name": "body", "metallic": 1.0, "base_color": [0.02, 0.02, 0.03],
             "roughness": 0.2}]
    diags = diagnose(_inspection(objects=[_subject("hero")], materials=mats,
                                 world={"strength": 1.5}))
    assert not any(x["code"] == "material.metal_void" for x in diags)


def test_unreadable_part_gets_aimed_light():
    rep = {"parts": [{"name": "groove_cut", "readable": False}],
           "unreadable_parts": ["groove_cut"]}
    objs = [_subject("groove_cut", loc=(1, 0, 0.5),
                     bbox=[0.4, 0.4, 0.5, 0.6])]
    diags = diagnose(_inspection(objects=objs), readability_report=rep)
    d = next(x for x in diags if x["code"] == "part.unreadable")
    light = next(o for o in d["ops"] if o["op"] == "add_light")
    assert light["schema"]["look_at"] == [1, 0, 0.5]


def test_reference_brightness_direction_darker(tmp_path):
    ours = tmp_path / "ours.png"
    ref = tmp_path / "ref.png"
    _save(ours, 40)
    _save(ref, 140)
    diags = diagnose(_inspection(objects=[_subject("hero")]),
                     render_path=ours, reference_path=ref)
    d = next(x for x in diags if x["code"] == "ref.brightness")
    op = next(o for o in d["ops"] if o["op"] == "adjust_world")
    assert op["strength_scale"] > 1.0  # we're darker → scale up
    assert "darker" in d["problem"]


def test_reference_brightness_direction_brighter(tmp_path):
    ours = tmp_path / "ours.png"
    ref = tmp_path / "ref.png"
    _save(ours, 200)
    _save(ref, 80)
    diags = diagnose(_inspection(objects=[_subject("hero")]),
                     render_path=ours, reference_path=ref)
    d = next(x for x in diags if x["code"] == "ref.brightness")
    op = next(o for o in d["ops"] if o["op"] == "adjust_world")
    assert op["strength_scale"] < 1.0
    assert "brighter" in d["problem"]


def test_saliency_centroid_shift_direction(tmp_path):
    # ours: bright blob on the right half; ref: bright blob on the left
    ours = tmp_path / "ours.png"
    ref = tmp_path / "ref.png"
    _save_gradient(ours, dark_left=True)   # bright on right
    _save_gradient(ref, dark_left=False)   # bright on left
    diags = diagnose(_inspection(objects=[_subject("hero")]),
                     render_path=ours, reference_path=ref)
    d = next(x for x in diags if x["code"] == "ref.saliency_center")
    assert "left" in d["problem"]


def test_saliency_centroid_emits_reframe_op(tmp_path):
    """With camera pose in the inspection, the centroid diagnosis must emit a
    concrete reframe_camera op that moves look_at toward the needed shift."""
    ours = tmp_path / "ours.png"
    ref = tmp_path / "ref.png"
    _save_gradient(ours, dark_left=True)   # our saliency on the right
    _save_gradient(ref, dark_left=False)   # ref saliency on the left
    insp = _inspection(objects=[_subject("hero", loc=(0, 0, 0.5))])
    # camera at (0,-6,0.5) looking straight +Y at the subject: rotation (pi/2,0,0)
    import math
    insp["active_camera"] = {"name": "cam", "lens_mm": 50,
                             "sensor_width": 36,
                             "location": [0, -6, 0.5],
                             "rotation": [math.pi / 2, 0, 0]}
    diags = diagnose(insp, render_path=ours, reference_path=ref)
    d = next(x for x in diags if x["code"] == "ref.saliency_center")
    op = next(o for o in d["ops"] if o["op"] == "reframe_camera")
    # our centroid is right of the ref's -> aim must shift toward camera-right.
    # camera right with rotation (pi/2,0,0) = world +X.
    assert op["look_at"][0] > 0.0
    res = validate_recipe({"operations": [op]})
    assert res.passed


def test_diagnose_returns_empty_for_healthy_scene():
    img = {"pct_near_black": 0.1, "pct_near_white": 0.05,
           "edge_density": 0.05, "contrast": 0.1}
    objs = [
        _subject("hero"), _subject("accent", loc=(1, 0, 0)),
        {"name": "ground", "collection": "ENVIRONMENT",
         "in_camera_frame": True, "world_location": [0, 0, -1]},
    ]
    diags = diagnose(_inspection(objects=objs), image_metrics=img)
    assert diags == []


def test_sparse_scene_flagged_as_generic():
    objs = [_subject("hero")]
    diags = diagnose(_inspection(objects=objs))
    codes = {d["code"] for d in diags}
    assert "composition.no_environment" in codes
    assert "composition.too_sparse" in codes
    d = next(x for x in diags if x["code"] == "composition.no_environment")
    assert any(o["op"] == "create_mesh_primitive" for o in d["ops"])


def test_adjust_light_and_material_validate():
    r = {"operations": [
        {"op": "adjust_light", "name": "key", "power_scale": 0.5,
         "look_at": [0, 0, 1]},
        {"op": "adjust_material", "material": "body",
         "pbr": {"metallic": 0.7, "roughness": 0.35}},
    ]}
    assert validate_recipe(r).passed


def test_adjust_light_requires_name():
    r = {"operations": [{"op": "adjust_light", "power": 500}]}
    res = validate_recipe(r)
    assert not res.passed


def test_edge_crowding_flagged():
    objs = [_subject("hero", bbox=[0.6, 0.2, 1.0, 0.8])]  # maxx touches edge
    diags = diagnose(_inspection(objects=objs))
    d = next((x for x in diags if x["code"] == "framing.edge_crowding"), None)
    assert d and d["severity"] == "warn"
    assert any(o["op"] == "reframe_camera" for o in d["ops"])


def test_dead_side_detected(tmp_path):
    # right third black, rest lit
    arr = np.full((64, 96, 4), 120, dtype=np.uint8)
    arr[:, 64:, :3] = 4
    arr[..., 3] = 255
    p = tmp_path / "unbalanced.png"
    Image.fromarray(arr, "RGBA").save(p)
    diags = diagnose(_inspection(objects=[_subject("hero", loc=(0, 0, 0.5))]),
                     render_path=p)
    assert any(d["code"] == "composition.dead_side" and "right" in d["problem"]
               for d in diags)


def test_buried_object_lifts_onto_host():
    # cup centre inside the table's bbox — invisible in the render
    objs = [
        _subject("table", loc=(0, 0, 0.4), dims=(1.6, 1.6, 2.0)),
        _subject("cup", loc=(0.3, 0, 1.0), dims=(0.25, 0.25, 0.3)),
    ]
    diags = diagnose(_inspection(objects=objs))
    d = next(x for x in diags if x["code"] == "geometry.buried_object")
    op = d["ops"][0]
    assert op["op"] == "set_object_transform" and op["target"] == "cup"
    # host top = 0.4 + 1.0 = 1.4; cup half-height 0.15 -> 1.55 + epsilon
    assert abs(op["location"][2] - 1.56) < 1e-6
    assert validate_recipe({"operations": [op]}).passed


def test_completeness_missing_and_offscreen_parts():
    manifest = {"success_criteria": {"required_parts": ["hero", "lantern"]}}
    objs = [
        _subject("hero_body", in_frame=True),
        _subject("lantern_prop", in_frame=False, loc=(9, 0, 0)),
    ]
    diags = diagnose(_inspection(objects=objs), manifest=manifest)
    codes = [d["code"] for d in diags]
    assert "completeness.part_offscreen" in codes
    d = next(x for x in diags if x["code"] == "completeness.part_offscreen")
    assert "lantern" in d["problem"]
    assert any(o["op"] == "reframe_camera" for o in d["ops"])
    # now a part that doesn't exist at all
    diags = diagnose(_inspection(objects=[_subject("hero_body")]),
                     manifest=manifest)
    d = next(x for x in diags if x["code"] == "completeness.part_missing")
    assert "lantern" in d["problem"]


def test_buried_object_ignores_nested_assembly_parts():
    """Watch anatomy is nested by design: hour markers sit inside the bezel
    ring's bbox (a ring's bbox contains its hole), dial glass is seated in the
    case. Bbox containment alone must not flag these — a repair that lifts
    markers off the dial would destroy the watch."""
    bezel = _subject("watch_bezel_ring", loc=(0, 0, 0.55),
                     dims=(2.72, 2.72, 0.41))
    case = _subject("watch_case_beveled", loc=(0, 0, 0.4),
                    dims=(2.2, 2.2, 0.62))
    # marker flush with the bezel's top face, mounted on the dial
    marker = _subject("dial_hour_marker_04", loc=(0.72, 0, 0.7405),
                      dims=(0.06, 0.12, 0.025))
    # glass inside the ring hole, bottom seated inside the case body
    glass = _subject("watch_dial_glass", loc=(0, 0, 0.68),
                     dims=(1.82, 1.82, 0.064))
    diags = diagnose(_inspection(objects=[bezel, case, marker, glass]))
    assert not any(d["code"] == "geometry.buried_object" for d in diags)


def test_completeness_missing_part_emits_scaffold_op():
    """A missing required part must produce an actionable scaffold, not just
    advice — otherwise the mechanical loop stalls on 'build it'."""
    manifest = {"success_criteria": {"required_parts": ["mug"]}}
    host = _subject("desk_top", loc=(0, 0, 0.75), dims=(2.8, 1.4, 0.1))
    diags = diagnose(_inspection(objects=[host]), manifest=manifest)
    d = next(x for x in diags if x["code"] == "completeness.part_missing")
    assert d["severity"] == "fail"
    op = next((o for o in d["ops"] if o["op"] == "create_mesh_primitive"), None)
    assert op is not None and op["name"] == "mug_scaffold"
    assert op["collection"] == "SUBJECT"
    # lands on the host's top surface, not floating or buried
    assert op["location"][2] > 0.75
    issues = validate_recipe({"operations": [op]}).issues
    assert not [i for i in issues if i.severity == "error"]


def test_completeness_scaffolds_spread_across_host():
    manifest = {"success_criteria": {"required_parts": ["mug", "books"]}}
    host = _subject("desk_top", loc=(0, 0, 0.75), dims=(2.8, 1.4, 0.1))
    diags = diagnose(_inspection(objects=[host]), manifest=manifest)
    ops = [d["ops"][0] for d in diags
           if d["code"] == "completeness.part_missing"]
    assert len(ops) == 2
    xs = sorted(o["location"][0] for o in ops)
    assert xs[1] - xs[0] > 0.1  # not stacked on each other


def test_completeness_bare_primitive_placeholder_warn():
    manifest = {"success_criteria": {"required_parts": ["mug"]}}
    bare = {**_subject("mug_body"), "type": "MESH", "faces": 6,
            "modifiers": []}
    diags = diagnose(_inspection(objects=[bare]), manifest=manifest)
    d = next((x for x in diags
              if x["code"] == "completeness.part_is_placeholder"), None)
    assert d is not None and d["severity"] == "warn"
    # a developed part (bevel modifier, more faces) does not warn
    developed = {**_subject("mug_body"), "type": "MESH", "faces": 420,
                 "modifiers": [{"type": "BEVEL"}]}
    diags = diagnose(_inspection(objects=[developed]), manifest=manifest)
    assert not any(x["code"] == "completeness.part_is_placeholder"
                   for x in diags)


def test_completeness_alias_match():
    manifest = {"success_criteria": {"required_parts": ["marker"]}}
    objs = [_subject("dial_hash_marks")]  # 'hash' is a marker alias
    diags = diagnose(_inspection(objects=objs), manifest=manifest)
    assert not any(d["code"].startswith("completeness.") for d in diags)


def test_no_manifest_no_completeness_noise():
    diags = diagnose(_inspection(objects=[_subject("hero")]))
    assert not any(d["code"].startswith("completeness.part") for d in diags)


def test_lint_driven_diagnoses_for_broken_scene():
    """The worst-case input (baseline-style: no camera, no lights, no
    materials) must still produce concrete build-out ops — this is where a
    weak agent needs the most guidance."""
    from blender_cinematic.linters import lint_scene
    from blender_cinematic.results import CheckResult, error
    lint = CheckResult("scene")
    lint.add(error("camera.none", "no active camera in scene"))
    lint.add(error("lighting.none", "no meaningful lighting"))
    lint.add(error("material.missing", "important object has no material: Cube",
                   "Cube"))
    lint.add(error("material.missing", "important object has no material: Sphere",
                   "Sphere"))
    objs = [{"name": "Cube", "collection": "SUBJECT", "in_camera_frame": False,
             "world_location": [0, 0, 0.5], "screen_coverage": 0}]
    diags = diagnose(_inspection(objects=objs), lint=lint)
    codes = {d["code"] for d in diags}
    assert {"fix.no_camera", "fix.no_lighting", "fix.no_material"} <= codes
    # every object with a missing material gets its own fix, not just the first
    mat_fixes = [d for d in diags if d["code"] == "fix.no_material"]
    assert len(mat_fixes) == 2
    for d in diags:
        res = validate_recipe({"operations": d["ops"]})
        assert res.passed, (d["code"], [i.message for i in res.issues])


def test_lint_accepts_real_lint_scene_output():
    """diagnose() must accept the CheckResult lint_scene actually returns."""
    from blender_cinematic.linters import lint_scene
    inspection = {"objects": [], "collections": [], "materials": [],
                  "lights": [], "active_camera": None}
    lint = lint_scene(inspection, {"output_mode": "still"})
    diags = diagnose(inspection, lint=lint)
    assert any(d["code"] == "fix.no_camera" for d in diags)


def test_adjust_material_warns_on_unknown_param():
    r = {"operations": [{"op": "adjust_material", "material": "m",
                         "bogus": 1}]}
    res = validate_recipe(r)
    assert res.passed  # warnings don't fail; the unknown param is flagged
    assert any("unknown param" in i.message for i in res.warnings)


def _anim_inspection(keyframed=("a",), sampled=None, cam_animated=False):
    insp = _inspection(objects=[_subject("a"), _subject("b")])
    insp["animation"] = {
        "has_action": bool(keyframed), "frame_start": 1, "frame_end": 48,
        "fps": 24, "keyframed_objects": list(keyframed),
        "camera_animated": cam_animated,
        "sampled_objects": sampled if sampled is not None else [
            {"name": n, "max_location_delta": 0.5,
             "max_rotation_delta": 3.0} for n in keyframed],
    }
    return insp


_ANIM_MANIFEST = {"output_mode": "animation",
                  "target": {"final_format": ["mp4"]}}


def test_animation_missing_fails_when_manifest_requires_motion():
    """output_mode=animation + zero keyframes must be a hard fail — the
    animation op was never applied."""
    insp = _anim_inspection(keyframed=())
    insp["animation"]["sampled_objects"] = []
    diags = diagnose(insp, manifest=_ANIM_MANIFEST)
    miss = [d for d in diags if d["code"] == "animation.missing"]
    assert miss and miss[0]["severity"] == "fail"
    # the suggested op must be a real, schema-valid recipe op
    res = validate_recipe({"operations": miss[0]["ops"]})
    assert res.passed, [i.message for i in res.issues]
    schema = miss[0]["ops"][0]["schema"]
    assert set(schema["targets"]) == {"a", "b"}


def test_animation_static_fails_when_keyframes_move_nothing():
    """Keyframes exist but every sampled object is frozen — broken curves
    must not pass the mechanical floor."""
    insp = _anim_inspection(sampled=[
        {"name": "a", "max_location_delta": 0.0, "max_rotation_delta": 0.001}])
    diags = diagnose(insp, manifest=_ANIM_MANIFEST)
    assert any(d["code"] == "animation.static" and d["severity"] == "fail"
               for d in diags)


def test_animation_partially_static_warns_on_dead_keys():
    insp = _anim_inspection(keyframed=("a", "b"), sampled=[
        {"name": "a", "max_location_delta": 1.0, "max_rotation_delta": 0.0},
        {"name": "b", "max_location_delta": 0.0, "max_rotation_delta": 0.0}])
    diags = diagnose(insp, manifest=_ANIM_MANIFEST)
    assert any(d["code"] == "animation.partially_static"
               and d["severity"] == "warn" for d in diags)
    assert not any(d["code"] == "animation.static" for d in diags)


def test_animation_ok_when_objects_move():
    insp = _anim_inspection()
    diags = diagnose(insp, manifest=_ANIM_MANIFEST)
    assert not any(d["code"].startswith("animation.") for d in diags)


def test_animation_checks_silent_for_still_manifests():
    """A still scene must not get animation diagnoses even with keys present."""
    insp = _anim_inspection(keyframed=())
    insp["animation"]["sampled_objects"] = []
    diags = diagnose(insp, manifest={"output_mode": "still"})
    assert not any(d["code"].startswith("animation.") for d in diags)


def test_animation_reveal_visibility_counts_as_motion():
    """reveal-mode animations keyframe hide_render, not transforms — a pure
    visibility toggle must NOT read as a frozen animation."""
    insp = _anim_inspection(sampled=[
        {"name": "a", "max_location_delta": 0.0, "max_rotation_delta": 0.0,
         "max_scale_delta": 0.0, "visibility_changes": True,
         "max_energy_delta": 0.0}])
    diags = diagnose(insp, manifest=_ANIM_MANIFEST)
    assert not any(d["code"] == "animation.static" for d in diags)


def test_animation_light_pulse_energy_counts_as_motion():
    """light_pulse keys data.energy — energy deltas must count as motion."""
    insp = _anim_inspection(sampled=[
        {"name": "key_l", "max_location_delta": 0.0, "max_rotation_delta": 0.0,
         "max_scale_delta": 0.0, "visibility_changes": False,
         "max_energy_delta": 900.0}])
    diags = diagnose(insp, manifest=_ANIM_MANIFEST)
    assert not any(d["code"] == "animation.static" for d in diags)
