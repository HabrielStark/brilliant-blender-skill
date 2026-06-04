#!/usr/bin/env python
"""Generate a human-reviewable visual benchmark pack."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.visual_review import write_review_pack
from blender_cinematic.workspace import WorkspaceResolver

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--summary",
        default=str(ROOT / "benchmarks" / "results" / "summary.json"),
        help="benchmark summary JSON produced by benchmarks/runners/run_benchmarks.py",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "visual_review_pack"),
        help="output directory inside this repository",
    )
    parser.add_argument(
        "--min-score-delta",
        type=float,
        default=40.0,
        help="minimum required skill score improvement over the naive baseline",
    )
    parser.add_argument(
        "--human-review",
        default=None,
        help="optional human_review.json with per-task visual signoff",
    )
    parser.add_argument(
        "--require-human-signoff",
        action="store_true",
        default=True,
        help="fail the pack unless human_review.json approves every task with strong ratings (default)",
    )
    parser.add_argument(
        "--allow-unreviewed",
        action="store_false",
        dest="require_human_signoff",
        help="generate an automated evidence pack without claiming human visual signoff",
    )
    args = parser.parse_args(argv)

    resolver = WorkspaceResolver([ROOT])
    manifest = write_review_pack(
        args.summary,
        args.out,
        resolver,
        min_score_delta=args.min_score_delta,
        human_review_path=args.human_review,
        require_human_signoff=args.require_human_signoff,
    )
    artifacts = manifest["artifacts"]
    print(f"visual review status: {manifest['status']}")
    print(f"markdown: {artifacts['markdown']}")
    print(f"contact sheet: {artifacts['contact_sheet']}")
    print(f"human review template: {artifacts['human_review_template']}")
    if manifest["failures"]:
        print("failures:")
        for failure in manifest["failures"]:
            print(f"- {failure}")
    return 0 if manifest["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
