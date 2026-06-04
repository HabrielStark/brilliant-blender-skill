#!/usr/bin/env python
"""Compute a hardware-aware render budget (SRS 9.5)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.budget import compute_budget


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Render budget")
    ap.add_argument("--hardware", required=True, help="hardware_report.json")
    ap.add_argument("--profile", default="auto")
    ap.add_argument("--final", default=None, help="final resolution WxH, e.g. 3840x2160")
    args = ap.parse_args(argv)

    report = json.loads(Path(args.hardware).read_text(encoding="utf-8"))
    final = [int(x) for x in args.final.lower().split("x")] if args.final else None
    print(json.dumps(compute_budget(report, args.profile, final), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
