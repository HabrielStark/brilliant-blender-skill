# Camera Language

The camera is the biggest "looks expensive vs looks cheap" lever. Never just put
`camera at (0,-5,3)`. Choose a preset, frame the subject, validate coverage.

## Presets (`CameraSchema.preset`)

| Preset | Focal feel | Use case |
|---|---|---|
| `macro_product` | 70–100 mm, shallow DOF | watches, gadgets, luxury product |
| `hero_low_angle` | 35–50 mm, powerful | car / robot / device hero |
| `orthographic_technical` | ortho, no distortion | exploded view, diagrams |
| `wide_environment` | 18–28 mm, depth | corridor, city, landscape |
| `top_down_layout` | ortho/long, map view | planning, board scenes |
| `portrait_medium` | 50–85 mm | stylised character/product |
| `scroll_hero_start` | wide-ish opening | website opening section |
| `scroll_hero_detail` | tighter | web scroll feature reveal |

## Lens

- `focal_length_mm` is intentional, not default 50 unless that is the choice.
- `sensor_width_mm` 36 (full frame) by default.
- `dof=true` **requires** a `focus_target` (schema-enforced). Use DOF to separate
  subject from background, not to hide a weak scene.
- Aperture: f/2.8 for product separation; f/8+ for technical clarity.

## Composition targets

- `subject_screen_coverage` 0.4–0.7 for product heroes; the linter warns below
  0.05 (too tiny) and above 0.85 for web (mobile crop risk).
- `safe_margin` ≥ 0.08; keep the subject off the very edge.
- Named hero anatomy is part of the frame contract. Product caps, labels, logos,
  plinth/base pieces, lenses, dials, straps, screens, handles, nozzles/necks and
  comparable requested parts must be in frame unless the user explicitly asks for
  a fragment crop.
- Rule-of-thirds with a slight centre bias reads as "premium".

## Translating vague words

- **premium** → controlled focal length, shallow DOF, clean background, rim highlights.
- **cinematic** → foreground/midground/background layers, intentional contrast, not a flat front view.
- **technical** → orthographic or clean perspective, labels, no dramatic distortion.
- **website hero** → scroll-safe path, subject not too close, mobile crop considered.
- **epic** → scale reference, careful low/wide angle, atmospheric depth if hardware allows.

## Validation (`lint_camera`)

Fails on: no active camera, subject not in frame, important named hero parts out
of frame, camera inside geometry, DOF without focus target. Warns on: default
camera name, subject too tiny/cut off, multiple cameras with no
`metadata.final_camera`, coverage unsafe for mobile.
