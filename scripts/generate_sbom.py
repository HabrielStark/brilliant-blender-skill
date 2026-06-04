#!/usr/bin/env python
"""Generate release SBOMs for Python and Node dependencies."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from blender_cinematic.security import run_checked
from blender_cinematic.workspace import WorkspaceResolver

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate CycloneDX SBOMs")
    ap.add_argument("--out", default="dist", help="output directory inside the repository")
    args = ap.parse_args(argv)

    resolver = WorkspaceResolver([ROOT])
    out = resolver.ensure_dir(args.out)
    py_sbom = resolver.resolve(out / "python-sbom.cdx.json")
    npm_sbom = resolver.resolve(out / "npm-sbom.cdx.json")
    npm_exe = shutil.which("npm")
    if not npm_exe:
        raise RuntimeError("npm executable not found on PATH")

    run_checked(
        [
            sys.executable,
            "-m",
            "cyclonedx_py",
            "environment",
            "--pyproject",
            "pyproject.toml",
            "--mc-type",
            "library",
            "--output-reproducible",
            "--of",
            "JSON",
            "-o",
            str(py_sbom),
        ],
        timeout=120,
        cwd=str(ROOT),
    )
    npm_proc = run_checked(
        [npm_exe, "sbom", "--sbom-format", "cyclonedx", "--package-lock-only"],
        timeout=120,
        cwd=str(ROOT),
    )
    resolver.write_text(npm_sbom, npm_proc.stdout or "")

    for path in (py_sbom, npm_sbom):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("bomFormat") != "CycloneDX":
            raise ValueError(f"{path} is not a CycloneDX SBOM")

    checksums = resolver.write_text(
        out / "sbom-checksums.sha256",
        "".join(f"{_sha256(path)}  {path.name}\n" for path in (py_sbom, npm_sbom)),
    )
    print(json.dumps({
        "python_sbom": str(py_sbom),
        "npm_sbom": str(npm_sbom),
        "checksums": str(checksums),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
