# Web Export

Web is first-class: a web result is only "done" when the GLB loads in a local
viewer with no console errors and the integration code + camera path are
generated.

## Export

```bash
python scripts/export_glb.py --blend artifacts/<task>/final/scene.blend \
                             --out  artifacts/<task>/final/export_final.glb --max-mb 20
```

The exporter (`addon/.../exporter.py`) runs `export_scene.gltf` with
`export_apply=True` (bakes modifiers + geometry nodes), hides
`HELPERS`/`REFERENCE`/`PROXIES`, and keeps meaningful node names.

## Validation (two independent validators)

- **Python** (no deps beyond stdlib): `blender_cinematic.glb.validate_glb` â€”
  parses the GLB container, reports node/mesh/material/animation/texture counts
  and size, and flags external textures, empty scenes, oversize, missing clips.
- **Node** (`@gltf-transform/core`): `node web/dist/web_validate_asset.js` or `bcas-validate-glb` with `<file.glb> --max-mb 20` -- the runtime-grade cross-check.

```bash
npm run build
node web/dist/web_validate_asset.js artifacts/<task>/final/export_final.glb --max-mb 20
bcas-validate-glb artifacts/<task>/final/export_final.glb --max-mb 20
```

## Generated integration

`blender_cinematic.webgen.generate_integration` (and the MCP
`web_generate_integration` tool) write:

- `index.html` â€” vanilla three.js + `GLTFLoader` viewer (poster-ready).
- `Scene.jsx` â€” React Three Fiber `<Canvas>` + `useGLTF`.
- `ScrollHero.jsx` â€” Drei `ScrollControls` + `useScroll`, reduced-motion aware.
- `scroll_scene.js` â€” GSAP `ScrollTrigger` scrubbed-camera variant.
- `camera_path.json` â€” scroll `0..1` â†’ sampled camera position/target.

See `examples/web-demo/` for a generated set with a real `scene.glb`.

## Scroll-linked camera

Define non-overlapping segments mapping scroll progress to Blender frames
(`ScrollTimeline` schema). The path is exported as `camera_path.json` because
native GLB camera animation is unreliable across runtimes. Always ship a
reduced-motion fallback and a mobile/poster fallback.

## Budget & material rules

Stay under `constraints.max_glb_mb`. Glass/transmission and heavy procedural
graphs are `web_unsafe` â€” declare a `fallback_material` (and the exporter bakes).
The material linter fails a web export that uses an unsupported material with no
fallback.
