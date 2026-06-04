# Benchmark Rubrics

Every benchmark task is scored by the same engine the live pipeline uses
(`blender_cinematic.evaluation.score_iteration`, the 100-point rubric in
`references/visual-critique-rubric.md`) plus per-task `checks`.

## Modes

- `skill_plus_tools` runs the task's structured skill recipe through Blender,
  inspects, lints, scores, and validates web export.
- `baseline_no_skill` (`--baseline`) runs the task's naive recipe: bare
  primitives, no camera/lights/materials. It should fail for contrast.
- `adversarial_slop_*` (`--baseline`, when configured) runs plausible but weak
  scenes with cameras, lights, materials, and keyword-heavy names. These must
  fail; otherwise the checks are rewarding well-named slop.

## Pass Criteria

| Field | Meaning |
|---|---|
| `min_score` | rubric total must reach this, default 80 |
| `require_glb` | a GLB must exist and pass local validation |
| `require_animation` | the scene must contain keyframes/an exported clip |
| `max_subject_coverage` | rejects overcropped hero framing even when score is high |
| `min_subject_objects` | requires enough semantic subject detail to avoid primitive slop |
| `min_visible_subject_objects` | requires enough subject parts to be visible in the final camera |
| `max_offscreen_subject_objects` | rejects scenes where important subject parts fall out of frame |
| `min_subject_depth_layers` | requires separated layout/exploded-view layers along an inspected axis |
| `require_named_parts` | requires semantic subject names such as screw, trace, contact, sofa, petal, or rim |
| `min_named_part_object_coverage` | ignores named-part objects below this visible screen-coverage floor for anti-micro-detail gates |
| `min_distinct_named_part_objects` | requires enough distinct visible semantic parts so one keyword-stuffed object cannot satisfy the brief |
| `min_named_part_total_coverage` | requires semantic named parts to contribute meaningful visible frame area, not only exist in the scene graph |
| `min_subject_total_faces` | requires a minimum mesh-detail floor for hard-surface/reference tasks |
| `min_subject_modifiers` | requires modeled bevels/arrays/subdivision/solidify/technical surface treatment |
| `min_smooth_subject_objects` | requires smooth organic/soft-surface forms rather than faceted primitives |
| `min_curved_detail_objects` | requires smooth named petal/leaf/fold mesh details with enough faces; low-poly cuboid markers do not count |
| `curved_detail_keywords` | names that identify curved detail families for `min_curved_detail_objects` |
| `curved_detail_min_faces` | minimum per-object face count for a curved detail object |
| `min_environment_objects` | requires enough modeled environment parts for interior/world scenes |
| `min_visible_environment_objects` | requires environment parts to be visible in the final camera |
| `max_offscreen_environment_objects` | rejects environment scenes where too many important surroundings are out of frame |
| `min_environment_depth_layers` | requires separated environment layout/corridor layers along an inspected axis |
| `environment_depth_axis` | inspected axis for `min_environment_depth_layers` |
| `environment_depth_tolerance` | grouping tolerance for environment depth bands |
| `require_environment_named_parts` | requires semantic environment names such as floor, wall, window, shelf, or rug |
| `min_environment_materials` | requires material variation in the environment, not only on the hero subject |
| `min_subject_materials` | requires visible material variation on the subject |
| `min_subject_material_node_count` | requires at least one non-trivial subject shader graph |
| `min_subject_material_link_count` | requires at least one subject shader graph with enough real node links |
| `min_rich_linked_subject_materials` | requires several assigned subject materials to exceed node/link thresholds, not only one hero material |
| `rich_material_min_nodes` / `rich_material_min_links` | define the per-material thresholds used by `min_rich_linked_subject_materials` |
| `min_subject_procedural_materials` | requires procedural shader features on subject materials |
| `require_subject_material_features` | requires specific shader-node features such as `noise_color_ramp`, `wave_bump`, or `checker_texture` |
| `require_subject_material_node_name_substrings` | requires inspected material node names that prove specific authored shader subgraphs are present |
| `require_subject_image_texture_roles` | requires declared image texture roles such as `base_color` and `displacement` |
| `forbid_visual_style_tags` | rejects previews whose measured style tags conflict with the task intent, such as `very_dark` or `dark_blue_cyan` on bright technical/interior/material-study briefs |
| `require_visual_style_tags` | requires measured style tags when a task intentionally asks for a family such as warm, bright, or dark/cinematic output |
| `min_emissive_materials` | requires enough emissive shader families for VFX/neon scenes |
| `min_particle_systems` | requires real inspected Blender particle systems, not only manually placed spark meshes |
| `min_total_particles` | requires the configured/evaluated particle count to meet the VFX task floor |
| `min_palette_similarity` | requires rendered palette to match the reference/style palette anchors |
| `require_reference_image` | requires an actual reference image file instead of neutral reference scoring |
| `min_reference_ssim` | requires structural similarity to the configured reference image |
| `min_reference_saliency_iou` | requires the render's salient silhouette/highlight mask to overlap the reference |
| `min_reference_edge_iou` | requires edge/detail structure to overlap the reference |
| `max_reference_center_delta` | limits composition-center drift from the reference salient region |
| `max_reference_coverage_delta` | limits subject/highlight coverage drift from the reference |
| `max_reference_brightness_delta` / `max_reference_contrast_delta` | limits tone and contrast drift from the reference |
| `min_animation_frames` | requires enough timeline duration for requested animation |
| `min_keyframed_objects` | requires actual keyed targets, not an empty action |
| `min_sampled_moving_objects` | requires inspected start/mid/end frame samples to show enough actually moving animated objects |
| `min_sampled_rotation_radians` | requires sampled animated rotation to change meaningfully, catching near-static keyframes |
| `min_sampled_location_delta` | requires sampled animated location movement to change meaningfully |
| `require_camera_animated` | requires the active camera itself to have animation data |
| `min_camera_sampled_location_delta` | requires sampled active-camera movement across the animation |
| `require_animation_frame_proof` | requires benchmark-rendered start/mid/end animation frames for visual motion proof |
| `min_animation_frame_delta` | requires rendered animation frames to differ by enough mean RGB delta |
| `min_animation_changed_pixel_ratio` | requires enough pixels to visibly change across rendered animation frames |
| `require_glb_animation` | requires exported GLB animation clips |
| `require_camera_path` | requires generated `camera_path.json` for scroll/interactive scenes |
| `min_camera_path_samples` | requires enough sampled camera states for smooth scroll playback |
| `min_camera_path_distance` | requires meaningful camera movement across the sampled path |
| `min_geometry_node_groups` | requires real Geometry Nodes modifiers in inspected Blender scene |
| `require_geometry_seed` | requires deterministic seed capture for procedural node graphs |
| `min_geometry_node_count` | requires non-trivial Geometry Nodes graph complexity |
| `min_geometry_link_count` | requires linked node graph, not an empty node group |
| `min_geometry_detail_objects` | requires inspected visual objects generated from Geometry Nodes recipes, so a node group name alone cannot satisfy the task |
| `require_geometry_detail_roles` | requires recipe-specific generated roles such as `panel_wall_plate`, `cable_curve`, `orbital_ring`, or `bolt_head` |

A task also fails on any hard-fail: no camera, black render, default materials,
no lighting, missing requested animation, or un-loadable GLB.

## Result Shape

```json
{ "task_id": "product_hero_watch", "mode": "skill_plus_tools", "pass": true,
  "visual_score": 90, "technical_score": 100, "runtime_seconds": 6.0,
  "iterations": 1, "artifacts": ["...preview.png", "...export_final.glb"], "failures": [] }
```

## Expected Contrast

The skill recipe should pass while the naive baseline hard-fails. When
adversarial baselines are configured, those must fail too. The naive gap proves
basic structure; the adversarial gap proves the checks reject plausible
AI-slop scenes that have cameras, lights, materials, and matching keywords but
lack real anatomy/detail.

## Tasks

`architectural_interior_scene` (environment), `product_hero_watch` (shader),
`sci_fi_corridor` (geometry nodes), `mechanical_exploded_view` (rig),
`web_scroll_hero` (web/GLB/scroll), `low_spec_laptop_safe` (safe downshift),
`organic_soft_surface_study` (organic/soft surface),
`particle_vfx_energy_burst` (VFX/particles), `reference_match` (palette),
`shader_texture_material_study` (shader/texture nodes),
`turntable_animation` (animation clip), `scene_repair` (repair),
`glb_web_budget` (export budget), `camera_expensive` (cinematography).

For `organic_soft_surface_study`, the main hero form must read as one cohesive
fluted or lobed soft-surface body, not a cluster of unrelated spheres. Curved
detail gates then prove petals, leaves, and cloth folds are modeled as smooth
surface meshes with enough resolution to survive a macro camera.
