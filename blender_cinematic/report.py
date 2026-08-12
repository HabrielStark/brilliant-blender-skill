"""Final report writer (SRS 7.3 / 15.1 layer 7).

The report is built from *real artifacts on disk*: it scans the task directory,
records which files actually exist, folds in the manifest / hardware / budget /
iteration evaluations / lint / web validation, and states passes, failures and
honest limitations. This is what lets the agent legitimately say "done".
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .results import CheckResult

_RENDER_EXTENSIONS = {".png", ".jpg", ".jpeg", ".exr", ".tif", ".tiff", ".mp4", ".mov", ".webm"}


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def collect_artifacts(task_base: str | Path) -> dict[str, list[str]]:
    base = Path(task_base)
    out: dict[str, list[str]] = {}
    if not base.exists():
        return out
    for path in sorted(base.rglob("*")):
        if path.is_file():
            rel = path.relative_to(base)
            group = rel.parts[0] if len(rel.parts) > 1 else "."
            out.setdefault(group, []).append(str(rel).replace("\\", "/"))
    return out


def build_final_report(
    task_base: str | Path,
    manifest: dict | None = None,
    hardware_report: dict | None = None,
    budget: dict | None = None,
    evals: list[dict] | None = None,
    scene_lint: CheckResult | dict | None = None,
    web_validation: dict | None = None,
    notes: list[str] | None = None,
    runtime_failures: list[str] | None = None,
) -> tuple[str, dict]:
    base = Path(task_base)
    manifest = manifest or _load_json(base / "scene_manifest.json") or {}
    hardware_report = hardware_report or _load_json(base / "hardware_report.json") or {}
    budget = budget or hardware_report.get("render_budget") or {}
    if evals is None:
        evals = []
        it = base / "iterations"
        if it.exists():
            for f in sorted(it.glob("*_eval.json")):
                ev = _load_json(f)
                if ev:
                    evals.append(ev)
    lint_dict = scene_lint.to_dict() if isinstance(scene_lint, CheckResult) else (scene_lint or {})

    artifacts = collect_artifacts(base)
    best = max(evals, key=lambda e: e.get("scores", {}).get("total", 0), default=None)
    latest = max(evals, key=lambda e: e.get("iteration", -1), default=None)
    passed = bool(latest and latest.get("passed"))

    # Acceptance signals derived from artifacts (SRS: no claims without files).
    has_preview = any(
        group == "iterations"
        and Path(f).suffix.lower() in _RENDER_EXTENSIONS
        and "preview" in Path(f).stem.lower()
        for group, fs in artifacts.items()
        for f in fs
    )
    # A .blend or GLB under `final/` is not a rendered image. Require a real
    # image/video artifact whose name identifies it as a render.
    has_render = any(
        Path(f).suffix.lower() in _RENDER_EXTENSIONS
        and "render" in Path(f).stem.lower()
        for fs in artifacts.values()
        for f in fs
    )
    has_glb = any(f.endswith((".glb", ".gltf")) for fs in artifacts.values() for f in fs)
    wants_web = manifest.get("output_mode") in ("web_asset", "interactive_web") or any(
        x in ("glb", "gltf") for x in ((manifest.get("target") or {}).get("final_format") or [])
    )

    failures: list[str] = []
    if not latest:
        failures.append("no iteration evaluation found")
    elif not latest.get("passed"):
        failures.append(f"latest iteration {latest.get('iteration')} did not pass")
    if latest and latest.get("hard_fail"):
        failures += [f"hard-fail: {r}" for r in latest.get("hard_fail_reasons", [])]
    for issue in lint_dict.get("issues", []):
        if issue.get("severity") == "error":
            failures.append(f"lint: {issue.get('message')}")
    if wants_web and not has_glb:
        failures.append("web export requested but no GLB artifact found")
    if wants_web and (web_validation is None or web_validation.get("ok") is not True):
        failures.append(
            f"GLB validation failed: {(web_validation or {}).get('errors', ['validation not run'])}"
        )
    if best and not has_preview:
        failures.append("preview artifact missing")
    if best and not has_render:
        failures.append("final render artifact missing")
    failures.extend(runtime_failures or [])

    report = {
        "schema": "final_report/0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_id": manifest.get("task_id"),
        "brief": manifest.get("brief"),
        "output_mode": manifest.get("output_mode"),
        "quality_profile": budget.get("quality_profile") or manifest.get("quality_profile"),
        "passed": passed and has_render and not failures,
        "best_score": best.get("scores", {}).get("total") if best else None,
        "latest_iteration": latest.get("iteration") if latest else None,
        "latest_score": latest.get("scores", {}).get("total") if latest else None,
        "iterations_run": len(evals),
        "artifacts": artifacts,
        "acceptance": {
            "has_preview": has_preview,
            "has_render": has_render,
            "has_glb": has_glb,
            "web_validation": web_validation,
        },
        "scores": best.get("scores") if best else None,
        "failures": failures,
        "limitations": notes or [],
        "render_budget": budget,
        "hardware_warnings": hardware_report.get("warnings", []),
    }
    return _render_markdown(report, evals, lint_dict), report


def _render_markdown(r: dict, evals: list[dict], lint: dict) -> str:
    lines: list[str] = []
    status = "PASS" if r["passed"] else "NOT PASSED"
    lines += [
        f"# Final Report — {r.get('task_id') or 'scene'}",
        "",
        f"- **Status:** {status}",
        f"- **Brief:** {r.get('brief')}",
        f"- **Output mode:** {r.get('output_mode')}",
        f"- **Quality profile:** {r.get('quality_profile')}",
        f"- **Best score:** {r.get('best_score')}/100  (iterations run: {r.get('iterations_run')})",
        f"- **Generated:** {r['generated_at']}",
        "",
    ]
    sc = r.get("scores")
    if sc:
        lines.append("## Rubric scores")
        lines.append("")
        lines.append("| Category | Score |")
        lines.append("|---|---:|")
        for k, v in sc.items():
            if k != "total":
                lines.append(f"| {k} | {v} |")
        lines.append(f"| **total** | **{sc.get('total')}** |")
        lines.append("")
    acc = r["acceptance"]
    lines += [
        "## Acceptance signals",
        "",
        f"- preview present: {acc['has_preview']}",
        f"- render present: {acc['has_render']}",
        f"- GLB present: {acc['has_glb']}",
        f"- web validation: {acc['web_validation']}",
        "",
    ]
    if r["failures"]:
        lines.append("## Failures")
        lines += [f"- {f}" for f in r["failures"]] + [""]
    else:
        lines += ["## Failures", "", "- none", ""]
    if r["limitations"]:
        lines.append("## Limitations")
        lines += [f"- {n}" for n in r["limitations"]] + [""]
    if r["hardware_warnings"]:
        lines.append("## Hardware warnings")
        lines += [f"- {w}" for w in r["hardware_warnings"]] + [""]
    lines.append("## Artifacts")
    lines.append("")
    for group, files in r["artifacts"].items():
        lines.append(f"**{group}/**")
        lines += [f"- `{f}`" for f in files]
        lines.append("")
    if evals:
        lines.append("## Iteration history")
        lines.append("")
        for e in evals:
            t = e.get("scores", {}).get("total")
            hf = " (HARD-FAIL)" if e.get("hard_fail") else ""
            lines.append(f"- iter {e.get('iteration')}: {t}/100{hf}; "
                         f"next: {', '.join(e.get('next_actions', [])) or '—'}")
        lines.append("")
    return "\n".join(lines)


def write_final_report(resolver, task_base: str | Path, **kwargs) -> tuple[Path, Path]:
    base = Path(task_base)
    md, report = build_final_report(base, **kwargs)
    final_dir = base / "final"
    md_path = resolver.write_text(final_dir / "final_report.md", md)
    json_path = resolver.write_text(final_dir / "final_report.json", json.dumps(report, indent=2))
    return md_path, json_path
