"""Scene inspector (bpy) -> inspection dict matching the linter contract.

Produces exactly the shape documented in
``blender_cinematic/linters.py`` so the pure-Python linters can score a real
Blender scene with no further translation.
"""
import json
import math
import traceback

import bmesh  # type: ignore
import bpy  # type: ignore
from bpy_extras.object_utils import world_to_camera_view  # type: ignore


def _bsdf(mat):
    if not mat.use_nodes:
        return None
    for n in mat.node_tree.nodes:
        if n.type == "BSDF_PRINCIPLED":
            return n
    return None


def _inp(bsdf, names, default=None):
    for n in names:
        if n in bsdf.inputs:
            try:
                return bsdf.inputs[n].default_value
            except Exception:
                return default
    return default


def _camera_projection(scene, cam, obj):
    """Return (in_frame, coverage) for obj's bbox under cam."""
    if not cam or obj.type not in ("MESH", "CURVE", "FONT"):
        return True, 0.0
    xs, ys, in_front = [], [], False
    for corner in obj.bound_box:
        world = obj.matrix_world @ _v(corner)
        co = world_to_camera_view(scene, cam, world)
        xs.append(co.x)
        ys.append(co.y)
        if co.z > 0:
            in_front = True
    minx, maxx = max(0.0, min(xs)), min(1.0, max(xs))
    miny, maxy = max(0.0, min(ys)), min(1.0, max(ys))
    coverage = max(0.0, (maxx - minx)) * max(0.0, (maxy - miny))
    in_frame = in_front and (maxx > minx) and (maxy > miny)
    return in_frame, round(coverage, 4)


def _v(seq):
    from mathutils import Vector  # type: ignore
    return Vector(seq)


def _plain(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)) or hasattr(value, "__iter__"):
        try:
            return [_plain(v) for v in value]
        except TypeError:
            return str(value)
    return str(value)


def _json_property(value):
    plain = _plain(value)
    if isinstance(plain, str):
        try:
            decoded = json.loads(plain)
        except json.JSONDecodeError:
            return plain
        return _plain(decoded)
    return plain


def _mesh_quality(obj):
    non_manifold = False
    flipped = False
    try:
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        # True non-manifold = edge shared by >2 faces (boolean artifacts), not
        # open boundary edges (1 face) which are normal for planes/cards.
        non_manifold = any(len(e.link_faces) > 2 for e in bm.edges)
        closed = bool(bm.edges) and all(len(e.link_faces) >= 2 for e in bm.edges)
        flipped = closed and bm.calc_volume(signed=True) < -1e-9
        bm.free()
    except Exception:
        print(f"Blender Cinematic Agent: mesh quality inspection failed for {obj.name!r}")
        traceback.print_exc()
    return non_manifold, flipped


def _vec_distance(a, b):
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def _sample_animation_motion(scene, anim_object_names, cam):
    if not anim_object_names and not (cam and cam.animation_data and cam.animation_data.action):
        return {"sampled_objects": [], "moving_object_count": 0}
    current_frame = scene.frame_current
    fs, fe = int(scene.frame_start), int(scene.frame_end)
    mid = int(round((fs + fe) / 2))
    frames = sorted({fs, mid, fe})
    targets = []
    seen = set()
    for name in anim_object_names:
        obj = bpy.data.objects.get(name)
        if obj and obj.name not in seen:
            targets.append(obj)
            seen.add(obj.name)
    if cam and cam.animation_data and cam.animation_data.action and cam.name not in seen:
        targets.append(cam)
        seen.add(cam.name)

    samples_by_object = {obj.name: [] for obj in targets}
    try:
        for frame in frames:
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            for obj in targets:
                samples_by_object[obj.name].append({
                    "frame": frame,
                    "location": [float(v) for v in obj.location],
                    "rotation": [float(v) for v in obj.rotation_euler],
                })
    finally:
        scene.frame_set(current_frame)
        bpy.context.view_layer.update()

    sampled = []
    moving = 0
    max_location_delta = 0.0
    max_rotation_delta = 0.0
    camera_motion = None
    for name, samples in samples_by_object.items():
        if not samples:
            continue
        base = samples[0]
        loc_delta = max(_vec_distance(base["location"], s["location"]) for s in samples)
        rot_delta = max(_vec_distance(base["rotation"], s["rotation"]) for s in samples)
        item = {
            "name": name,
            "sample_count": len(samples),
            "frames": frames,
            "max_location_delta": round(loc_delta, 4),
            "max_rotation_delta": round(rot_delta, 4),
        }
        sampled.append(item)
        max_location_delta = max(max_location_delta, loc_delta)
        max_rotation_delta = max(max_rotation_delta, rot_delta)
        if loc_delta > 0.01 or rot_delta > 0.1:
            moving += 1
        if cam and name == cam.name:
            camera_motion = item
    return {
        "sampled_objects": sampled,
        "moving_object_count": moving,
        "max_sampled_location_delta": round(max_location_delta, 4),
        "max_sampled_rotation_delta": round(max_rotation_delta, 4),
        "camera_sampled_motion": camera_motion,
    }


def _collection_of(obj):
    for c in obj.users_collection:
        return c.name
    return None


def inspect_scene():
    scene = bpy.context.scene
    cam = scene.camera
    objects = []
    for obj in scene.objects:
        faces = len(obj.data.polygons) if obj.type == "MESH" and obj.data else 0
        in_frame, coverage = _camera_projection(scene, cam, obj)
        non_manifold, flipped = _mesh_quality(obj) if obj.type == "MESH" else (False, False)
        smooth = bool(obj.type == "MESH" and obj.data.polygons and obj.data.polygons[0].use_smooth)
        objects.append({
            "name": obj.name,
            "type": obj.type,
            "collection": _collection_of(obj),
            "faces": faces,
            "verts": len(obj.data.vertices) if obj.type == "MESH" and obj.data else 0,
            "materials": [m.name for m in obj.data.materials] if getattr(obj.data, "materials", None) else [],
            "modifiers": [{"type": m.type, "show_render": m.show_render} for m in obj.modifiers],
            "location": list(obj.location),
            "scale": list(obj.scale),
            "dimensions": list(obj.dimensions),
            "visible": not obj.hide_render,
            "smooth": smooth,
            "in_camera_frame": in_frame,
            "screen_coverage": coverage,
            "non_manifold": non_manifold,
            "flipped_normals": flipped,
            "gn_recipe": _plain(obj.get("bcas_gn_recipe")),
            "gn_role": _plain(obj.get("bcas_gn_role")),
            "gn_source": _plain(obj.get("bcas_gn_source")),
            "craft_role": _plain(obj.get("bcas_craft_role")),
            "craft_group": _plain(obj.get("bcas_craft_group")),
            "craft_source": _plain(obj.get("bcas_craft_source")),
        })

    materials = []
    for mat in bpy.data.materials:
        if mat.users == 0 and not mat.use_fake_user:
            continue
        bsdf = _bsdf(mat)
        emission = bool(bsdf and (_inp(bsdf, ["Emission Strength"], 0) or 0) > 0)
        transmission = bool(bsdf and (_inp(bsdf, ["Transmission Weight", "Transmission"], 0) or 0) > 0)
        tex = [n.image.size[0] for n in (mat.node_tree.nodes if mat.use_nodes else [])
               if n.type == "TEX_IMAGE" and n.image and n.image.size[0]]
        node_names = [n.name for n in (mat.node_tree.nodes if mat.use_nodes else [])]
        declared_fallback = bool(mat.get("bcas_fallback"))
        web_safe_flag = bool(mat.get("bcas_web_safe", not transmission))
        materials.append({
            "name": mat.name,
            "metallic": float(_inp(bsdf, ["Metallic"], 0.0) or 0.0) if bsdf else 0.0,
            "roughness": float(_inp(bsdf, ["Roughness"], 0.5) or 0.5) if bsdf else 0.5,
            "node_count": len(mat.node_tree.nodes) if mat.use_nodes else 0,
            "link_count": len(mat.node_tree.links) if mat.use_nodes else 0,
            "node_names": node_names,
            "users": mat.users,
            "has_emission": emission,
            "has_transmission": transmission,
            "web_unsafe": transmission and not web_safe_flag,
            "has_fallback": declared_fallback,
            "is_default": mat.name.lower().startswith("material"),
            "max_texture_resolution": max(tex) if tex else None,
            "procedural_features": str(mat.get("bcas_procedural_features", "")),
            "image_texture_roles": str(mat.get("bcas_image_texture_roles", "")),
        })

    lights = [{"name": o.name, "type": o.data.type, "energy": o.data.energy,
               "color": list(o.data.color)} for o in scene.objects if o.type == "LIGHT"]

    active_camera = None
    if cam:
        active_camera = {
            "name": cam.name,
            "lens_mm": cam.data.lens,
            "dof": bool(cam.data.dof.use_dof),
            "focus_target": cam.data.dof.focus_object.name if cam.data.dof.focus_object else None,
            "inside_geometry": False,
            "clip_end": cam.data.clip_end,
        }

    anim_objects = [o.name for o in scene.objects if o.animation_data and o.animation_data.action]
    sampled_motion = _sample_animation_motion(scene, anim_objects, cam)
    eng = scene.render.engine
    samples = getattr(scene.cycles, "samples", None) if eng == "CYCLES" else \
        getattr(scene.eevee, "taa_render_samples", None)

    missing = []
    for img in bpy.data.images:
        if img.source == "FILE" and img.filepath:
            import os
            if not os.path.exists(bpy.path.abspath(img.filepath)):
                missing.append(img.filepath)
    for mat in bpy.data.materials:
        paths = str(mat.get("bcas_missing_texture_paths", ""))
        missing.extend([path for path in paths.split("|") if path])

    geometry_nodes = []
    for obj in scene.objects:
        for m in obj.modifiers:
            if m.type == "NODES" and m.node_group:
                geometry_nodes.append({
                    "name": m.node_group.name,
                    "recipe": m.get("bcas_recipe") or m.node_group.get("bcas_recipe") or obj.get("gn_recipe"),
                    "seed": m.get("bcas_seed") or m.node_group.get("bcas_seed") or obj.get("gn_seed"),
                    "target": obj.name,
                    "applied": False,
                    "generated_faces": m.get("bcas_count") or m.node_group.get("bcas_count"),
                    "visible_from_camera": True,
                    "node_count": len(m.node_group.nodes),
                    "link_count": len(m.node_group.links),
                    "instance_size": m.get("bcas_instance_size") or m.node_group.get("bcas_instance_size"),
                    "detail_count": m.get("bcas_detail_count") or m.node_group.get("bcas_detail_count"),
                    "detail_roles": m.get("bcas_detail_roles") or m.node_group.get("bcas_detail_roles"),
                })

    comp_tree = getattr(scene, "node_tree", None)
    comp_uses = bool(getattr(scene, "use_nodes", False)) and comp_tree is not None
    comp_names = [n.name for n in comp_tree.nodes] if comp_uses else []

    return {
        "schema": "scene_inspection/0.1",
        "collections": [c.name for c in bpy.data.collections],
        "objects": objects,
        "materials": materials,
        "lights": lights,
        "active_camera": active_camera,
        "cameras": [o.name for o in scene.objects if o.type == "CAMERA"],
        "node_groups": [ng.name for ng in bpy.data.node_groups],
        "geometry_nodes": geometry_nodes,
        "particles": [
            {
                "name": ps.name,
                "object": o.name,
                "count": max(len(ps.particles), int(getattr(ps.settings, "count", 0) or 0)),
                "cache_present": True,
            }
            for o in scene.objects for ps in getattr(o, "particle_systems", [])
        ],
        "animation": {
            "has_action": bool(anim_objects),
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "fps": scene.render.fps,
            "keyframed_objects": anim_objects,
            "markers": [m.name for m in scene.timeline_markers],
            "camera_animated": bool(cam and cam.animation_data and cam.animation_data.action),
            **sampled_motion,
        },
        "compositor": {
            "use_nodes": comp_uses,
            "node_names": comp_names,
            "raw_render_saved": True,
        },
        "render": {
            "engine": eng,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "samples": samples,
            "volumetric": False,
            "view_transform": scene.view_settings.view_transform,
        },
        "metadata": {k: _plain(scene[k]) for k in scene.keys()},
        "camera_path_json": _json_property(scene.get("camera_path_json")),
        "missing_files": missing,
    }
