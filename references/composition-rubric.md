# Composition Rubric

Composition is worth **20 points** (the largest rubric category). It is scored
from measurable signals in `evaluation._score_composition`: an active camera, the
subject inside frame, subject coverage in 0.2–0.85, and presence of both
`SUBJECT` and `ENVIRONMENT` collections (depth layering).

## What earns points

- **Subject framed and readable** — bounding box inside the frame, clear silhouette.
- **Coverage in range** — fills the frame without being cut off.
- **Depth** — distinct foreground / midground / background. Even a gradient world
  + a silhouette behind the subject reads as depth.
- **Negative space** — moderate edge density (0.02–0.4). A frame that is either
  empty or edge-to-edge clutter loses readability.

## Practical moves

1. Put the subject on a third, not dead-centre, unless the style is symmetric hero.
2. Add a simple environment (floor plane + gradient world) so the subject is not
   floating in void.
3. Use a low/3-4 angle for products; eye-level for characters; ortho for technical.
4. Leave breathing room — `safe_margin ≥ 0.08`.
5. Separate subject from background with a rim light or DOF, not by luck.

## Anti-patterns

- Subject tiny in a huge empty frame.
- Subject clipped by the frame edge.
- Flat front-on view with no depth cue.
- Competing background silhouettes that fight the subject (the critique loop
  should flag "background competes with subject").
