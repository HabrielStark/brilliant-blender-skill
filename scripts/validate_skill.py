#!/usr/bin/env python
"""Validate the skill package: SKILL.md frontmatter, references, core imports."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.skill_self_audit import REQUIRED_REFERENCES, audit_skill  # noqa: E402

REQUIRED_FRONTMATTER = ("name", "description")


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out = {}
    for line in text[3:end].strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def main() -> int:
    errors: list[str] = []
    skill = ROOT / "SKILL.md"
    if not skill.exists():
        errors.append("SKILL.md missing")
    else:
        fm = _parse_frontmatter(skill.read_text(encoding="utf-8"))
        for key in REQUIRED_FRONTMATTER:
            if not fm.get(key):
                errors.append(f"SKILL.md frontmatter missing '{key}'")
        if fm.get("name") and " " in fm["name"]:
            errors.append("skill name must not contain spaces")

    for ref in REQUIRED_REFERENCES:
        if not (ROOT / "references" / ref).exists():
            errors.append(f"missing reference: {ref}")

    contract = audit_skill(ROOT)
    errors.extend(contract.get("errors", []))

    try:
        from blender_cinematic.schemas import SceneManifest
        SceneManifest(task_id="t", brief="b", output_mode="still")
    except Exception as exc:
        errors.append(f"core import/schema check failed: {exc}")

    if errors:
        print("SKILL VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("SKILL VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
