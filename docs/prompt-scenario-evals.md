# Prompt Scenario Evals

Prompt scenarios close a different gap than the curated Blender benchmarks.
The benchmark recipes prove that structured operations can render strong scenes;
prompt scenarios prove that a prompt-shaped agent artifact has enough semantic,
material, camera, lighting, and craft detail before it is accepted as a Skill
output.

This is intentionally not labeled as a live LLM eval unless the scenario
provenance says `live_agent`. Current repo fixtures use `prompt_fixture`, which
means they are acceptance contracts derived from realistic prompts. They are
useful, but they do not prove that an external agent generated the recipe in a
fresh run. Separate archived live-agent runs are used as forward tests for
specific high-risk prompt families.

## Run

```bash
python scripts/run_prompt_scenarios.py --list
python scripts/run_prompt_scenarios.py
python scripts/run_prompt_scenarios.py --render --out artifacts/prompt_scenarios_final_render
python scripts/run_prompt_scenarios.py --live-runs --runs watch_live_agent_forward_v6_20260604 --render --out artifacts/live_watch_final_after_docs
python scripts/run_prompt_scenarios.py --live-runs --runs reference_match_live_agent_forward_v12_20260604 --render --out artifacts/live_reference_match_final_after_docs
python scripts/run_prompt_scenarios.py --live-runs --runs shader_texture_live_agent_forward_v6_20260604 --render --out artifacts/live_shader_texture_final_after_docs
python scripts/run_prompt_scenarios.py --live-runs --runs turntable_animation_live_agent_forward_v2_20260604 --render --out artifacts/live_turntable_animation_final_after_docs
```

Without `--render`, the runner performs static anti-slop checks:

- structured recipe validation;
- estimated complexity budget;
- required camera, lighting, material, and craft operations;
- semantic named anatomy from the prompt;
- procedural material and image texture role presence;
- rejection of default `Cube`, `Cylinder`, `Material`, and similar names;
- provenance reporting so fixtures are not confused with live agent output.

With `--render`, each scenario also runs the candidate recipe through the
corresponding full Blender benchmark task checks. This verifies actual preview,
scene inspection, lint, visual score, materials, named-part visibility,
reference/image fidelity, GLB, or animation gates already attached to that task.

## Evidence Boundary

Passing prompt scenarios at `static_prompt_fixture_contract` means the stored
prompt artifact is not a minimal keyword-stuffed recipe. Passing at
`prompt_fixture_plus_render` means the same artifact also survives real Blender
visual benchmark gates.

Neither level is equivalent to independent community taste review or a live
agent/subagent generation loop. Release notes must keep that distinction.

Passing a `live_agent_*` archive with `--render` proves a specific archived
agent output survived the same static contract and Blender render gates. It is
stronger than a prompt fixture, but still not equivalent to broad provider,
community, or external artist validation.

Current local live render spot checks:

- `watch_live_agent_forward_v6_20260604`: passed static and render gates for
  premium product anatomy, material families, bevels, labels, straps, camera
  safety, and authored detail.
- `reference_match_live_agent_forward_v12_20260604`: passed after earlier live
  failures exposed missing reference pixels, bad crop/long lens, hidden lens
  detail, weak black-body tone matching, and unsafe visible parenting.
- `shader_texture_live_agent_forward_v6_20260604`: passed static and render
  gates for glass/liquid/metal/label material craft, procedural shader signals,
  image texture roles, and readable material-study framing.
- `turntable_animation_live_agent_forward_v2_20260604`: passed after an earlier
  live failure exposed a dark, low-geometry turntable that animated technically
  but did not read as a polished product shot.
