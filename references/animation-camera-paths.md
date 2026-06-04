# Animation & Camera Paths

## Modes (`AnimationSchema.mode`)

| Mode | Output |
|---|---|
| `turntable` | frame sequence/video + optional GLB clip |
| `camera_flythrough` | camera path + preview |
| `scroll_linked` | GLB + `camera_path.json` + R3F code |
| `exploded_view` | animated parts + labels |
| `reveal` | keyframed visibility / material alpha |
| `loop_idle` | seamless loop |
| `light_pulse` | emission / intensity animation |
| `rig_basic` | basic armature/pose, only when requested |

## Keyframe rules

- Intentional interpolation: `linear`, `ease_in_out`, `ease_in`, `ease_out`, `hold`,
  `bezier`, `constant`.
- Timeline **markers** for important beats (the linter warns when a ≥60-frame
  animation has none).
- Camera motion is **previewed** before the final render.
- Loops must match first/last frame (`loop_match`); a mismatch warns.
- No random keyframes — explain them in the manifest.
- Keyframes are not enough by themselves. Inspect sampled start/mid/end frames
  and verify that animated objects or the active camera actually move. A static
  object with an action, a tiny wobble, or a scroll camera path that never
  changes the Blender camera is animation slop.
- For release benchmarks, render start/mid/end proof frames and compare the
  images. A turntable must visibly change the silhouette/details between frames;
  a multi-part product should orbit around a shared center, not rotate every
  detached part in place. A scroll hero should keep the first frame readable and
  then move the active camera enough to create a visible rendered delta.

## Camera paths

Provide a curve/path object or explicit sampled transforms; smooth speed; keep the
subject framed throughout; change focal length / DOF target only when justified;
capture a viewport preview.

## Scroll-linked web (`ScrollTimeline`)

Map Blender frames to scroll progress `0..1` in non-overlapping segments:

```json
{ "scroll_timeline": { "duration_pages": 4, "segments": [
  {"from_scroll":0.0,"to_scroll":0.25,"camera_from_frame":1,"camera_to_frame":40,"text_section":"intro"},
  {"from_scroll":0.25,"to_scroll":0.60,"camera_from_frame":41,"camera_to_frame":90,"text_section":"feature_reveal"}
]}}
```

Export the path as `camera_path.json` (native GLB camera animation is unreliable
across runtimes). Inspection must expose the same `camera_path_json` with
`schema: camera_path/0.1`, timeline segments, and sampled camera positions.
Reject paths whose sampled first and last camera positions are effectively the
same; a static camera with a JSON file is not a scroll-linked animation.
Always include a **reduced-motion fallback**.

## Animation linter

Fails: animation requested but no keyframes; invalid frame range; camera animated
with no active camera; GLB requested but clip not exported; scroll web with no
`camera_path.json`, no scroll timeline segments, too few sampled positions, or a
static sampled camera path. Warns: default 1..250 range, loop mismatch, missing
markers.
