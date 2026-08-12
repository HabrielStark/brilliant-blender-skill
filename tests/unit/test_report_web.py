"""Unit tests for report writer + web codegen + pure-Python GLB validator."""
import json
import struct

import pytest

from blender_cinematic.glb import validate_glb
from blender_cinematic.report import build_final_report
from blender_cinematic.webgen import (
    camera_path_json,
    densify_camera_samples,
    generate_integration,
    r3f_scroll_component,
)


def test_report_from_artifacts(tmp_path):
    base = tmp_path / "task"
    (base / "iterations").mkdir(parents=True)
    (base / "final").mkdir(parents=True)
    (base / "scene_manifest.json").write_text(json.dumps(
        {"task_id": "t", "brief": "b", "output_mode": "still"}))
    (base / "iterations" / "iter_01_eval.json").write_text(json.dumps(
        {"iteration": 1, "passed": True, "hard_fail": False,
         "scores": {"total": 88}, "next_actions": []}))
    (base / "iterations" / "iter_01_preview.png").write_bytes(b"\x89PNG")
    (base / "final" / "render_final.png").write_bytes(b"\x89PNG")
    md, report = build_final_report(base)
    assert report["passed"] is True
    assert report["best_score"] == 88
    assert report["acceptance"]["has_preview"] is True
    assert report["acceptance"]["has_render"] is True
    assert "Status:** PASS" in md


def test_report_does_not_treat_final_blend_as_render(tmp_path):
    base = tmp_path / "task"
    (base / "iterations").mkdir(parents=True)
    (base / "final").mkdir(parents=True)
    (base / "scene_manifest.json").write_text(json.dumps(
        {"task_id": "t", "brief": "b", "output_mode": "still"}))
    (base / "iterations" / "iter_01_eval.json").write_text(json.dumps(
        {"iteration": 1, "passed": True, "hard_fail": False,
         "scores": {"total": 88}, "next_actions": []}))
    (base / "final" / "scene.blend").write_bytes(b"blend")

    _, report = build_final_report(base)

    assert report["acceptance"]["has_render"] is False
    assert report["passed"] is False
    assert "final render artifact missing" in report["failures"]


def test_report_requires_preview_for_pass(tmp_path):
    base = tmp_path / "task"
    (base / "iterations").mkdir(parents=True)
    (base / "final").mkdir(parents=True)
    (base / "scene_manifest.json").write_text(json.dumps(
        {"task_id": "t", "brief": "b", "output_mode": "still"}))
    (base / "iterations" / "iter_01_eval.json").write_text(json.dumps(
        {"iteration": 1, "passed": True, "hard_fail": False,
         "scores": {"total": 88}, "next_actions": []}))
    (base / "final" / "render_final.png").write_bytes(b"\x89PNG")

    _, report = build_final_report(base)

    assert report["acceptance"]["has_preview"] is False
    assert report["passed"] is False
    assert "preview artifact missing" in report["failures"]


def test_latest_failed_iteration_overrides_older_pass(tmp_path):
    base = tmp_path / "task"
    (base / "iterations").mkdir(parents=True)
    (base / "final").mkdir(parents=True)
    (base / "scene_manifest.json").write_text(json.dumps(
        {"task_id": "t", "brief": "b", "output_mode": "still"}))
    (base / "iterations" / "iter_01_eval.json").write_text(json.dumps(
        {"iteration": 1, "passed": True, "hard_fail": False,
         "scores": {"total": 90}, "next_actions": []}))
    (base / "iterations" / "iter_02_eval.json").write_text(json.dumps(
        {"iteration": 2, "passed": False, "hard_fail": True,
         "scores": {"total": 95}, "hard_fail_reasons": ["subject cropped"]}))
    (base / "iterations" / "iter_02_preview.png").write_bytes(b"\x89PNG")
    (base / "final" / "render_final.png").write_bytes(b"\x89PNG")

    _, report = build_final_report(base)

    assert report["latest_iteration"] == 2
    assert report["best_score"] == 95
    assert report["passed"] is False
    assert "latest iteration 2 did not pass" in report["failures"]


def test_web_report_requires_validation_even_with_glb(tmp_path):
    base = tmp_path / "task"
    (base / "iterations").mkdir(parents=True)
    (base / "final").mkdir(parents=True)
    (base / "scene_manifest.json").write_text(json.dumps(
        {"task_id": "t", "brief": "b", "output_mode": "web_asset",
         "target": {"final_format": ["glb"]}}))
    (base / "iterations" / "iter_01_eval.json").write_text(json.dumps(
        {"iteration": 1, "passed": True, "hard_fail": False,
         "scores": {"total": 88}, "next_actions": []}))
    (base / "iterations" / "iter_01_preview.png").write_bytes(b"\x89PNG")
    (base / "final" / "render_final.png").write_bytes(b"\x89PNG")
    (base / "final" / "export_final.glb").write_bytes(b"glTF")

    _, report = build_final_report(base)

    assert report["passed"] is False
    assert any("GLB validation failed" in failure for failure in report["failures"])


def test_report_flags_missing_glb(tmp_path):
    base = tmp_path / "task"
    (base / "iterations").mkdir(parents=True)
    (base / "scene_manifest.json").write_text(json.dumps(
        {"task_id": "t", "brief": "b", "output_mode": "web_asset",
         "target": {"final_format": ["glb"]}}))
    _, report = build_final_report(base)
    assert any("no GLB" in f for f in report["failures"])


def test_webgen_writes_files(tmp_path):
    segs = [{"from_scroll": 0, "to_scroll": 1, "camera_from_frame": 1, "camera_to_frame": 40}]
    written = generate_integration(tmp_path, glb_name="scene.glb",
                                   runtime="react-three-fiber",
                                   scroll_segments=segs,
                                   scroll_samples=[{"position": [0, 0, 4]},
                                                   {"position": [4, -4, 5]}])
    assert set(written) == {"threejs_html", "r3f_component", "camera_path", "r3f_scroll", "gsap_scroll"}
    assert all(str(tmp_path) in path for path in written.values())
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "Scene.jsx").exists()
    assert (tmp_path / "camera_path.json").exists()
    assert "ScrollControls" in r3f_scroll_component()
    assert camera_path_json(segs)["schema"] == "camera_path/0.1"
    path = json.loads((tmp_path / "camera_path.json").read_text(encoding="utf-8"))
    assert len(path["samples"]) >= 9


def test_camera_path_samples_are_densified():
    dense = densify_camera_samples([
        {"position": [0, 0, 4], "target": [0, 0, 0]},
        {"position": [4, -4, 5], "target": [0, 0, 1]},
    ], steps_per_segment=4)
    assert len(dense) == 5
    assert dense[0]["position"] == [0.0, 0.0, 4.0]
    assert dense[-1]["position"] == [4, -4, 5]
    assert dense[2]["position"][0] == 2.0


def test_webgen_rejects_code_injection_asset_names(tmp_path):
    with pytest.raises(ValueError):
        generate_integration(tmp_path, glb_name="scene.glb');window.__pwned=1;//")


def test_webgen_escapes_asset_names_in_code(tmp_path):
    written = generate_integration(tmp_path, glb_name="models/scene.glb")
    html = (tmp_path / "index.html").read_text(encoding="utf-8")
    jsx = (tmp_path / "Scene.jsx").read_text(encoding="utf-8")
    assert "GLTFLoader().load(\"models/scene.glb\"" in html
    assert "useGLTF(\"/models/scene.glb\")" in jsx
    assert written["threejs_html"].endswith("index.html")


def _make_glb(path, gltf: dict, bin_len: int = 0):
    js = json.dumps(gltf).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js
    if bin_len:
        body += struct.pack("<II", bin_len, 0x004E4942) + b"\x00" * bin_len
    header = struct.pack("<III", 0x46546C67, 2, 12 + len(body))
    path.write_bytes(header + body)


def test_glb_valid(tmp_path):
    p = tmp_path / "ok.glb"
    _make_glb(p, {"asset": {"version": "2.0", "generator": "test"},
                  "nodes": [{"mesh": 0}], "meshes": [{"primitives": []}],
                  "materials": [{}]}, bin_len=16)
    res = validate_glb(p, max_mb=20)
    assert res["ok"]
    assert res["info"]["nodes"] == 1


def test_glb_empty_and_external_texture(tmp_path):
    empty = tmp_path / "empty.glb"
    _make_glb(empty, {"asset": {"version": "2.0"}})
    assert not validate_glb(empty)["ok"]

    ext = tmp_path / "ext.glb"
    _make_glb(ext, {"asset": {"version": "2.0"}, "nodes": [{}],
                    "images": [{"uri": "texture.png"}]})
    res = validate_glb(ext)
    assert not res["ok"]
    assert any("external" in e for e in res["errors"])


def test_glb_over_budget(tmp_path):
    p = tmp_path / "big.glb"
    _make_glb(p, {"asset": {"version": "2.0"}, "nodes": [{}]}, bin_len=2048)
    assert not validate_glb(p, max_mb=0.0001)["ok"]


def test_glb_rejects_truncated_chunk_header(tmp_path):
    p = tmp_path / "truncated-header.glb"
    trailing = b"\x00\x00\x00\x00"
    p.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(trailing)) + trailing)

    res = validate_glb(p)

    assert res["ok"] is False
    assert "truncated GLB chunk header" in res["errors"][0]


def test_glb_rejects_chunk_payload_shorter_than_declared_length(tmp_path):
    p = tmp_path / "truncated-payload.glb"
    payload = b'{}  '
    chunk = struct.pack("<II", len(payload) + 4, 0x4E4F534A) + payload
    p.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk)

    res = validate_glb(p)

    assert res["ok"] is False
    assert "truncated GLB chunk" in res["errors"][0]


def test_glb_rejects_unaligned_chunk_length(tmp_path):
    p = tmp_path / "unaligned-chunk.glb"
    payload = b"{} "
    chunk = struct.pack("<II", len(payload), 0x4E4F534A) + payload
    p.write_bytes(struct.pack("<III", 0x46546C67, 2, 12 + len(chunk)) + chunk)

    res = validate_glb(p)

    assert res["ok"] is False
    assert "unaligned length" in res["errors"][0]
