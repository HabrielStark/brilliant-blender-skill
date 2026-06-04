"""Web E2E (SRS 17.4): drive the built Node GLB validator on a real asset.

Marked ``web`` so it auto-skips when ``web/dist`` is not built. Browser-based
Playwright tests are optional and intentionally out of the default run (no
network/runtime download required).
"""
import json
import shutil
import subprocess  # nosec B404
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "web" / "dist" / "web_validate_asset.js"
SAMPLE_GLB = ROOT / "examples" / "web-demo" / "scene.glb"

pytestmark = pytest.mark.web


def test_node_validator_on_real_glb():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not on PATH")
    if not VALIDATOR.exists() or not SAMPLE_GLB.exists():
        pytest.skip("web/dist or sample GLB missing (run npm run build + the watch pipeline)")
    proc = subprocess.run(  # nosec B603
        [node, str(VALIDATOR), str(SAMPLE_GLB), "--max-mb", "20"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    report = json.loads(proc.stdout)
    assert report["ok"] is True, report
    assert report["meshes"] >= 1
    assert report["externalTextures"] == []
    assert proc.returncode == 0
