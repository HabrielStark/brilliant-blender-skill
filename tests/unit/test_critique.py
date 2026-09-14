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


def _subject(name, in_frame=True, coverage=0.3, loc=(0, 0, 0), bbox=None):
    return {
        "name": name, "collection": "SUBJECT", "in_camera_frame": in_frame,
        "screen_coverage": coverage, "world_location": list(loc),
        "screen_bbox": bbox,
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
    objs = [{"name": "Cube", "collection": "SUBJECT", "in_camera_frame": False,
             "world_location": [0, 0, 0.5], "screen_coverage": 0}]
    diags = diagnose(_inspection(objects=objs), lint=lint)
    codes = {d["code"] for d in diags}
    assert {"fix.no_camera", "fix.no_lighting", "fix.no_material"} <= codes
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
