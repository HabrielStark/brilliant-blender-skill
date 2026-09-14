"""GLB export (bpy). Bakes modifiers/geometry-nodes and validates the write."""
import os

import bpy  # type: ignore


def export_glb(filepath, manifest=None):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Hide helper/reference collections from export (SRS 14.2).
    hidden = []
    for coll in bpy.data.collections:
        if coll.name in ("HELPERS", "REFERENCE", "PROXIES"):
            for obj in coll.objects:
                # use_visible checks visible_get(): hide_set excludes the
                # object while keeping it in the depsgraph so export_apply
                # still evaluates it as e.g. a boolean operand.
                if not obj.hide_get():
                    obj.hide_set(True)
                    hidden.append(obj)
    # The create_animation op stores the AnimExport contract on the scene;
    # default to exporting animations (glTF exporter behavior) when no
    # animation op declared a policy.
    export_anim = bool(bpy.context.scene.get("animation_export_glb", True))
    # Objects flagged apply_before_glb=False export their raw base geometry —
    # disable their modifiers for the export so glTF doesn't bake them.
    raw_export = []
    for obj in bpy.data.objects:
        if obj.get("bcas_apply_before_glb") is False:
            disabled = [m for m in obj.modifiers if m.show_viewport]
            for m in disabled:
                m.show_viewport = False
            if disabled:
                raw_export.append((obj, disabled))
    try:
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format="GLB",
            export_apply=True,          # bake modifiers + geometry nodes
            export_yup=True,
            use_visible=True,
            export_animations=export_anim,
        )
    finally:
        for obj, mods in raw_export:
            for m in mods:
                m.show_viewport = True
        for obj in hidden:
            obj.hide_set(False)
    ok = os.path.exists(filepath)
    return {"exported": ok, "path": filepath,
            "size_bytes": os.path.getsize(filepath) if ok else 0}
