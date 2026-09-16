# Lighting & Materials

## Lighting rigs (`LightingSchema.lighting_rig`)

| Rig | Use case |
|---|---|
| `three_point_soft` | generic readable lighting |
| `studio_product_large_softbox` | premium product |
| `neon_cyberpunk` | sci-fi / cyberpunk |
| `corridor_practical_lights` | environment depth |
| `technical_clean` | diagrams / exploded views |
| `dramatic_rim` | hero edge highlights |
| `world_hdri_like` | environment fill without paid HDRIs |
| `low_spec_flat_safe` | weak-hardware fallback |

Lighting makes form readable. The render must not be black-crushed, blown out, or
flat. `lint_lighting` fails a scene with no lights and no world strength, or with
only default-named lights; the evaluator scores lighting from real image
brightness/contrast. Metallic and glass need highlights — give them something to
reflect (rim light, specular card, bright world patch).

Avoid defaulting to dark/cyan. Use the brief to pick exposure and palette:
technical/exploded views should be clean and readable, safe-hardware scenes
should use simple bright separation, organic scenes should keep natural warmth,
and material studies should expose shader texture detail instead of hiding it in
black.

### Three-point quick recipe

- **Key** `AREA`, large (size 3–5), front-left-high, power ~ 300–600 W.
- **Fill** `AREA`, dimmer (¼ key), opposite side, soft.
- **Rim** `AREA`/`SPOT`, behind/above, coloured for separation (cold blue reads premium).
- **World** low strength (0.2–0.5) so shadows are not pure black.

### Aiming lights

`position_role` only *places* a light — an AREA light at `rim` position still
points straight down unless you aim it. Every light accepts:

- `look_at: [x, y, z]` — rotate so the light's -Z axis points at that coordinate.
- `target: "<object name>"` — aim at the object's location (resolved at build
  time; a missing target leaves the light unrotated).

Use `look_at`/`target` for any light that must strike a surface: grazing side
lights, backdrop pools, fill cards. Role-only lights are fine for broad soft
coverage where direction barely matters.

## Material presets (`MaterialSchema.preset`)

`matte_plastic`, `glossy_plastic`, `brushed_metal`, `painted_metal`, `glass_clear`,
`frosted_glass`, `emissive_neon`, `rubber_dark`, `fabric`, `skin_stylized`,
`stone_concrete`, `wood`, `water_simple`, `hologram`, `metallic_roughness_pbr`.

Every important material is **named and intentional**: base color, roughness,
metallic where relevant, emission where relevant; glass/alpha/transmission only
when needed; procedural noise/bump for close surfaces.

### Procedural patterns

Edge wear (brighten bevels), dust/dirt (noise mask in cavities), micro scratches
(anisotropic lines), fingerprints (roughness variation), fabric weave, multi-scale
concrete, hologram scanlines, glass imperfections, layered energy core.

### Structured procedural shader features

Use `create_material.schema.procedural` for deterministic shader-node craft
instead of ad hoc Python:

- `noise: true` adds noise-driven bump for close-up surface breakup.
- `color_ramp: {...}` routes noise through a color ramp into base color for
  brushed metal variation, patina, tinted glass, or stone veining.
- `wave: {...}` adds wave-driven bump for strap grain, machined grooves, panel
  seams, or fabric-like ridges.
- `roughness_variation: {...}` routes procedural noise into roughness for
  fingerprints, uneven clearcoat, glass imperfections, worn metal, or fabric nap.
- `edge_wear: "subtle" | "medium" | "heavy"` adds an ambient-occlusion mask and
  color layer for handled edges, liquid rim highlights, bevel wear, and patina.
- `scanlines: true` adds a high-frequency wave/color layer for holograms,
  display labels, micro-printing, and technical overlays.
- `voronoi_panels: {scale, seam_color, seam_width, seam_bump,
  cell_darken: {fraction, color}}` draws recessed seam lines at voronoi
  cell edges and darkens a random subset of cells — football panels,
  cracked earth, tiles, scaled skin. Stuck-on decal discs read as polka
  dots; seams on the shell itself read as panels.
- `grid_alpha: {scale, line_width, axes}` turns a plane into a real
  net/grate — opaque strands along two generated axes (`"XY"` default; use
  `"XZ"` for a vertical panel) with transparent holes between. Cheap nets,
  fences, screens at mid/far distance; use `create_net_lattice` geometry
  when the net is a hero close-up element.
- `world.gradient` on `create_lighting_rig` (or `adjust_world.gradient`)
  maps view direction to a below/horizon/zenith ramp — the fix for a night
  sky rendering as a flat black void. Pair with `create_silhouette_ring`.
  Keep `below` near-black: at night the whole sub-horizon dome renders as a
  pale slab if it carries any brightness.
- `window_grid: {columns, rows, lit_fraction, window_color,
  emission_strength, line_width, axes}` maps a facade into lit window
  cells — snapped per-cell white-noise decides which are lit, so cells are
  clean rectangles with stable random lit/dark variation. Night buildings,
  distant cities, stadium towers. Assign one material to a whole skyline
  family; per-object Object coords keep each building's pattern unique.
  Do NOT put full-face emission on skyline buildings — they render as pale
  monoliths.
- `anisotropic` plus `wave` makes brushed metal read as machined instead of flat
  yellow/grey Principled BSDF.
- `image_textures: [...]` loads real file textures or deterministic generated
  textures by role (`base_color`, `roughness`, `normal`, `emission`, `alpha`,
  `displacement`). Use `generated: "checker_label"`, `"stripe_label"`, or
  `"microprint_label"` when the brief needs texture craft but no asset file was
  supplied. Missing image paths are reported in inspection; do not silently
  pretend a texture loaded.
- Image textures support authored mapping: `projection` (`uv`, `generated`, or
  `object`), `repeat`, `offset`, and `rotation_degrees`. Use these fields for
  product labels, display microprint, machined stripe relief, woven fabric
  direction, and other close-surface reads. Do not accept a texture node that is
  merely present but visually unscaled or misplaced.
- Every generated mesh receives a UV layer automatically — parametric on
  grid-built surfaces (organic surface, drape, energy streaks) and a
  dominant-axis box projection elsewhere — so `projection: "uv"` is safe by
  default. For a specific projection or a named channel, run
  `{"op": "generate_uv", "target": "…", "method": "box|cylinder|sphere",
  "name": "UVMap.decal"}` and point `uv_map` at that name. Inspection reports
  `uv_layers` per object; an empty list on a `uv`-textured object is a defect.
- The `displacement` image role wires through a Blender displacement node for
  material-study relief. Keep strength subtle unless the brief asks for visible
  embossing; the texture should reveal craft, not destroy the form.

For hero product/material tasks, require multiple assigned subject materials
with non-trivial linked node graphs, not just one ornate material hidden on a
minor prop. A serious material study should expose different shader families:
tinted glass, liquid, brushed metal, label texture, emissive highlight, and
reflective surface. Inspection should show rich node/link counts and recognizable
node signatures such as `EdgeWearAO`, `ScanlineWave`, `RoughnessRamp`,
`Mapping`, and `TexCoord` where those features are requested. Do not accept a
"premium shader" made only from a flat Principled BSDF.

### Node naming

Good: `NG_BrushedMetal_Base`, `NG_EdgeWear_Subtle`, `NG_Hologram_Scanlines`.
Forbidden: `NodeGroup.001`, `Material.004`, `Noise Texture.023`.

## Post-processing (`apply_post`)

`view_transform`/`look`/`exposure`/`gamma` set color management.
`effects.bloom` (`off`/`low`/`medium`/`high`) wires a compositor **Glare →
output** chain so emissive neon, VFX cores, and highlights actually bloom —
use it on emissive scenes; without it "glowing" materials render flat. For
explicit control pass `compositor.glare` `{type, threshold, size, strength,
quality}` (`type` accepts `fog_glow`/`bloom`/`streaks`/`ghosts`…; Blender 5.0
menu sockets take title-case values, handled internally).

The other `effects` fields are live too — they extend the same compositor
chain (`color_balance → mist → glare → vignette → output`):

- `effects.vignette` (`off`/`subtle`/`strong`): ellipse-mask + blur multiply
  that darkens frame corners. Use `subtle` for product heroes to keep the
  eye on the subject.
- `effects.mist` (`true`) enables the **mist pass** and fades depth toward a
  fog color — atmospheric depth for landscapes/exteriors. Tune via
  `compositor.mist` `{start, depth, falloff, color}` (world-space distances;
  pick a fog color near the horizon/sky tone, e.g. warm peach for golden
  hour).
- `effects.color_balance` (`neutral`/`warm`/`cool`): multiplies the frame by
  a warm or cool tint — cheap global grade.

Every `effects`/`compositor` value is schema-constrained — a typo fails
validation instead of silently rendering flat.

## Web/export policy

For GLB targets, set `export_policy.web_safe`. Unsupported shader tricks
(complex procedural graphs, true volumetrics) must be **baked or simplified** to a
`metallic_roughness_pbr` fallback, or reported. `lint_materials` fails a web export
that uses a `web_unsafe` material with no fallback, and warns when a material graph
is too heavy for a web-bound asset or the texture exceeds the profile cap.

## Material linter highlights

Fails: missing material on key object, default/grey material, value out of [0,1],
web material without fallback, texture over cap. Warns: unused material, monotone
(all key objects share one material), metallic with no bevel+light to reveal it,
heavy node graph for web.
