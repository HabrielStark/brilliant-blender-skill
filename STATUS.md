# Production Readiness Status

**Project:** Blender Cinematic Agent Skill
**Date:** 2026-06-04
**Environment used for current local gates:** Windows, Python 3.11, Node 24.x.

## 2026-08-10 Upgrade Verification

The execution contract was strengthened with durable goal/checkpoint/evidence
rules, bounded sub-agent review, actual-pixel/browser gates, and a deterministic
skill self-audit. Bridge recipe bounds, GLB chunk parsing, latest-iteration
truth, final-render evidence, and failed Blender-stage propagation were hardened.
Blender 5.0.1 is available locally. The full Python suite, Blender integration
and visual regression suites, Node build/tests, Chromium desktop/mobile e2e,
Bandit, repository invariants, packaging, and the complete 14-task benchmark
matrix pass locally. Automated contact-sheet evidence is at
`artifacts/skill_upgrade_visual_review/contact_sheet.png`; it is not human taste
signoff. Remaining production gaps are listed in `TASK_BREAKDOWN.md`.

This repository is locally strong for open-source release engineering under the
tested toolchain. Automated Blender benchmarks, prompt-scenario fixtures, and
unreviewed blind packets are evidence only; current local visual acceptance is
based on the reviewed v28 Codex visual-review artifacts listed below plus the
4/4 prompt-scenario render evidence, archived live-agent render spot checks for
all four prompt-scenario families, v36 reference-fidelity,
v35 shader-graph, v34 rendered animation-frame, geometry, texture, and
surface-microdetail regression evidence. External/community human review
remains a release-matrix follow-up, not hidden completed work.
The release artifacts are built, package metadata is valid, dependencies are
pinned, security/static checks pass, browser/WebGL e2e tests pass, and
source/binary distribution contents are verified.

## Delivered

- Agent skill package: `SKILL.md`, `AGENTS.md`, `references/`, docs, examples,
  scripts, tests, open-source governance docs, `THIRD_PARTY_NOTICES.md`, and
  release metadata.
- Pure-Python core in `blender_cinematic/` with no `bpy` imports.
- Structured MCP server in `mcp_server/` with typed tools, resources, prompts,
  sandboxed workspace handling, and raw Python disabled by default.
- Blender add-on in `addon/blender_cinematic_agent/`, with Blender API use kept
  outside the pure-Python core.
- Web package with TypeScript GLB validation, compiled distributable CLI,
  node tests, and Playwright e2e WebGL rendering checks.
- Release artifacts in `dist/`:
  - `blender-cinematic-scene-skill.zip`
  - `blender_cinematic_agent.zip`
  - `blender_cinematic_agent_skill-0.1.0-py3-none-any.whl`
  - `blender_cinematic_agent_skill-0.1.0.tar.gz`
  - `checksums.sha256`
  - `python-sbom.cdx.json`
  - `npm-sbom.cdx.json`
  - `sbom-checksums.sha256`

## Current Verification Evidence

| Gate | Result |
|---|---|
| `python -m pip install -e ".[dev]"` | PASS |
| `pytest tests -q` | PASS |
| `ruff check blender_cinematic mcp_server scripts tests` | PASS |
| `python scripts\audit_repo_invariants.py` | PASS |
| `bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon` | PASS |
| `python -m pip_audit .` | PASS, no known vulnerabilities |
| `python -m build --sdist --wheel` | PASS |
| `python -m twine check dist\blender_cinematic_agent_skill-0.1.0.tar.gz dist\blender_cinematic_agent_skill-0.1.0-py3-none-any.whl` | PASS |
| `python scripts\validate_skill.py` | PASS |
| `python -m benchmarks.runners.run_benchmarks --baseline --out artifacts\visual_acceptance_artfix_v28` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_final_after_docs` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL after final docs/package updates |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_craft_v29` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with craft-detail gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_craft_v29 --allow-unreviewed` | PASS, v29 automated evidence packet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_craft_v29 --seed 20260604 --allow-unreviewed` | PASS, v29 anonymized evidence packet generated |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_texture_microdetail_v31` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with texture-role and surface-microdetail gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_texture_microdetail_v31 --allow-unreviewed` | PASS, v31 automated evidence packet and contact sheet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_texture_microdetail_v31 --seed 20260604 --allow-unreviewed` | PASS, v31 anonymized evidence packet generated |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_geometry_detail_v32` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with geometry-detail role gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_geometry_detail_v32 --allow-unreviewed` | PASS, v32 automated evidence packet and contact sheet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_geometry_detail_v32 --seed 20260604 --allow-unreviewed` | PASS, v32 anonymized evidence packet generated |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_animation_motion_v33` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with sampled animation/camera-motion gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_animation_motion_v33 --allow-unreviewed` | PASS, v33 automated evidence packet and contact sheet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_animation_motion_v33 --seed 20260604 --allow-unreviewed` | PASS, v33 anonymized evidence packet generated |
| `python benchmarks\runners\run_benchmarks.py --tasks turntable_animation,web_scroll_hero --baseline --out artifacts\visual_acceptance_animation_frame_v34_probe7` | PASS: both animation skill tasks PASS 100; naive baselines FAIL; adversarial baselines FAIL; rendered start/mid/end frame deltas active |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_animation_frame_v34` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with rendered animation-frame proof gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_animation_frame_v34 --allow-unreviewed` | PASS, v34 automated evidence packet and contact sheet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_animation_frame_v34 --seed 20260604 --allow-unreviewed` | PASS, v34 anonymized evidence packet generated |
| `python benchmarks\runners\run_benchmarks.py --tasks shader_texture_material_study --baseline --out artifacts\visual_acceptance_shader_graph_v35_probe2` | PASS: shader/material skill task PASS 100; naive baseline FAIL 27; adversarial baseline FAIL; rich linked material graph gates active |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_shader_graph_v35` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with shader-graph gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_shader_graph_v35 --allow-unreviewed` | PASS, v35 automated evidence packet and contact sheet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_shader_graph_v35 --seed 20260604 --allow-unreviewed` | PASS, v35 anonymized evidence packet generated |
| `python benchmarks\runners\run_benchmarks.py --tasks reference_match --baseline --out artifacts\visual_acceptance_reference_fidelity_v36_probe2` | PASS: reference skill task PASS 98; naive baseline FAIL 29; adversarial baseline FAIL with saliency/edge/coverage/tone reference gates active |
| `python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_reference_fidelity_v36` | PASS: 14/14 skill PASS, 14/14 naive baseline FAIL, 14/14 adversarial FAIL with reference-fidelity gates active |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_reference_fidelity_v36 --allow-unreviewed` | PASS, v36 automated evidence packet and contact sheet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_reference_fidelity_v36 --seed 20260604 --allow-unreviewed` | PASS, v36 anonymized evidence packet generated |
| `python scripts\run_prompt_scenarios.py` | PASS: 4/4 prompt fixtures pass static anti-slop recipe contracts; `live_agent_runs=0` |
| `python scripts\run_prompt_scenarios.py --render --out artifacts\prompt_scenarios_final_render` | PASS: 4/4 prompt fixtures pass static contracts and real Blender benchmark checks; `live_agent_runs=0` |
| `python scripts\run_prompt_scenarios.py --live-runs --runs watch_live_agent_forward_v6_20260604 --render --out artifacts\live_watch_final_after_docs` | PASS: archived live-agent watch output passes static contract and real Blender render gates |
| `python scripts\run_prompt_scenarios.py --live-runs --runs reference_match_live_agent_forward_v12_20260604 --render --out artifacts\live_reference_match_final_after_docs` | PASS: archived live-agent reference-match output passes static contract and real Blender render gates |
| `python scripts\run_prompt_scenarios.py --live-runs --runs shader_texture_live_agent_forward_v6_20260604 --render --out artifacts\live_shader_texture_final_after_docs` | PASS: archived live-agent shader/texture output passes static contract and real Blender render gates |
| `python scripts\run_prompt_scenarios.py --live-runs --runs turntable_animation_live_agent_forward_v2_20260604 --render --out artifacts\live_turntable_animation_final_after_docs` | PASS: archived live-agent turntable output passes static contract and real Blender render gates |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_artfix_v28 --allow-unreviewed` | PASS, automated evidence packet generated |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_artfix_v28 --seed 20260604 --allow-unreviewed` | PASS, anonymized evidence packet generated |
| `python scripts\visual_review_pack.py --out artifacts\visual_review_pack_artfix_v28_reviewed --human-review artifacts\visual_review_pack_artfix_v28\codex_visual_review.json` | PASS, reviewed Codex visual signoff embedded |
| `python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_artfix_v28_reviewed --seed 20260604 --human-review artifacts\blind_visual_eval_artfix_v28\codex_blind_review.json` | PASS, reviewed Codex blind visual signoff embedded |
| `python scripts\assert_visual_acceptance.py --visual-review artifacts\visual_review_pack_artfix_v28_reviewed\visual_review_pack.json --blind-eval artifacts\blind_visual_eval_artfix_v28_reviewed\blind_visual_eval.json` | PASS |
| `python scripts\package_skill.py --out dist` | PASS |
| `python scripts\generate_sbom.py --out dist` | PASS |
| `python scripts\assert_release_artifacts.py --dist dist` | PASS |
| `npm pack --pack-destination dist` | PASS: `dist\brilliant-blender-skill-0.1.0.tgz` generated without Python cache files |
| npm tarball install smoke | PASS: installed `dist\brilliant-blender-skill-0.1.0.tgz` into an isolated prefix, ran `brilliant-blender-skill doctor`, installed the Skill into `C:\tmp\bbs-npm-smoke-install`, and `python C:\tmp\bbs-npm-smoke-install\scripts\validate_skill.py` passed |
| `npm test` | PASS |
| `npm run e2e` | PASS, desktop WebGL, animation mixer, and mobile viewport |
| `npm audit --package-lock-only --audit-level=high` | PASS, 0 vulnerabilities |
| `npm pack --dry-run` | PASS |
| npm install smoke from a clean temp project | PASS, CLI and module export work |
| artifact content assertions | PASS, sdist/skill zip/wheel/npm bin contents verified |

## Acceptance Coverage

- Local-first open-source workflow: met. No paid APIs are required by the
  default workflow.
- Dependency pinning: met. Python and Node dependencies are exact pinned
  versions; optional NVIDIA support uses the maintained `nvidia-ml-py`
  distribution.
- Third-party notices: met. `THIRD_PARTY_NOTICES.md` is included in source,
  skill, and npm release packaging.
- Supply-chain artifacts: met. Python and npm SBOMs plus checksums are generated.
- Security baseline: met locally via sandbox tests, Bandit, pip-audit, npm audit,
  pinned GitHub Actions, and package-content checks.
- Browser/WebGL readiness: met locally through Playwright e2e tests that render
  the GLB on a live WebGL canvas in desktop and mobile viewports.
- Visual benchmark readiness: met locally through 14/14 Blender benchmark skill
  passes, 14/14 naive baseline failures, 14/14 adversarial baseline failures,
  visual review pack generation, and an anonymized blind visual eval packet.
  The current v34 animation-frame regression run keeps all 14 skill tasks
  passing while adding rendered start/mid/end frame-difference proof to the
  turntable and web-scroll animation benchmarks. The accepted turntable now shows mean RGB frame delta
  about 0.129 with about 53% changed pixels, and the accepted web scroll hero
  shows mean RGB frame delta about 0.072 with about 33% changed pixels. Static
  baselines render 0.0 frame delta and fail. v34 also fixes turntable assembly
  motion so offset parts orbit a shared center instead of merely rotating in
  place, and reframes the web scroll hero so the object is readable rather than
  cut off by the camera. It preserves v32 gates for Geometry Nodes
  generated visual roles (`panel_wall_plate`) on the corridor benchmark and v31
  gates for
  real authored detail roles (`text_label`,
  `decal_plane`, `curve_tube`, `fastener`, `panel_cutline`, `grille_slat`,
  `organic_surface`, `energy_streak`, `surface_microdetail`) plus shader image
  texture roles (`base_color`, `displacement`) in product, web speaker,
  weak-laptop locker, mechanical exploded-view, organic, VFX, and shader-study
  tasks. The benchmark runner now counts visual semantic parts across `MESH`,
  `CURVE`, and `FONT` objects while keeping face/modifier budgets on mesh
  geometry.
  The current v28 skill score range is 97-100; `camera_expensive` passes at 100
  after its controlled lighting was lifted enough to reveal the premium faceted
  body and plinth without flattening the dark cinematic look. `particle_vfx_energy_burst`
  passes at 97 after adding a visible metallic containment/iris assembly around
  the emissive core, and `architectural_interior_scene` passes at 97 after
  removing invisible curtain-fold tail objects from the subject set and adding
  visible sofa/contact/table craft details; the current recipe also tightens the
  interior camera while keeping plant and curtain details inside frame.
  `low_spec_laptop_safe` stays PASS100 after adding floor-mat grounding,
  service-wall panels, and restrained staging accents. `scene_repair` passes at
  100 after adding a readable repair-studio context, dial, cable, vent, tool,
  and visible front-foot details.
- Anti-slop score honesty: met locally in v28. Render-sanity now rejects flat,
  unreadable, or dark low-detail previews earlier, and hard-failed scenes are
  capped below the passing visual-score threshold. In the current run, all 14 adversarial slop baselines score 79 and fail; they no longer look numerically close to the accepted skill scenes.
- Anti-slop named-part gates: met locally for high-risk tasks that use
  `min_distinct_named_part_objects` and `min_named_part_total_coverage`, so
  keyword-stuffed one-object or micro-object adversarial scenes cannot satisfy
  semantic-part requirements by name alone.
- Authored craft-detail gates: met locally in v31 for representative product,
  web asset, weak-hardware, mechanical, organic, VFX, and shader scenes.
  Keyword-stuffed or visually flat baselines fail on missing craft roles, while
  skill scenes create real Blender `FONT` labels, bevelled `CURVE` cables,
  fasteners, panel cutlines, grille slats, decal plates, energy streaks,
  organic surface details, and raised surface microdetails.
- Shader/texture craft gates: met locally in v35 for the shader/material study.
  The accepted skill scene has authored procedural shader features, declared
  image texture roles for `base_color` and `displacement`, required material
  node-name signatures such as `EdgeWearAO`, `ScanlineWave`, `RoughnessRamp`,
  `Mapping`, and `TexCoord`, and at least four assigned subject materials with
  rich linked shader graphs. Naive and adversarial baselines fail when they only
  name a label/bottle without the node texture stack.
- Geometry-node detail gates: met locally in v32 for the sci-fi corridor. The
  accepted skill scene exposes at least 48 inspected recipe-specific generated
  detail objects with `panel_wall_plate`; naive and adversarial baselines now
  fail on missing Geometry Nodes detail roles, not only on missing node groups.
- Animation/camera motion gates: met locally in v34 for the turntable and
  web-scroll benchmarks. Accepted scenes now expose sampled start/mid/end
  movement from inspected Blender animation data and rendered start/mid/end
  image differences from real preview frames; static actions, missing GLB
  clips, invisible turntable motion, and scroll heroes with a non-keyframed
  active camera fail on sampled moving object, rotation, camera-location, and
  rendered-frame delta checks.
- Prompt-scenario artifact gates: met locally for four realistic prompt
  families: premium watch product hero, shader/texture material study,
  reference-matched dark product, and premium turntable animation. These
  scenarios reject keyword/default-name slop before render, require
  camera/lighting/material/craft/procedural/animation signals, and then pass the
  corresponding real Blender benchmark checks with `--render`. This is
  explicitly `prompt_fixture_plus_render`, not live external model generation
  proof.
- Live-agent forward-test gates: met locally for all four prompt-scenario
  families: watch v6, reference-match v12, shader/texture v6, and
  turntable-animation v2. All four pass the same static prompt contracts and
  real Blender render checks. Earlier archived failures are preserved as
  regression evidence: they exposed missing reference pixels, loose/cropped
  cameras, long focal length, hidden lens detail, bad visible parenting,
  missing `color_ramp` material craft, material-study framing issues, dark
  unreadable turntables, and too little modeled animation detail.
- Local visual signoff: met by reviewed v28 Codex visual artifacts:
  `artifacts\visual_review_pack_artfix_v28\codex_visual_review.json` and
  `artifacts\blind_visual_eval_artfix_v28\codex_blind_review.json`. The
  strict `scripts\assert_visual_acceptance.py` gate passes only against the
  reviewed v28 manifests and still rejects evidence-only `--allow-unreviewed`
  JSON.
- Release packaging: met. Skill zip, add-on zip, wheel, sdist, npm package dry
  run, and install smoke all pass. The Python sdist includes source, scripts,
  tests, add-on source, benchmarks, docs, examples, CI, and notices.
- NPM/GitHub install path: met locally. The package name is
  `brilliant-blender-skill`, the GitHub repository URL points at
  `HabrielStark/brilliant-blender-skill`, and the npm bin
  `brilliant-blender-skill install` copies the Skill into a Codex skills
  directory. The package also preserves the existing `bcas-validate-glb` bin for
  GLB validation.

- Reference fidelity gates: met locally in v36 for the `reference_match`
  benchmark. The accepted scene passes SSIM and palette checks plus saliency IoU,
  edge IoU, center/coverage drift, and tone/contrast drift gates. The
  adversarial lit box keeps high palette similarity but fails reference-spatial
  gates, so color matching alone no longer counts as reference fidelity.

## Remaining External Validation

These items are outside the current local proof boundary and must be treated as
release-matrix follow-ups, not as hidden completed work:

1. Run the Blender integration matrix on every advertised Blender/OS/GPU target,
   not only the local executable available to the maintainer.
2. Run a full 4K Cycles final-render benchmark on representative high-end GPU
   hardware before advertising specific production render-time numbers.
3. Connect the MCP server to each target host application in a live session
   before claiming host-specific UX validation beyond stdio/server checks.
4. Optional enterprise/integrator follow-up: complete a deeper Codex Security
   repository scan if this skill is embedded into a larger production pipeline.
   This is not the primary Blender-taste acceptance gate; it is defense-in-depth
   for users who run the MCP/add-on around valuable project files.
5. Optional external taste validation: have independent Blender artists or
   community reviewers fill the v28 review templates and compare their ratings
   against `codex_visual_review_agent_gpt5_2026_06_04_v28`. This is the next
   maturity step for open-source confidence, not a current local gate failure.
6. Expand the archived live-agent prompt generation loop to every benchmark
   family and external provider/model that the project wants to advertise.
   Current live render proof covers all four prompt-scenario families, not
   every possible Skill use case or every host/model combination.

## Reproduce

```bash
python -m pip install -e ".[dev]"
pytest tests -q
ruff check blender_cinematic mcp_server scripts tests
python scripts\audit_repo_invariants.py
bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon
python -m pip_audit .
python -m build --sdist --wheel
python -m twine check dist\blender_cinematic_agent_skill-0.1.0.tar.gz dist\blender_cinematic_agent_skill-0.1.0-py3-none-any.whl
python scripts\validate_skill.py
python -m benchmarks.runners.run_benchmarks --baseline --out artifacts\visual_acceptance_artfix_v28
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_final_after_docs
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_craft_v29
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_craft_v29 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_craft_v29 --seed 20260604 --allow-unreviewed
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_texture_microdetail_v31
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_texture_microdetail_v31 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_texture_microdetail_v31 --seed 20260604 --allow-unreviewed
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_geometry_detail_v32
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_geometry_detail_v32 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_geometry_detail_v32 --seed 20260604 --allow-unreviewed
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_animation_motion_v33
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_animation_motion_v33 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_animation_motion_v33 --seed 20260604 --allow-unreviewed
python benchmarks\runners\run_benchmarks.py --tasks turntable_animation,web_scroll_hero --baseline --out artifacts\visual_acceptance_animation_frame_v34_probe7
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_animation_frame_v34
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_animation_frame_v34 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_animation_frame_v34 --seed 20260604 --allow-unreviewed
python benchmarks\runners\run_benchmarks.py --tasks shader_texture_material_study --baseline --out artifacts\visual_acceptance_shader_graph_v35_probe2
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_shader_graph_v35
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_shader_graph_v35 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_shader_graph_v35 --seed 20260604 --allow-unreviewed
python benchmarks\runners\run_benchmarks.py --tasks reference_match --baseline --out artifacts\visual_acceptance_reference_fidelity_v36_probe2
python benchmarks\runners\run_benchmarks.py --baseline --out artifacts\visual_acceptance_reference_fidelity_v36
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_reference_fidelity_v36 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_reference_fidelity_v36 --seed 20260604 --allow-unreviewed
python scripts\run_prompt_scenarios.py
python scripts\run_prompt_scenarios.py --render --out artifacts\prompt_scenarios_final_render
python scripts\run_prompt_scenarios.py --live-runs --runs watch_live_agent_forward_v6_20260604 --render --out artifacts\live_watch_final_after_docs
python scripts\run_prompt_scenarios.py --live-runs --runs reference_match_live_agent_forward_v12_20260604 --render --out artifacts\live_reference_match_final_after_docs
python scripts\run_prompt_scenarios.py --live-runs --runs shader_texture_live_agent_forward_v6_20260604 --render --out artifacts\live_shader_texture_final_after_docs
python scripts\run_prompt_scenarios.py --live-runs --runs turntable_animation_live_agent_forward_v2_20260604 --render --out artifacts\live_turntable_animation_final_after_docs
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_artfix_v28 --allow-unreviewed
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_artfix_v28 --seed 20260604 --allow-unreviewed
python scripts\visual_review_pack.py --out artifacts\visual_review_pack_artfix_v28_reviewed --human-review artifacts\visual_review_pack_artfix_v28\codex_visual_review.json
python scripts\blind_visual_eval.py --out artifacts\blind_visual_eval_artfix_v28_reviewed --seed 20260604 --human-review artifacts\blind_visual_eval_artfix_v28\codex_blind_review.json
python scripts\assert_visual_acceptance.py --visual-review artifacts\visual_review_pack_artfix_v28_reviewed\visual_review_pack.json --blind-eval artifacts\blind_visual_eval_artfix_v28_reviewed\blind_visual_eval.json
python scripts\package_skill.py --out dist
python scripts\generate_sbom.py --out dist
npm pack --pack-destination dist
python scripts\assert_release_artifacts.py --dist dist
npm install --prefix C:\tmp\bbs-npm-smoke-prefix -g dist\brilliant-blender-skill-0.1.0.tgz
C:\tmp\bbs-npm-smoke-prefix\brilliant-blender-skill.cmd doctor
C:\tmp\bbs-npm-smoke-prefix\brilliant-blender-skill.cmd install --target C:\tmp\bbs-npm-smoke-install
python C:\tmp\bbs-npm-smoke-install\scripts\validate_skill.py
npm test
npm run e2e
npm audit --package-lock-only --audit-level=high
npm pack --dry-run
```
