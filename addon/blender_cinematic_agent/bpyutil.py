"""bpy utilities shared by the add-on (self-contained: bpy + stdlib only).

No pydantic, no ``blender_cinematic`` imports — Blender's bundled Python does not
ship our dependencies, and the core validates everything before a job is sent.
"""
import traceback

import bpy  # type: ignore

REQUIRED_COLLECTIONS = ("CAMERAS", "LIGHTS", "SUBJECT", "ENVIRONMENT", "FX", "HELPERS", "EXPORT")


def resolve_engine(logical: str) -> str:
    """Map a logical engine name to the identifier in *this* Blender build.

    EEVEE is ``BLENDER_EEVEE`` on 5.0 and ``BLENDER_EEVEE_NEXT`` on 4.2-4.5.
    Under ``--factory-startup`` the Cycles engine is not registered, so it is
    enabled on demand (otherwise CYCLES would silently fall back to EEVEE).
    """
    logical = (logical or "EEVEE").upper()

    def _engines():
        return {i.identifier for i in
                bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}

    if logical == "CYCLES":
        # Cycles is not listed in the static engine enum even when usable, but
        # assigning 'CYCLES' works once the add-on is enabled.
        if "cycles" not in bpy.context.preferences.addons:
            try:
                bpy.ops.preferences.addon_enable(module="cycles")
            except Exception:
                print("Blender Cinematic Agent: failed to enable Cycles add-on")
                traceback.print_exc()
        return "CYCLES"
    items = _engines()
    if logical in ("WORKBENCH", "BLENDER_WORKBENCH"):
        return "BLENDER_WORKBENCH"
    for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if cand in items:
            return cand
    return "BLENDER_EEVEE"


def ensure_collection(name: str, parent=None):
    if name in bpy.data.collections:
        coll = bpy.data.collections[name]
    else:
        coll = bpy.data.collections.new(name)
    target = parent.children if parent else bpy.context.scene.collection.children
    if coll.name not in target and coll is not bpy.context.scene.collection:
        try:
            target.link(coll)
        except RuntimeError:
            pass
    return coll


def ensure_standard_collections():
    return {name: ensure_collection(name) for name in REQUIRED_COLLECTIONS}


def link_to_collection(obj, collection_name: str):
    coll = ensure_collection(collection_name)
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    coll.objects.link(obj)
    return coll


def get_object(name: str):
    return bpy.data.objects.get(name)
