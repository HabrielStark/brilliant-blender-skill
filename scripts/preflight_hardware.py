#!/usr/bin/env python
"""Hardware preflight + profile/budget selection -> hardware_report.json."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.preflight import main

if __name__ == "__main__":
    raise SystemExit(main())
