#!/usr/bin/env python
"""Validate or summarise a scene manifest (SRS 8)."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.schemas import SceneManifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Scene manifest tool")
    ap.add_argument("command", choices=["validate", "show"])
    ap.add_argument("path")
    args = ap.parse_args(argv)

    raw = json.loads(Path(args.path).read_text(encoding="utf-8"))
    try:
        manifest = SceneManifest.model_validate(raw)
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 1
    if args.command == "show":
        print(manifest.model_dump_json(indent=2))
    else:
        print(json.dumps({"valid": True, "task_id": manifest.task_id,
                          "output_mode": manifest.output_mode,
                          "wants_web": manifest.wants_web(),
                          "wants_animation": manifest.wants_animation()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
