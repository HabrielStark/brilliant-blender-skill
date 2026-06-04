"""Hardware preflight (SRS 9.2).

Collects OS/CPU/RAM/disk/GPU/battery information with ``psutil`` plus best-effort
GPU/VRAM detection (pynvml -> nvidia-smi -> platform heuristics), and probes a
Blender executable when one is available. Produces the ``hardware_report.json``
dictionary consumed by :mod:`blender_cinematic.profiles` and ``budget``.
"""
from __future__ import annotations

import argparse
import json
import platform
import shutil
from pathlib import Path
from typing import Optional

import psutil

from . import blender as blender_mod
from .security import run_checked
from .workspace import WorkspaceResolver


def _bytes_to_gb(n: float) -> float:
    return round(n / (1024 ** 3), 2)


def _nvidia_via_pynvml() -> Optional[dict]:
    try:
        import pynvml  # type: ignore
    except Exception:
        return None
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        name = pynvml.nvmlDeviceGetName(handle)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        info = {
            "vendor": "NVIDIA",
            "device": name.decode() if isinstance(name, bytes) else str(name),
            "vram_total_gb": _bytes_to_gb(mem.total),
            "vram_available_gb": _bytes_to_gb(mem.free),
            "present": True,
        }
        pynvml.nvmlShutdown()
        return info
    except Exception:
        return None


def _nvidia_via_smi() -> Optional[dict]:
    if not shutil.which("nvidia-smi"):
        return None
    try:
        proc = run_checked(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader,nounits"],
            timeout=20,
        )
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    first = proc.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 3:
        return None
    try:
        return {
            "vendor": "NVIDIA",
            "device": parts[0],
            "vram_total_gb": round(float(parts[1]) / 1024, 2),
            "vram_available_gb": round(float(parts[2]) / 1024, 2),
            "present": True,
        }
    except ValueError:
        return None


def detect_gpu() -> dict:
    info = _nvidia_via_pynvml() or _nvidia_via_smi()
    if info:
        return info
    # Apple Silicon: Metal GPU is integrated with the SoC.
    if platform.system() == "Darwin" and platform.machine() in ("arm64", "aarch64"):
        return {"vendor": "Apple", "device": "Apple Silicon GPU (Metal)",
                "vram_total_gb": 0.0, "vram_available_gb": 0.0, "present": True}
    return {"vendor": "unknown", "device": "integrated/unknown",
            "vram_total_gb": 0.0, "vram_available_gb": 0.0, "present": False}


def _infer_render_devices(gpu: dict) -> list[str]:
    vendor = gpu.get("vendor")
    if vendor == "NVIDIA":
        return ["OPTIX", "CUDA", "CPU"]
    if vendor == "Apple":
        return ["METAL", "CPU"]
    return ["CPU"]


def _battery() -> Optional[dict]:
    try:
        b = psutil.sensors_battery()
    except Exception:
        b = None
    if b is None:
        return None
    return {"percent": b.percent, "power_plugged": b.power_plugged}


def collect_hardware_report(
    project_dir: str | Path,
    blender_exe: Optional[str] = None,
    do_tiny_render: bool = False,
) -> dict:
    project = Path(project_dir).expanduser()
    project.mkdir(parents=True, exist_ok=True)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(project))
    gpu = detect_gpu()

    warnings: list[str] = []
    exe = blender_mod.locate_blender(blender_exe)
    blender_info: dict = {"path": exe, "version": None, "can_background": exe is not None,
                          "tiny_render_ok": None}
    render_devices = _infer_render_devices(gpu)
    if exe:
        blender_info["version"] = blender_mod.blender_version(exe)
        real_devices = blender_mod.query_render_devices(exe)
        if real_devices:
            render_devices = real_devices
        if do_tiny_render:
            out = project / "_tiny_render.png"
            blender_info["tiny_render_ok"] = blender_mod.tiny_test_render(exe, str(out))
            if blender_info["tiny_render_ok"] is False:
                warnings.append("Blender tiny test render failed")
    else:
        warnings.append("Blender executable not found; render/export steps will be unavailable")

    if vm.total and vm.available / vm.total < 0.25:
        warnings.append("Available RAM below 25% of total")
    if disk.free < 2 * 1024 ** 3:
        warnings.append("Less than 2GB free disk space in project directory")

    return {
        "schema": "hardware_report/0.1",
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "cpu": {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "processor": platform.processor() or platform.machine(),
        },
        "ram": {
            "total_gb": _bytes_to_gb(vm.total),
            "available_gb": _bytes_to_gb(vm.available),
            "percent_used": vm.percent,
        },
        "disk": {"free_gb": _bytes_to_gb(disk.free), "total_gb": _bytes_to_gb(disk.total)},
        "gpu": gpu,
        "render_devices": render_devices,
        "battery": _battery(),
        "blender": blender_info,
        "warnings": warnings,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Hardware preflight + report")
    parser.add_argument("--project-dir", required=True)
    parser.add_argument("--blender", default=None, help="explicit Blender executable")
    parser.add_argument("--tiny-render", action="store_true", help="run a 32x32 Blender test render")
    parser.add_argument("--profile", default="auto", help="requested quality profile")
    args = parser.parse_args(argv)

    report = collect_hardware_report(args.project_dir, args.blender, args.tiny_render)
    # Attach the selected profile + budget so the report is directly usable.
    from .budget import compute_budget

    budget = compute_budget(report, args.profile)
    report["selected_profile"] = budget["quality_profile"]
    report["render_budget"] = budget

    resolver = WorkspaceResolver([Path(args.project_dir).expanduser().resolve()])
    out_path = resolver.write_text("hardware_report.json", json.dumps(report, indent=2))
    print(json.dumps({"hardware_report_path": str(out_path),
                      "quality_profile": budget["quality_profile"],
                      "warnings": report["warnings"]}, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
