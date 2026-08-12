# Blender Cinematic Agent Skill

A **skill-driven Blender production pipeline** for AI coding agents (Codex, Claude
Code, Cursor, Gemini CLI, and any Agent-Skills-compatible host). It is **not just
a Blender MCP**: MCP gives the agent *tools*; this project gives the agent *rules,
taste, tests and iteration behaviour* so it builds artistically and technically
sound 3D scenes instead of dumping random primitives.

The goal is **not** magical one-shot perfection. The goal is **controlled
improvement within at most 10 iterations**, with hardware-aware rendering, honest
visual QA, and validated web/GLB export. The primary product promise is
anti-slop Blender output: stronger camera, lighting, material, reference,
texture, geometry-detail and animation behavior than a generic agent would
produce from raw prompts.

> Local-first, open-source-first, **no paid APIs by default**. Heavy features are
> profile-gated to protect hardware. Web export is first-class.

---

## NPM / GitHub quick install

```bash
npm install -g https://raw.githubusercontent.com/HabrielStark/brilliant-blender-skill/main/npm/releases/brilliant-blender-skill-0.1.0.tgz
brilliant-blender-skill install
```

That installs the Skill into the default Codex skills folder:
`~/.codex/skills/blender-cinematic-scene` on macOS/Linux or
`%USERPROFILE%\.codex\skills\blender-cinematic-scene` on Windows.

The npm package is a small launcher plus the GLB validator; `brilliant-blender-skill install`
copies the bundled payload when present or fetches the full Skill from this
GitHub repository.

You can also run it without a global install:

```bash
npx --yes --package https://raw.githubusercontent.com/HabrielStark/brilliant-blender-skill/main/npm/releases/brilliant-blender-skill-0.1.0.tgz brilliant-blender-skill install
```

See [docs/npm-github-install.md](docs/npm-github-install.md) for target
overrides, package checks, the launcher/full payload split, and the Python/MCP
add-on path.

## What it gives the agent

1. **`SKILL.md`** — short, strict mandatory workflow.
2. **`references/`** — playbooks: camera, lighting/materials, composition, geometry,
   animation, web export, hardware profiles, visual critique, failure modes.
3. **`blender_cinematic/`** — pure-Python core (no `bpy`): schemas, hardware
   preflight, quality profiles, render budget, path sandbox, **all linters**,
   image-sanity metrics, evaluation rubric, iteration manager, report writer.
4. **`mcp_server/`** — safe structured MCP tools (stdio), resources and prompts.
5. **`addon/`** — Blender add-on (`bpy` layer): localhost bridge, validated
   operations, scene inspector, renderer, builders.
6. **`scripts/`** — local CLIs: preflight, run-job, scene-lint, visual-eval,
   export-glb, report, validate/package skill.
7. **`web/`** — Node GLB validation (`@gltf-transform/core`) + three.js / R3F /
   ScrollControls / GSAP code generation.
8. **`tests/`, `benchmarks/`, `examples/`, `docs/`**.

The skill also ships an explicit execution contract: write the goal and
acceptance gates first, keep a checkpoint/evidence ledger, delegate only
independent review branches, inspect actual pixels, and downgrade claims when
runtime, browser, or human review is unavailable. See
[`references/evidence-contract.md`](references/evidence-contract.md),
[`references/agent-orchestration.md`](references/agent-orchestration.md), and
[`references/visual-verification.md`](references/visual-verification.md).

## Architecture

```
AI host -> Agent Skill (SKILL.md + references + scripts)
                | optional MCP tool calls
                v
        MCP server (stdio, structured tools, sandbox)
                | localhost TCP/IPC
                v
        Blender add-on (bpy, validated ops, render/inspect)
                v
   artifacts/<task_id>/  (manifest, hardware report, iterations,
                          previews, renders, exports, web demo, reports)
```

The **core is fully unit-testable without Blender**. Real Blender work is isolated
in `addon/` and exercised by integration tests when a Blender executable exists.

## Install

```bash
# core + dev tooling (pip; uv optional)
python -m venv .venv
. .venv/Scripts/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"           # or: pip install -e ".[all]"
# uv equivalent: uv sync --all-extras

# web tooling (optional, for GLB validation / codegen)
npm install
npm run build
npx bcas-validate-glb examples/web-demo/scene.glb --max-mb 20
```

Blender is required only to *execute* scenes (render/export). The skill, schemas,
linters, evaluation and MCP server run without it.

## Quickstart

```bash
# 1. hardware preflight + profile selection
python scripts/preflight_hardware.py --project-dir ./artifacts/demo

# 2. validate / explore a manifest
python scripts/scene_manifest.py validate examples/prompts/product_hero_watch.json

# 3. compute a hardware-aware render budget
python scripts/render_budget.py --hardware ./artifacts/demo/hardware_report.json --profile auto

# 4. run a manifest through Blender background mode (needs Blender on PATH or --blender)
python scripts/run_blender_job.py --manifest examples/prompts/product_hero_watch.json

# 5. lint a scene-inspection JSON (no Blender needed)
python scripts/scene_lint.py ./artifacts/demo/iterations/iter_01_inspect.json

# 6. visual sanity + rubric on a preview image
python scripts/visual_eval.py ./artifacts/demo/iterations/iter_01_preview.png

# 7. write the final report
python scripts/report_writer.py ./artifacts/demo

# 8. after benchmarks, generate an automated visual evidence pack with thumbnails
python scripts/visual_review_pack.py --out ./artifacts/visual_review_pack --allow-unreviewed

# 9. generate an anonymized blind visual eval packet without claiming signoff
python scripts/blind_visual_eval.py --out ./artifacts/blind_visual_eval --allow-unreviewed

# 10. audit the skill contract itself (read-only, deterministic)
python scripts/skill_self_audit.py
```

## MCP server

```bash
pip install -e ".[mcp]"
blender-cinematic-mcp            # stdio transport
```

See `docs/mcp-setup.md` for host configuration (Claude Code / Cursor / Codex /
Gemini CLI) and `docs/blender-addon.md` for installing the add-on into Blender.

## Hardware profiles

| Profile | Final still | Engine | Texture cap | Samples |
|---|---:|---|---:|---:|
| `safe_laptop` | <=1920px | EEVEE/Workbench (Cycles if safe) | 1024 | 32-96 |
| `balanced` | 1080p/1440p | EEVEE preview, Cycles final | 2048 | 96-256 |
| `cinematic` | up to 4K | Cycles GPU | 2048-4096 | 256-512 |
| `ultra_4k` | 4K+ | Cycles GPU | 4096 | 512-1024 |

`auto` selects the safe profile from the hardware report. Details in
`references/hardware-quality-profiles.md`.

## Security model

* Bind **localhost only** by default; no network in strict mode.
* **Workspace-root allowlist** -- every write goes through the path sandbox.
* **Structured operations preferred**; raw Blender Python is **disabled by default**.
* Subprocess calls use **argument arrays**, never shell strings.
* Timeouts, complexity budget, file-size limits, full logs.

Full details: `docs/security.md`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/unit tests/security -q     # no Blender required (CI light)
bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon
pytest tests/integration_blender -q     # auto-skips without --blender-executable
pytest -q                               # everything (Blender/web tests auto-skip)
npm ci && npm run build && npm test     # web validator + TypeScript
python scripts/skill_self_audit.py      # goal/evidence/visual/sub-agent contract
```

Open-source maintenance docs:

- [SECURITY.md](SECURITY.md) for vulnerability reporting and project security boundaries.
- [CONTRIBUTING.md](CONTRIBUTING.md) for local setup and required checks.
- [RUNBOOK.md](RUNBOOK.md) for health checks, release packaging, incident response and rollback.
- [docs/dependency-pins.md](docs/dependency-pins.md) for exact dependency pins and freshness notes.
- [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and
  `python scripts/assert_release_artifacts.py --dist dist` for release
  redistribution checks.
- `python scripts/audit_repo_invariants.py` for repository-wide guardrails from
  `AGENTS.md` such as no `bpy` imports in core, exact dependency pins, no
  direct subprocess calls, and SHA-pinned GitHub Actions.
- [docs/VISUAL_ACCEPTANCE_REPORT.md](docs/VISUAL_ACCEPTANCE_REPORT.md) for the
  current visual anti-slop acceptance boundary, live-agent render evidence, and
  the honest limits of local taste validation.
- [docs/npm-github-install.md](docs/npm-github-install.md) for installing the
  Skill from GitHub through npm.

## Benchmarks

```bash
python benchmarks/runners/run_benchmarks.py --list
python benchmarks/runners/run_benchmarks.py --profile balanced --tasks product_hero_watch
python benchmarks/runners/run_benchmarks.py --baseline
python scripts/visual_review_pack.py --out artifacts/visual_review_pack --allow-unreviewed
python scripts/blind_visual_eval.py --out artifacts/blind_visual_eval --allow-unreviewed
python scripts/run_prompt_scenarios.py --render --out artifacts/prompt_scenarios_final_render
python scripts/run_prompt_scenarios.py --live-runs --runs watch_live_agent_forward_v6_20260604 --render --out artifacts/live_watch_final_after_docs
python scripts/run_prompt_scenarios.py --live-runs --runs reference_match_live_agent_forward_v12_20260604 --render --out artifacts/live_reference_match_final_after_docs
python scripts/run_prompt_scenarios.py --live-runs --runs shader_texture_live_agent_forward_v6_20260604 --render --out artifacts/live_shader_texture_final_after_docs
python scripts/run_prompt_scenarios.py --live-runs --runs turntable_animation_live_agent_forward_v2_20260604 --render --out artifacts/live_turntable_animation_final_after_docs
python scripts/assert_visual_acceptance.py \
  --visual-review artifacts/visual_review_pack/visual_review_pack.json \
  --blind-eval artifacts/blind_visual_eval/blind_visual_eval.json
```

Benchmarks compare *no-skill* vs *skill+tools* against the rubric and include a
visual review contact sheet for human inspection. The blind visual eval command
copies previews to anonymized `BVR-*` files and writes a private mapping so
reviewers can rate prompt fit, composition, material craft, detail precision,
anti-slop, and ship readiness without seeing task names or scores. See
`docs/benchmarking.md`.
Release/taste acceptance is strict by default: review-pack and blind-eval CLIs
fail unless a real human review JSON is supplied. Use `--allow-unreviewed` only
for automated evidence generation, not for claiming final taste signoff.
`scripts/assert_visual_acceptance.py` rejects evidence-only packs even when they
say `Status: PASS`; both JSON manifests must embed reviewed human/blind ratings.
Prompt-scenario fixtures currently cover product, reference-match,
shader/texture, and turntable-animation prompts. Archived live-agent render
spot checks pass for all four prompt families; they prove the Skill was
forward-tested on those visual failure modes, not just static fixtures.

## Troubleshooting & contributing

See `docs/troubleshooting.md`. Contributions must keep the core `bpy`-free, pin
dependencies, and add a test for every schema and a negative test for every safety
guard (`docs/skill-authoring.md`).

## License

MIT -- see [LICENSE](LICENSE).
