# Web Export — GLB, three.js, R3F, Scroll

Web export is **first-class**. A web result is only "done" when the GLB loads in a
local viewer with no console errors and the integration code is generated.

## GLB rules

- Default to a single `.glb` unless a split `.gltf` is requested.
- Stay under `constraints.max_glb_mb` (manifest requires it for web modes).
- Export only what is needed: remove helpers unless tagged for the `EXPORT`
  collection; apply transforms; keep meaningful node names.
- Include animation clips if requested; include cameras only if the runtime uses
  the Blender camera path.
- Simplify/bake/report unsupported material features (see `lighting-materials.md`).
- **Validate after writing** (`scripts/export_glb.py` → `web/` validator):
  load success, console errors, animation clips, cameras, material/texture
  warnings, bounding box, approximate size.

## Optimization (optional, local only)

`@gltf-transform/functions` for dedup/prune/resize; Draco or Meshopt **only** when
the target runtime supports it; texture compression only if the local toolchain
exists and validation still passes. Never require a paid service.

## three.js / R3F integration (generated)

Generated code includes: loader setup, camera selection (or generated camera),
`AnimationMixer` handling, resize handling, disposal notes, scroll mapping when
requested, a fallback poster image, and performance-budget comments.

- `web.generate_threejs_viewer` → vanilla three.js + `GLTFLoader`.
- `web.generate_r3f_component` → React Three Fiber `<Suspense>` + `useGLTF`.
- Drei `ScrollControls` + `useScroll` for scroll-driven camera.
- GSAP `ScrollTrigger` timeline variant for scrubbed camera/animation.

## Scroll-linked section

Map scroll `0..1` to camera position/quaternion (or animation time) using the
`camera_path.json` segments. Validate that scrolling actually changes camera
state. Provide a **reduced-motion** path and a **mobile** fallback (simplified
asset or poster). The web linter flags: missing/oversized GLB, no loading
fallback, no mobile consideration, camera clipping through the model, animations
that never start, and code that references missing nodes.
