# Procedural Modeling Recipes

## Modifiers (allowlisted in `recipes.py`)

`BEVEL`, `SUBSURF`, `ARRAY`, `MIRROR`, `SOLIDIFY`, `WEIGHTED_NORMAL`, `DECIMATE`,
`TRIANGULATE`, `SHRINKWRAP`, `BOOLEAN`, `CURVE`, `WIREFRAME`, `DISPLACE`,
`SIMPLE_DEFORM`, `WELD`, `CAST`, `REMESH`.

`SIMPLE_DEFORM` params use raw bpy values — `angle` is **radians**
(0.1–0.2 rad ≈ 6–12° for a subtle wind lean on grass/leaf blades; >0.4 rad
flops geometry). `deform_method`: `BEND`/`TWIST`/`TAPER`/`STRETCH`;
`deform_axis`: the axis the deform wraps around (X bends a Z-tall object).
`WELD` merges duplicate verts after booleans; `REMESH` voxel-remeshes blobby
organics; `CAST` projects toward sphere/cylinder.

`add_modifier` `params` accept **object and texture names** and resolve them at
build time — `{"modifier": "BOOLEAN", "params": {"object": "cutter_name",
"operation": "DIFFERENCE"}}`, `{"modifier": "DISPLACE", "params": {"texture":
"noise_tex", "strength": 0.1}}`, `{"modifier": "MIRROR", "params":
{"mirror_object": "rig_root"}}` all work. Unknown or mistyped params are
reported in the op result as `skipped_params` instead of silently dropping.

`DISPLACE` needs a texture datablock — create one first with
`create_procedural_texture` (`type`: `CLOUDS`, `VORONOI`, `DISTORTED_NOISE`,
`NOISE`, `MARBLE`, `WOOD`, `MAGIC`, `BLEND`, `STUCI`; plus `noise_scale`,
`contrast`, `noise_depth`). Use it for terrain relief, worn surfaces, and
organic asymmetry; keep `strength` small on hero forms.

### Hard-surface quality rules

- For luxury/product hero forms, prefer an authored faceted or machined body over
  a smooth primitive. A faceted body should keep flat face reads, use bevel and
  weighted normals for controlled catchlights, and add separate visible accent
  details instead of relying on material gloss alone.
- Almost every premium hard-surface object gets a **bevel** (width proportional to
  scale, 2–6 segments) so edges catch light. `lint_mesh` warns when a key object in
  a premium render has no bevel/subsurf and is not smooth-shaded.
- Recalculate/validate **normals**; flipped normals are a hard error.
- Apply **scale** before export (unapplied scale + export request is an error).
- Use **array/mirror/instances** instead of hundreds of duplicate loose objects.
- `BOOLEAN` only when the result is validated — the op reports
  `boolean: {eval_faces, non_manifold_edges}` and fails cleanly when the
  operand is missing, not a mesh, or the target itself.

### Repair ops (mechanical fixes, no judgment needed)

- `reframe_camera` `{camera?, look_at, pull_back}` — re-aim the active
  camera at a point and scale its distance. Use when inspection reports
  offscreen subject objects or overcoverage; escalate `pull_back`
  (1.25 → 1.7) rather than nudging repeatedly. No-op on keyframed cameras.
- `adjust_world` `{color?, strength?, strength_scale?}` — retune world
  ambient when a preview tags `very_dark`/`very_bright` without rebuilding
  the light rig.
- The benchmark runner applies these automatically (max 2 rounds) when a
  skill-mode result fails a repairable check, then re-validates the whole
  scene — repairs that break other checks still fail.

### Boolean cutter workflow (recesses, ports, slots)

For a real inset (USB port, vent slot, button well) instead of a surface
decal:

1. Create the cutter as a normal primitive in `HELPERS` with
   `"hide_render": true` (also hides it from the viewport; it still
   evaluates as a modifier operand). `add_modifier` auto-hides the operand
   too, but the flag keeps intent explicit.
2. `add_modifier` `BOOLEAN` on the target with `params.object` = cutter
   name. Place `BOOLEAN` **before** `BEVEL` in the op order so cut edges
   get the chamfer real ports have.
3. Keep a thin dark plate just inside the cut as the port's inner wall —
   a hole alone reads as a void, not a connector.
4. Hidden cutters are excluded from renders and `use_visible` GLB exports;
   verify the cut with the `boolean` health fields in the op result
   (`non_manifold_edges` should stay 0) rather than trusting the name.

## Authored craft detail operations

Use these structured operations when a detail must read as a specific designed
thing, not as generic filler geometry.

| Operation | Use for |
|---|---|
| `create_text_label` | real `FONT` text for brand marks, labels, callouts |
| `create_decal_plane` | thin plates, badges, decals, interface cards |
| `create_curve_tube` | real bevelled `CURVE` cables, wires, hoses, trim |
| `create_fastener_pattern` | screws, bolts, rivets, washers |
| `create_panel_cutlines` | seams, engraved/raised panel cuts, product split lines |
| `create_grille` | vents, speaker grilles, heatsinks, intakes |
| `create_surface_microdetails` | raised micro-lines, veins, edge glints, machined hairlines, texture relief geometry |

Inspection exposes these objects with `craft_role`, `craft_group`, and
`craft_source`. If a product/mechanical brief needs labels, screws, vents,
cables, seams, or badges and the recipe only creates anonymous cubes, treat it
as anti-slop failure even if the object count is high.
For macro product, shader, VFX, and organic soft-surface briefs, micro-detail is
also a visual contract: use `surface_microdetail`, `organic_surface`, or
domain-specific craft roles so the review can distinguish real close-up surface
work from renamed filler objects.

## Geometry-node recipes (`GeometryNodeSchema.recipe`)

| Recipe | Purpose |
|---|---|
| `GN_PanelWall` | corridor / architecture panels |
| `GN_BoltDistributor` | bolts / rivets on surfaces |
| `GN_CableBundle` | controlled curve cables |
| `GN_CityWindows` | window grids with emissive variation |
| `GN_RockScatter` | deterministic rock / asteroid scatter |
| `GN_TechGreebles` | sci-fi surface detail |
| `GN_LabelArrows` | exploded-view arrows / labels |
| `GN_OrbitalRings` | rings around a core / planet / product |
| `GN_ParticleDots` | lightweight dots / field points |
| `GN_VegetationLow` | simple grass / leaves for safe scenes |

### Determinism & budget

Every geometry-node group logs a **seed**, an estimated face count, and whether it
is applied/baked before export. `estimate_complexity` rejects geometry that would
blow the face budget *before* Blender runs. `lint_geometry` fails an unbaked node
group on a web export and when generated faces exceed budget; it warns on a missing
seed, a default node-group name, results invisible from camera, or procedural
detail that dominates the subject.

Recipe names are visual contracts, not labels. `GN_PanelWall` must read as raised
wall plates, `GN_CableBundle` as curved cables, `GN_OrbitalRings` as rings, and
so on. Inspection exposes generated detail objects with `gn_recipe` and `gn_role`;
if different recipes only produce the same cube scatter, treat that as a failed
implementation even when the node group exists and has a seed.

### When NOT to use geometry nodes

A plain mesh + modifier is enough; export has no bake path; it creates unbounded
geometry; weak hardware + high node complexity; results would be random without a
logged seed.
