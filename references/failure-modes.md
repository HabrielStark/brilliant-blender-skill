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
| Declared brief element never built | `required_parts` ledger + `completeness.part_missing` fail + scaffold op |
| Element exists only as a named primitive | `completeness.part_is_placeholder` warn + verifier three-tier identity test |
| Nested assembly part "fixed" off its mount | buried-object guards: flush-top, embedded-bottom, bbox-periphery |
| Scale stack: `set_object_transform` scale on baked-scale object multiplies | `create_mesh_primitive` bakes `scale` into the mesh — later transform scale is absolute, so re-issue the intended final dims, not a delta |
| Single hero angle hides backside omissions | `render_multiview` orbit set + verifier pass before done |
| Enclosure/backdrop wall occludes orbit views | place backdrop outside the orbit shell or lower it so every orbit angle still shows the subject; an orbit view that shows only wall is a failed view |
| Refinement pass duplicates generated detail | `remove_modifier` + `delete_objects_by_prefix` the stale family before re-running a `create_geometry_nodes` recipe — replace, never accumulate |
| Facade recipe scatters onto roofs/undersides | `GN_CityWindows` restricts to near-vertical faces via a normal-dot-Z selection; keep the same pattern for other facade recipes |
| Animation declared but never keyed | `animation.missing` fail when manifest wants motion and nothing is keyframed |
| Keyframes exist but nothing moves | `animation.static` fail / `animation.partially_static` warn — sampled deltas cover loc/rot/scale/hide_render/light energy so reveal and pulse modes aren't false-flagged |
| Still render "proves" an animation | `render_preview(frames=[...])` temporal strip + verifier brief auto-includes frame samples + motion check |
| Rotationally symmetric subject "verifies" a turntable | verifier is told which objects are keyframed; invisible rotation on symmetric parts is flagged as unverifiable, not passed |
| Net as curtain of parallel strings | `create_net_lattice` — strands in BOTH directions on a quad patch + sag + border ropes; verifier checks for woven read |
| Paneled ball as sphere with stuck-on discs | `voronoi_panels` material — recessed seams + darkened cell subset on the shell itself; decals read as polka dots |
| Night sky = pure black void filling top of frame | `world.gradient` (horizon→zenith ramp) + `create_silhouette_ring` — horizon needs a glow band AND a silhouette line |
| Thrown/flying object travels a straight line then freezes mid-air | `custom` animation `keys` — arc the up-axis curve, and repeat the rest value in late keys so it *settles* |
| Material assigned in a later batch silently missing after save/reopen | create the material and assign it in the SAME job (`create_material.target_objects` or same-batch `assign_material`) — orphan materials don't persist |
| Camera aim applied before a camera animation | keyframed location/rotation overrides the raw transform — `reframe_camera` AFTER `create_animation`, then `set_active_camera` before rendering |
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
