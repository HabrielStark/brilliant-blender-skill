#!/usr/bin/env python
"""Locate a Blender executable and report version + Cycles render devices."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic import blender as b


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Locate and probe Blender")
    ap.add_argument("--blender", default=None, help="explicit executable to probe")
    ap.add_argument("--devices", action="store_true", help="also enumerate Cycles devices (launches Blender)")
    args = ap.parse_args(argv)

    exe = b.locate_blender(args.blender)
    out = {"found": exe is not None, "path": exe}
    if exe:
        out["version"] = b.blender_version(exe)
        if args.devices:
            out["render_devices"] = b.query_render_devices(exe)
    print(json.dumps(out, indent=2))
    return 0 if exe else 1


if __name__ == "__main__":
    raise SystemExit(main())
