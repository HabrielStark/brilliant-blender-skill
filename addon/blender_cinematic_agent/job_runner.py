"""Headless job entrypoint executed by Blender:

    blender -b --factory-startup -noaudio --python job_runner.py -- <job.json>

Reads the validated job dict, performs the action, writes the result JSON to
``job["result_path"]`` and prints ``BCAS_RESULT=<path>`` for the core runner.
The core has already validated everything; here we just execute and report.
"""
import json
import os
import sys
import traceback
from pathlib import Path

_ADDON_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_ADDON_DIR.parent))  # make `blender_cinematic_agent` importable

import bpy  # type: ignore

from blender_cinematic_agent import builders, bpyutil, exporter, renderer, scene_inspector


class WorkspaceResolver:
    """Small in-Blender path sandbox matching the core WorkspaceResolver contract."""

    def __init__(self, roots):
        self.roots = [Path(root).expanduser().resolve() for root in roots]
        if not self.roots:
            raise ValueError("WorkspaceResolver requires at least one root")

    def resolve(self, path):
        target = Path(path).expanduser()
        if not target.is_absolute():
            target = self.roots[0] / target
        target = target.resolve()
        for root in self.roots:
            if target == root or root in target.parents:
                return target
        raise ValueError(f"write path escapes workspace: {target}")

    def write_text(self, path, text, encoding="utf-8"):
        target = self.resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding=encoding)
        return target


def _job_path():
    argv = sys.argv
    return argv[argv.index("--") + 1] if "--" in argv else argv[-1]


def _clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def _initialize(job):
    _clear_scene()
    bpyutil.ensure_standard_collections()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    manifest = job.get("manifest") or {}
    scene["blender_cinematic_skill_version"] = "0.1"
    scene["task_id"] = manifest.get("task_id", "")
    scene["quality_profile"] = (job.get("budget") or {}).get("quality_profile",
                                                             manifest.get("quality_profile", "auto"))
    return {"collections": list(bpyutil.REQUIRED_COLLECTIONS)}


def _save(blend_path):
    os.makedirs(os.path.dirname(blend_path), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)


def _workspace_path(job, path):
    return str(WorkspaceResolver([job["workspace"]]).resolve(path))


def _write_json(job, path, data):
    return WorkspaceResolver([job["workspace"]]).write_text(
        path,
        json.dumps(data, indent=2),
        encoding="utf-8",
    )


def main():
    job = json.loads(Path(_job_path()).read_text(encoding="utf-8"))
    action = job["action"]
    blend_path = job["blend_path"]
    result = {"ok": True, "action": action, "blend_path": blend_path}
    try:
        opened = False
        if action != "initialize_blend" and action != "full_pipeline" and os.path.exists(blend_path):
            bpy.ops.wm.open_mainfile(filepath=blend_path)
            opened = True

        mutated = False
        if action in ("initialize_blend", "full_pipeline"):
            result.update(_initialize(job))
            mutated = True
        if action in ("apply_recipe", "full_pipeline"):
            result["operations"] = builders.apply_recipe(job.get("recipe") or {"operations": []})
            mutated = True
        if action == "inspect":
            result["inspection"] = scene_inspector.inspect_scene()
            out = (job.get("output") or {}).get("inspect")
            if out:
                inspect_path = _workspace_path(job, out)
                _write_json(job, inspect_path, result["inspection"])
                result["inspect_path"] = inspect_path
        if action in ("render_preview", "full_pipeline"):
            img = _workspace_path(
                job,
                (job.get("output") or {}).get("image") or os.path.join(job["workspace"], "iterations", "preview.png"),
            )
            render_opts = job.get("render") or {}
            result["render"] = renderer.render_still(img, job.get("budget") or {}, preview=True,
                                                      film_transparent=False,
                                                      frame=render_opts.get("frame"))
        if action == "render_final":
            img = _workspace_path(
                job,
                (job.get("output") or {}).get("image") or os.path.join(job["workspace"], "final", "render_final.png"),
            )
            render_opts = job.get("render") or {}
            result["render"] = renderer.render_still(img, job.get("budget") or {}, preview=False,
                                                      frame=render_opts.get("frame"))
        if action in ("export_glb", "full_pipeline"):
            glb = _workspace_path(
                job,
                (job.get("output") or {}).get("glb") or os.path.join(job["workspace"], "final", "export_final.glb"),
            )
            result["export"] = exporter.export_glb(glb, job.get("manifest"))

        if mutated or not opened or action in ("initialize_blend", "full_pipeline", "apply_recipe"):
            try:
                save_path = _workspace_path(job, blend_path)
                _save(save_path)
                result["saved"] = save_path
            except Exception as exc:  # saving is best-effort for read-only actions
                result["save_warning"] = str(exc)
    except Exception:
        result = {"ok": False, "action": action, "error": "job_exception",
                  "trace": traceback.format_exc()}

    rp = _workspace_path(job, job.get("result_path") or os.path.join(job["workspace"], "logs", "result.json"))
    _write_json(job, rp, result)
    print("BCAS_RESULT=" + rp)


if __name__ == "__main__":
    main()
