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
                if not obj.hide_render:
                    obj.hide_render = True
                    hidden.append(obj)
    try:
        bpy.ops.export_scene.gltf(
            filepath=filepath,
            export_format="GLB",
            export_apply=True,          # bake modifiers + geometry nodes
            export_yup=True,
            use_visible=True,
        )
    finally:
        for obj in hidden:
            obj.hide_render = False
    ok = os.path.exists(filepath)
    return {"exported": ok, "path": filepath,
            "size_bytes": os.path.getsize(filepath) if ok else 0}
