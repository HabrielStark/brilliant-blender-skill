# Visual Acceptance Report

This project exists to reduce Blender AI slop: generic primitives, weak camera
work, flat materials, missing authored detail, fake animation, and reference
matches that only pass on text. Security and sandboxing are required guardrails,
but the primary release gate is visual production behavior.

## Current Local Acceptance

Date: 2026-06-04

Local status: **production-usable local release candidate for visual Skill
shipping**, with the limits below. This is not a claim that every possible
Blender task or every host/provider/community workflow has been exhausted.

| Gate | Current evidence |
|---|---|
| Whole benchmark suite | `python benchmarks/runners/run_benchmarks.py --baseline --out artifacts/visual_acceptance_final_after_docs`: 14/14 skill tasks pass, naive and adversarial baselines fail. |
| Prompt-shaped artifacts | `python scripts/run_prompt_scenarios.py --render --out artifacts/prompt_scenarios_final_render`: 4/4 pass with real Blender render checks. |
| Live product-watch forward test | `python scripts/run_prompt_scenarios.py --live-runs --runs watch_live_agent_forward_v6_20260604 --render --out artifacts/live_watch_final_after_docs`: pass. |
| Live reference-match forward test | `python scripts/run_prompt_scenarios.py --live-runs --runs reference_match_live_agent_forward_v12_20260604 --render --out artifacts/live_reference_match_final_after_docs`: pass. |
| Live shader/texture forward test | `python scripts/run_prompt_scenarios.py --live-runs --runs shader_texture_live_agent_forward_v6_20260604 --render --out artifacts/live_shader_texture_final_after_docs`: pass. |
| Live turntable forward test | `python scripts/run_prompt_scenarios.py --live-runs --runs turntable_animation_live_agent_forward_v2_20260604 --render --out artifacts/live_turntable_animation_final_after_docs`: pass. |
| Reviewed visual signoff | `python scripts/assert_visual_acceptance.py --visual-review artifacts/visual_review_pack_artfix_v28_reviewed/visual_review_pack.json --blind-eval artifacts/blind_visual_eval_artfix_v28_reviewed/blind_visual_eval.json`: pass against embedded reviewed Codex visual-review artifacts. |
| Release package | `python scripts/package_skill.py --out dist`, `npm pack --pack-destination dist`, and `python scripts/assert_release_artifacts.py --dist dist`: pass. |
| NPM install smoke | `npm install --prefix C:\tmp\bbs-npm-smoke-prefix -g dist\brilliant-blender-skill-0.1.0.tgz`, `brilliant-blender-skill doctor`, `brilliant-blender-skill install`, and installed-copy `scripts/validate_skill.py`: pass. |

## What The Live Loop Fixed

The live forward tests were not one-shot green checks. They exposed concrete
Skill failures and converted them into instructions and static/render gates:

- reference image was initially not actually supplied to the agent;
- reference camera was too wide, then too cropped by a long lens;
- lens/sensor/groove details could be hidden by bad parenting or occlusion
  patches;
- dark reference materials could look like broad gray metal instead of a
  near-black silhouette with blue/white edge strokes;
- prompt fixtures could pass while live recipes had too few authored operations;
- product/watch and shader/material live outputs needed stronger visible craft
  coverage, material richness, and camera-safe authored anatomy;
- animation recipes could contain keyframes but still produce a dark,
  low-geometry, hard-to-read turntable.

The current Skill and prompt-scenario contracts now require the specific fixes:
real reference inspection, frontal readable lens construction, tighter reference
coverage, focal-length limits, `color_ramp` material craft, no visible
`parent_objects` in the reference prompt, forbidden `occlusion` naming, real
`create_animation`, GLB animation export, loop metadata, rendered frame-delta
proof, and enough bevel/fins/ribs/rings to make the animation visibly readable.

## Coverage Map

| Visual capability | Covered by |
|---|---|
| Product hero anatomy, labels, straps, bevels, camera safety | `product_hero_watch`, `product_watch_prompt`, live v6 render archive. |
| Reference matching from pixels | `reference_match`, `reference_match_prompt`, live v12 render archive. |
| Shader/material/texture craft | `shader_texture_material_study`, `shader_texture_prompt`, live v6 render archive, material-node and image-texture gates. |
| Animation/turntable truth | `turntable_animation`, `turntable_animation_prompt`, live v2 render archive, rendered start/mid/end frame proof. |
| Web/GLB export | `glb_web_budget`, `web_scroll_hero`, Node validator, Playwright e2e. |
| Anti-slop rejection | naive baselines and adversarial baselines in the 14-task benchmark suite. |

## Honest Boundary

This report does not claim external community taste consensus. The strongest
local evidence is a reviewed Codex visual/blind review plus live-agent render
spot checks. The next open-source maturity step is independent Blender artist
or community review on the same blind packet format.

This report also does not claim every Blender feature is modeled. It proves the
current Skill is a tested anti-slop production workflow across representative
camera, lighting, material, reference, animation, web export, and benchmark
families. New Blender domains should add new structured operations, benchmark
tasks, prompt scenarios, and live forward tests before being advertised as
covered.
