# Runbook

This project is local-first. Normal operation should not require secrets or paid
APIs.

## Install

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install -e ".[dev]"
npm ci
npx playwright install chromium
```

Set `BLENDER_EXECUTABLE` only when Blender cannot be auto-detected.

## Health Checks

```bash
python scripts/blender_locator.py
python scripts/preflight_hardware.py --project-dir artifacts/healthcheck
pytest tests/unit tests/security -q
ruff check blender_cinematic mcp_server scripts tests
python scripts/audit_repo_invariants.py
bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon
npm run build
npm test
npm run e2e
python -m pip_audit .
npm audit --package-lock-only --audit-level=high
python scripts/generate_sbom.py --out dist
python scripts/assert_release_artifacts.py --dist dist
```

## Real Pipeline Smoke Test

```bash
python scripts/run_blender_job.py \
  --manifest examples/prompts/product_hero_watch.json \
  --recipe examples/prompts/product_hero_watch.recipe.json
```

Expected result: JSON summary with `"passed": true`, a positive score, preview
PNG, final `.blend`, final GLB, and `final_report.md` under
`artifacts/product_hero_watch/`.

## Release Packaging

```bash
python scripts/package_skill.py --out dist
python -m build --sdist --wheel
python -m twine check dist/*.tar.gz dist/*.whl
python scripts/generate_sbom.py --out dist
python scripts/audit_repo_invariants.py
python scripts/assert_release_artifacts.py --dist dist
Get-Content dist/checksums.sha256
Get-Content dist/sbom-checksums.sha256
```

Publish both zip files, Python distributions, SBOMs, and checksum files
together. Do not publish local `artifacts/`, `.venv/`, `node_modules/`,
`test-results/`, or `.env`.

## Incident Response

1. Reproduce with the smallest manifest/recipe and keep generated artifacts.
2. Run `pytest tests/unit tests/security -q` before changing code.
3. For path, subprocess, bridge, or raw-Python issues, inspect `SECURITY.md`
   boundaries first.
4. If a dependency advisory appears, update the exact pin and lockfile, then run
   both Python and Node audits.
5. Regenerate release packages only after tests and audits are green.

## Rollback

Use the previous release zip plus its checksum. Generated artifacts are
workspace-local and can be removed without affecting source releases.
