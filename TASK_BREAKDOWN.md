# Skill Upgrade Goal — Evidence-Driven Blender Cinematic Workflow

## Goal contract

**Outcome:** Upgrade the existing Blender cinematic scene skill from a strong
scene recipe guide into a production-grade, self-verifying workflow that can
plan, delegate, render, inspect, export, report, and stop honestly.

**Audience:** AI coding agents and maintainers using Codex, Claude Code, Cursor,
Gemini CLI, or another Agent-Skills-compatible host.

**Deliverables:**

- explicit goal/checkpoint/evidence rules in `SKILL.md`;
- reusable sub-agent and visual/browser verification references;
- a machine-checkable skill self-audit and negative tests;
- README/authoring guidance grounded in the actual commands;
- validation evidence for Python, security, Node, web, and available visual paths.

**Non-goals:** redesign unrelated Blender builders, weaken the structured-op or
workspace safety model, add unpinned dependencies, require paid services, or
claim Blender/GPU/live/human proof that is unavailable in the environment.

## Requirements and acceptance gates

| ID | Requirement | Acceptance criterion | Verification |
|---|---|---|---|
| R1 | Goal contract | outcome, inputs, deliverables, non-goals, gates, and evidence root are required before scene work | SKILL.md + reference review |
| R2 | Checkpoint ledger | every meaningful iteration records hypothesis, files, commands, artifacts, result, and stop status | reference + negative tests |
| R3 | Sub-agent discipline | independent roles, raw-artifact prompts, ownership, merge, fallback, and stop rules are explicit | reference + skill self-audit |
| R4 | Visual truth | Blender previews and web canvases are actually inspected; desktop/mobile and console/network checks are required for web | reference + existing visual/e2e tests |
| R5 | Claim honesty | static/runtime/visual/human/live claim levels cannot be conflated | reference + skill self-audit |
| R6 | Machine guard | required sections, commands, and references are checked by a deterministic CLI | `python scripts/skill_self_audit.py` |
| R7 | Regression safety | current unit/security/repository/Node checks remain green | commands below |
| R8 | Runtime truth | malformed bridge recipes and truncated GLBs fail closed; latest failed evaluations and missing/stale render evidence cannot pass | focused negative tests + report tests |

## Execution phases

1. **Discovery:** inspect the current skill, tests, packaging, benchmarks, and
   visual tooling; record facts and limitations.
2. **Contract design:** define the goal, checkpoint, claim-level, delegation,
   and visual verification contracts.
3. **Implementation:** add references, self-audit CLI, and focused negative
   tests; wire the validator and docs.
4. **Integration:** run Python and Node checks, package validation, and browser/
   visual checks where the environment supports them.
5. **Final audit:** map every requirement to evidence, inspect the diff, and
   stop when no required criterion or new hypothesis remains.

## Validation commands

```text
python scripts/skill_self_audit.py
python scripts/validate_skill.py
python scripts/audit_repo_invariants.py
pytest tests/unit tests/security -q
python -m ruff check blender_cinematic mcp_server scripts tests
npm run build
npm test
npm run e2e                 # when browser dependencies are available
```

Blender integration and rendered benchmark commands are conditional on a
discoverable Blender executable. Their absence is recorded as a limitation,
never silently converted to a pass.

## Stop conditions

- **Done:** all required gates pass and the final evidence matrix has no unknowns.
- **Blocked:** a named external capability is required and cannot be supplied;
  report the exact command, error, and next decision.
- **Churn stop:** two consecutive checks produce no changed files, new failure,
  new hypothesis, or measurable improvement.

## Evidence log (this upgrade)

- Contract references, `SKILL.md`, README, authoring docs, CI, and changelog were
  updated; `TASK_BREAKDOWN.md` is the durable goal state.
- `python scripts/skill_self_audit.py --json` — PASS (5 required sections, 12
  linked references, 390 skill lines, no warnings).
- `python scripts/validate_skill.py` and `python scripts/audit_repo_invariants.py`
  — PASS.
- `pytest -q` — PASS; unit/security, MCP, Python web, visual regression, and
  Blender integration suites pass with Blender 5.0.1.
- `python -m ruff check blender_cinematic mcp_server scripts tests` and Bandit
  — PASS with no issues.
- `npm run build`, `npm test`, and `npm run e2e` — PASS; Chromium desktop/mobile
  canvas and animation checks pass with the stronger readable-silhouette gate.
- Representative Blender benchmark gate — PASS for product watch, reference
  match, turntable animation, and web scroll hero; naive and adversarial baselines
  fail as expected.
- End-to-end smoke with Blender 5.0.1 — PASS for the product-watch recipe: fresh
  preview, fresh 1920x1080 final render, GLB validation, score 99, and a passing
  final report. The inspected final render is readable and preserves the
  requested product anatomy; this is local evidence, not external production
  signoff.
- Visual contact sheet was generated and inspected at
  `artifacts/skill_upgrade_visual_review/contact_sheet.png`. It is automated
  evidence only; no human taste signoff is claimed.

## Honest remaining risks

- The repository still lacks a checked-in golden-image regression system,
  authenticated interactive bridge, server-side reference-metric provenance,
  full multi-format animation/video export, and cross-platform/GPU coverage.
- The current browser fixture proves the vendored GLB harness, not every generated
  React/R3F app variant. The skill now requires that distinction in its claim
  levels and final report.
