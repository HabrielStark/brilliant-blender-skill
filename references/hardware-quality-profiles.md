# Hardware & Quality Profiles

Pick the safe profile *first*, then build to it. The selector
(`blender_cinematic/profiles.py`) chooses from the hardware report; you may go
lower than your hardware allows, never silently higher.

## Profiles

| Profile | Preview | Final still | Preview engine | Final engine | Texture cap | Samples | 4K | Volumetrics |
|---|---:|---:|---|---|---:|---:|:--:|:--:|
| `safe_laptop` | ≤960px | ≤1920px | EEVEE | EEVEE | 1024 | 32–96 | no | no |
| `balanced` | ≤1280px | ≤2560px | EEVEE | Cycles | 2048 | 96–256 | no | no |
| `cinematic` | ≤1920px | ≤3840px | EEVEE | Cycles | 2048–4096 | 256–512 | yes | yes |
| `ultra_4k` | ≤1920px | ≤4096px | EEVEE | Cycles | 4096 | 512–1024 | yes | yes |

Engine names are **logical** (`EEVEE`/`CYCLES`/`WORKBENCH`); the add-on resolves
them to the running Blender's actual identifier (`BLENDER_EEVEE` on 5.0,
`BLENDER_EEVEE_NEXT` on 4.2–4.5).

## Auto-selection thresholds

- `balanced` needs ≥ 8 GB RAM.
- `cinematic` needs ≥ 16 GB RAM, a usable GPU and ≥ 8 GB VRAM.
- `ultra_4k` needs ≥ 32 GB RAM and ≥ 12 GB VRAM.
- A usable GPU = an NVIDIA/Apple/AMD device or a Cycles OPTIX/CUDA/HIP/oneAPI/Metal device.

## Safety rules (enforced in `budget.py`)

- 4K is clamped down unless the profile allows it.
- A failed tiny test render caps the profile at `balanced` (no heavy Cycles/4K).
- Textures above the cap are reduced.
- Volumetrics are disabled on `safe_laptop`/`balanced`.
- If available RAM < 25 % of total, `ram_guard_ok=false` — do not start the final
  render until there is headroom; save the `.blend` first.
- Preview first, final later. Always.

## Weak-hardware playbook

1. Force `safe_laptop`; use EEVEE for both preview and final.
2. Replace volumetrics with `smoke_cards`/emissive fakes.
3. Keep particle counts ≤ 200; prefer geometry/instancing over simulation.
4. Cap final at 1920px; explain the downshift in the report.
