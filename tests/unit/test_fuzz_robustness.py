"""Fuzz / robustness: malformed and random inputs must not crash (SRS 17.5)."""
import random
import struct

import pytest

from blender_cinematic.glb import validate_glb
from blender_cinematic.linters import lint_scene
from blender_cinematic.recipes import estimate_complexity, validate_recipe
from blender_cinematic.security import scan_python_source


@pytest.mark.parametrize("seed", range(25))
def test_recipe_validator_never_crashes(seed):
    rnd = random.Random(seed)  # nosec B311
    junk = {"operations": [
        {"op": rnd.choice(["create_mesh_primitive", "x", "", "add_modifier"]),
         rnd.choice(["type", "name", "k", "modifier"]): rnd.choice(["cube", 1, None, [1, 2], {"a": 1}])}
        for _ in range(rnd.randint(0, 5))
    ]}
    res = validate_recipe(junk)        # must return a CheckResult, not raise
    assert hasattr(res, "passed")
    estimate_complexity(junk)          # must not raise


@pytest.mark.parametrize("seed", range(15))
def test_lint_scene_handles_partial_inspection(seed):
    rnd = random.Random(seed)  # nosec B311
    keys = ["collections", "objects", "active_camera", "lights", "materials",
            "animation", "render", "metadata", "geometry_nodes", "particles"]
    insp = {k: rnd.choice([[], {}, None, [{"name": "x"}]]) for k in keys if rnd.random() > 0.4}
    lint_scene(insp, manifest={"output_mode": rnd.choice(["still", "web_asset", None])})


def test_glb_parser_rejects_garbage(tmp_path):
    for i in range(20):
        p = tmp_path / f"junk{i}.glb"
        rnd = random.Random(i)  # nosec B311
        p.write_bytes(bytes(rnd.randbytes(rnd.randint(0, 64))))
        res = validate_glb(p)             # must not raise
        assert res["ok"] is False


def test_glb_parser_truncated_chunks(tmp_path):
    p = tmp_path / "trunc.glb"
    p.write_bytes(struct.pack("<III", 0x46546C67, 2, 9999))  # header claims a length it lacks
    assert validate_glb(p)["ok"] is False


def test_scanner_handles_weird_source():
    for src in ["", "@@@", "def (:", "import os" * 1000, "x = " + "(" * 500]:
        scan_python_source(src)  # must not raise (returns issues or syntax error issue)
