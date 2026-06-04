"""MCP resources (SRS 12.5).

Exposes the reference playbooks as ``docs://`` resources and per-task artifacts
(manifest, hardware report, inspection, final report) as templated ``project://``
/ ``blender://`` resources read from the workspace sandbox.
"""
from __future__ import annotations

from pathlib import Path

from .security import ServerContext

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REFS = _REPO_ROOT / "references"

_DOC_RESOURCES = {
    "camera-language": "camera-language.md",
    "visual-critique-rubric": "visual-critique-rubric.md",
    "lighting-materials": "lighting-materials.md",
    "hardware-quality-profiles": "hardware-quality-profiles.md",
    "web-export-threejs-r3f": "web-export-threejs-r3f.md",
    "failure-modes": "failure-modes.md",
}


def register_resources(mcp, ctx: ServerContext) -> None:
    def _read(path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else f"(missing: {path.name})"

    for key, fname in _DOC_RESOURCES.items():
        def make(fn=fname):
            def res() -> str:
                return _read(_REFS / fn)
            return res
        fn_obj = make()
        fn_obj.__name__ = f"doc_{key.replace('-', '_')}"
        mcp.resource(f"docs://{key}", name=key, mime_type="text/markdown")(fn_obj)

    @mcp.resource("project://{task_id}/scene_manifest.json", mime_type="application/json")
    def scene_manifest(task_id: str) -> str:
        return _read(ctx.task_dir(task_id) / "scene_manifest.json")

    @mcp.resource("project://{task_id}/final_report.md", mime_type="text/markdown")
    def final_report(task_id: str) -> str:
        return _read(ctx.task_dir(task_id) / "final" / "final_report.md")

    @mcp.resource("blender://{task_id}/hardware_report.json", mime_type="application/json")
    def hardware_report(task_id: str) -> str:
        return _read(ctx.task_dir(task_id) / "hardware_report.json")

    @mcp.resource("blender://{task_id}/current_scene.json", mime_type="application/json")
    def current_scene(task_id: str) -> str:
        return _read(ctx.task_dir(task_id) / "iterations" / "inspect.json")
