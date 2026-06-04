# Failure Modes

The behaviours this skill exists to prevent, and the guard that catches each.

| Failure | Guard |
|---|---|
| Random primitives instead of a scene | rubric geometry/composition + "too few meaningful objects" hard-fail |
| Confusing "3840×2160" with real 4K quality | budget clamps 4K to profile; report must show preview→final |
| No camera planning | `lint_camera` (no camera, subject hidden, inside geometry) |
| Hero product anatomy cropped out of frame | `lint_camera` (`camera.subject_part_hidden`) |
| Floating/disconnected cap, label, strap, lens, button or support | mandatory preview inspection; repair placement before final |
| Black / empty / noisy / off-camera render | `image_sanity` + `render_sanity_issues` hard-fails |
| Heavy Cycles on a weak laptop | preflight + profile downshift + tiny-render gate |
| GLB that will not load in the browser | `export_glb` + local `web/` validator before "done" |
| No iterations / logs / proofs saved | `artifacts/<task_id>/` layout + final report from real files |
| "Looks beautiful" without looking | mandatory preview inspection + measured rubric |
| Default `Cube.001` / `Material.001` names | `lint_naming` (error on key objects/materials) |
| Flipped/broken mesh normals on hero geometry | `lint_mesh` (`mesh.normals`) + evaluator hard-fail |
| Unbaked geometry nodes exported | `lint_geometry` unbaked-for-web error |
| Particle/sim bombs | `estimate_complexity` + `lint_vfx` budget caps |
| Over-processed compositor hiding bad lighting | `lint_compositor` overbloom / no-raw-render |
| Raw Python as the normal path | structured-operation allowlist; raw Python disabled by default |
| Writing outside the project | `WorkspaceResolver` path sandbox |
| Shell injection via filenames/params | argument arrays only; no `shell=True` |

## Recovery

- Before any heavy operation: save the `.blend`, write the operation plan JSON,
  flush logs.
- On Blender crash: report the failing operation, keep the last good `.blend`,
  preserve artifacts.
- If three iterations do not improve the score: stop and write an honest failure
  report — do not keep thrashing.

## Honesty rule

Never declare *done*, *4K*, *cinematic* or *web-ready* without artifact paths, an
inspected preview, and a validation report. "Almost done" is not done.
