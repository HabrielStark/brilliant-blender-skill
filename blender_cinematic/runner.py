"""Headless Blender job orchestration (core side, no ``bpy``).

The runner builds a *validated* job dict and invokes Blender in background mode
with the add-on's ``job_runner.py``. Everything Blender does is driven by plain,
already-validated dicts — the in-Blender code never imports pydantic (Blender's
bundled Python does not ship it). Results come back as JSON on disk.

This is the path the MCP server and ``scripts/run_blender_job.py`` use for CI /
headless work; the socket bridge in the add-on is the interactive alternative.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from .blender import locate_blender
from .security import run_checked
from .workspace import WorkspaceResolver

ACTIONS = (
    "initialize_blend", "apply_recipe", "inspect", "render_preview",
    "render_final", "export_glb", "full_pipeline",
)

_RESULT_SENTINEL = "BCAS_RESULT="
_MUTATING_ACTIONS = {"initialize_blend", "apply_recipe", "full_pipeline"}
_OUTPUT_PATH_KEYS = {"image", "glb", "inspect"}


def _addon_job_runner() -> Path:
    override = os.environ.get("BCAS_ADDON_DIR")
    if override:
        return Path(override) / "job_runner.py"
    return Path(__file__).resolve().parents[1] / "addon" / "blender_cinematic_agent" / "job_runner.py"


def build_job(
    action: str,
    workspace: str | Path,
    blend_path: str | Path,
    *,
    manifest: dict | None = None,
    budget: dict | None = None,
    recipe: dict | None = None,
    render: dict | None = None,
    output: dict | None = None,
    safety_mode: str = "strict",
) -> dict:
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; allowed {ACTIONS}")
    workspace_root = Path(workspace).expanduser().resolve()
    resolver = WorkspaceResolver([workspace_root])
    if action in _MUTATING_ACTIONS:
        blend = resolver.resolve(blend_path)
    else:
        blend = Path(blend_path).expanduser().resolve()
    safe_output = {}
    for key, value in (output or {}).items():
        if key in _OUTPUT_PATH_KEYS and value:
            safe_output[key] = str(resolver.resolve(value))
        else:
            safe_output[key] = value
    return {
        "schema": "blender_job/0.1",
        "action": action,
        "workspace": str(workspace_root),
        "blend_path": str(blend),
        "manifest": manifest or {},
        "budget": budget or {},
        "recipe": recipe or {"operations": []},
        "render": render or {},
        "output": safe_output,
        "safety_mode": safety_mode,
    }


def run_job(
    job: dict,
    blender_exe: Optional[str] = None,
    timeout: float = 600,
    log_dir: Optional[str | Path] = None,
) -> dict:
    """Execute a job in headless Blender; return the structured result dict."""
    exe = locate_blender(blender_exe)
    if not exe:
        return {"ok": False, "error": "blender_not_found",
                "message": "no Blender executable found (set BLENDER_EXECUTABLE)"}

    runner = _addon_job_runner()
    if not runner.exists():
        return {"ok": False, "error": "job_runner_missing", "message": str(runner)}

    ws = Path(job["workspace"]).expanduser().resolve()
    resolver = WorkspaceResolver([ws])
    logs = resolver.ensure_dir(log_dir if log_dir else ws / "logs")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    job_path = resolver.resolve(logs / f"job_{job['action']}_{stamp}.json")
    result_path = resolver.resolve(logs / f"result_{job['action']}_{stamp}.json")
    job = {**job, "result_path": str(result_path)}
    resolver.write_text(job_path, json.dumps(job, indent=2))

    args = [exe, "-b", "--factory-startup", "-noaudio", "--python", str(runner), "--", str(job_path)]
    try:
        proc = run_checked(args, timeout=timeout)
    except Exception as exc:  # timeout / OS error
        return {"ok": False, "error": "blender_invocation_failed", "message": str(exc)}

    resolver.write_text(
        logs / f"stdout_{job['action']}_{stamp}.log",
        (proc.stdout or "") + "\n--- STDERR ---\n" + (proc.stderr or ""),
    )
    if result_path.exists():
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
            result.setdefault("ok", proc.returncode == 0)
            return result
        except json.JSONDecodeError:
            pass
    # Fall back to a sentinel printed on stdout.
    for line in (proc.stdout or "").splitlines():
        if line.startswith(_RESULT_SENTINEL):
            rp = Path(line[len(_RESULT_SENTINEL):].strip())
            if rp.exists():
                return json.loads(rp.read_text(encoding="utf-8"))
    return {
        "ok": False,
        "error": "no_result",
        "returncode": proc.returncode,
        "stderr_tail": (proc.stderr or "")[-2000:],
        "stdout_tail": (proc.stdout or "")[-2000:],
    }
