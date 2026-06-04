#!/usr/bin/env python
"""Package the skill folder and the Blender add-on into release zips + checksums (SRS 27)."""
import argparse
import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from blender_cinematic.workspace import WorkspaceResolver  # noqa: E402

SKILL_INCLUDE = [
    "SKILL.md",
    "AGENTS.md",
    "README.md",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    ".gitignore",
    ".github",
    "MANIFEST.in",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "RUNBOOK.md",
    "CHANGELOG.md",
    ".env.example",
    "docs",
    "references",
    "scripts",
    "benchmarks",
    "blender_cinematic",
    "mcp_server",
    "web",
    "examples",
    "tests",
    "pyproject.toml",
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "playwright.config.mjs",
]
ADDON_DOCS = ["LICENSE", "docs/blender-addon.md", "docs/security.md", "docs/troubleshooting.md"]


def _assert_packaged_path_safe(path: Path) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing to package symlink: {path}")
    target = path.resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ValueError(f"refusing to package path outside repository: {path}")


def _zip_dir(zf: zipfile.ZipFile, src: Path, arc_root: str) -> None:
    _assert_packaged_path_safe(src)
    if src.is_file():
        zf.write(src, f"{arc_root}/{src.name}")
        return
    for p in sorted(src.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            _assert_packaged_path_safe(p)
            zf.write(p, f"{arc_root}/{p.relative_to(src.parent)}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Package skill + add-on")
    ap.add_argument("--out", default="dist")
    args = ap.parse_args(argv)

    resolver = WorkspaceResolver([ROOT])
    out = resolver.ensure_dir(args.out)

    skill_zip = out / "blender-cinematic-scene-skill.zip"
    with zipfile.ZipFile(skill_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in SKILL_INCLUDE:
            _zip_dir(zf, ROOT / item, "blender-cinematic-scene")

    addon_zip = out / "blender_cinematic_agent.zip"
    with zipfile.ZipFile(addon_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        _zip_dir(zf, ROOT / "addon" / "blender_cinematic_agent", "blender_cinematic_agent")
        for item in ADDON_DOCS:
            src = ROOT / item
            if src.exists():
                zf.write(src, f"blender_cinematic_agent/{src.name}")

    sums = out / "checksums.sha256"
    resolver.write_text(sums, "".join(f"{_sha256(z)}  {z.name}\n" for z in (skill_zip, addon_zip)))
    print(f"skill package: {skill_zip}\naddon package: {addon_zip}\nchecksums:     {sums}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
