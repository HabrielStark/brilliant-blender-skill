---
name: blender-cinematic-scene
license: MIT
compatibility: "Codex, Claude Code, Cursor, Gemini CLI, and other Agent Skills-compatible coding agents. Requires a local Blender (4.2+, tested on 5.0) for execution. No paid APIs required."
description: "Use when the user wants a Blender scene, cinematic 3D render, camera animation, GLB/glTF asset, 3D website hero, scroll-linked 3D effect, reference-based 3D scene, or automated Blender quality iteration. Do not use for ordinary 2D images, CSS-only animation, or non-Blender scripting."
---

# Blender Cinematic Scene Skill

Build artistically and technically sound Blender scenes through a disciplined,
hardware-aware, self-critiquing production loop. **MCP gives you tools; this
skill gives you the rules, taste, tests and iteration behaviour.** The goal is
not one-shot perfection — it is **controlled improvement within at most 10
iterations**, with honest visual QA and validated web/GLB export.

Never claim a result is *final*, *4K*, *cinematic* or *web-ready* without
artifact paths, a preview/render you actually inspected, and a validation report.

This skill exists to stop generic Blender AI slop: default cubes, vague black
objects, flat materials, weak cameras, missing detail, and scenes that pass on
paper while looking amateur. A good result must read as a designed 3D artifact:
semantic subject parts, intentional camera language, authored materials/shaders,
visible lighting structure, surface detail, exportable assets, and an inspected
preview that matches the user's brief or reference.

Style variety is part of quality. Do not collapse unrelated briefs into the same
black glossy object with cyan rim lights. Choose palette, exposure, background,
and lighting from the domain: bright technical diagrams stay readable, organic
macro work can be warm/natural, interiors can be editorial daylight, and only
briefs that ask for noir/cyber/dark product drama should stay dark.

## Mandatory workflow

1. **Classify** the request: `still`, `animation`, `web_asset`, `interactive_web`,
   `reference_match`, `scene_repair`, or `benchmark`.
2. **Manifest.** Create/validate `scene_manifest.json`
   (`scripts/scene_manifest.py validate <file>`). If the user gave no quality, use `auto`.
3. **Preflight hardware** before any heavy render
   (`scripts/preflight_hardware.py --project-dir <dir>`) and select a safe profile.
4. **Budget.** Compute the render budget (`scripts/render_budget.py`). Never start
   a final 4K render immediately; never exceed the profile's texture/sample caps.
5. **Plan** the scene (subject, composition, modeling, materials, lighting, animation,
   export) before touching Blender.
6. **Initialize** the `.blend`: the seven collections (`CAMERAS LIGHTS SUBJECT
   ENVIRONMENT FX HELPERS EXPORT`), units, scene metadata.
   Use these exact uppercase collection names. Put visible hero anatomy,
   material swatches, labels, relief, rim/catchlight geometry, contact
   reflection cards, and named details that the visual rubric should count in
   `SUBJECT`. Reserve `ENVIRONMENT` for floors/backdrops, `FX` for optional
   non-semantic effects, and `HELPERS` for invisible helpers only. Do not invent
   `Subject`, `DETAIL`, `Materials`, `TextureDetail`, or other ad hoc
   collection names; they can disappear from subject/object-count metrics.
7. **Blockout first**, then detail. Use *structured recipe operations*, not raw Python.
   Emit operation shapes exactly as the allowlist expects. Use
   `{"op":"create_material","schema":{...}}`, not flat material fields. Use
   `{"op":"create_camera","schema":{...}}`, not flat camera fields. Use
   `create_mesh_primitive` with `type`, not `primitive`; use `add_modifier` with
   `modifier`, not `modifier_type`; use `apply_transform` with
   `location`/`rotation`/`scale` booleans, not `apply_scale`. Unknown aliases
   are not portable Skill output and may fail validation before Blender opens.
8. **Use authored craft operations for visible detail:** prefer
   `create_text_label`, `create_decal_plane`, `create_curve_tube`,
   `create_fastener_pattern`, `create_panel_cutlines`, `create_grille`, and
   `create_surface_microdetails` over generic cubes for labels, badges, cables,
   screws, seams, vents, intakes, surface veins, machined hairlines, glints, and
   close-up hard-surface or organic read.
9. **Add anti-slop detail before scoring:** named subject parts, bevels/weighted
   normals, at least 3 purposeful material families, visible micro-detail for
   product/mechanical subjects, and camera framing that leaves safe margins.
   Treat named hero parts as a composition contract: cap, label, logo, body,
   plinth/base, lens, dial, strap, screen, handle, nozzle/neck and other requested
   subject anatomy must be visible in the camera unless the brief explicitly asks
   for an extreme crop. If `scene_lint` says `camera.subject_part_hidden`, fix the
   camera or subject placement before doing anything else.
   Also check physical plausibility in the preview: caps sit on necks, labels sit
   on surfaces, plinths support products, buttons/straps/lenses connect to the
   body. Floating hero anatomy is a visual failure even when the rubric passes.
   For "make it look expensive" or luxury product briefs, avoid default spheres
   and plain cylinders: use an authored faceted or machined hero body, edge
   catchlights, sapphire/glass accents, procedural metal variation, and a macro
   camera with visible depth-of-field intent. A macro camera for a full product
   hero is not an excuse to crop the product anatomy: when the brief asks for
   case, dial, logo, crown, strap, buckle, screws, reflections or similar full
   subject parts, keep `subject_screen_coverage <= 0.50` and
   `safe_margin >= 0.24` unless the user explicitly asks for an extreme crop.
   Aim `look_at` at the full assembly center (for a vertical watch with upper
   and lower strap, usually around `y=0`, not `y=0.28` on the dial/top half).
   If a preview would hide crown/strap/screws/markers, pull the camera back or
   shorten/recenter the strap before adding more detail.
   Put explicit composition hints on authored cameras:
   `composition.subject_screen_coverage` and `composition.safe_margin`.
   These are not decorative metadata; they are the contract you will verify
   against the preview. Use conservative values for complete products
   (`0.50-0.72` coverage with visible breathing room) and never leave the
   fields blank on benchmark-quality or Skill-quality outputs.
   For organic or soft-surface briefs, start from a cohesive authored body
   (fluted/lobed/waisted surface when appropriate), then add curved surface
   geometry such as petals, leaves, folds, cloth, or membranes with smooth
   shading and procedural material variation. Do not assemble the hero form from
   separate spheres or low-poly cuboid markers that merely have good names.
   For material/shader briefs, read `references/lighting-materials.md` and use
   structured procedural fields such as `color_ramp`, `wave`,
   `roughness_variation`, `edge_wear`, `scanlines`, `anisotropic`, and
   `image_textures`. A flat Principled BSDF is not a premium material, even when
   the color/roughness values are named well. Texture briefs must use real or
   generated image texture slots with declared roles such as `base_color`,
   `roughness`, `normal`, `emission`, `alpha`, or `displacement`; use mapping
   fields (`projection`, `repeat`, `offset`, `rotation_degrees`) to make labels,
   stripes, micro-print, and relief read in the render instead of relying on
   material names. A shader/material-study brief is not complete with a single
   hero object and a few labels: include material swatches, contact/reflection
   planes, visible highlight strips, cap/nozzle ridges or radial markers, and
   enough authored parts to expose each material family in the render. For
   perfume/glass/liquid/metal/label briefs, aim for at least 8 material
   families, 4 procedural materials, 30 material-targeted objects, a
   `scanlines` procedural signal on patterned/microprint labels, image texture
   roles for both `base_color` and `displacement`, and at least 5 smooth curved
   or polished subject surfaces. Leave `safe_margin >= 0.16` on material-study
   cameras unless the user explicitly asks for an extreme crop. The preview must
   keep the bottle body, base/lens, cap, nozzle/spout, front label, contact
   reflection, highlight/catchlight strips, and material swatches visible in the
   active camera; if any of those are outside the frame, pull back before adding
   more texture detail. Do not trust declared camera coverage metadata alone:
   use a physically wider camera setup for tall bottle studies (for example
   lower focal length or farther camera) and leave vertical room for cap/nozzle
   plus the base reflection. Put a visible subject object named with `ridge`
   when the cap has knurling/ridges, and add a visible `backlight` panel or
   rim-card object in `SUBJECT` when the brief asks for rim light/backlight
   read. That backlight/rim card must be physically composed with the product:
   place it behind or close beside the bottle as a background/rim plane, not as
   a detached white plate floating far from the subject. Avoid dense radial
   markers on top/back faces unless the camera can see the entire marker ring; a
   ring of hidden markers is not visual craft.
   Create materials before any operation references them. If a generated-detail
   operation (`create_linear_markers`, `create_radial_markers`,
   `create_grille`, `create_fastener_pattern`, `create_panel_cutlines`,
   `create_surface_microdetails`) must be emitted before the material exists,
   add explicit `assign_material` operations for the generated names
   (`prefix_01`, `prefix_02`, ...). Otherwise Blender will create visible parts
   with no material, and the run must fail.
   Keep generated details physically on their parent form. Strap stitching,
   holes, grain lines, buckle bridges, bezel screws, crown knurling, labels,
   glass reflections, and edge catchlights must overlap the strap/case/dial
   surface in object space and remain inside the active camera frame. Do not
   scatter decorative markers past the strap end or outside the photographed
   product just to increase detail count. For straps and narrow product bands,
   calculate the parent half-width before placing edge details: if a strap cube
   has `scale: [0.42, ...]`, visible stitches must be inside about `x=+/-0.21`
   plus a tiny surface offset, not `+/-0.36`. Use `parent` and `role` on
   generated markers when they are semantic details:
   `role: "strap_stitch"` for stitch lines, `role: "hour_marker"` for dial
   markers, `role: "bezel_screw"` for screws. Keep `create_text_label` role as
   `text_label`; express logo meaning through the object name/text, not by
   replacing the craft role with a custom logo role.
   Treat `scale` on mesh primitives as construction dimensions, not as an export
   transform. Apply scale on scaled mesh parts before parenting small generated
   details to them and before GLB/export validation; unapplied scale on rings,
   dials, markers, hands, screws, or parent bodies is a technical failure.
   Smooth the right surfaces. Faceted hero cases may keep crisp facets, but
   circular/curved objects such as bezel rings, dial discs, sapphire/glass,
   crowns, pinions, markers, screws, hands, and polished hardware need
   `set_smooth_shading` and/or weighted normals. A premium product scene should
   have several smooth curved subject objects, not one smooth glass object in a
   field of faceted defaults.
10. **Capture a preview** after every significant change (preview engine + low res).
11. **Inspect the actual preview**, not your plan. List 5 concrete visual defects and
   up to 3 technical defects (`scripts/visual_eval.py`, `scripts/scene_lint.py`).
   Cross-check the inspection JSON: every important `SUBJECT` part must have
   `in_camera_frame=true`; hero mesh normals must be clean; glass/metal edges must
   have bevel/weighted-normal support. A high numeric score is not enough if any
   lint error, obvious crop, disconnected/floating subject part, flat low-contrast
   preview, or low edge/detail density remains.
12. **Improve one targeted group of issues per iteration.** Do not rebuild randomly.
13. **Final render/export only after** hard checks pass, the rubric ≥ 80, and
   task-specific visual gates pass (`max_subject_coverage`, subject detail count,
   material variation, reference/image fidelity when provided). For `reference_match`
   or any manifest with references, real SSIM/palette reference metrics are
   required; never substitute a neutral or inferred score.
   Reference-match product recipes need enough structure to compare against the
   image, not a sparse symbolic model: use layered body shells, separate smoked
   inset panels, lens rings/core/glints, sensor details, side grooves, named
   bevel catch planes/highlights, blue rim geometry, contact reflections, at
   least 5 smooth curved/glass/lens objects, and enough operations to describe
   the reference anatomy (roughly 100+ operations for a premium product
   benchmark). Include the word `bevel` in visible bevel/catchlight object names
   when bevels are a required reference feature.
   Match the reference image before adding generic premium detail. Preserve the
   reference silhouette, object placement, brightness, contrast, and accent
   layout: if the reference is nearly black with sparse blue/white strokes, do
   not produce a bright brushed-metal block. Put the main lens, sensor, side
   grooves, top strip, bottom reflection dashes, and rim accents in the same
   relative positions as the reference (for example, lens on the right and
   sensor/grooves on the left when shown that way). Use camera and exposure to
   keep `brightness_delta` and `contrast_delta` close, then add material craft
   inside that visual envelope.
   A dark compact reference product must remain one connected, camera-visible
   silhouette, not two separated floating platforms. Build the main body first
   as a single cohesive dark shell, then attach lens, sensor, grooves, bevel
   strokes, inset panels, and reflection dashes to that shell. Keep the camera
   frontal and tight enough for reference comparison: for compact product
   references use `subject_screen_coverage` around `0.60-0.76` with
   `safe_margin >= 0.12`; avoid very wide `0.40-0.55` framings unless the
   reference itself has that much empty space, and avoid long macro lenses that
   crop the body. For compact frontal reference products, prefer a physically
   wider setup such as a `42-55mm` focal length with the camera far enough back
   to see the whole silhouette, lens, sensor, grooves, top strip, and bottom
   dashes in one frame. Do not use `70mm+` focal lengths for a full reference
   match unless a checked preview proves no subject part is cut off. For dark
   reference bodies, add
   procedural tone craft on assigned subject materials: `noise`, `bump_strength`,
   and a `color_ramp` with near-black and slightly lifted blue/gray stops so
   the Blender material inspection reports `noise_color_ramp` while the render
   still stays low-brightness and high-contrast.
   Make the reference lens visually readable, not hidden inside the dark body:
   use visible rings/discs/arcs/glints on the camera-facing surface, with the
   lens center well inside the body silhouette and away from frame edges. Avoid
   black `occlusion` patches for reference-match lens detail; they often detach
   or hide the very detail the reference metric needs. If a crescent or shadow
   is needed, make it a small attached `lens_detail` decal/curve that overlaps
   the lens disc in object space and remains visible in the preview.
   For reference-match outputs, avoid `parent_objects` for visible lens, sensor,
   groove, strip, and reflection details after placing them in world space; some
   Blender builders preserve parenting differently and can move or hide the very
   parts that must be measured. Place camera-facing details directly in their
   final coordinates, apply scale, assign materials, and leave them unparented
   unless the operation is proven by a preview.
   For frontal camera/lens references, use cylinder `size` for the visible disc
   diameter and reserve `scale` mainly for lens thickness. A reliable pattern is
   a backing/bezel cylinder with `size` about `0.60-0.68`, an outer glass/accent
   cylinder around `0.50-0.56`, an inner dark glass cylinder around `0.34-0.38`,
   all rotated camera-facing and only thin in depth (for example
   `scale: [1, 1, 0.06-0.09]`). Do not shrink the lens diameter with
   `scale: [0.18, 0.18, ...]` unless the primitive's `size` is also set; it can
   render as a tiny flattened side mark instead of the readable circular lens in
   the reference. Keep the body material near-black and let white/blue strokes
   define form; avoid a broad gray metallic slab when the reference is black.
   Follow the local recipe examples for camera-facing cylinder rotation: use
   `rotation: [90, 0, 0]` for front-facing lens/sensor discs in these structured
   recipes, not `1.5708`, unless the specific builder documentation for that
   operation says radians. A wrong right-angle unit makes the lens render as a
   thin side ellipse instead of a circular front glyph.
   If the user supplies a reference image, inspect it directly before writing
   the recipe. Do not infer from text alone. Record the observed layout in scene
   metadata (for example `reference_observation`) and place the Blender parts to
   match that observation. A live Skill evaluation with real SSIM/edge/brightness
   gates is invalid if the agent never saw the reference pixels.
   For Skill-quality regression work, run prompt-scenario acceptance
   (`scripts/run_prompt_scenarios.py`) so prompt-shaped recipe artifacts are
   checked for semantic anatomy, authored craft, material/shader detail,
   camera/lighting, and provenance before they are treated as valid Skill
   outputs. Use `--render` when Blender is available.
14. For web assets: **export GLB and validate it locally** (`scripts/export_glb.py`
   then `web/` validator). Generate the three.js/R3F integration and a camera path.
    For scroll/camera animation, verify `camera_path_json` exists in inspection
    and includes timeline segments plus sampled camera positions whose first and
    last positions differ meaningfully; do not accept a web hero with a static
    camera pretending to be scroll-linked.
    For turntable or product animation, use `create_animation` with a real
    frame range, `loop: true` when the brief asks for a loop/turntable,
    at least the visible hero detail objects in `targets`, and
    `export.include_in_glb: true` when GLB/web export is requested. A static
    product with nice lighting is a failure for an animation brief.
    Product turntables should be readable studio product shots, not automatically
    very-dark noir scenes. If the prompt asks for modeled details to remain
    readable during rotation, use neutral/cool studio lighting, enough fill on
    the floor/background, and sufficient modeled geometry density; avoid
    `very_dark` style outcomes unless the user explicitly asks for a dark/noir
    turntable. Dense product animation gates may require extra fins/ribs/ring
    details and bevel segments so the mesh has enough real geometry, not only
    named low-face boxes.
15. **Final report** with artifact paths, scores, passes, failures and limitations
    (`scripts/report_writer.py <dir>`).

## Iteration budget

`still ≤ 3`, `web_asset/animation ≤ 6`, `reference_match ≤ 8`, `interactive_web ≤ 10`
(global hard cap 10). Stop early when the rubric passes. Stop with a failure report
if three consecutive iterations do not improve the score.

## Hard-fail (reject before final output)

No active camera · subject not visible · render almost all black/white · default
materials on key objects · no meaningful lighting · requested animation without
keyframes · requested GLB cannot load locally · exported asset references missing
textures · final output without manifest/report · subject cropped against the
frame edge · important hero parts outside the camera frame · flipped/broken
normals · product/mechanical subject made from too few meaningful parts.

## Never

- Never claim 4K just because resolution is 3840×2160.
- Never skip preview inspection or invent a score you did not measure.
- Never accept a render just because it scores high if the actual image still
  looks like generic primitives, missing subject anatomy, or weak camera work.
- Never reuse the same dark/cyan visual language across unrelated briefs just
  because it looks superficially cinematic.
- Never claim final production taste signoff from automated scores alone. Use
  blind/human review JSON for release acceptance, or mark the run explicitly as
  `--allow-unreviewed`.
- Never leave default `Cube.001` / `Material.001` names in a final scene.
- Never run heavy final renders before preflight, or above the selected profile.
- Never require paid APIs, cloud render farms, or unlicensed assets.
- Never expose or rely on raw Blender Python execution in normal mode.

## References (progressive disclosure)

| File | When to read |
|---|---|
| `references/hardware-quality-profiles.md` | choosing/defending a profile, weak hardware |
| `references/camera-language.md` | framing, focal length, DOF, "make it look expensive" |
| `references/composition-rubric.md` | scoring composition, negative space, depth |
| `references/lighting-materials.md` | light rigs + PBR/procedural material recipes |
| `references/procedural-modeling-recipes.md` | bevels, modifiers, geometry nodes, greebles |
| `references/animation-camera-paths.md` | turntable, flythrough, scroll-linked camera |
| `references/web-export-threejs-r3f.md` | GLB rules, three.js/R3F/ScrollControls/GSAP |
| `references/visual-critique-rubric.md` | the 100-point rubric + refinement logic |
| `references/failure-modes.md` | the common ways agents ruin Blender scenes |
| `docs/prompt-scenario-evals.md` | prompt artifact eval levels and provenance boundaries |
