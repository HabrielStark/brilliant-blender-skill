#!/usr/bin/env python
# ruff: noqa: E402
"""CLI wrapper for prompt-scenario acceptance evals."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmarks.runners.run_prompt_scenarios import main

if __name__ == "__main__":
    raise SystemExit(main())
