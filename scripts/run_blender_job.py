#!/usr/bin/env python
"""Run a manifest (+ optional recipe) through Blender background mode end-to-end.

preflight -> budget -> workspace -> build+preview+export -> inspect -> lint ->
score -> final report. Without a recipe it initialises the .blend and stops with
a clear note (a scene needs a recipe of structured operations).
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic import runner
from blender_cinematic.budget import compute_budget
from blender_cinematic.evaluation import score_iteration
from blender_cinematic.imaging import image_sanity
from blender_cinematic.linters import lint_scene
from blender_cinematic.preflight import collect_hardware_report
from blender_cinematic.recipes import validate_recipe
from blender_cinematic.report import write_final_report
from blender_cinematic.schemas import SceneManifest
from blender_cinematic.workspace import task_workspace


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run a Blender job from a manifest")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--recipe", default=None)
    ap.add_argument("--project-dir", default="./artifacts")
    ap.add_argument("--blender", default=None)
    ap.add_argument("--profile", default=None, help="override manifest quality_profile")
    args = ap.parse_args(argv)

    manifest = SceneManifest.model_validate(json.loads(Path(args.manifest).read_text(encoding="utf-8")))
    profile = args.profile or manifest.quality_profile

    report = collect_hardware_report(args.project_dir, args.blender)
    budget = compute_budget(report, profile, manifest.target.render_resolution,
                            manifest.target.preview_resolution)
    resolver, base = task_workspace(args.project_dir, manifest.task_id)
    resolver.write_text(base / "scene_manifest.json", manifest.model_dump_json(indent=2))
    report["render_budget"] = budget
    resolver.write_text(base / "hardware_report.json", json.dumps(report, indent=2))

    blend = base / "final" / "scene.blend"
    summary = {"task_id": manifest.task_id, "profile": budget["quality_profile"]}

    if not args.recipe:
        job = runner.build_job("initialize_blend", base, blend, manifest=manifest.model_dump(), budget=budget)
        summary["init"] = runner.run_job(job, args.blender)
        summary["note"] = "no --recipe provided: .blend initialised but scene not built"
        write_final_report(resolver, base, manifest=manifest.model_dump(),
                           notes=["scene not built (no recipe supplied)"])
        print(json.dumps(summary, indent=2))
        return 0

    recipe = json.loads(Path(args.recipe).read_text(encoding="utf-8"))
    check = validate_recipe(recipe)
    if not check.passed:
        print(json.dumps({"error": "invalid_recipe", "issues": check.to_dict()["issues"]}, indent=2))
        return 1

    preview = base / "iterations" / "iter_01_preview.png"
    glb = base / "final" / "export_final.glb"
    out = {"image": str(preview)}
    if manifest.wants_web():
        out["glb"] = str(glb)
    job = runner.build_job("full_pipeline", base, blend, manifest=manifest.model_dump(),
                           budget=budget, recipe=recipe, output=out)
    summary["pipeline"] = runner.run_job(job, args.blender, timeout=600)

    # inspect -> lint -> score
    insp_job = runner.build_job("inspect", base, blend,
                                output={"inspect": str(base / "iterations" / "iter_01_inspect.json")})
    insp_res = runner.run_job(insp_job, args.blender, timeout=180)
    inspection = insp_res.get("inspection") or {}
    lint = lint_scene(inspection, manifest.model_dump(), budget)
    metrics = image_sanity(preview) if preview.exists() else None
    ev = score_iteration(1, inspection, lint, metrics, manifest.model_dump(), budget)
    resolver.write_text(base / "iterations" / "iter_01_eval.json", json.dumps(ev.to_dict(), indent=2))

    web_validation = None
    if manifest.wants_web() and glb.exists():
        from blender_cinematic.glb import validate_glb
        web_validation = validate_glb(glb, manifest.constraints.max_glb_mb)

    write_final_report(resolver, base, manifest=manifest.model_dump(), hardware_report=report,
                       budget=budget, evals=[ev.to_dict()], scene_lint=lint, web_validation=web_validation)
    summary["score"] = ev.scores["total"]
    summary["passed"] = ev.passed
    summary["report"] = str(base / "final" / "final_report.md")
    print(json.dumps(summary, indent=2, default=str))
    return 0 if ev.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
