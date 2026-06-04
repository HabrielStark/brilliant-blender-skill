"""Unit tests for profile selection + render budget (SRS 9, 17.1)."""
from blender_cinematic.budget import compute_budget
from blender_cinematic.profiles import hardware_capability, select_profile

WEAK = {"ram": {"total_gb": 6, "available_gb": 1.0}, "gpu": {"present": False},
        "render_devices": ["CPU"], "blender": {}}
MID = {"ram": {"total_gb": 16, "available_gb": 9}, "gpu": {"present": True, "vram_total_gb": 8},
       "render_devices": ["OPTIX", "CPU"], "blender": {"tiny_render_ok": True}}
STRONG = {"ram": {"total_gb": 64, "available_gb": 40}, "gpu": {"present": True, "vram_total_gb": 24},
          "render_devices": ["OPTIX", "CUDA", "CPU"], "blender": {"tiny_render_ok": True}}


def test_capability_tiers():
    assert hardware_capability(WEAK) == "safe_laptop"
    assert hardware_capability(MID) == "cinematic"
    assert hardware_capability(STRONG) == "ultra_4k"


def test_requested_downshift_on_weak_hardware():
    prof, reasons = select_profile(WEAK, "cinematic")
    assert prof.name == "safe_laptop"
    assert any("downshift" in r for r in reasons)


def test_user_can_go_lower_than_capability():
    prof, _ = select_profile(STRONG, "balanced")
    assert prof.name == "balanced"


def test_tiny_render_failure_caps_profile():
    bad = dict(STRONG)
    bad["blender"] = {"tiny_render_ok": False}
    prof, reasons = select_profile(bad, "ultra_4k")
    assert prof.name == "balanced"
    assert any("tiny test render" in r for r in reasons)


def test_budget_clamps_4k_on_weak():
    b = compute_budget(WEAK, "auto", final_resolution=[3840, 2160], want_volumetrics=True)
    assert b["quality_profile"] == "safe_laptop"
    assert max(b["final_resolution"]) <= 1920
    assert b["volumetrics_allowed"] is False
    assert b["selected_engine"] == "EEVEE"


def test_budget_strong_4k_uses_gpu():
    b = compute_budget(STRONG, "ultra_4k", final_resolution=[3840, 2160])
    assert b["device"] == "GPU_OPTIX"
    assert b["final_resolution"] == [3840, 2160]
    assert b["selected_engine"] == "CYCLES"


def test_budget_ram_guard():
    b = compute_budget(WEAK, "auto")
    assert b["ram_guard_ok"] is False
