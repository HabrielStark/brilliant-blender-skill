"""Operators + panel to control the bridge (SRS 13.1: manual start/stop)."""
import bpy  # type: ignore

from . import bridge


def _prefs(context):
    return context.preferences.addons[__package__].preferences


class BCAS_OT_start_bridge(bpy.types.Operator):
    bl_idname = "bcas.start_bridge"
    bl_label = "Start Blender Cinematic Bridge"
    bl_description = "Start the localhost command bridge"

    def execute(self, context):
        p = _prefs(context)
        try:
            bridge.start_bridge(p.host, p.port, p.safety_mode, p.workspace_root)
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Bridge listening on {p.host}:{p.port} ({p.safety_mode})")
        return {"FINISHED"}


class BCAS_OT_stop_bridge(bpy.types.Operator):
    bl_idname = "bcas.stop_bridge"
    bl_label = "Stop Blender Cinematic Bridge"

    def execute(self, context):
        bridge.stop_bridge()
        self.report({"INFO"}, "Bridge stopped")
        return {"FINISHED"}


class BCAS_PT_panel(bpy.types.Panel):
    bl_label = "Cinematic Agent"
    bl_idname = "BCAS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Cinematic"

    def draw(self, context):
        p = _prefs(context)
        col = self.layout.column()
        col.label(text=f"{p.host}:{p.port} · {p.safety_mode}")
        col.operator("bcas.start_bridge", icon="PLAY")
        col.operator("bcas.stop_bridge", icon="PAUSE")


CLASSES = (BCAS_OT_start_bridge, BCAS_OT_stop_bridge, BCAS_PT_panel)
