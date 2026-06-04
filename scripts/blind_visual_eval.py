#!/usr/bin/env python
"""Generate a blind human-style visual eval packet."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.blind_review import write_blind_eval_pack
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
        "--tasks-dir",
        default=str(ROOT / "benchmarks" / "tasks"),
        help="directory containing benchmark task JSON files",
    )
    parser.add_argument(
        "--out",
        default=str(ROOT / "artifacts" / "blind_visual_eval"),
        help="output directory inside this repository",
    )
    parser.add_argument("--seed", type=int, default=20260603, help="stable shuffle seed")
    parser.add_argument("--human-review", default=None, help="optional blind review JSON")
    parser.add_argument(
        "--require-human-signoff",
        action="store_true",
        default=True,
        help="fail unless blind review JSON approves every item with strong ratings (default)",
    )
    parser.add_argument(
        "--allow-unreviewed",
        action="store_false",
        dest="require_human_signoff",
        help="generate the blind packet without claiming human visual signoff",
    )
    args = parser.parse_args(argv)

    resolver = WorkspaceResolver([ROOT])
    manifest = write_blind_eval_pack(
        args.summary,
        args.tasks_dir,
        args.out,
        resolver,
        seed=args.seed,
        human_review_path=args.human_review,
        require_human_signoff=args.require_human_signoff,
    )
    artifacts = manifest["artifacts"]
    print(f"blind visual eval status: {manifest['status']}")
    print(f"markdown: {artifacts['markdown']}")
    print(f"contact sheet: {artifacts['contact_sheet']}")
    print(f"review template: {artifacts['review_template']}")
    print(f"private mapping: {artifacts['private_mapping']}")
    if manifest["failures"]:
        print("failures:")
        for failure in manifest["failures"]:
            print(f"- {failure}")
    return 0 if manifest["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
