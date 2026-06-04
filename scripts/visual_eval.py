#!/usr/bin/env python
"""Render sanity metrics + optional rubric score for a preview image (SRS 15.2)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.evaluation import score_iteration
from blender_cinematic.imaging import image_sanity, render_sanity_issues, ssim
from blender_cinematic.linters import lint_scene


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Visual evaluation")
    ap.add_argument("image")
    ap.add_argument("--inspection", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--reference", default=None, help="reference image for SSIM")
    args = ap.parse_args(argv)

    metrics = image_sanity(args.image)
    out = {"metrics": metrics, "sanity_issues": render_sanity_issues(metrics)}
    if args.reference:
        out["ssim_to_reference"] = round(ssim(args.image, args.reference), 4)
    if args.inspection:
        insp = json.loads(Path(args.inspection).read_text(encoding="utf-8"))
        manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8")) if args.manifest else None
        lint = lint_scene(insp, manifest)
        ref = {"ssim": out.get("ssim_to_reference", 0)} if args.reference else None
        out["evaluation"] = score_iteration(1, insp, lint, metrics, manifest, reference_metrics=ref).to_dict()
    print(json.dumps(out, indent=2))
    return 0 if not out["sanity_issues"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
