# Blender Add-on

The add-on (`addon/blender_cinematic_agent/`) is the `bpy` layer. It has two
modes:

1. **Headless** (`job_runner.py`) — invoked by the core runner / MCP / scripts as
   `blender -b --factory-startup --python job_runner.py -- job.json`. No
   registration needed. This is the CI / automation path.
2. **Interactive** — a normal Blender add-on with a localhost bridge, used when
   you want the agent to drive a *running* Blender session.

## Install (interactive)

1. Zip the add-on: `python scripts/package_skill.py` → `dist/blender_cinematic_agent.zip`.
2. Blender → Edit → Preferences → Add-ons → *Install from Disk…* → pick the zip.
3. Enable **Blender Cinematic Agent**.
4. Open the sidebar (N) in the 3D viewport → **Cinematic** tab → *Start Bridge*.

## Preferences

- **Bridge Host / Port** — `127.0.0.1:8765` by default (localhost only).
- **Auto-start bridge** — start the listener on enable.
- **Workspace Root** — sandbox for bridge writes. `render_preview`,
  `render_final`, and `export_glb` outputs must resolve inside this directory.
- **Safety Mode** — `strict` (structured ops only) or `dev`.

A non-localhost host shows a warning and is refused in strict mode.

## Bridge protocol

4-byte big-endian length prefix + JSON. Commands are validated against the
allowlist (`validators.py`) before touching Blender; sockets run on a worker
thread while Blender data is mutated only on the main thread via a
`bpy.app.timers` callback (bpy is not thread-safe). One job at a time; 16 MB
message cap.

Actions: `ping`, `initialize`, `apply_recipe`, `inspect`, `render_preview`,
`render_final`, `export_glb`.

## Headless job contract

`job.json` (built by `blender_cinematic.runner.build_job`):

```json
{ "action": "full_pipeline", "workspace": "...", "blend_path": "...",
  "manifest": {...}, "budget": {...}, "recipe": {"operations": [...]},
  "render": {...}, "output": {"image": "...", "glb": "..."}, "result_path": "..." }
```

Actions: `initialize_blend`, `apply_recipe`, `inspect`, `render_preview`,
`render_final`, `export_glb`, `full_pipeline`. The runner writes the result JSON
to `result_path` and prints `BCAS_RESULT=<path>`.

## Scene inspection contract

`scene_inspector.inspect_scene()` returns the dict the linters consume:
`collections`, `objects[]` (faces, materials, modifiers, scale, `in_camera_frame`,
`screen_coverage`, `non_manifold`, `flipped_normals`), `active_camera`, `cameras`,
`lights`, `materials`, `node_groups`, `geometry_nodes`, `animation`, `particles`,
`compositor`, `render`, `metadata`, `missing_files`.

## Version notes

Engine identifiers are resolved at runtime: EEVEE is `BLENDER_EEVEE` on 5.0 and
`BLENDER_EEVEE_NEXT` on 4.2–4.5. Principled BSDF input names (`Coat Weight`,
`Transmission Weight`) and the layered Action system (5.0) are handled
defensively.
