"""Evaluation rubric + hard-fail logic (SRS 10.2, 10.3, 15.5, 46).

Scores are derived from *measurable* signals (camera framing, image statistics,
lint findings, budget fit, optional reference metrics) — never invented. A
hard-fail overrides the numeric score: a scene that is black, has no camera, no
lights, or default materials cannot "pass" no matter what the rubric sums to.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .constants import PASS_THRESHOLD, RUBRIC_MAX
from .imaging import render_sanity_issues
from .linters import is_default_name
from .results import CheckResult

_ACTION_MAP = {
    "camera.none": "add and activate a named camera framing the subject",
    "camera.subject_hidden": "reposition camera so the subject sits inside the frame",
    "camera.subject_part_hidden": "reframe so all important hero parts remain inside the camera frame",
    "camera.subject_tiny": "move the camera closer or raise focal length to fill the frame",
    "camera.mobile_unsafe": "leave safe margin so the subject survives a mobile crop",
    "lighting.none": "add a lighting rig (key/fill/rim) or world illumination",
    "lighting.default": "replace default lights with an intentional rig",
    "material.default": "replace default grey materials with intentional PBR materials",
    "material.missing": "assign a material to the key object",
    "material.monotone": "introduce material variation across key objects",
    "mesh.unapplied_scale": "apply object scale before export",
    "mesh.sharp_edges": "add bevels/subsurf so edges catch light",
    "geometry.unbaked": "apply/bake geometry nodes before GLB export",
    "geometry.face_budget": "reduce generated geometry to fit the face budget",
    "animation.missing": "add keyframes for the requested animation",
    "animation.glb_clip": "export the animation clip into the GLB",
    "vfx.particle_budget": "reduce particle count to fit the profile",
    "spatial.floating_part": "attach floating detail parts to the subject body or mark the scene as intentionally exploded/floating",
}


@dataclass
class IterationEval:
    iteration: int
    hard_fail: bool
    scores: dict[str, int]
    defects: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    hard_fail_reasons: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.scores.get("total", 0)

    @property
    def passed(self) -> bool:
        return (not self.hard_fail) and self.total >= PASS_THRESHOLD

    def to_dict(self) -> dict:
        return {
            "iteration": self.iteration,
            "hard_fail": self.hard_fail,
            "passed": self.passed,
            "scores": self.scores,
            "defects": self.defects,
            "next_actions": self.next_actions,
            "hard_fail_reasons": self.hard_fail_reasons,
        }


def _clamp(v: float, hi: int) -> int:
    return int(max(0, min(hi, round(v))))


def hard_fail_reasons(
    inspection: dict,
    image_metrics: dict | None,
    manifest: dict | None,
    lint: CheckResult,
    web_load_ok: bool | None = None,
) -> list[str]:
    reasons: list[str] = []
    if image_metrics is not None:
        reasons += render_sanity_issues(image_metrics)
    lint_codes = {i.code for i in lint.errors}
    if "camera.none" in lint_codes or not inspection.get("active_camera"):
        reasons.append("no active camera")
    if "camera.subject_hidden" in lint_codes:
        reasons.append("subject not visible from camera")
    if "camera.subject_part_hidden" in lint_codes:
        reasons.append("important subject detail is outside the camera frame")
    if "camera.subject_cut" in lint_codes:
        reasons.append("subject is cut off by camera frame")
    if "material.default" in lint_codes:
        reasons.append("default materials on key objects")
    if "lighting.none" in lint_codes:
        reasons.append("no meaningful lighting")
    if "animation.missing" in lint_codes:
        reasons.append("requested animation has no keyframes")
    for issue in lint.errors:
        msg = issue.message.strip()
        if msg and msg not in reasons:
            reasons.append(msg)
    if inspection.get("missing_files"):
        reasons.append(f"missing files: {inspection['missing_files']}")
    if not inspection.get("objects"):
        reasons.append("scene is empty")
    m = manifest or {}
    wants_web = m.get("output_mode") in ("web_asset", "interactive_web") or any(
        f in ("glb", "gltf") for f in ((m.get("target") or {}).get("final_format") or [])
    )
    if wants_web and web_load_ok is False:
        reasons.append("requested GLB cannot load in local viewer")
    return reasons


def _score_composition(inspection: dict, img: dict | None) -> float:
    s = 0.0
    cam = inspection.get("active_camera")
    subjects = [o for o in inspection.get("objects", []) if o.get("collection") == "SUBJECT"]
    if cam:
        s += 6
    if subjects and all(o.get("in_camera_frame", True) for o in subjects):
        s += 6
    cov = max((o.get("screen_coverage", 0) for o in subjects), default=0)
    if 0.2 <= cov <= 0.85:
        s += 5
    elif cov:
        s += 2
    cols = set(inspection.get("collections", []))
    if {"SUBJECT", "ENVIRONMENT"} <= cols:
        s += 3
    return s


def _score_lighting(inspection: dict, img: dict | None) -> float:
    s = 0.0
    if inspection.get("lights") or (inspection.get("world") or {}).get("strength"):
        s += 5
    if img:
        if 0.08 <= img["mean_brightness"] <= 0.85:
            s += 5
        if img["contrast"] > 0.05:
            s += 3
        if img["pct_near_black"] < 0.9 and img["pct_near_white"] < 0.9:
            s += 2
    else:
        s += 5  # no render yet: don't punish structurally-lit scene
    return s


def _score_materials(inspection: dict) -> float:
    mats = inspection.get("materials", [])
    objs = [o for o in inspection.get("objects", []) if o.get("collection") in ("SUBJECT", "EXPORT")]
    if not mats:
        return 0.0
    named = [mt for mt in mats if not mt.get("is_default") and not is_default_name(mt.get("name", ""))]
    s = 8 * (len(named) / max(1, len(mats)))
    if len({mt.get("name") for mt in named}) >= 2:
        s += 4
    for o in objs:
        if any(mt for mt in named if mt.get("name") in (o.get("materials") or []) and (mt.get("metallic") or 0) > 0.5):
            if any(mod.get("type") == "BEVEL" for mod in o.get("modifiers", [])):
                s += 3
                break
    return s


def _score_geometry(inspection: dict) -> float:
    objs = inspection.get("objects", [])
    faces = sum(o.get("faces", 0) for o in objs if o.get("collection") == "SUBJECT") or sum(o.get("faces", 0) for o in objs)
    s = min(7.0, math.log10(faces + 1) * 2.2)
    if len(objs) >= 3:
        s += 3
    defaults = sum(1 for o in objs if is_default_name(o.get("name", "")))
    s += max(0, 5 - defaults * 2)
    return s


def _score_camera(inspection: dict) -> float:
    cam = inspection.get("active_camera")
    if not cam:
        return 0.0
    if cam.get("inside_geometry"):
        return 1.0
    s = 3.0
    if cam.get("lens_mm"):
        s += 2
    if (not cam.get("dof")) or cam.get("focus_target"):
        s += 2
    if (inspection.get("metadata") or {}).get("final_camera"):
        s += 3
    return s


def _score_technical(lint: CheckResult, inspection: dict) -> float:
    s = 10.0 - 2 * len(lint.errors)
    if inspection.get("missing_files"):
        s -= 3
    return s


def _score_performance(inspection: dict, manifest: dict | None, budget: dict | None) -> float:
    s = 1.0
    faces = sum(o.get("faces", 0) for o in inspection.get("objects", []))
    if faces <= (budget or {}).get("budget_faces", 2_000_000):
        s += 2
    glb_mb = inspection.get("glb_size_mb")
    cap = ((manifest or {}).get("constraints") or {}).get("max_glb_mb")
    if glb_mb is None or cap is None or glb_mb <= cap:
        s += 2
    return s


def score_iteration(
    iteration: int,
    inspection: dict,
    lint: CheckResult,
    image_metrics: dict | None = None,
    manifest: dict | None = None,
    budget: dict | None = None,
    reference_metrics: dict | None = None,
    web_load_ok: bool | None = None,
) -> IterationEval:
    scores = {
        "composition": _clamp(_score_composition(inspection, image_metrics), RUBRIC_MAX["composition"]),
        "lighting": _clamp(_score_lighting(inspection, image_metrics), RUBRIC_MAX["lighting"]),
        "materials": _clamp(_score_materials(inspection), RUBRIC_MAX["materials"]),
        "geometry_detail": _clamp(_score_geometry(inspection), RUBRIC_MAX["geometry_detail"]),
        "camera": _clamp(_score_camera(inspection), RUBRIC_MAX["camera"]),
        "technical": _clamp(_score_technical(lint, inspection), RUBRIC_MAX["technical"]),
        "performance": _clamp(_score_performance(inspection, manifest, budget), RUBRIC_MAX["performance"]),
    }
    if reference_metrics:
        ref = 0.0
        ref += 6 * float(reference_metrics.get("ssim", 0))
        ref += 4 * float(reference_metrics.get("palette_similarity", 0))
        scores["reference_fidelity"] = _clamp(ref, RUBRIC_MAX["reference_fidelity"])
    else:
        others_max = sum(v for k, v in RUBRIC_MAX.items() if k != "reference_fidelity")
        frac = sum(scores.values()) / others_max if others_max else 0
        scores["reference_fidelity"] = _clamp(RUBRIC_MAX["reference_fidelity"] * frac, RUBRIC_MAX["reference_fidelity"])

    reasons = hard_fail_reasons(inspection, image_metrics, manifest, lint, web_load_ok)
    m = manifest or {}
    wants_reference = m.get("output_mode") == "reference_match" or bool(m.get("references"))
    if wants_reference and not reference_metrics:
        reasons.append("reference match requested but no reference metrics were provided")
    raw_total = sum(v for k, v in scores.items() if k != "total")
    scores["total"] = min(raw_total, PASS_THRESHOLD - 1) if reasons else raw_total

    defects: list[str] = list(reasons)
    actions: list[str] = []
    for i in lint.errors + lint.warnings:
        if i.message not in defects:
            defects.append(i.message)
        if i.code in _ACTION_MAP and _ACTION_MAP[i.code] not in actions:
            actions.append(_ACTION_MAP[i.code])
    return IterationEval(
        iteration=iteration,
        hard_fail=bool(reasons),
        scores=scores,
        defects=defects[:8],
        next_actions=actions[:5],
        hard_fail_reasons=reasons,
    )
