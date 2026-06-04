# Visual Critique Rubric

Preview/final score = **100 points**. Pass threshold **80**; excellent **90+**.
A hard-fail overrides the score: a black scene scoring 75 on paper still fails.

## Categories (`blender_cinematic/constants.py::RUBRIC_MAX`)

| Category | Points | Measured from |
|---|---:|---|
| Composition | 20 | camera + subject framing + depth + edge density |
| Lighting | 15 | image brightness/contrast + lights present |
| Materials | 15 | non-default named materials, variation, metal+bevel |
| Geometry / detail | 15 | subject face count, object count, clean names |
| Camera / cinematic | 10 | lens set, DOF valid, final camera saved, not inside geo |
| Reference fidelity | 10 | SSIM + palette + saliency/edge/tone match when references are provided; neutral only when no reference is requested |
| Technical correctness | 10 | lint errors, missing files |
| Performance / export | 5 | face budget, GLB size, profile fit |

## Hard-fail conditions

Render almost all black/white · subject outside frame · too few meaningful objects
· default materials everywhere · no active camera · no meaningful light · output
file missing/empty · Blender render/export error · GLB requested but cannot load ·
animation requested but frame range/keyframes missing · subject overcropped by
the camera · important named hero parts outside the camera frame · flipped/broken
hero mesh normals · product/mechanical subject lacks semantic parts or visible
detail.

## Anti-slop visual gates

Use these gates in addition to the 100-point score when the task is visual,
product, mechanical, cinematic, or reference-driven:

| Gate | Reject when |
|---|---|
| Framing | subject coverage is above the task's max safe coverage or key parts touch/cross frame edges |
| Hero-part visibility | named anatomy such as cap, label, logo, plinth/base, lens, dial, strap, screen, handle or nozzle/neck is missing from the camera frame |
| Physical attachment | caps, labels, straps, buttons, lenses, plinths and supports appear detached or floating without an intentional design reason |
| Subject anatomy | object count is too low for the requested subject, or names are generic primitives |
| Material design | fewer than 3 purposeful material families on a hero asset, or key objects use defaults |
| Shader craft | shader/material tasks have only flat Principled BSDF graphs, no procedural features, or no visible surface breakup |
| Surface craft | important hard-surface objects lack bevels/weighted normals/smooth shading |
| Detail read | no micro-detail is visible at final camera distance: markers, seams, ridges, fasteners, panels, controls |
| Image craft | preview contrast or edge/detail density is too low, making the render read as flat even if the scene graph is populated |
| Reference truth | obvious requested/reference features are missing even if the numeric score passes; color similarity alone is not enough when silhouette, edge placement, coverage, or tone drift from the reference |
| Style collapse | unrelated briefs resolve into the same palette, lighting, silhouette language, or glow-strip detailing |

## Self-critique loop (run after every preview)

1. Inspect the **actual** preview/render, not the plan.
2. List **5 concrete visual defects** visible in the image, not abstract guesses.
3. List up to **3 technical defects**.
4. Decide which are fixable within the remaining iteration budget.
5. Make **one targeted improvement pass** — do not randomly rebuild everything.

## Refinement logic

For contact sheets, compare tasks against each other. If product, repair, web,
material, and animation prompts all share the same dark glossy/cyan-strip visual
language, treat that as a skill failure even when each individual preview has
enough objects and materials.
If a preview is effectively a flat patch of color with weak edges/details, treat
that as a skill failure even when object names, material names, and counts look
healthy in JSON. For reference tasks, missing SSIM/palette/saliency metrics are
a hard evidence failure rather than a score to infer from other categories.
Reject outputs that match the palette but miss the reference silhouette,
highlight rows, lens placement, reflection coverage, or overall tone.
Physical attachment is for subject anatomy, not visual effects: reflections,
specular streaks, highlights, shadows, and material swatches may be spatially
separate when the brief calls for them. Do not "fix" those by gluing them to the
hero body; instead verify they read correctly in the preview.

- Stop early once the rubric passes (and ≥ minimum iterations).
- Stop with a failure report after **3 iterations with no score improvement**.
- The evaluator emits `defects` and `next_actions` derived from real lint findings
  and image metrics; act on the highest-impact action first (lighting/camera before
  micro-detail).

## Iteration eval shape

```json
{ "iteration": 3, "hard_fail": false, "passed": false,
  "scores": {"composition":15,"lighting":12,"materials":10,"geometry_detail":12,
             "camera":8,"reference_fidelity":7,"technical":9,"performance":5,"total":78},
  "defects": ["rim light too strong on the left", "background competes with subject"],
  "next_actions": ["reduce rim light energy by 25%", "darken background arches"] }
```
