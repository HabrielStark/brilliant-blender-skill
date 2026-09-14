"""Scene critique: turn inspection + image metrics into prioritized, op-ready fixes.

This is the codified "eye" — the same reasoning an artist applies when a render
looks wrong, expressed as ordered diagnoses with concrete repair ops a caller
can apply via apply_recipe. Pure Python (no bpy): it consumes the inspection
dict, image-sanity metrics, and optionally a reference image for signed tonal
direction.

Each diagnosis::

    {
      "severity": "fail" | "warn",
      "code": "tonal.too_dark",           # stable machine key
      "problem": "human-readable what is wrong",
      "evidence": "numbers that show it",
      "ops": [{"op": "adjust_world", ...}] # suggested ops, most-direct first
    }
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .imaging import _edge_map, _load, _luma, _saliency_mask


def _subject_objects(inspection: dict) -> list[dict]:
    return [o for o in inspection.get("objects", [])
            if o.get("collection") == "SUBJECT"]


def _in_frame(objs: list[dict]) -> list[dict]:
    return [o for o in objs if o.get("in_camera_frame")]


def _centroid(objs: list[dict]) -> list[float] | None:
    pts = [o["world_location"] for o in objs if o.get("world_location")]
    if not pts:
        return None
    return [sum(p[i] for p in pts) / len(pts) for i in range(3)]


def _diag(severity, code, problem, evidence, ops):
    return {"severity": severity, "code": code, "problem": problem,
            "evidence": evidence, "ops": ops}


def _lint_issues(lint) -> list:
    """Normalise a CheckResult (or its dict form) to (severity, code, loc)."""
    if lint is None:
        return []
    items = []
    if isinstance(lint, dict):
        for i in lint.get("errors", []):
            items.append(("fail", i.get("code", ""), i.get("location"),
                          i.get("message", "")))
        for i in lint.get("warnings", []):
            items.append(("warn", i.get("code", ""), i.get("location"),
                          i.get("message", "")))
        return items
    for i in getattr(lint, "errors", []):
        items.append(("fail", i.code, i.location, i.message))
    for i in getattr(lint, "warnings", []):
        items.append(("warn", i.code, i.location, i.message))
    return items


def _check_lint(lint, inspection: dict, out: list) -> None:
    issues = _lint_issues(lint)
    if not issues:
        return
    subjects = _subject_objects(inspection)
    anchor = _centroid(_in_frame(subjects)) or _centroid(subjects)
    default_look = anchor or [0, 0, 0.5]
    emitted = set()
    for sev, code, loc, msg in issues:
        if (code, loc) in emitted:
            continue
        if code == "camera.none":
            emitted.add((code, loc))
            cam_schema = {
                "camera_name": "hero_camera",
                "location": [default_look[0], default_look[1] - 6,
                             default_look[2] + 1.5],
                "look_at": default_look}
            if subjects:
                cam_schema["target"] = subjects[0]["name"]
            out.append(_diag(
                "fail", "fix.no_camera",
                "scene has no active camera — nothing will render",
                msg,
                [{"op": "create_camera", "schema": cam_schema}]))
        elif code == "lighting.none":
            emitted.add((code, loc))
            out.append(_diag(
                "fail", "fix.no_lighting",
                "no meaningful lighting — the scene renders flat or black",
                msg,
                [{"op": "create_lighting_rig", "schema": {
                    "lighting_rig": "rescue_three_point",
                    "lights": [
                        {"name": "key", "type": "AREA", "power": 500,
                         "size": 4.0, "position_role": "front_left_high",
                         "look_at": default_look},
                        {"name": "rim", "type": "AREA", "power": 300,
                         "size": 3.0, "color": [0.7, 0.8, 1.0],
                         "position_role": "rim", "look_at": default_look},
                        {"name": "fill", "type": "AREA", "power": 150,
                         "size": 5.0, "position_role": "front_right_high",
                         "look_at": default_look},
                    ]}}]))
        elif code == "material.missing":
            emitted.add((code, loc))
            # vary the rescue colour per object so a multi-object fix doesn't
            # come out monotone and trip material.monotone next round
            h = (hash(str(loc)) % 7) / 7.0
            base = [0.30 + 0.25 * h, 0.30 + 0.18 * ((h * 3) % 1),
                    0.36 + 0.20 * ((h * 5) % 1), 1.0]
            out.append(_diag(
                "fail", "fix.no_material",
                f"object '{loc}' has no material — renders as untextured grey",
                msg,
                [{"op": "create_material", "schema": {
                    "name": f"mat_{loc or 'obj'}", "preset": "glossy_plastic",
                    "pbr": {"base_color": [round(c, 3) for c in base],
                            "roughness": 0.4},
                    "target_objects": [loc] if loc else []}}]))
        elif code == "material.default":
            emitted.add((code, loc))
            out.append(_diag(
                "fail", "fix.default_material",
                f"default/grey material on '{loc}' — reads as unfinished",
                msg,
                [{"op": "adjust_material", "material": loc,
                  "pbr": {"base_color": [0.3, 0.32, 0.38, 1.0],
                          "roughness": 0.35}}]))
        elif code in ("camera.subject_hidden", "camera.subject_cut",
                      "camera.subject_part_hidden"):
            emitted.add((code, loc))
            if anchor:
                out.append(_diag(
                    "fail", "fix.subject_framing",
                    "subject is cut off or hidden — reframe at the in-frame "
                    "centroid, not the all-subject centroid",
                    msg,
                    [{"op": "reframe_camera", "look_at": anchor,
                      "pull_back": 1.25}]))
        elif code == "material.metal_unreadable":
            emitted.add((code, loc))
            out.append(_diag(
                "warn", "fix.metal_unreadable",
                f"metallic material on '{loc}' has no bevel or light to "
                "reveal it — metal needs edges and a light to reflect",
                msg,
                [{"op": "add_bevel_modifier", "target": loc, "width": 0.03,
                  "segments": 3},
                 {"op": "add_light", "schema": {
                     "name": f"catch_{str(loc)[:24]}", "type": "AREA",
                     "power": 150, "size": 2.0, "position_role": "rim"}}]))
        elif code == "material.monotone":
            emitted.add((code, loc))
            out.append(_diag(
                "warn", "fix.material_monotone",
                "materials are near-identical — a finished scene needs "
                "distinct surface reads (matte body / glass / emissive / metal)",
                msg, []))


# --------------------------------------------------------------------------- #
#  absolute (no-reference) checks                                              #
# --------------------------------------------------------------------------- #

def _check_exposure(img: dict, out: list) -> None:
    if not img:
        return
    nb = img.get("pct_near_black", 0.0)
    nw = img.get("pct_near_white", 0.0)
    edge = img.get("edge_density", 0.0)
    contrast = img.get("contrast", 0.0)
    if nb > 0.65 and edge < 0.018:
        out.append(_diag(
            "fail", "tonal.crushed_blacks",
            "render is mostly near-black and the subject has no readable detail",
            f"near_black={nb:.2f} edge_density={edge:.3f}",
            [{"op": "adjust_world", "strength_scale": 1.8},
             {"op": "add_light", "schema": {
                 "name": "rescue_rim", "type": "AREA", "power": 300,
                 "size": 3.0, "color": [0.7, 0.8, 1.0],
                 "position_role": "rim"}}]))
    elif nw > 0.6:
        out.append(_diag(
            "fail", "tonal.blown_out",
            "render is largely blown-out white",
            f"near_white={nw:.2f}",
            [{"op": "adjust_world", "strength_scale": 0.55}]))
    elif contrast < 0.02:
        out.append(_diag(
            "warn", "tonal.flat",
            "render is nearly flat — no usable contrast between subject and set",
            f"contrast={contrast:.3f}",
            [{"op": "add_light", "schema": {
                "name": "rescue_key", "type": "AREA", "power": 400,
                "size": 4.0, "position_role": "front_left_high"}}]))


def _check_scene_richness(inspection: dict, out: list) -> None:
    """A scene with one primitive on nothing is technically renderable but
    reads as a default blockout — the generic-AI-slop signature."""
    subjects = _subject_objects(inspection)
    env = [o for o in inspection.get("objects", [])
           if o.get("collection") == "ENVIRONMENT"]
    if subjects and not env:
        out.append(_diag(
            "warn", "composition.no_environment",
            "subject floats in empty space — no ground, backdrop, or set "
            "dressing; every finished scene needs an ENVIRONMENT layer",
            f"subjects={len(subjects)} environment_objects=0",
            [{"op": "create_mesh_primitive", "type": "plane",
              "name": "ground_plane", "size": 20,
              "collection": "ENVIRONMENT"}]))
    if len(subjects) == 1 and len(env) <= 1:
        out.append(_diag(
            "warn", "composition.too_sparse",
            "single-subject scene with no supporting detail — the reference "
            "exemplars layer body, accents, and set elements; a lone primitive "
            "reads as a blockout",
            f"subjects={len(subjects)} environment={len(env)}", []))


def _check_buried_objects(inspection: dict, out: list) -> None:
    """A small subject fully inside another object's bbox is invisible —
    the classic weak-model layout bug (props placed at plausible heights
    but swallowed by the table/pedestal). Computable purely from
    world_location + dimensions."""
    subjects = _subject_objects(inspection)
    def _bounds(o):
        loc, dim = o.get("world_location"), o.get("dimensions")
        if not loc or not dim:
            return None
        return ([loc[i] - dim[i] / 2 for i in range(3)],
                [loc[i] + dim[i] / 2 for i in range(3)])
    boxes = {o["name"]: _bounds(o) for o in subjects
             if o.get("name") and _bounds(o)}
    for name, (lo, hi) in boxes.items():
        for host, (hlo, hhi) in boxes.items():
            if name == host:
                continue
            if all(lo[i] >= hlo[i] and hi[i] <= hhi[i] for i in range(3)):
                # buried -> sit it on top of the host's bounding box
                loc = next(o["world_location"] for o in subjects
                           if o.get("name") == name)
                dim = next(o.get("dimensions") for o in subjects
                           if o.get("name") == name)
                out.append(_diag(
                    "fail", "geometry.buried_object",
                    f"'{name}' is fully inside '{host}' — invisible in the "
                    "render; lift it onto the host's top surface",
                    f"{name} bbox {lo}..{hi} inside {host} {hlo}..{hhi}",
                    [{"op": "set_object_transform", "target": name,
                      "location": [loc[0], loc[1],
                                   hhi[2] + dim[2] / 2 + 0.01]}]))
                break


def _check_subject_visible(inspection: dict, out: list) -> None:
    subjects = _subject_objects(inspection)
    if not subjects:
        return
    offscreen = [o for o in subjects if not o.get("in_camera_frame")]
    if offscreen:
        visible = [o for o in subjects if o.get("in_camera_frame")]
        anchor = _centroid(visible) or _centroid(subjects)
        if anchor:
            out.append(_diag(
                "fail", "framing.offscreen_subjects",
                f"{len(offscreen)} subject objects are outside the camera frame",
                ", ".join(o.get("name", "?") for o in offscreen[:6]),
                [{"op": "reframe_camera", "look_at": anchor, "pull_back": 1.25}]))
    # subject bleeding into the frame edge is the #1 amateur-comp tell —
    # screen_bbox is [minx, miny, maxx, maxy] in normalised camera space
    for o in subjects:
        bb = o.get("screen_bbox")
        if not bb or not o.get("in_camera_frame"):
            continue
        margins = [bb[0], bb[1], 1.0 - bb[2], 1.0 - bb[3]]
        if min(margins) < 0.01:
            out.append(_diag(
                "warn", "framing.edge_crowding",
                f"'{o.get('name')}' touches the frame edge — the eye reads "
                "bleed as accidental crop",
                f"screen_bbox={[round(v, 2) for v in bb]}",
                [{"op": "reframe_camera", "look_at": _centroid(subjects),
                  "pull_back": 1.12}]))
            break
    cov = max((o.get("screen_coverage", 0) or 0 for o in subjects), default=0)
    if cov and cov < 0.02:
        out.append(_diag(
            "fail", "framing.subject_tiny",
            "subject occupies under 2% of frame — reads as distant/empty",
            f"max screen_coverage={cov:.4f}",
            [{"op": "reframe_camera", "look_at": _centroid(subjects),
              "pull_back": 0.6}]))
    elif cov > 0.9:
        out.append(_diag(
            "warn", "framing.subject_floods",
            "subject fills nearly the whole frame — no breathing room",
            f"max screen_coverage={cov:.2f}",
            [{"op": "reframe_camera", "look_at": _centroid(subjects),
              "pull_back": 1.3}]))


def _check_materials(inspection: dict, out: list) -> None:
    # Metallic-1.0 in a dark world renders as a void: the classic "black slab".
    world = inspection.get("world") or {}
    wstrength = float(world.get("strength", 0) or 0)
    for m in inspection.get("materials", []):
        base = m.get("base_color") or [1, 1, 1]
        if (float(m.get("metallic", 0) or 0) >= 0.9
                and max(base[:3]) < 0.08 and wstrength < 0.8):
            out.append(_diag(
                "warn", "material.metal_void",
                f"material '{m.get('name')}' is near-black fully-metallic in a "
                "dark world — a mirror with nothing to reflect renders as a void",
                f"metallic={m.get('metallic')} base={base[:3]} "
                f"world_strength={wstrength}",
                [{"op": "adjust_material", "material": m.get("name"),
                  "pbr": {"metallic": 0.7, "roughness": 0.35}},
                 {"op": "adjust_world", "strength_scale": 1.5}]))


def _check_readability(inspection: dict, report: dict | None, out: list) -> None:
    if not report:
        return
    for name in report.get("unreadable_parts") or []:
        obj = next((o for o in inspection.get("objects", [])
                    if o.get("name") == name), None)
        loc = (obj or {}).get("world_location")
        ops = []
        if loc:
            ops.append({"op": "add_light", "schema": {
                "name": f"catch_{name[:24]}", "type": "AREA", "power": 120,
                "size": 1.2, "location": [loc[0] * 2.2, loc[1] - 1.5, loc[2] + 1.0],
                "look_at": loc}})
        out.append(_diag(
            "warn", "part.unreadable",
            f"named part '{name}' merges into its surround — no internal "
            "contrast, edge detail, or luminance separation",
            "see part_readability", ops))


def _check_frame_balance(render_path, inspection: dict, out: list) -> None:
    """Thirds-grid analysis: a whole outer third of frame dead-dark while the
    rest is lit means the composition has a dead side — content was placed
    without considering the full frame."""
    try:
        luma = _luma(_load(render_path)[..., :3])
    except Exception:
        return
    h, w = luma.shape
    cols = [luma[:, :w // 3], luma[:, w // 3:2 * w // 3], luma[:, 2 * w // 3:]]
    col_luma = [float(c.mean()) for c in cols]
    lit = max(col_luma)
    if lit < 0.05:
        return  # uniformly dark — tonal.crushed_blacks already covers it
    dead = [i for i, v in enumerate(col_luma)
            if v < lit * 0.35 and v < 0.04]
    subjects = _subject_objects(inspection)
    anchor = _centroid(_in_frame(subjects)) or _centroid(subjects)
    for i in dead:
        if i == 1:
            continue  # dead centre column is rarely a defect
        side = "left" if i == 0 else "right"
        out.append(_diag(
            "warn", "composition.dead_side",
            f"the {side} third of frame is near-empty darkness while the rest "
            "is lit — the frame reads lopsided; add set elements or shift "
            "the composition toward it",
            f"column lumas L/C/R={[round(v, 3) for v in col_luma]}",
            [{"op": "reframe_camera", "look_at": anchor, "pull_back": 1.1}]
            if anchor else []))


# --------------------------------------------------------------------------- #
#  reference-relative checks (need the two images for signed direction)         #
# --------------------------------------------------------------------------- #

def _check_reference(render_path, reference_path, inspection: dict,
                     out: list) -> None:
    try:
        la = _luma(_load(render_path)[..., :3])
        lb = _luma(_load(reference_path)[..., :3])
    except Exception:
        return
    if lb.shape != la.shape:
        from .imaging import _resize_rgba_like
        lb = _luma(_resize_rgba_like(reference_path, la.shape[:2])[..., :3])

    ma, mb = _saliency_mask(la), _saliency_mask(lb)
    ea, eb = _edge_map(la), _edge_map(lb)

    # --- brightness direction
    dmean = float(la.mean() - lb.mean())
    if abs(dmean) > 0.02:
        scale = float(np.clip(1.0 - dmean * 4.0, 0.4, 2.2))
        direction = "darker" if dmean < 0 else "brighter"
        out.append(_diag(
            "fail" if abs(dmean) > 0.05 else "warn", "ref.brightness",
            f"render is {direction} than the reference",
            f"mean luma ours={la.mean():.3f} ref={lb.mean():.3f}",
            [{"op": "adjust_world", "strength_scale": round(scale, 2)}]))

    # --- contrast direction: where does our excess spread come from?
    dstd = float(la.std() - lb.std())
    if abs(dstd) > 0.008:
        if dstd > 0:
            # our spread too wide — find which band is over-populated
            ha, _ = np.histogram(la, bins=16, range=(0, 1))
            hb, _ = np.histogram(lb, bins=16, range=(0, 1))
            diff = (ha - hb) / la.size
            worst = int(np.argmax(diff))
            band = f"{worst / 16:.2f}-{(worst + 1) / 16:.2f}"
            if worst <= 1:
                hint = ("our dark mass is too dark — lift ambient/uniform fill "
                        "rather than dimming accents")
                ops = [{"op": "adjust_world", "strength_scale": 1.25}]
            else:
                hint = ("broad mid-tone surfaces exceed the reference — darken "
                        "the widest face material or narrow the key light")
                ops = [{"op": "adjust_world", "strength_scale": 0.8}]
            out.append(_diag(
                "fail" if dstd > 0.025 else "warn", "ref.contrast",
                "luma spread does not match the reference",
                f"std ours={la.std():.3f} ref={lb.std():.3f}; "
                f"over-populated band {band}. {hint}", ops))
        else:
            out.append(_diag(
                "warn", "ref.contrast_low",
                "render is flatter than the reference — accent contrast too weak",
                f"std ours={la.std():.3f} ref={lb.std():.3f}",
                []))

    # --- saliency centroid: which way must the composition move?
    if float(ma.mean()) > 0.005 and float(mb.mean()) > 0.005:
        ya, xa = np.nonzero(ma)
        yb, xb = np.nonzero(mb)
        dcy = float(ya.mean() / la.shape[0] - yb.mean() / la.shape[0])
        dcx = float(xa.mean() / la.shape[1] - xb.mean() / la.shape[1])
        big = max(abs(dcy), abs(dcx))
        if big > 0.05:
            vdir = "lower" if dcy < 0 else "raise"
            hdir = "left" if dcx > 0 else "right"
            out.append(_diag(
                "fail" if big > 0.12 else "warn", "ref.saliency_center",
                f"salient mass sits off the reference centroid — {vdir} the "
                f"subject in frame (shift look_at {'up' if dcy < 0 else 'down'}"
                f", {hdir})",
                f"ours=({xa.mean()/la.shape[1]:.2f},{ya.mean()/la.shape[0]:.2f}) "
                f"ref=({xb.mean()/la.shape[1]:.2f},{yb.mean()/la.shape[0]:.2f})",
                _look_at_shift_ops(inspection, dcx, dcy, la.shape)))


def _look_at_shift_ops(inspection: dict, dcx: float, dcy: float,
                       shape) -> list:
    """Convert a screen-space saliency-centroid error into a concrete
    reframe_camera op: shift look_at along the camera's world right/up axes by
    the frame span at the subject's depth, so the composition slides toward
    the reference centroid."""
    import math
    cam = inspection.get("active_camera") or {}
    loc, rot = cam.get("location"), cam.get("rotation")
    lens = float(cam.get("lens_mm") or 50.0)
    sensor_w = float(cam.get("sensor_width") or 36.0)
    if not loc or not rot:
        return []
    subjects = _subject_objects(inspection)
    anchor = _centroid(_in_frame(subjects)) or _centroid(subjects)
    if not anchor:
        return []
    depth = math.dist(loc, anchor)
    if depth < 1e-4:
        return []
    w, h = shape[1], shape[0]
    frame_w = 2 * depth * (sensor_w / 2) / lens      # AUTO fit: horizontal
    frame_h = frame_w * h / w
    rx, ry, rz = rot
    # Blender XYZ euler: R = Rz @ Ry @ Rx; camera right = R@(1,0,0), up = R@(0,1,0)
    right = [math.cos(rz) * math.cos(ry),
             math.sin(rz) * math.cos(ry),
             -math.sin(ry)]
    up = [-math.sin(rz) * math.cos(rx) - math.cos(rz) * math.sin(ry) * math.sin(rx),
          math.cos(rz) * math.cos(rx) - math.sin(rz) * math.sin(ry) * math.sin(rx),
          math.cos(ry) * math.sin(rx)]
    # ours centroid right of ref -> aim further right (subject slides left)
    # ours centroid lower than ref (dcy>0) -> aim down (subject rises)
    new_look = [
        anchor[i] + right[i] * dcx * frame_w - up[i] * dcy * frame_h
        for i in range(3)
    ]
    return [{"op": "reframe_camera",
             "look_at": [round(v, 3) for v in new_look], "pull_back": 1.0}]

    # --- saliency coverage
    dcov = float(ma.mean() - mb.mean())
    if abs(dcov) > 0.04:
        sev = "fail" if abs(dcov) > 0.10 else "warn"
        if dcov > 0:
            out.append(_diag(
                sev, "ref.saliency_wide",
                "too much of the frame reads as salient — the reference keeps "
                "lit content sparse; darken broad surfaces or add a vignette",
                f"saliency coverage ours={ma.mean():.2f} ref={mb.mean():.2f}",
                [{"op": "apply_post", "schema": {
                    "post_preset": "custom", "effects": {"vignette": "subtle"}}}]))
        else:
            out.append(_diag(
                sev, "ref.saliency_thin",
                "too little salient content — the reference carries more lit "
                "accents; brighten the feature strips or add a light pool",
                f"saliency coverage ours={ma.mean():.2f} ref={mb.mean():.2f}",
                [{"op": "adjust_world", "strength_scale": 1.15}]))

    # --- edge mass: crisp CG edges vs photo edges
    dedg = float(ea.mean() - eb.mean())
    if dedg > 0.015:
        out.append(_diag(
            "warn", "ref.edge_excess",
            "render carries more edge mass than the reference — accent "
            "geometry is too thick or too numerous; thin the marker strips",
            f"edge density ours={ea.mean():.3f} ref={eb.mean():.3f}",
            []))


def diagnose(inspection: dict, image_metrics: dict | None = None,
             render_path: str | Path | None = None,
             reference_path: str | Path | None = None,
             readability_report: dict | None = None,
             lint=None) -> list[dict]:
    """Ordered diagnoses: fails first, then warnings, most-direct fixes first."""
    out: list[dict] = []
    _check_lint(lint, inspection, out)
    _check_exposure(image_metrics, out)
    _check_scene_richness(inspection, out)
    _check_buried_objects(inspection, out)
    _check_subject_visible(inspection, out)
    _check_materials(inspection, out)
    _check_readability(inspection, readability_report, out)
    if render_path:
        _check_frame_balance(render_path, inspection, out)
    if render_path and reference_path:
        _check_reference(render_path, reference_path, inspection, out)
    order = {"fail": 0, "warn": 1}
    out.sort(key=lambda d: order.get(d["severity"], 2))
    return out
