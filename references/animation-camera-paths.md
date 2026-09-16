# Animation & Camera Paths

## Modes (`AnimationSchema.mode`)

| Mode | Output |
|---|---|
| `turntable` | frame sequence/video + optional GLB clip |
| `camera_flythrough` | camera path + preview |
| `scroll_linked` | GLB + `camera_path.json` + R3F code |
| `exploded_view` | animated parts + labels |
| `reveal` | keyframed visibility / material alpha |
| `loop_idle` | seamless breathing loop: subtle scale pulse + yaw sway returning to rest (params: `sway_degrees`, `breathe`) |
| `light_pulse` | emission / intensity animation |
| `bone_pose` | pose-bone gesture on `"armature.bone"` targets (params: `degrees`, `axis`) — rest → swing → rest |
| `custom` | free-form f-curve animation via `curves` — the generic carrier for authored motion |

## `custom` mode — authored curves

`curves` keys any of `location_x/y/z`, `rotation_x/y/z`, `scale_x/y/z`.
Two shapes per curve:

- `{"from": a, "to": b, "interpolation": "linear"}` — keys at frame_start /
  frame_end. Use `linear` for spins; omit interpolation for smooth bezier.
- `{"keys": [[frame, value], ...]}` — multi-point trajectories. This is the
  arc/bounce/settle tool: a thrown object is `location_z` rising then
  falling, a landing is a peak key followed by a flat settle key — not a
  straight line that freezes mid-air.

Real motion almost always needs **keys, not from/to**: a ball lobbed into a
net arcs up, dips in, then *settles* (later keys repeat the rest value).
`exploded_view` only moves radially from world origin — fine for part
separation, wrong for a directed throw unless the layout is built around it.

```json
{"op": "create_animation", "schema": {
  "animation_name": "throw_in", "mode": "custom",
  "frame_start": 1, "frame_end": 48, "targets": ["ball"],
  "curves": {
    "location_y": {"keys": [[1, -11.0], [16, -1.5], [28, 0.9]], "interpolation": "bezier"},
    "location_z": {"keys": [[1, 0.3], [10, 1.8], [28, 0.9], [48, 0.55]], "interpolation": "bezier"},
    "rotation_y": {"from": 0.0, "to": 12.0, "interpolation": "linear"}}}}
```

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

## Rig controls & drivers (`create_rig`)

`create_rig` creates named control objects (empties live in `RIGS`/`HELPERS`)
and can wire **scripted drivers** so a driven property follows a control
property — the classic exploded-view slider: move `CTRL_explode.location.z`
and every driven part rises with it.

```json
{"op": "create_rig", "schema": {
  "rig_name": "exploded_rig",
  "controls": [
    {"name": "CTRL_explode", "type": "empty",
     "drives": ["case_top_shell", "board_pcb_round"]}],
  "drivers": [
    {"target": "connector_ribbon.location.z",
     "driver": "CTRL_explode.location.y"}]}}
```

- `controls[].drives` **parents** the listed objects to the control empty —
  moving the empty moves the children.
- `drivers[]` adds a real scripted driver: `target` property is driven by the
  `driver` property via `expression = "v"` on a `SINGLE_PROP` variable.
  Path format is `object.property.axis` — `location`, `rotation_euler`,
  `scale`, or any scalar RNA property (e.g. `hide_render`); the axis letter
  (`x`/`y`/`z`/`w`) selects the array index. Omit `.axis` for scalar props.
- A driver writes the object's **local** transform channel; if the object is
  also parented, the parent's matrix still applies on top.
- Unresolvable object names or unknown properties are reported in the op
  result under `driver_errors` — the rest of the rig still builds.
- Verify it evaluates: move the control, re-inspect, and check the driven
  object's `world_location` actually followed (the integration suite does
  exactly this).

### Armatures

`type: "armature"` builds a real `bpy` armature — bones from
`controls[].bones` (`name`, `head`, `tail`, `parent`), not an empty.
Objects in `drives` get an Armature modifier plus a vertex group on
`deform_bone` (whole-mesh binding) so pose bones deform them. Animate
bones with `create_animation` mode `bone_pose` and `"armature.bone"`
targets:

```json
{"op": "create_animation", "schema": {"animation_name": "wave",
  "mode": "bone_pose", "frame_start": 1, "frame_end": 24,
  "targets": ["char_armature.arm_l"], "params": {"degrees": 40, "axis": "y"}}}
```

The inspector samples `pose.bones[*].matrix` per frame — bone motion is
visible to `scene_critique`/`sampled_objects` even though the armature
object itself never moves.

## Animation linter

Fails: animation requested but no keyframes; invalid frame range; camera animated
with no active camera; GLB requested but clip not exported; scroll web with no
`camera_path.json`, no scroll timeline segments, too few sampled positions, or a
static sampled camera path. Warns: default 1..250 range, loop mismatch, missing
markers.
