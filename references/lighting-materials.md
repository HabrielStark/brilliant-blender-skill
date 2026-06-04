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
