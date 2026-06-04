"""MCP tool handlers + registration (SRS 12.3/12.4 + 44).

Handlers are plain ``ctx``-first functions so they are unit-testable without an
MCP transport. ``register_tools`` binds thin typed wrappers onto a FastMCP
instance. Tool names use underscores (MCP-safe); the dotted SRS namespace is
given in each docstring.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from blender_cinematic import runner
from blender_cinematic.budget import compute_budget
from blender_cinematic.evaluation import score_iteration
from blender_cinematic.glb import validate_glb
from blender_cinematic.imaging import image_sanity
from blender_cinematic.linters import lint_scene
from blender_cinematic.preflight import collect_hardware_report
from blender_cinematic.recipes import estimate_complexity, validate_recipe
from blender_cinematic.report import write_final_report
from blender_cinematic.schemas import (
    CameraSchema,
    LightingSchema,
    MaterialSchema,
    SceneManifest,
)
from blender_cinematic.security import (
    ensure_raw_python_allowed,
    scan_python_source,
)
from blender_cinematic.webgen import generate_integration
from blender_cinematic.workspace import task_workspace

from .security import ServerContext


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # tools must never crash the server
            return {"ok": False, "error": type(exc).__name__, "message": str(exc)}
    return wrapper


def _load_manifest(ctx: ServerContext, task_id: str) -> dict:
    path = ctx.task_dir(task_id) / "scene_manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# --------------------------- preflight / project --------------------------- #
@_safe
def h_preflight_system_check(ctx: ServerContext, project_dir: str, requested_profile: str = "auto") -> dict:
    """preflight.system_check"""
    target = ctx.resolver.resolve(Path(project_dir))
    report = collect_hardware_report(target, ctx.blender_exe)
    budget = compute_budget(report, requested_profile)
    report["render_budget"] = budget
    report["selected_profile"] = budget["quality_profile"]
    path = ctx.resolver.write_text(target / "hardware_report.json", json.dumps(report, indent=2))
    return {"ok": True, "hardware_report_path": str(path),
            "quality_profile": budget["quality_profile"], "warnings": report["warnings"]}


@_safe
def h_project_create_scene_workspace(ctx: ServerContext, task_id: str, manifest: dict) -> dict:
    """project.create_scene_workspace"""
    m = SceneManifest.model_validate(manifest)
    resolver, base = task_workspace(ctx.workspace_root, task_id)
    mp = resolver.write_text(base / "scene_manifest.json", m.model_dump_json(indent=2))
    return {"ok": True, "task_dir": str(base), "manifest_path": str(mp)}


@_safe
def h_project_final_report(ctx: ServerContext, task_id: str, limitations: list[str] | None = None) -> dict:
    """project.final_report"""
    base = ctx.task_dir(task_id)
    md, js = write_final_report(ctx.resolver, base, notes=limitations)
    return {"ok": True, "report_md": str(md), "report_json": str(js)}


# --------------------------------- scene ----------------------------------- #
@_safe
def h_scene_validate_manifest(ctx: ServerContext, manifest: dict) -> dict:
    """scene.validate_manifest"""
    try:
        SceneManifest.model_validate(manifest)
        return {"ok": True, "valid": True, "errors": []}
    except Exception as exc:
        return {"ok": True, "valid": False, "errors": [str(exc)]}


@_safe
def h_scene_initialize_blend(ctx: ServerContext, task_id: str, budget: dict | None = None) -> dict:
    """scene.initialize_blend"""
    base = ctx.task_dir(task_id)
    manifest = _load_manifest(ctx, task_id)
    job = runner.build_job("initialize_blend", base, base / "final" / "scene.blend",
                           manifest=manifest, budget=budget or {}, safety_mode=ctx.safety_mode)
    return runner.run_job(job, ctx.blender_exe)


@_safe
def h_scene_apply_recipe(ctx: ServerContext, task_id: str, recipe: dict) -> dict:
    """scene.apply_recipe — validate + complexity-gate, then execute structured ops."""
    check = validate_recipe(recipe)
    if not check.passed:
        return {"ok": False, "error": "invalid_recipe", "issues": check.to_dict()["issues"]}
    complexity = estimate_complexity(recipe)
    if not complexity["within_budget"]:
        return {"ok": False, "error": "complexity_budget", "complexity": complexity}
    base = ctx.task_dir(task_id)
    job = runner.build_job("apply_recipe", base, base / "final" / "scene.blend",
                           recipe=recipe, safety_mode=ctx.safety_mode)
    result = runner.run_job(job, ctx.blender_exe)
    result["complexity"] = complexity
    return result


@_safe
def h_scene_inspect(ctx: ServerContext, task_id: str) -> dict:
    """scene.inspect"""
    base = ctx.task_dir(task_id)
    job = runner.build_job("inspect", base, base / "final" / "scene.blend",
                           output={"inspect": str(base / "iterations" / "inspect.json")},
                           safety_mode=ctx.safety_mode)
    return runner.run_job(job, ctx.blender_exe)


@_safe
def h_evaluate_scene_lint(ctx: ServerContext, inspection: dict, task_id: str | None = None) -> dict:
    """evaluate.scene_lint"""
    manifest = _load_manifest(ctx, task_id) if task_id else None
    result = lint_scene(inspection, manifest)
    return {"ok": True, "lint": result.to_dict()}


@_safe
def h_scene_execute_python_safe(ctx: ServerContext, code: str) -> dict:
    """scene.execute_blender_python_safe — disabled by default (SRS 12.4)."""
    ensure_raw_python_allowed(ctx.raw_python_enabled, ctx.safety_mode)  # raises in strict
    scan = scan_python_source(code)
    if not scan.safe:
        return {"ok": False, "error": "unsafe_code", "issues": [i.to_dict() for i in scan.issues]}
    return {"ok": True, "approved": True,
            "note": "code passed static scan; execution requires dev-mode bridge approval"}


# ---------------------- camera / lighting / material ----------------------- #
@_safe
def h_camera_plan_and_create(ctx: ServerContext, task_id: str, schema: dict) -> dict:
    """camera.plan_and_create"""
    CameraSchema.model_validate(schema)
    return h_scene_apply_recipe(ctx, task_id, {"operations": [{"op": "create_camera", "schema": schema}]})


@_safe
def h_lighting_create_setup(ctx: ServerContext, task_id: str, schema: dict) -> dict:
    """lighting.create_setup"""
    LightingSchema.model_validate(schema)
    return h_scene_apply_recipe(ctx, task_id, {"operations": [{"op": "create_lighting_rig", "schema": schema}]})


@_safe
def h_material_create_pbr(ctx: ServerContext, task_id: str, schema: dict) -> dict:
    """material.create_pbr"""
    MaterialSchema.model_validate(schema)
    return h_scene_apply_recipe(ctx, task_id, {"operations": [{"op": "create_material", "schema": schema}]})


@_safe
def h_geometry_estimate_complexity(ctx: ServerContext, recipe: dict) -> dict:
    """geometry.estimate_complexity"""
    return {"ok": True, "complexity": estimate_complexity(recipe)}


# --------------------------------- render ---------------------------------- #
@_safe
def h_render_budget(ctx: ServerContext, hardware_report_path: str, requested_profile: str = "auto",
                    final_resolution: list[int] | None = None) -> dict:
    """render.budget"""
    report = json.loads(ctx.resolver.resolve(Path(hardware_report_path)).read_text(encoding="utf-8"))
    return {"ok": True, "budget": compute_budget(report, requested_profile, final_resolution)}


@_safe
def h_render_preview(ctx: ServerContext, task_id: str, budget: dict | None = None) -> dict:
    """render.preview"""
    base = ctx.task_dir(task_id)
    out = base / "iterations" / "preview.png"
    job = runner.build_job("render_preview", base, base / "final" / "scene.blend",
                           budget=budget or {}, output={"image": str(out)}, safety_mode=ctx.safety_mode)
    return runner.run_job(job, ctx.blender_exe)


@_safe
def h_render_final(ctx: ServerContext, task_id: str, budget: dict | None = None, force: bool = False) -> dict:
    """render.final — only after preview passes unless force=True."""
    base = ctx.task_dir(task_id)
    if not force:
        evals = sorted((base / "iterations").glob("*_eval.json"))
        last = json.loads(evals[-1].read_text(encoding="utf-8")) if evals else None
        if not last or last.get("hard_fail") or not last.get("passed"):
            return {"ok": False, "error": "preview_not_passed",
                    "message": "final render gated; pass preview eval or use force=true"}
    out = base / "final" / "render_final.png"
    job = runner.build_job("render_final", base, base / "final" / "scene.blend",
                           budget=budget or {}, output={"image": str(out)}, safety_mode=ctx.safety_mode)
    return runner.run_job(job, ctx.blender_exe, timeout=1800)


@_safe
def h_evaluate_preview(ctx: ServerContext, image_path: str, inspection: dict | None = None,
                       task_id: str | None = None, reference_metrics: dict | None = None) -> dict:
    """evaluate.preview — render sanity + rubric."""
    img = ctx.resolver.resolve(Path(image_path))
    metrics = image_sanity(img)
    manifest = _load_manifest(ctx, task_id) if task_id else None
    inspection = inspection or {}
    lint = lint_scene(inspection, manifest) if inspection else lint_scene({"objects": []}, manifest)
    n = 1
    if task_id:
        n = len(list((ctx.task_dir(task_id) / "iterations").glob("*_eval.json"))) + 1
    ev = score_iteration(n, inspection, lint, metrics, manifest, reference_metrics=reference_metrics)
    if task_id:
        ctx.resolver.write_text(ctx.task_dir(task_id) / "iterations" / f"iter_{n:02d}_eval.json",
                                json.dumps(ev.to_dict(), indent=2))
    return {"ok": True, "metrics": metrics, "evaluation": ev.to_dict()}


# -------------------------------- export / web ----------------------------- #
@_safe
def h_export_glb(ctx: ServerContext, task_id: str) -> dict:
    """export.glb"""
    base = ctx.task_dir(task_id)
    out = base / "final" / "export_final.glb"
    manifest = _load_manifest(ctx, task_id)
    job = runner.build_job("export_glb", base, base / "final" / "scene.blend",
                           manifest=manifest, output={"glb": str(out)}, safety_mode=ctx.safety_mode)
    return runner.run_job(job, ctx.blender_exe)


@_safe
def h_web_validate_glb(ctx: ServerContext, glb_path: str, max_mb: float | None = None,
                       require_animation: bool = False) -> dict:
    """web.validate_glb (pure-Python structural validation)."""
    p = ctx.resolver.resolve(Path(glb_path))
    return validate_glb(p, max_mb, require_animation)


@_safe
def h_web_generate_integration(ctx: ServerContext, task_id: str, runtime: str = "react-three-fiber",
                               glb_name: str = "scene.glb", scroll_segments: list[dict] | None = None,
                               scroll_samples: list[dict] | None = None) -> dict:
    """web.generate_integration"""
    base = ctx.task_dir(task_id)
    written = generate_integration(base / "web-demo", ctx.resolver, glb_name, runtime,
                                   scroll_segments, scroll_samples)
    return {"ok": True, "files": written}


# -------------------------------- security --------------------------------- #
@_safe
def h_security_scan_python(ctx: ServerContext, code: str) -> dict:
    """security.scan_python"""
    scan = scan_python_source(code)
    return {"ok": True, "safe": scan.safe, "issues": [i.to_dict() for i in scan.issues]}


@_safe
def h_security_policy(ctx: ServerContext) -> dict:
    """security.policy"""
    return {"ok": True, "policy": ctx.policy()}


HANDLERS = {
    "preflight_system_check": h_preflight_system_check,
    "project_create_scene_workspace": h_project_create_scene_workspace,
    "project_final_report": h_project_final_report,
    "scene_validate_manifest": h_scene_validate_manifest,
    "scene_initialize_blend": h_scene_initialize_blend,
    "scene_apply_recipe": h_scene_apply_recipe,
    "scene_inspect": h_scene_inspect,
    "scene_execute_python_safe": h_scene_execute_python_safe,
    "evaluate_scene_lint": h_evaluate_scene_lint,
    "evaluate_preview": h_evaluate_preview,
    "camera_plan_and_create": h_camera_plan_and_create,
    "lighting_create_setup": h_lighting_create_setup,
    "material_create_pbr": h_material_create_pbr,
    "geometry_estimate_complexity": h_geometry_estimate_complexity,
    "render_budget": h_render_budget,
    "render_preview": h_render_preview,
    "render_final": h_render_final,
    "export_glb": h_export_glb,
    "web_validate_glb": h_web_validate_glb,
    "web_generate_integration": h_web_generate_integration,
    "security_scan_python": h_security_scan_python,
    "security_policy": h_security_policy,
}


def register_tools(mcp, ctx: ServerContext) -> None:
    """Bind each handler onto FastMCP, injecting ctx and exposing a real schema.

    Each wrapper advertises the handler's own signature (minus ``ctx``) via
    ``__signature__`` so FastMCP/pydantic generate proper structured input
    schemas instead of an opaque ``**kwargs`` blob.
    """
    import inspect

    for name, handler in HANDLERS.items():
        sig = inspect.signature(handler)
        params = [p for n, p in sig.parameters.items() if n != "ctx"]
        new_sig = inspect.Signature(parameters=params, return_annotation=dict)
        annotations = {p.name: (p.annotation if p.annotation is not inspect.Parameter.empty else dict)
                       for p in params}
        annotations["return"] = dict

        def make(h):
            def tool(**kwargs) -> dict:
                return h(ctx, **kwargs)
            return tool

        wrapped = make(handler)
        wrapped.__name__ = name
        wrapped.__doc__ = (handler.__doc__ or name).strip()
        wrapped.__signature__ = new_sig
        wrapped.__annotations__ = annotations
        mcp.tool(name=name, description=wrapped.__doc__)(wrapped)
