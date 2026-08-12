# Skill Authoring

How to extend the skill without breaking its guarantees.

## Golden rules

- **Core stays `bpy`-free.** `blender_cinematic/` must import without Blender.
  All `bpy` code lives in `addon/`.
- **Structured operations over raw Python.** New scene capability = a new
  allowlisted op, never an "exec arbitrary Python" path.
- **Every write through `WorkspaceResolver`.** No writes outside the workspace.
- **Subprocess = argument arrays** via `security.run_checked`; never `shell=True`.
- **Pin dependencies.** No open version ranges.
- **Keep the execution contract explicit.** A goal, checkpoint ledger, claim
  level, visual evidence, and honest stop condition are part of the feature.
- **Use sub-agents for independent evidence only.** Assign disjoint ownership,
  keep reviewers read-only, and never repeat a check without a new hypothesis.

## Add a new structured operation

1. **Allowlist + spec** — add it to `OPERATION_SPECS` in
   `blender_cinematic/recipes.py` with required/optional param types.
2. **Builder** — implement `op_<name>(params)` in
   `addon/blender_cinematic_agent/builders.py` and register it in `BUILDERS`.
3. **Bridge allowlist** — add the op name to `validators.ALLOWED_OPS`
   (a security test asserts it stays in sync with the core).
4. **Complexity** — if it generates geometry, account for it in
   `estimate_complexity`.
5. **Tests** — a unit test for validation + a real-Blender integration test.

## Add a schema

Add a Pydantic model in `blender_cinematic/schemas.py` (subclass `_Strict` so
unknown fields are rejected). Add a unit test covering a valid case and each
documented invalid case.

## Add a linter rule

Add the check inside the relevant `lint_*` function in
`blender_cinematic/linters.py`, emitting `error()`/`warn()`/`info()`. Errors fail
the scene; warnings inform. Add a unit test with a scene that triggers it.

## Authoring a manifest + recipe

A manifest (`SceneManifest`) declares intent; a recipe is the list of structured
operations that build it. See `examples/prompts/product_hero_watch.{json,recipe.json}`
and the `benchmarks/tasks/*.json`. Run it end-to-end:

```bash
python scripts/run_blender_job.py --manifest <manifest> --recipe <recipe>
```

## Definition of done

1. Schema/validation for any new structured input.
2. A unit test covers it; a safety guard gets a **negative** test.
3. `pytest tests/unit tests/security -q`, `ruff check blender_cinematic mcp_server scripts tests`, and `bandit -c pyproject.toml -r blender_cinematic mcp_server scripts tests addon` green **without** Blender.
4. If it touches Blender, an `integration_blender` test exists.
5. Docs/README updated if user-facing.
6. `python scripts/skill_self_audit.py` reports `PASS` and every required
   contract reference is linked from `SKILL.md`.
7. Visual claims cite inspected pixels or explicitly state that Blender,
   WebGL, Playwright, or human review was unavailable.
