#!/usr/bin/env python
"""Audit the machine-checkable contract of the installed Blender skill."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_SECTIONS = (
    "## Goal contract (write before scene work)",
    "## Sub-agents and independent review",
    "## Evidence and claim levels",
    "## Visual and browser verification",
    "## Stop, recovery, and escalation",
)

REQUIRED_REFERENCES = (
    "camera-language.md",
    "composition-rubric.md",
    "lighting-materials.md",
    "procedural-modeling-recipes.md",
    "animation-camera-paths.md",
    "web-export-threejs-r3f.md",
    "hardware-quality-profiles.md",
    "visual-critique-rubric.md",
    "failure-modes.md",
    "evidence-contract.md",
    "agent-orchestration.md",
    "visual-verification.md",
)

REQUIRED_COMMANDS = (
    "scripts/scene_manifest.py",
    "scripts/preflight_hardware.py",
    "scripts/render_budget.py",
    "scripts/visual_eval.py",
    "scripts/scene_lint.py",
    "scripts/report_writer.py",
)


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    values: dict[str, str] = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key.strip()] = value.strip().strip('"')
    return values


def audit_skill(root: Path = ROOT) -> dict[str, Any]:
    """Return a deterministic, read-only audit report for a skill checkout."""
    root = root.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        return {
            "schema": "blender_cinematic_skill_audit/0.1",
            "status": "FAIL",
            "errors": ["SKILL.md missing"],
            "warnings": [],
        }

    text = skill_path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)
    for key in ("name", "description"):
        if not frontmatter.get(key):
            errors.append(f"SKILL.md frontmatter missing '{key}'")
    if frontmatter.get("name") and " " in frontmatter["name"]:
        errors.append("skill name must not contain spaces")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            errors.append(f"SKILL.md missing required section: {section}")
    for command in REQUIRED_COMMANDS:
        if command not in text:
            errors.append(f"SKILL.md missing required command reference: {command}")
    for reference in REQUIRED_REFERENCES:
        path = root / "references" / reference
        if not path.is_file():
            errors.append(f"missing reference: {reference}")
        elif f"references/{reference}" not in text:
            warnings.append(f"reference exists but is not linked from SKILL.md: {reference}")

    required_terms = {
        "sub-agent": "delegation language",
        "claim level": "claim-level honesty",
        "mobile": "mobile visual verification",
        "human review": "review integrity",
        "checkpoint ledger": "checkpoint evidence",
    }
    lowered = text.lower()
    for term, label in required_terms.items():
        if term not in lowered:
            errors.append(f"SKILL.md missing {label} term: {term}")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "schema": "blender_cinematic_skill_audit/0.1",
        "status": "PASS" if not errors else "FAIL",
        "errors": errors,
        "warnings": warnings,
        "skill_sha256": digest,
        "skill_lines": len(text.splitlines()),
        "required_sections": len(REQUIRED_SECTIONS),
        "required_references": len(REQUIRED_REFERENCES),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="skill checkout to audit")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)
    report = audit_skill(Path(args.root))
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"SKILL SELF-AUDIT {report['status']}")
        for error in report.get("errors", []):
            print(f"- ERROR: {error}")
        for warning in report.get("warnings", []):
            print(f"- WARNING: {warning}")
        if report["status"] == "PASS":
            print(
                f"- sections={report['required_sections']} "
                f"references={report['required_references']} "
                f"lines={report['skill_lines']}"
            )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
