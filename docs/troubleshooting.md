# Troubleshooting

## Blender not found

`run_blender_job` / benchmarks need Blender. The locator checks PATH,
`BLENDER_EXECUTABLE`/`BLENDER_PATH`/`BLENDER`, and standard install folders.

```bash
python scripts/blender_locator.py
export BLENDER_EXECUTABLE="/path/to/blender"   # Windows: set BLENDER_EXECUTABLE=...
```

The core (schemas, linters, evaluation, MCP, web validation) works **without**
Blender; only render/inspect/export need it.

## `result: blender_not_found` or `no_result`

The headless job could not run. Check the per-task logs in
`artifacts/<task>/logs/` (`stdout_*.log` has Blender's output). Confirm the
add-on path: the runner uses `addon/blender_cinematic_agent/job_runner.py` (or
`BCAS_ADDON_DIR`).

## Render is black / flat (hard-fail)

`render has no discernible silhouette/detail` or `almost entirely black` means
the lighting/contrast is too weak. Add a key + rim, raise world strength, lighten
materials, check the subject is in frame (`scene_lint`).

## GLB fails validation

- `external textures` → bake/pack textures; the exporter uses `export_apply=True`.
- `exceeds budget` → reduce geometry/textures or raise `max_glb_mb`.
- `no animation clips` but animation requested → ensure a `create_animation` op
  with `export.include_in_glb`.

## MCP raw Python refused

Intended. Raw Python is disabled by default. Set `BCAS_SAFETY_MODE=dev` and
`BCAS_RAW_PYTHON=1` only if you understand the risk; the static scanner still
rejects dangerous code.

## Engine / API errors on a different Blender version

Engine ids and Principled-BSDF input names are resolved defensively, but Blender
changes APIs. Run the integration tests against your build:

```bash
pytest tests/integration_blender -q --blender-executable /path/to/blender
```

## Web build issues

`npm run build` compiles `web/*.ts` → `web/dist`. If `node --test` can't find the
module, rebuild first. Browser-based Playwright E2E is optional and not in the
default run.

## PowerShell

Use `;` to chain commands (not `&`). Piping program output into another program's
stdin can mangle encoding; prefer `Out-File` / `Select-String`.
