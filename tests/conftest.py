"""Pytest configuration: path setup, Blender detection, marker-based skipping."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from blender_cinematic.blender import locate_blender  # noqa: E402


def pytest_addoption(parser):
    parser.addoption("--blender-executable", action="store", default=None,
                     help="Path to a Blender executable for integration tests")


@pytest.fixture(scope="session")
def blender_exe(request):
    exe = request.config.getoption("--blender-executable") or locate_blender()
    if not exe:
        pytest.skip("no Blender executable available")
    return exe


@pytest.fixture
def workspace(tmp_path):
    from blender_cinematic.workspace import WorkspaceResolver
    return WorkspaceResolver([tmp_path]), tmp_path


def pytest_collection_modifyitems(config, items):
    have_blender = bool(config.getoption("--blender-executable") or locate_blender())
    web_dist = (ROOT / "web" / "dist" / "web_validate_asset.js").exists()
    for item in items:
        if "blender" in item.keywords and not have_blender:
            item.add_marker(pytest.mark.skip(reason="Blender not available"))
        if "web" in item.keywords and not web_dist:
            item.add_marker(pytest.mark.skip(reason="web/dist not built (npm run build)"))
