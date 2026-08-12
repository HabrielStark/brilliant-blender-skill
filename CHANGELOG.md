# Changelog

## 0.1.0 - Unreleased

- Added an evidence-driven execution contract: durable goal/checkpoint ledgers,
  claim levels, bounded sub-agent review, actual-pixel/browser verification, a
  deterministic `scripts/skill_self_audit.py` gate, and negative tests for
  contract drift.
- Hardened GLB chunk-boundary parsing so truncated or unaligned chunks fail
  closed instead of being reported as valid.
- Added production CI for Python unit/security tests, skill validation, Node
  build, Node tests, Playwright e2e, and dependency audits.
- Pinned Python and Node dependencies exactly for reproducible installs.
- Hardened runner, web generation, packaging, export, and preflight writes so
  generated outputs stay inside workspace sandboxes.
- Added open-source `SECURITY.md`, `CONTRIBUTING.md`, and dependency pin docs.
- Added visual anti-slop acceptance reporting, 4/4 prompt-scenario render
  coverage, and archived live-agent render evidence for all four prompt
  families: product watch, reference match, shader/texture, and turntable
  animation.
- Added NPM/GitHub install support through the `brilliant-blender-skill` CLI,
  including `install`, `doctor`, package tests, and install documentation.
