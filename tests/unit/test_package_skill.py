"""Release package tests."""
import json
import os
import zipfile

import pytest

from scripts import package_skill


def _write(path, text="x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_package_includes_open_source_docs(tmp_path, monkeypatch):
    for name in (
        "SKILL.md",
        "AGENTS.md",
        "README.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        ".gitignore",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "RUNBOOK.md",
        "CHANGELOG.md",
        "MANIFEST.in",
        ".env.example",
    ):
        _write(tmp_path / name)
    for folder in ("references", "scripts", "blender_cinematic"):
        _write(tmp_path / folder / "sample.txt")
    for folder in ("mcp_server", "web", "examples"):
        _write(tmp_path / folder / "sample.txt")
    for name in (
        "pyproject.toml",
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "playwright.config.mjs",
    ):
        _write(tmp_path / name, "{}")
    for doc in ("blender-addon.md", "security.md", "troubleshooting.md"):
        _write(tmp_path / "docs" / doc)
    _write(tmp_path / ".github" / "dependabot.yml")
    _write(tmp_path / ".github" / "workflows" / "ci.yml")
    _write(tmp_path / "addon" / "blender_cinematic_agent" / "__init__.py")

    monkeypatch.setattr(package_skill, "ROOT", tmp_path)
    assert package_skill.main(["--out", "dist"]) == 0

    with zipfile.ZipFile(tmp_path / "dist" / "blender-cinematic-scene-skill.zip") as zf:
        names = set(zf.namelist())
        assert "blender-cinematic-scene/LICENSE" in names
        assert "blender-cinematic-scene/THIRD_PARTY_NOTICES.md" in names
        assert "blender-cinematic-scene/.gitignore" in names
        assert "blender-cinematic-scene/.github/dependabot.yml" in names
        assert "blender-cinematic-scene/.github/workflows/ci.yml" in names
        assert "blender-cinematic-scene/MANIFEST.in" in names
        assert "blender-cinematic-scene/README.md" in names
        assert "blender-cinematic-scene/RUNBOOK.md" in names
        assert "blender-cinematic-scene/docs/security.md" in names
        assert "blender-cinematic-scene/mcp_server/sample.txt" in names
        assert "blender-cinematic-scene/web/sample.txt" in names
        assert "blender-cinematic-scene/examples/sample.txt" in names
        assert "blender-cinematic-scene/pyproject.toml" in names
        assert "blender-cinematic-scene/package.json" in names

    with zipfile.ZipFile(tmp_path / "dist" / "blender_cinematic_agent.zip") as zf:
        names = set(zf.namelist())
        assert "blender_cinematic_agent/LICENSE" in names
        assert "blender_cinematic_agent/blender-addon.md" in names


def test_npm_package_bin_target_is_distributable():
    package = json.loads((package_skill.ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["name"] == "brilliant-blender-skill"
    assert package["repository"]["url"].endswith("HabrielStark/brilliant-blender-skill.git")
    for bin_target in package["bin"].values():
        assert bin_target in package["files"] or any(
            bin_target.startswith(entry.rstrip("/") + "/") for entry in package["files"]
        )
        assert (package_skill.ROOT / bin_target).exists()
        assert (package_skill.ROOT / bin_target).read_text(encoding="utf-8").startswith(
            "#!/usr/bin/env node"
        )
    assert "README.md" in package["files"]
    assert "LICENSE" in package["files"]
    assert "docs/npm-github-install.md" in package["files"]
    assert "npm/cli.mjs" in package["files"]
    assert "web/dist/" in package["files"]
    assert "SKILL.md" not in package["files"]
    assert "benchmarks/live_agent_runs/*.json" not in package["files"]
    assert (package_skill.ROOT / "THIRD_PARTY_NOTICES.md").exists()


def test_package_rejects_symlink_member(tmp_path, monkeypatch):
    target = tmp_path / "outside-secret.txt"
    target.write_text("secret", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    link = docs / "leak.txt"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")

    monkeypatch.setattr(package_skill, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        with zipfile.ZipFile(tmp_path / "x.zip", "w") as zf:
            package_skill._zip_dir(zf, docs, "pkg")
