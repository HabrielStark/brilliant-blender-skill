#!/usr/bin/env python
"""Lint a scene-inspection JSON (no Blender required)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.linters import lint_scene


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scene lint")
    ap.add_argument("inspection", help="scene-inspection JSON")
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--budget", default=None)
    args = ap.parse_args(argv)

    insp = json.loads(Path(args.inspection).read_text(encoding="utf-8"))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8")) if args.manifest else None
    budget = json.loads(Path(args.budget).read_text(encoding="utf-8")) if args.budget else None
    result = lint_scene(insp, manifest, budget)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
