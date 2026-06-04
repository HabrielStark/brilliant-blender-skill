# AGENTS.md

Operational notes for AI coding agents working **in this repository** (this is
distinct from `SKILL.md`, which tells an agent how to *use* the skill to build
Blender scenes).

## Ground rules

- **Keep `blender_cinematic/` free of `bpy`.** All Blender API code lives in
  `addon/` and is imported only at runtime inside Blender. This separation is
  what makes the core unit-testable without Blender.
- **Structured operations over raw Python.** New scene capabilities are added as
  allowlisted operations in `blender_cinematic/recipes.py` plus a builder in
  `addon/blender_cinematic_agent/builders.py`. Do not add a "run arbitrary
  Python" path to the normal flow.
- **Every write goes through `WorkspaceResolver`.** Never write outside the task
  workspace.
- **Subprocess = argument arrays.** Use `blender_cinematic.security.run_checked`;
  never build shell strings, never `shell=True`.
- **Pin dependencies.** No open-ended version ranges in `pyproject.toml` /
  `package.json`.

## Definition of done for a change

1. A schema/validation exists for any new structured input.
2. A unit test covers it; a safety guard gets a negative test.
3. `pytest tests/unit tests/security -q` is green without Blender.
4. If it touches Blender, an `integration_blender` test exists and runs when a
   Blender executable is provided.
5. Docs/README updated if user-facing.

## Layout

```
blender_cinematic/   pure-Python core (schemas, profiles, budget, sandbox,
                     linters, imaging, evaluation, iteration, report)
mcp_server/          MCP stdio server (structured tools, resources, prompts)
addon/               Blender add-on (bpy): bridge, ops, inspector, renderer, builders
scripts/             local CLIs (preflight, run-job, lint, eval, export, report)
web/                 Node GLB validation + three.js/R3F/scroll codegen
tests/               unit · security · integration_blender · visual_regression · web_e2e
benchmarks/          tasks · rubrics · runners
examples/ · docs/    sample manifests/web-demo · documentation
```

## Running things

```bash
pip install -e ".[dev]"
pytest tests/unit tests/security -q
python scripts/validate_skill.py
BLENDER_EXECUTABLE=/path/to/blender pytest tests/integration_blender -q
```
