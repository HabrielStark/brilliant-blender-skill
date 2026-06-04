"""Locate and query a Blender executable (no ``bpy`` here).

All Blender invocations use argument arrays (SRS 18.2/26) and short timeouts.
When Blender is not installed every function degrades to ``None``/``False`` so
the rest of the pipeline keeps working (the SRS requires the core to run
without Blender).
"""
from __future__ import annotations

import json
import os
import platform
import re
import shutil
from pathlib import Path
from typing import Optional

from .security import run_checked

_ENV_VARS = ("BLENDER_EXECUTABLE", "BLENDER_PATH", "BLENDER")


def _candidate_paths() -> list[str]:
    system = platform.system()
    out: list[str] = []
    if system == "Windows":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            bf = Path(base) / "Blender Foundation"
            if bf.is_dir():
                out += [str(p / "blender.exe") for p in sorted(bf.glob("Blender*"), reverse=True)]
    elif system == "Darwin":
        out += [
            "/Applications/Blender.app/Contents/MacOS/Blender",
            str(Path.home() / "Applications/Blender.app/Contents/MacOS/Blender"),
        ]
    else:  # Linux / other
        out += ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender",
                "/opt/blender/blender"]
    return out


def locate_blender(explicit: Optional[str] = None) -> Optional[str]:
    if explicit and Path(explicit).exists():
        return str(Path(explicit).resolve())
    for var in _ENV_VARS:
        val = os.environ.get(var)
        if val and Path(val).exists():
            return str(Path(val).resolve())
    which = shutil.which("blender")
    if which:
        return which
    for cand in _candidate_paths():
        if Path(cand).exists():
            return cand
    return None


def blender_version(exe: str, timeout: float = 30) -> Optional[str]:
    try:
        proc = run_checked([exe, "--version"], timeout=timeout)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    m = re.search(r"Blender\s+([\d.]+)", proc.stdout or "")
    return m.group(1) if m else (proc.stdout or "").strip().splitlines()[0] if proc.stdout else None


_DEVICE_QUERY = (
    "import bpy\n"
    "p=bpy.context.preferences.addons.get('cycles')\n"
    "out=set()\n"
    "if p:\n"
    "    cp=p.preferences\n"
    "    for be in ('OPTIX','CUDA','HIP','ONEAPI','METAL'):\n"
    "        try:\n"
    "            for d in cp.get_devices_for_type(be):\n"
    "                out.add(be)\n"
    "        except Exception:\n"
    "            pass\n"
    "out.add('CPU')\n"
    "print('RENDER_DEVICES='+','.join(sorted(out)))\n"
)


def query_render_devices(exe: str, timeout: float = 60) -> list[str]:
    """Ask Blender which Cycles devices exist (real, not inferred)."""
    try:
        proc = run_checked(
            [exe, "-b", "--factory-startup", "-noaudio", "--python-expr", _DEVICE_QUERY],
            timeout=timeout,
        )
    except Exception:
        return []
    for line in (proc.stdout or "").splitlines():
        if line.startswith("RENDER_DEVICES="):
            return [d for d in line.split("=", 1)[1].split(",") if d]
    return []


_TINY_RENDER = (
    "import bpy\n"
    "s=bpy.context.scene\n"
    "s.render.resolution_x=32\n"
    "s.render.resolution_y=32\n"
    "s.render.image_settings.file_format='PNG'\n"
    "s.render.filepath={out}\n"
    "bpy.ops.render.render(write_still=True)\n"
)


def _tiny_render_script(out_png: str) -> str:
    return _TINY_RENDER.format(out=json.dumps(str(out_png)))


def tiny_test_render(exe: str, out_png: str, timeout: float = 120) -> bool:
    """Render a 32x32 image to prove Blender can render at all (SRS 9.2)."""
    script = _tiny_render_script(out_png)
    try:
        proc = run_checked(
            [exe, "-b", "--factory-startup", "-noaudio", "--python-expr", script],
            timeout=timeout,
        )
    except Exception:
        return False
    return proc.returncode == 0 and Path(out_png).exists()
