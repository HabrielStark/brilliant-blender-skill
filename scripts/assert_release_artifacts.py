#!/usr/bin/env python
"""Assert that release artifacts contain the files needed for redistribution."""
from __future__ import annotations

import argparse
import hashlib
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDIST = "blender_cinematic_agent_skill-0.1.0.tar.gz"
WHEEL = "blender_cinematic_agent_skill-0.1.0-py3-none-any.whl"
SKILL_ZIP = "blender-cinematic-scene-skill.zip"
ADDON_ZIP = "blender_cinematic_agent.zip"
CHECKSUMS = "checksums.sha256"
SBOM_CHECKSUMS = "sbom-checksums.sha256"
NPM_TARBALL = "brilliant-blender-skill-0.1.0.tgz"

REQUIRED_SDIST = {
    ".gitignore",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "docs/dependency-pins.md",
    "THIRD_PARTY_NOTICES.md",
    "web/dist/web_validate_asset.js",
    "MANIFEST.in",
    "scripts/audit_repo_invariants.py",
    "scripts/assert_release_artifacts.py",
    "scripts/assert_visual_acceptance.py",
    "scripts/blind_visual_eval.py",
    "scripts/visual_review_pack.py",
    "addon/blender_cinematic_agent/job_runner.py",
    "benchmarks/runners/run_benchmarks.py",
    "tests/unit/test_repo_invariants.py",
}
REQUIRED_SKILL_SOURCE = {
    ".gitignore",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "docs/dependency-pins.md",
    "THIRD_PARTY_NOTICES.md",
    "web/dist/web_validate_asset.js",
    "MANIFEST.in",
    "scripts/audit_repo_invariants.py",
    "scripts/assert_release_artifacts.py",
    "scripts/assert_visual_acceptance.py",
    "scripts/blind_visual_eval.py",
    "scripts/visual_review_pack.py",
    "benchmarks/runners/run_prompt_scenarios.py",
    "benchmarks/prompt_scenarios/product_watch_prompt.json",
    "benchmarks/prompt_scenarios/reference_match_prompt.json",
    "benchmarks/prompt_scenarios/shader_texture_prompt.json",
    "benchmarks/prompt_scenarios/turntable_animation_prompt.json",
    "benchmarks/live_agent_runs/watch_live_agent_forward_v6_20260604.json",
    "benchmarks/live_agent_runs/reference_match_live_agent_forward_v12_20260604.json",
    "benchmarks/live_agent_runs/shader_texture_live_agent_forward_v6_20260604.json",
    "benchmarks/live_agent_runs/turntable_animation_live_agent_forward_v2_20260604.json",
    "tests/unit/test_prompt_scenarios.py",
    "tests/unit/test_release_status.py",
}
REQUIRED_SKILL = {f"blender-cinematic-scene/{name}" for name in REQUIRED_SKILL_SOURCE} | {
    "blender-cinematic-scene/package.json",
}
REQUIRED_ADDON = {
    "blender_cinematic_agent/LICENSE",
    "blender_cinematic_agent/blender-addon.md",
    "blender_cinematic_agent/security.md",
    "blender_cinematic_agent/troubleshooting.md",
}
REQUIRED_NPM_TARBALL = {
    "SKILL.md",
    "npm/cli.mjs",
    "docs/VISUAL_ACCEPTANCE_REPORT.md",
    "docs/npm-github-install.md",
    "benchmarks/prompt_scenarios/product_watch_prompt.json",
    "benchmarks/live_agent_runs/watch_live_agent_forward_v6_20260604.json",
    "benchmarks/live_agent_runs/reference_match_live_agent_forward_v12_20260604.json",
    "benchmarks/live_agent_runs/shader_texture_live_agent_forward_v6_20260604.json",
    "benchmarks/live_agent_runs/turntable_animation_live_agent_forward_v2_20260604.json",
    "web/dist/web_validate_asset.js",
}


def _assert_missing(label: str, names: set[str], required: set[str]) -> None:
    missing = sorted(required - names)
    if missing:
        raise AssertionError(f"{label} missing required files: {missing}")


def _sdist_names(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as tar:
        return {name.split("/", 1)[1] if "/" in name else name for name in tar.getnames()}


def _tar_names(path: Path) -> set[str]:
    with tarfile.open(path, "r:gz") as tar:
        return set(tar.getnames())


def _zip_names(path: Path) -> set[str]:
    with zipfile.ZipFile(path) as zf:
        return set(zf.namelist())


def _wheel_metadata(path: Path) -> str:
    with zipfile.ZipFile(path) as zf:
        metadata_name = next(name for name in zf.namelist() if name.endswith("METADATA"))
        return zf.read(metadata_name).decode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_checksum_file(dist: Path, checksum_file: str, expected_names: set[str]) -> None:
    path = dist / checksum_file
    if not path.is_file():
        raise AssertionError(f"missing checksum artifact: {path}")
    seen: dict[str, str] = {}
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            digest, name = line.split(None, 1)
        except ValueError as exc:
            raise AssertionError(f"{checksum_file}:{lineno} malformed checksum line") from exc
        name = name.strip()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
            raise AssertionError(f"{checksum_file}:{lineno} invalid sha256 digest")
        seen[name] = digest.lower()
    missing = expected_names - set(seen)
    extra = set(seen) - expected_names
    if missing or extra:
        raise AssertionError(f"{checksum_file} names mismatch: missing={sorted(missing)} extra={sorted(extra)}")
    for name, digest in seen.items():
        artifact = dist / name
        if not artifact.is_file():
            raise AssertionError(f"{checksum_file} references missing artifact: {name}")
        actual = _sha256(artifact)
        if actual != digest:
            raise AssertionError(f"{checksum_file} checksum mismatch for {name}")


def assert_release_artifacts(dist: Path) -> None:
    sdist = dist / SDIST
    wheel = dist / WHEEL
    skill = dist / SKILL_ZIP
    addon = dist / ADDON_ZIP
    for path in (
        sdist,
        wheel,
        skill,
        addon,
        dist / NPM_TARBALL,
        dist / "python-sbom.cdx.json",
        dist / "npm-sbom.cdx.json",
        dist / CHECKSUMS,
        dist / SBOM_CHECKSUMS,
    ):
        if not path.is_file():
            raise AssertionError(f"missing artifact: {path}")

    _assert_missing("sdist", _sdist_names(sdist), REQUIRED_SDIST)
    _assert_missing("skill zip", _zip_names(skill), REQUIRED_SKILL)
    _assert_missing("add-on zip", _zip_names(addon), REQUIRED_ADDON)
    npm_names = _sdist_names(dist / NPM_TARBALL)
    _assert_missing("npm tarball", npm_names, REQUIRED_NPM_TARBALL)
    generated = sorted(
        name for name in _tar_names(dist / NPM_TARBALL) if "__pycache__" in name or name.endswith(".pyc")
    )
    if generated:
        raise AssertionError(f"npm tarball contains generated Python cache files: {generated[:10]}")

    metadata = _wheel_metadata(wheel)
    if 'Requires-Dist: nvidia-ml-py==13.610.43; extra == "nvidia"' not in metadata:
        raise AssertionError("wheel metadata missing pinned nvidia-ml-py optional dependency")
    if "Requires-Dist: pynvml" in metadata:
        raise AssertionError("wheel metadata still references deprecated pynvml distribution")

    web_cli = ROOT / "web" / "dist" / "web_validate_asset.js"
    if not web_cli.read_text(encoding="utf-8").startswith("#!/usr/bin/env node"):
        raise AssertionError("web/dist/web_validate_asset.js is missing node shebang")
    _assert_checksum_file(dist, CHECKSUMS, {SKILL_ZIP, ADDON_ZIP})
    _assert_checksum_file(dist, SBOM_CHECKSUMS, {"python-sbom.cdx.json", "npm-sbom.cdx.json"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", default="dist", help="release artifact directory")
    args = parser.parse_args(argv)
    assert_release_artifacts((ROOT / args.dist).resolve())
    print("RELEASE ARTIFACT ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
