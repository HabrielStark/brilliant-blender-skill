# Procedural Modeling Recipes

## Modifiers (allowlisted in `recipes.py`)

`BEVEL`, `SUBSURF`, `ARRAY`, `MIRROR`, `SOLIDIFY`, `WEIGHTED_NORMAL`, `DECIMATE`,
`TRIANGULATE`, `SHRINKWRAP`, `BOOLEAN`, `CURVE`, `WIREFRAME`.

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
- `BOOLEAN` only when the result is validated (non-manifold artifacts warn/fail).

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
