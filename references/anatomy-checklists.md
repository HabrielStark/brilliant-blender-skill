# Anatomy checklists — what makes a thing read as itself

This is the decomposition knowledge the anatomy pass builds against and the
visual verifier judges against. It says **what parts a thing must have**, never
*where to put them* — placement, proportion, and style remain the agent's
creative choice. A category absent from this file does not exempt it:
decompose any brief element into primary form + secondary structure + surface
detail yourself, using these as the pattern.

## The universal rule

Every recognizable object decomposes into three tiers:

1. **Primary form** — the silhouette. If the silhouette alone doesn't
   identify the object, nothing below it will save it.
2. **Secondary structure** — the parts that make it *functional*: legs,
   handles, lids, stems, arms, frames, joints. This is where weak models
   stop — a mug without a handle is a cylinder.
3. **Surface detail** — seams, rims, wear, texture, markings, fastenings.
   This is where "correct" becomes "crafted".

A `part_is_placeholder` warn or a verifier `placeholder` verdict means tier 1
exists but tiers 2–3 are missing.

## Furniture

- **Table/desk**: top slab + support (legs, trestle, pedestal, or wall mount)
  + edge/apron detail. A floating slab reads as a shelf, not a desk. Legs
  must touch the floor plane; check the profile view.
- **Chair**: seat + back + legs/base + (often) armrests. Four loose sticks
  under a slab is not a chair until the joints read.
- **Shelf/cabinet**: carcass + shelf planes or drawer fronts + handles/pulls
  + plinth or feet. Interior scenes die on missing handles.

## Tableware & containers

- **Mug/cup**: body wall + **handle** + visible interior or rim thickness
  (a solid cylinder is a puck). Coffee inside sells the read.
- **Bottle/glass**: body + neck + lip/opening; glass needs transmission
  and visible wall thickness at the rim.
- **Plate/bowl**: concave interior must actually be concave — lathe/spin or
  boolean, not a disc.

## Lighting fixtures

- **Desk lamp**: base + stem/arm + head/shade + visible emitter (bulb,
  diffuser, or glowing inner face). A base alone is a knob. If the scene is
  dark, the lamp should visibly *emit* — emissive material plus a light.
- **Street lamp**: pole + arm/head + emitter + base flange. At night it is
  the light source; if the street is lit but no emitter glows, the verifier
  should flag it.
- **Ceiling/pendant**: canopy + cord/rod + shade + emitter.

## Electronics & products

- **Laptop/monitor**: body + screen plane (emissive or reflective) + hinge/
  stand + bezel. A slab with a dark face reads as a black box, not a screen.
- **Watch/clock**: case + dial face + hands or markers + glass + strap/lugs.
  Nested parts (markers inside bezel, glass in case) are intentional — do
  not "fix" them as buried objects.
- **Handheld device**: body + screen/lens + buttons/ports + seams. Premium
  products live in the seams and the bevel catchlights.

## Vehicles

- **Car**: body shell + wheels (4, touching ground, correct diameter) +
  windows/glass + lights + mirrors. Wheels floating or sunk is the
  commonest defect — check profile view ground contact.
- **Bicycle**: frame triangles + two wheels + handlebar + saddle + pedals/
  chain. If it doesn't read at thumbnail size, the frame tubes are too fat.

## Buildings & urban

- **Building**: massing + window grid (recessed or emissive, not flat
  decals at night) + entrance + roof edge/parapet. A city of bare boxes
  fails the "one lantern, one person" bar the brief sets — enumerate
  street-level dressing explicitly in `required_parts`.
- **Street**: road surface + markings + sidewalk + curbs + lamps + signage
  + furniture (benches, bins, hydrants). Scale check: a person is ~1.7 m;
  doors ~2.1 m; lamps 3–6 m. Windows that ignore floor height read as noise.
- **Vegetation**: trunk/stem + crown (multiple leaf/petal instances, never
  one blob) + ground contact. A lollipop tree is two primitives, not a tree.

## Characters & creatures

- **Humanoid**: head + torso + limbs (with hands/feet, not stumps) +
  anatomically plausible joint placement + surface definition (clothing,
  hair, facial features per the brief's fidelity level). "Not quite a
  person" is not acceptable — either the anatomy reads or the task is not
  done. If a sub-part resists after a real effort budget, simplify the
  *presentation* (silhouette, distance, occlusion) — never leave a broken
  humanoid in frame and call it finished.
- **Face**: eyes + nose/mouth structure + brow/cheek masses. Symmetric
  spheres read as a doll, not a face.

## Food & organic

- **Baked goods**: non-uniform silhouette (slight asymmetry) + surface
  texture (crust, crumbs, glaze) — a perfect torus is a toy donut.
- **Fruit**: body + stem + subtle asymmetry; a perfect sphere with a stick
  is a placeholder.

## Sports & nets

- **Goal (football/hockey)**: posts + crossbar + **rear stanchions** angled
  back + **box net** — back plane, top drape, and side panels sharing the
  frame edges, with slight sag. A flat curtain of parallel strings behind
  the mouth is a fence, not a goal net. Use `create_net_lattice` per panel
  (woven strands both directions); a `grid_alpha` material on a plane is
  the cheap far-shot fallback.
- **Ball (paneled)**: sphere + **seam/panel evidence** — `voronoi_panels`
  gives recessed seams + a darkened cell subset (the football read).
  Stuck-on discs read as a polka-dot toy, not panels. Under arena light the
  shell wants a slight sheen (low roughness + clearcoat).
- **Net anywhere** (tennis, fishing, hammock, fence): interwoven strands in
  BOTH directions + edge rope/cable + tension sag. Parallel strings in one
  direction is the classic failure.

## Atmosphere & vapour

- **Steam/smoke**: `create_vfx` preset `smoke_cards` — a column of
  noise-alpha cards that widen, drift and fade with height. Stacked
  spheres or beads read as beads, not vapour; HALO particles read as
  dots. Cards must start at the emitter's surface and dissolve upward.
- **Dust/motes**: `dust_motes` preset; keep counts low — dust is felt,
  not seen.

## Environment floor

Every scene needs: a **ground/support plane** (nothing floats), a
**backdrop or depth layer** (nothing ends in void), and **light that
motivates** (visible source or plausible direction). `no_environment`
warn means this floor is missing.

For night/wide shots the depth layer is two-part: `world.gradient`
(horizon glow → dark zenith — never leave the sky a flat black void)
**plus** `create_silhouette_ring` masses so the horizon has a silhouette
line (stands, skyline, treeline). A gradient alone still reads empty.

## Verifier usage

For each `required_parts` element ask three questions in order:

1. Does its silhouette identify it? (tier 1)
2. Are its functional parts present and attached? (tier 2)
3. Does its surface carry material/texture evidence? (tier 3)

The first tier that fails is the verdict: silhouette fail →
`unidentifiable`; missing parts → `placeholder`; flat surface → defect,
low priority. Cite the view that proves it.
