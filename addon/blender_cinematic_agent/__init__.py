"""Blender Cinematic Agent add-on.

Interactive layer: preferences + localhost bridge + operators. The headless path
(`job_runner.py`) does not require registration and is invoked directly by the
core runner in background mode.
"""
bl_info = {
    "name": "Blender Cinematic Agent",
    "author": "blender-cinematic-agent-skill contributors",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > Cinematic",
    "description": "Localhost bridge for the Blender Cinematic Agent Skill (structured ops, render, inspect, export).",
    "category": "Development",
    "doc_url": "",
    "tracker_url": "",
}

import importlib
import traceback

from . import bridge, ops, preferences

_MODULES = (preferences, ops, bridge)


def register():
    for m in _MODULES:
        importlib.reload(m)
    import bpy  # type: ignore
    bpy.utils.register_class(preferences.BCASAddonPreferences)
    for cls in ops.CLASSES:
        bpy.utils.register_class(cls)
    addon_prefs = bpy.context.preferences.addons[__package__].preferences
    if getattr(addon_prefs, "auto_start", False):
        try:
            bridge.start_bridge(
                addon_prefs.host,
                addon_prefs.port,
                addon_prefs.safety_mode,
                addon_prefs.workspace_root,
            )
        except Exception:
            print("Blender Cinematic Agent: auto-start bridge failed")
            traceback.print_exc()


def unregister():
    import bpy  # type: ignore
    bridge.stop_bridge()
    for cls in reversed(ops.CLASSES):
        bpy.utils.unregister_class(cls)
    bpy.utils.unregister_class(preferences.BCASAddonPreferences)


if __name__ == "__main__":  # pragma: no cover
    register()
