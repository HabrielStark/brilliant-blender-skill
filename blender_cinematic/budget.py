"""Render budget computation (SRS 9.5).

Combines a selected :class:`~blender_cinematic.profiles.Profile` with the
hardware report and the manifest's requested resolution to produce concrete,
safe render settings plus the reasoning trail required by the SRS.
"""
from __future__ import annotations

from typing import Optional

from .profiles import select_profile

_DEVICE_PRIORITY = ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL", "CPU")


def _pick_device(report: dict, engine: str) -> str:
    devices = [d.upper() for d in report.get("render_devices", [])]
    if engine != "CYCLES":
        return "CPU"
    for d in _DEVICE_PRIORITY:
        if d in devices:
            return f"GPU_{d}" if d != "CPU" else "CPU"
    return "CPU"


def _clamp_resolution(requested: list[int] | None, max_px: int, default: list[int]) -> tuple[list[int], bool]:
    res = list(requested) if requested else list(default)
    longest = max(res)
    if longest <= max_px:
        return res, False
    scale = max_px / longest
    return [max(2, int(round(c * scale))) for c in res], True


def compute_budget(
    report: dict,
    requested_profile: str = "auto",
    final_resolution: Optional[list[int]] = None,
    preview_resolution: Optional[list[int]] = None,
    texture_request: Optional[int] = None,
    want_volumetrics: bool = False,
) -> dict:
    profile, reasoning = select_profile(report, requested_profile)

    final_res, final_clamped = _clamp_resolution(
        final_resolution, profile.final_max_px, [1920, 1080]
    )
    preview_res, _ = _clamp_resolution(
        preview_resolution, profile.preview_max_px, [1280, 720]
    )

    # SRS 8.2 / 9.4: 4K only when the profile allows it.
    is_4k_request = bool(final_resolution and max(final_resolution) >= 3840)
    if is_4k_request and not profile.allow_4k:
        reasoning.append(
            f"4K request reduced to {final_res[0]}x{final_res[1]}: profile {profile.name} disallows 4K"
        )
    elif final_clamped:
        reasoning.append(f"final resolution clamped to profile max {profile.final_max_px}px")

    # Samples: mid-point of the profile band, raised slightly for Cycles.
    samples = (profile.samples_min + profile.samples_max) // 2
    device = _pick_device(report, profile.final_engine)
    if profile.final_engine == "CYCLES" and device == "CPU":
        samples = profile.samples_min  # CPU Cycles: keep it cheap.
        reasoning.append("Cycles on CPU: using minimum samples to stay within budget")

    volumetrics = bool(want_volumetrics and profile.volumetrics_allowed)
    if want_volumetrics and not profile.volumetrics_allowed:
        reasoning.append(f"volumetrics disabled: profile {profile.name} forbids heavy volumetrics")

    texture_cap = profile.texture_cap
    if texture_request and texture_request > profile.texture_cap:
        reasoning.append(
            f"texture request {texture_request} capped to profile limit {profile.texture_cap}"
        )
    elif texture_request:
        texture_cap = min(texture_request, profile.texture_cap)

    # RAM guard (SRS 9.4): warn when available RAM is low.
    ram = report.get("ram") or {}
    avail = float(ram.get("available_gb") or 0.0)
    total = float(ram.get("total_gb") or 0.0)
    ram_guard_ok = True
    if total and avail / total < 0.25:
        ram_guard_ok = False
        reasoning.append(
            f"available RAM {avail:.1f}/{total:.1f}GB below 25%: final render should wait for headroom"
        )

    return {
        "quality_profile": profile.name,
        "selected_engine": profile.final_engine,
        "preview_engine": profile.preview_engine,
        "device": device,
        "preview_resolution": preview_res,
        "final_resolution": final_res,
        "samples": samples,
        "texture_cap": texture_cap,
        "volumetrics_allowed": volumetrics,
        "ram_guard_ok": ram_guard_ok,
        "reasoning": reasoning,
    }
