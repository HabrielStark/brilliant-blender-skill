"""Repository-level invariant audit tests."""
import json
from pathlib import Path

from scripts.audit_repo_invariants import audit_repo


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _minimal_metadata(root: Path) -> None:
    _write(
        root / "pyproject.toml",
        """
[build-system]
requires = ["setuptools==78.1.1"]
build-backend = "setuptools.build_meta"

[project]
dependencies = ["pydantic==2.12.5"]

[project.optional-dependencies]
dev = ["pytest==9.0.3"]
""".strip(),
    )
    _write(
        root / "package.json",
        json.dumps(
            {
                "dependencies": {"three": "0.160.1"},
                "devDependencies": {"typescript": "5.7.2"},
                "optionalDependencies": {"@playwright/test": "1.60.0"},
            }
        ),
    )
    _write(
        root / ".github" / "workflows" / "ci.yml",
        """
name: CI
jobs:
  test:
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5
""".strip(),
    )


def test_current_repository_invariants_pass():
    assert audit_repo() == []


def test_repo_invariant_audit_catches_drift(tmp_path):
    _minimal_metadata(tmp_path)
    _write(tmp_path / "blender_cinematic" / "bad.py", "import bpy\n")
    _write(
        tmp_path / "scripts" / "bad.py",
        """
import subprocess
from pathlib import Path

subprocess.run(["echo", "x"], shell=True)
Path("x").write_text("x")
""".strip(),
    )
    _write(
        tmp_path / "pyproject.toml",
        """
[build-system]
requires = ["setuptools>=78"]
build-backend = "setuptools.build_meta"

[project]
dependencies = ["pydantic>=2"]
""".strip(),
    )
    _write(tmp_path / "package.json", json.dumps({"dependencies": {"three": "^0.160.1"}}))
    _write(
        tmp_path / ".github" / "workflows" / "ci.yml",
        "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v4\n",
    )

    errors = "\n".join(audit_repo(tmp_path))
    assert "imports bpy" in errors
    assert "shell=True" in errors
    assert "calls subprocess.run" in errors
    assert "writes via write_text" in errors
    assert "dependency is not exact-pinned" in errors
    assert "dependencies.three is not exact-pinned" in errors
    assert "action is not pinned by commit SHA" in errors
