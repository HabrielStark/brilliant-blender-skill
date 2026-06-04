# Contributing

This project favors small, verified changes over broad rewrites.

## Local Setup

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install -e ".[dev]"
npm ci
```

## Required Checks

```bash
pytest tests/unit tests/security -q
ruff check blender_cinematic mcp_server scripts tests
python scripts/audit_repo_invariants.py
bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon
pytest tests -q
python scripts/validate_skill.py
python -m build --sdist --wheel
python -m twine check dist/*.tar.gz dist/*.whl
python scripts/package_skill.py --out dist
python scripts/generate_sbom.py --out dist
python scripts/assert_release_artifacts.py --dist dist
npm run build
npm test
npm audit --package-lock-only --audit-level=high
npm pack --dry-run
```

Run Blender integration tests when Blender is available:

```bash
BLENDER_EXECUTABLE=/path/to/blender pytest tests/integration_blender -q
```

## Change Rules

- Keep `blender_cinematic/` pure Python and free of `bpy`.
- Add structured recipe operations instead of arbitrary Python execution.
- Route writes through `WorkspaceResolver`.
- Use `run_checked` for subprocesses.
- Pin dependencies exactly and update lockfiles.
- Add or update tests for schema, safety, and user-facing behavior changes.
