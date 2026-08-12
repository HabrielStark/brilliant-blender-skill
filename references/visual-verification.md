# Visual and browser verification playbook

Automated metrics are triage signals. The actual preview, render, animation
frames, or browser canvas is the source of truth for visual quality.

## Blender preview gate

After each meaningful scene change:

1. Render a low-cost preview using the selected hardware profile.
2. Inspect the actual image (not only JSON or object names) with an available
   image viewer, browser, or Playwright screenshot.
3. Record five concrete visual defects: framing/readability, lighting/value,
   material/surface, geometry/detail, and physical continuity. Record up to
   three technical defects separately.
4. Run `scripts/visual_eval.py` and `scripts/scene_lint.py` against the same
   iteration. A passing score does not override a visible crop, floating part,
   black/white collapse, missing anatomy, or flat material.
5. Fix one defect group, then capture a new preview. Stop when all required
   gates pass or the iteration budget is exhausted.

For animation, render start/mid/end frames and verify both inspected motion and
non-zero image differences. For reference matching, compare real reference
pixels using the available SSIM/palette/saliency/edge/tone gates; inferred
reference scores are invalid.

## Web and GLB gate

When the deliverable is web-facing, prove all of the following locally:

- GLB loads with `web/` validation and has no missing texture references.
- Exported animation clips and camera-path samples exist when requested.
- Generated three.js/R3F code builds without invented imports or paths.
- A browser check covers the desktop viewport and a narrow mobile viewport.
- The browser console has no uncaught errors and network requests have no
  unexpected failures.
- The canvas visibly contains the subject, and screenshots are saved with the
  report. Check resize/scroll interaction, not only initial load.

If Playwright, a browser, or WebGL is unavailable, run static/Node validation,
record the exact missing capability, and downgrade the claim level. Do not call
web-ready on static code alone.

## Review integrity

Use `--allow-unreviewed` only to generate evidence packets. Release acceptance
requires reviewed visual and blind-eval JSON with coverage for every item. Keep
the anonymized mapping private and never treat an agent's prose as human taste
signoff.
