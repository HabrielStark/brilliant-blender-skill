"""Add-on preferences (SRS 13.1)."""
import bpy  # type: ignore


class BCASAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    host: bpy.props.StringProperty(  # type: ignore
        name="Bridge Host", default="127.0.0.1",
        description="Localhost only by default (SRS 12.1/18.2)")
    port: bpy.props.IntProperty(name="Bridge Port", default=8765, min=1024, max=65535)  # type: ignore
    auto_start: bpy.props.BoolProperty(name="Auto-start bridge", default=False)  # type: ignore
    workspace_root: bpy.props.StringProperty(  # type: ignore
        name="Workspace Root", subtype="DIR_PATH", default="//artifacts")
    safety_mode: bpy.props.EnumProperty(  # type: ignore
        name="Safety Mode",
        items=[("strict", "Strict (structured ops only)", ""),
               ("dev", "Dev (scanned Python, sandboxed)", "")],
        default="strict")

    def draw(self, context):
        col = self.layout.column()
        col.prop(self, "host")
        col.prop(self, "port")
        col.prop(self, "auto_start")
        col.prop(self, "workspace_root")
        col.prop(self, "safety_mode")
        if self.host not in ("127.0.0.1", "localhost", "::1"):
            col.label(text="Warning: non-localhost host exposes a remote surface", icon="ERROR")
