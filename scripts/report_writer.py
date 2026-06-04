#!/usr/bin/env python
"""Write the final report from a task artifacts directory (SRS 7.3)."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.report import build_final_report
from blender_cinematic.workspace import WorkspaceResolver


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Final report writer")
    ap.add_argument("task_dir")
    ap.add_argument("--limitation", action="append", default=[])
    args = ap.parse_args(argv)

    base = Path(args.task_dir).resolve()
    md, report = build_final_report(base, notes=args.limitation)
    resolver = WorkspaceResolver([base])
    md_path = resolver.write_text(base / "final" / "final_report.md", md)
    import json
    json_path = resolver.write_text(base / "final" / "final_report.json", json.dumps(report, indent=2))
    print(f"wrote {md_path}\nwrote {json_path}\npassed={report['passed']} best_score={report['best_score']}")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
