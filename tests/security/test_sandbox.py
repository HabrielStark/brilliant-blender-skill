"""Security tests: workspace path sandbox (SRS 18.2, 17.5)."""
import pytest

from blender_cinematic import runner
from blender_cinematic.workspace import PathSandboxError, WorkspaceResolver


def test_resolve_inside_ok(tmp_path):
    r = WorkspaceResolver([tmp_path])
    assert r.resolve(tmp_path / "a" / "b.txt").is_relative_to(tmp_path)


def test_traversal_rejected(tmp_path):
    r = WorkspaceResolver([tmp_path])
    with pytest.raises(PathSandboxError):
        r.resolve("../../../etc/passwd")


def test_absolute_outside_rejected(tmp_path):
    r = WorkspaceResolver([tmp_path])
    outside = tmp_path.parent / "outside.txt"
    with pytest.raises(PathSandboxError):
        r.resolve(outside)


def test_write_outside_rejected(tmp_path):
    r = WorkspaceResolver([tmp_path])
    with pytest.raises(PathSandboxError):
        r.write_text(tmp_path.parent / "escape.txt", "x")


def test_write_inside_ok(tmp_path):
    r = WorkspaceResolver([tmp_path])
    p = r.write_text(tmp_path / "sub" / "ok.txt", "hello")
    assert p.read_text() == "hello"


def test_is_within(tmp_path):
    r = WorkspaceResolver([tmp_path])
    assert r.is_within(tmp_path / "x")
    assert not r.is_within(tmp_path.parent / "y")


def test_build_job_rejects_mutating_blend_outside_workspace(tmp_path):
    with pytest.raises(PathSandboxError):
        runner.build_job("full_pipeline", tmp_path / "ws", tmp_path / "outside.blend")


def test_build_job_rejects_output_outside_workspace(tmp_path):
    ws = tmp_path / "ws"
    blend = ws / "scene.blend"
    with pytest.raises(PathSandboxError):
        runner.build_job("render_preview", ws, blend, output={"image": tmp_path / "escape.png"})


def test_package_skill_rejects_absolute_output_outside_workspace(tmp_path, monkeypatch):
    import scripts.package_skill as package_skill

    monkeypatch.setattr(package_skill, "ROOT", tmp_path)
    with pytest.raises(PathSandboxError):
        package_skill.main(["--out", str(tmp_path.parent / "escape")])
