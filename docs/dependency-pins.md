# Dependency Pin Summary

Dependency freshness was checked on 2026-06-02 against PyPI, the npm registry,
and GitHub action tag refs. Runtime pins favor versions already verified by the
local test suite unless a package was already on the latest compatible release.

| Package | Chosen version | Source checked | Reason | Risk | Breaking changes |
|---|---:|---|---|---|---|
| pydantic | 2.12.5 | PyPI latest 2.13.4 | Current tested schema runtime; avoid unverified minor validation changes | Low | No |
| psutil | 6.1.1 | PyPI latest 7.2.2 | Current tested hardware preflight runtime | Low | Yes, 7.x major not adopted |
| mcp | 1.27.2 | PyPI latest 1.27.2 | First-class MCP runtime and console entry point dependency | Low | No |
| Pillow | 12.2.0 | PyPI latest 12.2.0 | Runtime image QA dependency; fixes PYSEC-2026-165 and related 12.1.1 advisories | Low | No |
| numpy | 1.26.4 | PyPI latest 2.4.6 | Runtime image metrics dependency; current tested broad-compatibility scientific stack | Medium | Yes, 2.x not adopted |
| scikit-image | 0.26.0 | PyPI latest 0.26.0 | Latest optional SSIM dependency | Low | No |
| nvidia-ml-py | 13.610.43 | PyPI latest 13.610.43 | Maintained optional NVIDIA/NVML detection dependency | Low | No |
| pytest | 9.0.3 | PyPI latest 9.0.3 | Latest local test runner | Low | No |
| pytest-cov | 7.1.0 | PyPI latest 7.1.0 | Latest tested coverage plugin | Low | No |
| jsonschema | 4.26.0 | PyPI latest 4.26.0 | Latest local schema validation dependency | Low | No |
| pip-audit | 2.10.0 | PyPI latest 2.10.0 | Latest CI dependency-audit runner | Low | No |
| build | 1.5.0 | PyPI latest 1.5.0 | Latest Python package build frontend | Low | No |
| twine | 6.2.0 | PyPI latest 6.2.0 | Latest distribution metadata checker | Low | No |
| cyclonedx-bom | 7.3.0 | PyPI latest 7.3.0 | Latest Python CycloneDX SBOM generator | Low | No |
| ruff | 0.15.15 | PyPI latest 0.15.15 | Latest Python lint/static-quality gate | Low | No |
| bandit | 1.9.4 | PyPI latest 1.9.4 | Latest Python static security scanner | Low | No |
| @gltf-transform/core | 4.1.1 | npm latest 4.3.0 | Current tested GLB validation runtime | Low | No |
| @gltf-transform/extensions | 4.1.1 | npm latest 4.3.0 | Kept in lockstep with core for GLB extension parsing | Low | No |
| sharp | 0.33.5 | npm latest 0.34.5 | Dev-only Playwright screenshot sanity dependency; excluded from global skill install runtime | Medium | No |
| three | 0.160.1 | npm latest 0.184.0 | Current tested generated viewer/runtime import target | Medium | Yes, many minor releases skipped |
| typescript | 5.7.2 | npm latest 6.0.3 | Current tested compiler; avoid unverified major upgrade | Medium | Yes, 6.x not adopted |
| @types/node | 22.10.2 | npm latest 25.9.1 | Matches conservative Node 20/22 development target | Low | No |
| @playwright/test | 1.60.0 | npm latest 1.60.0 | Fixes GHSA-7mvr-c777-76hp in older Playwright releases | Low | No |

GitHub Actions are pinned by commit SHA:

| Action | Ref |
|---|---|
| actions/checkout v4 | `34e114876b0b11c390a56381ad16ebd13914f8d5` |
| actions/setup-python v5 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| actions/setup-node v4 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| github/codeql-action v3 | `b22c66273205240d86582638b860f9b25772b4d3` |
