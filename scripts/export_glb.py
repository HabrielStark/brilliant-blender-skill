#!/usr/bin/env python
"""Export a .blend to GLB via Blender and validate the result (SRS 14.2)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic import runner
from blender_cinematic.glb import validate_glb


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Export + validate GLB")
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blender", default=None)
    ap.add_argument("--max-mb", type=float, default=None)
    args = ap.parse_args(argv)

    blend = Path(args.blend).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    job = runner.build_job("export_glb", out.parent, blend, output={"glb": str(out)})
    res = runner.run_job(job, args.blender, timeout=300)
    result = {"export": res.get("export", res)}
    if out.exists():
        result["validation"] = validate_glb(out, args.max_mb)
    print(json.dumps(result, indent=2))
    return 0 if out.exists() and result.get("validation", {}).get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
