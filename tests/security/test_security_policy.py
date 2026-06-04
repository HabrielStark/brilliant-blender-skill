"""Security tests: raw-python gating, network, subprocess arrays, code scan (SRS 18)."""
import json

import pytest

from blender_cinematic.blender import _tiny_render_script
from blender_cinematic.security import (
    SecurityError,
    as_arg_list,
    assert_network_allowed,
    assert_safety_mode,
    ensure_raw_python_allowed,
    run_checked,
    scan_python_source,
)


def test_raw_python_disabled_by_default():
    with pytest.raises(SecurityError):
        ensure_raw_python_allowed(False)
    with pytest.raises(SecurityError):
        ensure_raw_python_allowed(True, mode="strict")  # enabled but strict
    ensure_raw_python_allowed(True, mode="dev")  # only this is allowed


def test_network_disabled_in_strict():
    with pytest.raises(SecurityError):
        assert_network_allowed(True, mode="strict")
    assert_network_allowed(False, mode="strict")  # ok


def test_unsafe_mode_forbidden():
    assert_safety_mode("strict")
    assert_safety_mode("dev")
    with pytest.raises(SecurityError):
        assert_safety_mode("unsafe")


def test_shell_string_rejected():
    with pytest.raises(SecurityError):
        as_arg_list("rm -rf /")
    assert as_arg_list(["echo", "ok"]) == ["echo", "ok"]


def test_run_checked_forbids_shell():
    with pytest.raises(SecurityError):
        run_checked(["echo", "x"], timeout=5, shell=True)  # nosec B604


def test_scan_flags_dangerous_code():
    bad = scan_python_source("import os\nos.system('x')\neval('1')")
    codes = {i.code for i in bad.issues}
    assert "py.import" in codes
    assert "py.call" in codes or "py.attr" in codes
    assert not bad.safe


def test_scan_allows_safe_bpy_code():
    safe = scan_python_source("import bpy\nbpy.ops.mesh.primitive_cube_add()\n")
    assert safe.safe


def test_tiny_render_script_escapes_filepath_literal():
    payload = r"C:\tmp\bcas_x';__import__('os').system('calc');#.png"
    script = _tiny_render_script(payload)
    assert json.dumps(payload) in script
    assert "filepath=r'" not in script
