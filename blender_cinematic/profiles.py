"""Quality profiles and hardware-aware selection (SRS 9.3 / 9.4)."""
from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Profile:
    name: str
    preview_max_px: int
    final_max_px: int
    preview_engine: str
    final_engine: str
    texture_cap: int
    samples_min: int
    samples_max: int
    volumetrics_allowed: bool
    allow_4k: bool
    # auto-selection thresholds
    min_ram_gb: float
    min_vram_gb: float
    needs_gpu: bool

    def to_dict(self) -> dict:
        return asdict(self)


PROFILES: dict[str, Profile] = {
    "safe_laptop": Profile(
        name="safe_laptop", preview_max_px=960, final_max_px=1920,
        preview_engine="EEVEE", final_engine="EEVEE",
        texture_cap=1024, samples_min=32, samples_max=96,
        volumetrics_allowed=False, allow_4k=False,
        min_ram_gb=0, min_vram_gb=0, needs_gpu=False,
    ),
    "balanced": Profile(
        name="balanced", preview_max_px=1280, final_max_px=2560,
        preview_engine="EEVEE", final_engine="CYCLES",
        texture_cap=2048, samples_min=96, samples_max=256,
        volumetrics_allowed=False, allow_4k=False,
        min_ram_gb=8, min_vram_gb=0, needs_gpu=False,
    ),
    "cinematic": Profile(
        name="cinematic", preview_max_px=1920, final_max_px=3840,
        preview_engine="EEVEE", final_engine="CYCLES",
        texture_cap=4096, samples_min=256, samples_max=512,
        volumetrics_allowed=True, allow_4k=True,
        min_ram_gb=16, min_vram_gb=8, needs_gpu=True,
    ),
    "ultra_4k": Profile(
        name="ultra_4k", preview_max_px=1920, final_max_px=4096,
        preview_engine="EEVEE", final_engine="CYCLES",
        texture_cap=4096, samples_min=512, samples_max=1024,
        volumetrics_allowed=True, allow_4k=True,
        min_ram_gb=32, min_vram_gb=12, needs_gpu=True,
    ),
}

TIER_ORDER = ("safe_laptop", "balanced", "cinematic", "ultra_4k")


def _tier(name: str) -> int:
    return TIER_ORDER.index(name)


def _gpu_info(report: dict) -> tuple[bool, float]:
    gpu = report.get("gpu") or {}
    present = bool(gpu.get("present"))
    vram = float(gpu.get("vram_total_gb") or 0.0)
    # A render device beyond plain CPU also implies usable GPU.
    devices = [d.upper() for d in report.get("render_devices", [])]
    if any(d in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL") for d in devices):
        present = True
    return present, vram


def hardware_capability(report: dict) -> str:
    """Highest profile the hardware can sustain for auto-selection."""
    ram = float((report.get("ram") or {}).get("total_gb") or 0.0)
    gpu_present, vram = _gpu_info(report)
    best = "safe_laptop"
    for name in TIER_ORDER:
        p = PROFILES[name]
        if ram < p.min_ram_gb:
            continue
        if p.needs_gpu and not gpu_present:
            continue
        if vram < p.min_vram_gb:
            continue
        best = name
    return best


def select_profile(report: dict, requested: str = "auto") -> tuple[Profile, list[str]]:
    """Return the chosen :class:`Profile` plus human-readable reasoning."""
    reasoning: list[str] = []
    ram = float((report.get("ram") or {}).get("total_gb") or 0.0)
    gpu_present, vram = _gpu_info(report)
    reasoning.append(f"Detected {ram:.0f}GB RAM")
    reasoning.append("GPU available" if gpu_present else "No usable GPU detected")
    if gpu_present:
        reasoning.append(f"Detected {vram:.0f}GB VRAM")

    cap = hardware_capability(report)
    if requested == "auto":
        chosen = cap
        reasoning.append(f"auto -> {chosen} (hardware capability tier)")
    else:
        if requested not in PROFILES:
            chosen = cap
            reasoning.append(f"unknown profile {requested!r}; falling back to {chosen}")
        elif _tier(requested) > _tier(cap):
            chosen = cap
            reasoning.append(
                f"requested {requested} downshifted to {chosen}: hardware below thresholds "
                f"(needs RAM>={PROFILES[requested].min_ram_gb}GB, VRAM>={PROFILES[requested].min_vram_gb}GB)"
            )
        else:
            chosen = requested
            reasoning.append(f"using requested profile {chosen}")

    # Tiny render failure forbids the heaviest tier (SRS 9.4).
    blender = report.get("blender") or {}
    if blender.get("tiny_render_ok") is False and chosen in ("cinematic", "ultra_4k"):
        chosen = "balanced"
        reasoning.append("tiny test render failed -> capped at balanced (no heavy Cycles/4K)")

    return PROFILES[chosen], reasoning
