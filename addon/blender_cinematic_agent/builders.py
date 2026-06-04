"""Recipe operation builders (bpy). Self-contained; consumes validated dicts.

Each builder maps an allowlisted operation (see core ``recipes.OPERATION_SPECS``)
to real Blender API calls. The core validated names/params before this runs, but
builders still fail safe on unknown input.
"""
import json
import math
import os
import random

import bmesh  # type: ignore
import bpy  # type: ignore
from mathutils import Euler, Matrix, Vector  # type: ignore

from . import bpyutil


# --------------------------- mesh primitive helpers ------------------------ #
def _finish_mesh(name, bm, collection):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpyutil.link_to_collection(obj, collection or "SUBJECT")
    return obj


def _orient_closed_mesh_outward(bm):
    """Keep generated closed hero meshes from shipping inverted normals."""
    try:
        faces = list(bm.faces)
        if not faces:
            return
        bmesh.ops.recalc_face_normals(bm, faces=faces)
        bm.normal_update()
        if bm.calc_volume(signed=True) < 0:
            bmesh.ops.reverse_faces(bm, faces=faces)
            bm.normal_update()
    except Exception:
        return


def _primitive(kind, name, size, collection):
    bm = bmesh.new()
    r = size / 2.0
    try:
        if kind == "cube":
            bmesh.ops.create_cube(bm, size=size)
        elif kind == "uv_sphere":
            try:
                bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
            except TypeError:
                bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, diameter=r)
        elif kind == "ico_sphere":
            try:
                bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
            except TypeError:
                bmesh.ops.create_icosphere(bm, subdivisions=2, diameter=r)
        elif kind == "cylinder":
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                                  radius1=r, radius2=r, depth=size)
        elif kind == "cone":
            bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                                  radius1=r, radius2=0.0, depth=size)
        elif kind == "plane":
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=r)
        elif kind == "circle":
            bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=r)
        else:
            bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=r)
    finally:
        obj = _finish_mesh(name, bm, collection)
    return obj


def _torus(name, size, collection):
    """Real torus via operator, then relink to the target collection."""
    major = size / 2.0
    bpy.ops.mesh.primitive_torus_add(major_radius=major, minor_radius=major * 0.18)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    bpyutil.link_to_collection(obj, collection or "SUBJECT")
    return obj


def op_create_mesh_primitive(p):
    kind = p["type"]
    if kind == "torus":
        obj = _torus(p["name"], float(p.get("size", 2.0)), p.get("collection"))
    else:
        obj = _primitive(kind, p["name"], float(p.get("size", 2.0)), p.get("collection"))
    if p.get("location"):
        obj.location = Vector(p["location"])
    if p.get("rotation"):
        obj.rotation_euler = Euler([math.radians(a) for a in p["rotation"]])
    if p.get("scale"):
        obj.scale = Vector(p["scale"])
        _apply_mesh_scale(obj)
    return {"created": obj.name, "faces": len(obj.data.polygons)}


# -------------------------------- modifiers -------------------------------- #
_MOD_MAP = {"BEVEL": "BEVEL", "SUBSURF": "SUBSURF", "ARRAY": "ARRAY", "MIRROR": "MIRROR",
            "SOLIDIFY": "SOLIDIFY", "WEIGHTED_NORMAL": "WEIGHTED_NORMAL", "DECIMATE": "DECIMATE",
            "TRIANGULATE": "TRIANGULATE", "SHRINKWRAP": "SHRINKWRAP", "BOOLEAN": "BOOLEAN",
            "CURVE": "CURVE", "WIREFRAME": "WIREFRAME"}


def op_add_modifier(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    mtype = _MOD_MAP.get(p["modifier"], p["modifier"])
    mod = obj.modifiers.new(name=f"{mtype.title()}", type=mtype)
    for k, v in (p.get("params") or {}).items():
        if hasattr(mod, k):
            setattr(mod, k, v)
    return {"modifier": mod.name, "on": obj.name}


def op_add_bevel_modifier(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    mod = obj.modifiers.new(name="Bevel", type="BEVEL")
    mod.width = float(p["width"])
    mod.segments = int(p.get("segments", 2))
    mod.harden_normals = True
    return {"modifier": mod.name, "on": obj.name}


def op_add_subdivision(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    mod = obj.modifiers.new(name="Subdivision", type="SUBSURF")
    mod.levels = int(p.get("levels", 1))
    mod.render_levels = int(p.get("render_levels", mod.levels))
    return {"modifier": mod.name, "on": obj.name}


def op_add_array_modifier(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    mod = obj.modifiers.new(name="Array", type="ARRAY")
    mod.count = int(p["count"])
    if p.get("offset"):
        mod.use_relative_offset = False
        mod.use_constant_offset = True
        mod.constant_offset_displace = Vector(p["offset"])
    return {"modifier": mod.name, "on": obj.name, "count": mod.count}


# -------------------------------- materials -------------------------------- #
def _set_input(bsdf, names, value):
    for n in names:
        if n in bsdf.inputs:
            try:
                bsdf.inputs[n].default_value = value
                return True
            except (TypeError, ValueError):
                pass
    return False


def _node_input(node, names):
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
    return None


def _node_output(node, names):
    for name in names:
        if name in node.outputs:
            return node.outputs[name]
    return None


def _set_node_input(node, names, value):
    sock = _node_input(node, names)
    if sock is None:
        return False
    try:
        sock.default_value = value
        return True
    except (TypeError, ValueError):
        return False


def _constant_color_node(nt, name, color):
    rgb = nt.nodes.new("ShaderNodeRGB")
    rgb.name = name
    rgb.outputs["Color"].default_value = tuple(color)
    return rgb.outputs["Color"]


def _mix_color(nt, name, lhs_socket, rhs_socket, fac=0.35, blend_type="MIX"):
    try:
        mix = nt.nodes.new("ShaderNodeMixRGB")
    except RuntimeError:
        mix = nt.nodes.new("ShaderNodeMix")
        if hasattr(mix, "data_type"):
            mix.data_type = "RGBA"
    mix.name = name
    if hasattr(mix, "blend_type"):
        mix.blend_type = blend_type
    _set_node_input(mix, ["Fac", "Factor"], float(fac))
    lhs_input = _node_input(mix, ["Color1", "A"])
    rhs_input = _node_input(mix, ["Color2", "B"])
    out = _node_output(mix, ["Color", "Result"])
    if lhs_input is None or rhs_input is None or out is None:
        return rhs_socket
    nt.links.new(lhs_socket, lhs_input)
    nt.links.new(rhs_socket, rhs_input)
    return out


def _set_color_ramp(ramp, colors, low_position=0.2, high_position=1.0, stops=None):
    cr = ramp.color_ramp
    if stops:
        wanted = sorted(stops, key=lambda stop: float(stop.get("position", 0.0)))
        while len(cr.elements) < len(wanted):
            cr.elements.new(float(wanted[len(cr.elements)].get("position", 1.0)))
        while len(cr.elements) > len(wanted):
            cr.elements.remove(cr.elements[-1])
        for elem, stop in zip(cr.elements, wanted):
            elem.position = float(stop.get("position", 0.0))
            elem.color = tuple(stop["color"])
        return
    if colors:
        cr.elements[0].position = float(low_position)
        cr.elements[0].color = tuple(colors[0])
    if len(colors) > 1:
        cr.elements[1].position = float(high_position)
        cr.elements[1].color = tuple(colors[1])


def _generated_texture_image(name, kind):
    size = 64
    image_name = f"BCAS_{name}_{kind}"
    existing = bpy.data.images.get(image_name)
    if existing:
        return existing
    image = bpy.data.images.new(image_name, width=size, height=size, alpha=True)
    pixels = []
    for y in range(size):
        for x in range(size):
            if kind == "checker_label":
                on = ((x // 8) + (y // 8)) % 2 == 0
                color = (0.92, 0.9, 0.82, 1.0) if on else (0.04, 0.055, 0.085, 1.0)
            elif kind == "microprint_label":
                line = y % 11 in (0, 1) or (x % 17 == 0 and 10 < y < 54)
                color = (0.05, 0.06, 0.08, 1.0) if line else (0.88, 0.86, 0.78, 1.0)
            else:
                stripe = (x + y // 2) % 13 < 5
                color = (0.86, 0.78, 0.52, 1.0) if stripe else (0.08, 0.12, 0.16, 1.0)
            pixels.extend(color)
    image.pixels.foreach_set(pixels)
    image.pack()
    image["bcas_generated_texture"] = kind
    return image


def _connect_image_mapping(nt, tex, tex_schema):
    projection = str(tex_schema.get("projection", "uv"))
    texcoord = nt.nodes.new("ShaderNodeTexCoord")
    texcoord.name = f"{tex.name}_TexCoord"
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.name = f"{tex.name}_Mapping"
    repeat = tex_schema.get("repeat") or [1.0, 1.0]
    offset = tex_schema.get("offset") or [0.0, 0.0]
    rotation = math.radians(float(tex_schema.get("rotation_degrees", 0.0)))
    _set_node_input(mapping, ["Scale"], (float(repeat[0]), float(repeat[1]), 1.0))
    _set_node_input(mapping, ["Location"], (float(offset[0]), float(offset[1]), 0.0))
    _set_node_input(mapping, ["Rotation"], (0.0, 0.0, rotation))
    source_name = {"generated": "Generated", "object": "Object"}.get(projection, "UV")
    source = _node_output(texcoord, [source_name, "UV", "Generated"])
    if source and _node_input(mapping, ["Vector"]) and _node_input(tex, ["Vector"]):
        nt.links.new(source, _node_input(mapping, ["Vector"]))
        nt.links.new(_node_output(mapping, ["Vector"]), _node_input(tex, ["Vector"]))


_PRESET_DEFAULTS = {
    "brushed_metal": {"metallic": 1.0, "roughness": 0.35},
    "painted_metal": {"metallic": 0.6, "roughness": 0.4},
    "glossy_plastic": {"metallic": 0.0, "roughness": 0.15},
    "matte_plastic": {"metallic": 0.0, "roughness": 0.6},
    "glass_clear": {"metallic": 0.0, "roughness": 0.0, "transmission": 1.0, "alpha": 1.0},
    "frosted_glass": {"metallic": 0.0, "roughness": 0.35, "transmission": 1.0},
    "rubber_dark": {"metallic": 0.0, "roughness": 0.85},
    "emissive_neon": {"emission_strength": 5.0},
    "hologram": {"alpha": 0.4, "emission_strength": 3.0},
    "stone_concrete": {"metallic": 0.0, "roughness": 0.9},
    "wood": {"metallic": 0.0, "roughness": 0.6},
}


def _build_material(schema):
    name = schema["name"]
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])

    pbr = dict(schema.get("pbr") or {})
    for k, v in _PRESET_DEFAULTS.get(schema.get("preset", ""), {}).items():
        pbr.setdefault(k, v)

    _set_input(bsdf, ["Base Color"], tuple(pbr.get("base_color", [0.8, 0.8, 0.8, 1.0])))
    _set_input(bsdf, ["Metallic"], float(pbr.get("metallic", 0.0)))
    _set_input(bsdf, ["Roughness"], float(pbr.get("roughness", 0.5)))
    _set_input(bsdf, ["Alpha"], float(pbr.get("alpha", 1.0)))
    _set_input(bsdf, ["IOR"], float(pbr.get("ior", 1.45)))
    _set_input(bsdf, ["Coat Weight", "Clearcoat"], float(pbr.get("clearcoat", 0.0)))
    _set_input(bsdf, ["Transmission Weight", "Transmission"], float(pbr.get("transmission", 0.0)))
    if pbr.get("emission_strength"):
        _set_input(bsdf, ["Emission Color", "Emission"],
                   tuple(pbr.get("emission_color") or pbr.get("base_color", [0.1, 0.4, 1.0, 1.0])))
        _set_input(bsdf, ["Emission Strength"], float(pbr["emission_strength"]))
    if float(pbr.get("alpha", 1.0)) < 1.0 or float(pbr.get("transmission", 0.0)) > 0.0:
        mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else mat.blend_method

    features = []
    image_roles = []
    missing_texture_paths = []
    proc = schema.get("procedural") or {}
    base_color = tuple(pbr.get("base_color", [0.8, 0.8, 0.8, 1.0]))
    base_color_socket = None

    def ensure_base_socket():
        nonlocal base_color_socket
        if base_color_socket is None:
            base_color_socket = _constant_color_node(nt, f"NG_{name}_PBRBase", base_color)
        return base_color_socket

    def layer_color(socket, node_name, fac=0.35, blend_type="MIX"):
        nonlocal base_color_socket
        if base_color_socket is None:
            base_color_socket = socket
        else:
            base_color_socket = _mix_color(nt, node_name, ensure_base_socket(), socket, fac, blend_type)

    if proc.get("noise"):
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.name = f"NG_{name}_Noise"
        noise.inputs["Scale"].default_value = float(proc.get("noise_scale", 10.0))
        if "Detail" in noise.inputs:
            noise.inputs["Detail"].default_value = 8.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.name = f"NG_{name}_Bump"
        bump.inputs["Strength"].default_value = float(proc.get("bump_strength", 0.1))
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        if "Normal" in bsdf.inputs:
            nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        features.append("noise_bump")
    if proc.get("color_ramp"):
        ramp_schema = proc.get("color_ramp") or {}
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.name = f"NG_{name}_RampNoise"
        noise.inputs["Scale"].default_value = float(ramp_schema.get("noise_scale", proc.get("noise_scale", 18.0)))
        noise.inputs["Detail"].default_value = float(ramp_schema.get("detail", 8.0))
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.name = f"NG_{name}_ColorRamp"
        colors = ramp_schema.get("colors") or [
            pbr.get("base_color", [0.08, 0.08, 0.09, 1.0]),
            ramp_schema.get("highlight", [0.45, 0.55, 0.7, 1.0]),
        ]
        _set_color_ramp(
            ramp,
            colors,
            ramp_schema.get("low_position", 0.2),
            ramp_schema.get("high_position", 1.0),
            ramp_schema.get("stops") or None,
        )
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        layer_color(ramp.outputs["Color"], f"NG_{name}_RampLayer", 0.6, "MIX")
        features.append("noise_color_ramp")
    if proc.get("checker"):
        checker_schema = proc.get("checker") or {}
        checker = nt.nodes.new("ShaderNodeTexChecker")
        checker.name = f"NG_{name}_Checker"
        checker.inputs["Scale"].default_value = float(checker_schema.get("scale", 18.0))
        colors = checker_schema.get("colors") or [
            pbr.get("base_color", [0.08, 0.08, 0.09, 1.0]),
            checker_schema.get("accent", [0.8, 0.82, 0.86, 1.0]),
        ]
        if colors:
            checker.inputs["Color1"].default_value = tuple(colors[0])
        if len(colors) > 1:
            checker.inputs["Color2"].default_value = tuple(colors[1])
        layer_color(checker.outputs["Color"], f"NG_{name}_CheckerLayer", 0.42, "MIX")
        features.append("checker_texture")
    if proc.get("wave"):
        wave_schema = proc.get("wave") or {}
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.name = f"NG_{name}_Wave"
        wave.inputs["Scale"].default_value = float(wave_schema.get("scale", 18.0))
        wave.inputs["Distortion"].default_value = float(wave_schema.get("distortion", 4.0))
        bump = nt.nodes.new("ShaderNodeBump")
        bump.name = f"NG_{name}_WaveBump"
        bump.inputs["Strength"].default_value = float(wave_schema.get("bump_strength", 0.035))
        nt.links.new(wave.outputs["Color"], bump.inputs["Height"])
        if "Normal" in bsdf.inputs:
            nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        features.append("wave_bump")
    if proc.get("roughness_variation"):
        rv = proc.get("roughness_variation") or {}
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.name = f"NG_{name}_RoughnessNoise"
        noise.inputs["Scale"].default_value = float(rv.get("noise_scale", 36.0))
        if "Detail" in noise.inputs:
            noise.inputs["Detail"].default_value = float(rv.get("detail", 8.0))
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.name = f"NG_{name}_RoughnessRamp"
        min_r = float(rv.get("min_roughness", 0.25))
        max_r = float(rv.get("max_roughness", 0.75))
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = (min_r, min_r, min_r, 1.0)
        ramp.color_ramp.elements[1].position = 1.0
        ramp.color_ramp.elements[1].color = (max_r, max_r, max_r, 1.0)
        nt.links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        if "Roughness" in bsdf.inputs:
            nt.links.new(ramp.outputs["Color"], bsdf.inputs["Roughness"])
        features.append("roughness_variation")
    edge_wear = proc.get("edge_wear", "none")
    if edge_wear and edge_wear != "none":
        strength = {"subtle": 0.22, "medium": 0.38, "heavy": 0.58}.get(edge_wear, 0.22)
        ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
        ao.name = f"NG_{name}_EdgeWearAO"
        _set_node_input(ao, ["Distance"], 0.55)
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.name = f"NG_{name}_EdgeWearRamp"
        wear_color = tuple(min(1.0, float(c) + 0.28 + strength * 0.22) for c in base_color[:3]) + (1.0,)
        _set_color_ramp(ramp, [base_color, wear_color], 0.18, 1.0)
        nt.links.new(ao.outputs["AO"], ramp.inputs["Fac"])
        layer_color(ramp.outputs["Color"], f"NG_{name}_EdgeWearLayer", strength, "SCREEN")
        features.append(f"edge_wear_{edge_wear}")
    if proc.get("scanlines"):
        wave = nt.nodes.new("ShaderNodeTexWave")
        wave.name = f"NG_{name}_ScanlineWave"
        wave.inputs["Scale"].default_value = float(proc.get("scanline_scale", 80.0))
        if "Distortion" in wave.inputs:
            wave.inputs["Distortion"].default_value = 0.0
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.name = f"NG_{name}_ScanlineRamp"
        strength = float(proc.get("scanline_strength", 0.18))
        dark = tuple(max(0.0, float(c) * (1.0 - strength)) for c in base_color[:3]) + (1.0,)
        bright = tuple(min(1.0, float(c) + strength) for c in base_color[:3]) + (1.0,)
        _set_color_ramp(ramp, [dark, bright], 0.46, 0.54)
        nt.links.new(wave.outputs["Color"], ramp.inputs["Fac"])
        layer_color(ramp.outputs["Color"], f"NG_{name}_ScanlineLayer", strength, "MIX")
        features.append("scanlines")
    if float(proc.get("anisotropic", 0.0)) > 0.0:
        _set_input(bsdf, ["Anisotropic"], float(proc.get("anisotropic", 0.0)))
        _set_input(bsdf, ["Anisotropic Rotation"], float(proc.get("anisotropic_rotation", 0.0)))
        features.append("anisotropic_brush")
    for tex_schema in proc.get("image_textures") or []:
        tex_path = str(tex_schema.get("path", ""))
        role = str(tex_schema.get("role", "base_color"))
        generated = tex_schema.get("generated")
        abs_path = bpy.path.abspath(tex_path) if tex_path else ""
        if generated:
            image = _generated_texture_image(name, str(generated))
        elif abs_path and os.path.exists(abs_path):
            image = bpy.data.images.load(abs_path, check_existing=True)
        else:
            missing_texture_paths.append(tex_path)
            features.append(f"missing_image_texture_{role}")
            continue
        try:
            image.colorspace_settings.name = str(tex_schema.get("color_space", "sRGB"))
        except TypeError:
            pass
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.name = f"NG_{name}_Image_{role}"
        tex.image = image
        _connect_image_mapping(nt, tex, tex_schema)
        color_out = _node_output(tex, ["Color"])
        alpha_out = _node_output(tex, ["Alpha"])
        if role == "base_color" and color_out:
            layer_color(color_out, f"NG_{name}_ImageBaseLayer", 0.85, "MIX")
        elif role == "roughness" and color_out and "Roughness" in bsdf.inputs:
            nt.links.new(color_out, bsdf.inputs["Roughness"])
        elif role == "normal" and color_out and "Normal" in bsdf.inputs:
            bump = nt.nodes.new("ShaderNodeBump")
            bump.name = f"NG_{name}_ImageNormalBump"
            bump.inputs["Strength"].default_value = float(tex_schema.get("strength", 1.0))
            nt.links.new(color_out, bump.inputs["Height"])
            nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
        elif role == "emission" and color_out:
            if _node_input(bsdf, ["Emission Color", "Emission"]):
                nt.links.new(color_out, _node_input(bsdf, ["Emission Color", "Emission"]))
            _set_input(bsdf, ["Emission Strength"], float(tex_schema.get("strength", 1.0)))
        elif role == "alpha" and alpha_out and "Alpha" in bsdf.inputs:
            nt.links.new(alpha_out, bsdf.inputs["Alpha"])
            mat.blend_method = "BLEND" if hasattr(mat, "blend_method") else mat.blend_method
        elif role == "displacement" and color_out:
            disp = nt.nodes.new("ShaderNodeDisplacement")
            disp.name = f"NG_{name}_ImageDisplacement"
            _set_node_input(disp, ["Scale"], float(tex_schema.get("strength", 1.0)) * 0.025)
            nt.links.new(color_out, disp.inputs["Height"])
            if "Displacement" in out.inputs:
                nt.links.new(disp.outputs["Displacement"], out.inputs["Displacement"])
        image_roles.append(role)
        features.append(f"image_texture_{role}")
    if base_color_socket is not None and "Base Color" in bsdf.inputs:
        nt.links.new(base_color_socket, bsdf.inputs["Base Color"])
    mat["bcas_procedural_features"] = ",".join(features)
    mat["bcas_image_texture_roles"] = ",".join(image_roles)
    mat["bcas_missing_texture_paths"] = "|".join(missing_texture_paths)
    return mat


def op_create_material(p):
    mat = _build_material(p["schema"])
    policy = p["schema"].get("export_policy") or {}
    mat["bcas_web_safe"] = bool(policy.get("web_safe", True))
    mat["bcas_fallback"] = str(policy.get("fallback_material", "")) if policy.get("bake_if_needed", True) else ""
    for tname in (p["schema"].get("target_objects") or []):
        obj = bpyutil.get_object(tname)
        if obj and obj.type == "MESH":
            if obj.data.materials:
                obj.data.materials[0] = mat
            else:
                obj.data.materials.append(mat)
    return {"material": mat.name, "assigned_to": p["schema"].get("target_objects", [])}


def op_assign_material(p):
    obj = bpyutil.get_object(p["target"])
    mat = bpy.data.materials.get(p["material"])
    if not obj or not mat:
        return {"error": "object or material missing"}
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    return {"assigned": mat.name, "to": obj.name}


# --------------------------------- lights ---------------------------------- #
_ROLE_POS = {
    "front_left_high": (-4, -4, 5), "front_right_high": (4, -4, 5),
    "back_high": (0, 5, 6), "top": (0, 0, 7), "rim": (0, 4, 3),
}


def _make_light(spec):
    name = spec["name"]
    ld = bpy.data.lights.new(name, type=spec.get("type", "AREA"))
    ld.energy = float(spec.get("power", 100.0))
    if hasattr(ld, "size"):
        ld.size = float(spec.get("size", 1.0))
    ld.color = tuple(spec.get("color", [1.0, 1.0, 1.0]))[:3]
    obj = bpy.data.objects.new(name, ld)
    pos = spec.get("location") or _ROLE_POS.get(spec.get("position_role", ""), (3, -3, 4))
    obj.location = Vector(pos)
    bpyutil.link_to_collection(obj, "LIGHTS")
    return obj


def op_add_light(p):
    obj = _make_light(p["schema"])
    return {"light": obj.name}


def op_create_lighting_rig(p):
    schema = p["schema"]
    made = [_make_light(light).name for light in schema.get("lights", [])]
    world = schema.get("world")
    if world is not None:
        w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
        bpy.context.scene.world = w
        w.use_nodes = True
        bg = w.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = tuple(world.get("color", [0.05, 0.05, 0.05])) + (1.0,)
            bg.inputs[1].default_value = float(world.get("strength", 1.0))
    return {"rig": schema.get("lighting_rig"), "lights": made}


# --------------------------------- camera ---------------------------------- #
def op_create_camera(p):
    schema = p["schema"]
    name = schema["camera_name"]
    preset = schema.get("preset", "macro_product")
    cam = bpy.data.cameras.new(name)
    lens = schema.get("lens") or {}
    cam.lens = float(lens.get("focal_length_mm", 50.0))
    cam.sensor_width = float(lens.get("sensor_width_mm", 36.0))
    if preset == "orthographic_technical":
        cam.type = "ORTHO"
        cam.ortho_scale = float((schema.get("composition") or {}).get("ortho_scale", 4.2))
    obj = bpy.data.objects.new(name, cam)
    loc = schema.get("location") or (0.0, -6.0, 1.5)
    obj.location = Vector(loc)
    target_name = lens.get("focus_target") or schema.get("target")
    look = schema.get("look_at")
    tobj = bpyutil.get_object(target_name) if target_name else None
    if look or tobj:
        target_co = Vector(look) if look else tobj.location
        direction = (target_co - obj.location)
        if direction.length > 1e-6:
            obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    if lens.get("dof") and tobj:
        cam.dof.use_dof = True
        cam.dof.focus_object = tobj
        cam.dof.aperture_fstop = float(lens.get("aperture_fstop", 2.8))
    bpyutil.link_to_collection(obj, "CAMERAS")
    bpy.context.scene.camera = obj
    bpy.context.scene["final_camera"] = name
    obj["bcas_camera_preset"] = preset
    obj["bcas_subject_screen_coverage"] = float(
        (schema.get("composition") or {}).get("subject_screen_coverage", 0.6)
    )
    obj["bcas_safe_margin"] = float((schema.get("composition") or {}).get("safe_margin", 0.08))
    bpy.context.scene["camera_preset"] = preset
    bpy.context.scene["camera_subject_screen_coverage"] = obj["bcas_subject_screen_coverage"]
    bpy.context.scene["camera_safe_margin"] = obj["bcas_safe_margin"]
    return {"camera": name, "active": True, "preset": preset, "type": cam.type}


# --------------------------- transforms / misc ----------------------------- #
def op_set_object_transform(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    if p.get("location"):
        obj.location = Vector(p["location"])
    if p.get("rotation"):
        obj.rotation_euler = Euler([math.radians(a) for a in p["rotation"]])
    if p.get("scale"):
        obj.scale = Vector(p["scale"])
    return {"transformed": obj.name}


def op_apply_transform(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    with bpy.context.temp_override(active_object=obj, selected_objects=[obj],
                                   selected_editable_objects=[obj]):
        bpy.ops.object.transform_apply(location=bool(p.get("location", False)),
                                       rotation=bool(p.get("rotation", False)),
                                       scale=bool(p.get("scale", True)))
    return {"applied": obj.name, "scale": list(obj.scale)}


def op_set_smooth_shading(p):
    obj = bpyutil.get_object(p["target"])
    if not obj or obj.type != "MESH":
        return {"error": "mesh target required"}
    for poly in obj.data.polygons:
        poly.use_smooth = bool(p["smooth"])
    return {"smooth": bool(p["smooth"]), "on": obj.name}


def op_set_origin(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    with bpy.context.temp_override(active_object=obj, selected_objects=[obj],
                                   selected_editable_objects=[obj]):
        bpy.ops.object.origin_set(type=p.get("mode", "ORIGIN_GEOMETRY"))
    return {"origin_set": obj.name}


def op_move_to_collection(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    bpyutil.link_to_collection(obj, p["collection"])
    return {"moved": obj.name, "to": p["collection"]}


def op_parent_objects(p):
    child = bpyutil.get_object(p["child"])
    parent = bpyutil.get_object(p["parent"])
    if not child or not parent:
        return {"error": "child or parent missing"}
    child.parent = parent
    return {"parented": child.name, "to": parent.name}


def op_ensure_standard_collections(p):
    return {"collections": list(bpyutil.ensure_standard_collections().keys())}


def op_create_collection(p):
    coll = bpyutil.ensure_collection(p["name"])
    return {"collection": coll.name}


def op_set_scene_metadata(p):
    for k, v in (p.get("data") or {}).items():
        bpy.context.scene[k] = v
    return {"metadata_keys": list((p.get("data") or {}).keys())}


def op_add_constraint(p):
    obj = bpyutil.get_object(p["target"])
    if not obj:
        return {"error": f"target not found: {p['target']}"}
    con = obj.constraints.new(type=p["constraint"])
    for k, v in (p.get("params") or {}).items():
        if k == "target":
            v = bpyutil.get_object(v)
        if hasattr(con, k):
            setattr(con, k, v)
    return {"constraint": con.type, "on": obj.name}


# -------------------------- authored craft detail -------------------------- #
def _material_from_param(p):
    return bpy.data.materials.get(p.get("material", ""))


def _assign_material_if_present(obj, mat):
    if mat and getattr(obj.data, "materials", None) is not None:
        obj.data.materials.append(mat)


def _parent_if_requested(obj, parent_name):
    if not parent_name:
        return None
    parent = bpyutil.get_object(parent_name)
    if parent:
        world = obj.matrix_world.copy()
        obj.parent = parent
        obj.matrix_world = world
        return parent.name
    return None


def _tag_craft_detail(obj, role, group, source=None):
    obj["bcas_craft_role"] = role
    obj["bcas_craft_group"] = group
    if source:
        obj["bcas_craft_source"] = source
    return obj


def _apply_mesh_scale(obj):
    with bpy.context.temp_override(active_object=obj, selected_objects=[obj],
                                   selected_editable_objects=[obj]):
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)


def _add_detail_bevel(obj, width, segments=1):
    if obj.type != "MESH" or float(width) <= 0:
        return None
    bevel = obj.modifiers.new(name="Craft Detail Bevel", type="BEVEL")
    bevel.width = float(width)
    bevel.segments = int(segments)
    bevel.harden_normals = True
    return bevel


def _create_craft_box(name, location, rotation, dimensions, collection, material, role, group, bevel_width=0.006):
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.active_object
    obj.name = name
    obj.data.name = name
    obj.location = Vector(location)
    obj.rotation_euler = rotation
    obj.dimensions = Vector(dimensions)
    bpyutil.link_to_collection(obj, collection or "SUBJECT")
    _apply_mesh_scale(obj)
    _add_detail_bevel(obj, bevel_width, 1)
    _assign_material_if_present(obj, material)
    return _tag_craft_detail(obj, role, group)


def op_create_text_label(p):
    """Create real Blender FONT label text for product marks, callouts, and panels."""
    curve = bpy.data.curves.new(p["name"], "FONT")
    curve.body = p["text"]
    curve.align_x = str(p.get("align_x", "CENTER"))
    curve.align_y = str(p.get("align_y", "CENTER"))
    curve.size = float(p.get("size", 0.16))
    curve.extrude = float(p.get("extrude", 0.002))
    obj = bpy.data.objects.new(p["name"], curve)
    obj.location = Vector(p.get("location", [0, 0, 0]))
    obj.rotation_euler = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    obj.scale = Vector(p.get("scale", [1, 1, 1]))
    bpyutil.link_to_collection(obj, p.get("collection") or "SUBJECT")
    _assign_material_if_present(obj, _material_from_param(p))
    parented = _parent_if_requested(obj, p.get("parent"))
    _tag_craft_detail(obj, p.get("role", "text_label"), p["name"], parented)
    return {"created": obj.name, "type": obj.type, "chars": len(curve.body)}


def op_create_decal_plane(p):
    """Create a thin beveled plate/card for decals, labels, badges, and UI panels."""
    size = list(p.get("size") or [0.8, 0.24, 0.01])
    if len(size) == 2:
        size.append(0.01)
    obj = _create_craft_box(
        p["name"],
        p.get("location", [0, 0, 0]),
        Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])]),
        [float(size[0]), float(size[1]), float(size[2])],
        p.get("collection") or "SUBJECT",
        _material_from_param(p),
        p.get("role", "decal_plane"),
        p["name"],
        float(p.get("bevel_width", 0.004)),
    )
    parented = _parent_if_requested(obj, p.get("parent"))
    if parented:
        obj["bcas_craft_source"] = parented
    return {"created": obj.name, "type": obj.type, "role": obj["bcas_craft_role"]}


def op_create_curve_tube(p):
    """Create a real bevelled CURVE tube for cables, hoses, wires, or trim lines."""
    points = [Vector(point) for point in p["points"]]
    obj = _create_curve_cable(
        p["name"],
        points,
        float(p.get("bevel_depth", 0.018)),
        p.get("collection") or "SUBJECT",
        _material_from_param(p),
    )
    obj.data.resolution_u = int(p.get("resolution", 2))
    parented = _parent_if_requested(obj, p.get("parent"))
    _tag_craft_detail(obj, p.get("role", "curve_tube"), p["name"], parented)
    return {"created": obj.name, "type": obj.type, "points": len(points)}


def op_create_fastener_pattern(p):
    """Create shallow cylinders that read as screws, bolts, rivets, or washers."""
    count = max(1, min(256, int(p.get("count", 8))))
    pattern = str(p.get("pattern", "radial")).lower()
    center = Vector(p.get("center", [0, 0, 0]))
    radius = float(p.get("radius", 0.5))
    start = Vector(p.get("start", [0, 0, 0]))
    step = Vector(p.get("step", [0.12, 0, 0]))
    rotation = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    size = float(p.get("size", 0.06))
    coll = p.get("collection") or "SUBJECT"
    mat = _material_from_param(p)
    parent_name = p.get("parent")
    made = []
    for idx in range(count):
        angle = (2 * math.pi * idx) / count
        loc = center + Vector((math.sin(angle) * radius, math.cos(angle) * radius, 0.0))
        rot = Euler((rotation.x, rotation.y, rotation.z - angle))
        if pattern == "linear":
            loc = start + step * idx
            rot = rotation
        obj = _primitive("cylinder", f"{p['name_prefix']}_{idx + 1:02d}", size, coll)
        obj.location = loc
        obj.rotation_euler = rot
        obj.scale = Vector((1.0, 1.0, 0.18))
        _apply_mesh_scale(obj)
        _add_detail_bevel(obj, max(0.002, size * 0.08), 1)
        _assign_material_if_present(obj, mat)
        parented = _parent_if_requested(obj, parent_name)
        _tag_craft_detail(obj, p.get("role", "fastener"), p["name_prefix"], parented)
        made.append(obj.name)
    return {"fasteners": made, "count": count}


def op_create_panel_cutlines(p):
    """Create thin raised/engraved seam strips for product panels and hardsurface cuts."""
    count = max(1, min(256, int(p.get("count", 8))))
    start = Vector(p.get("start", [0, 0, 0]))
    step = Vector(p.get("step", [0.12, 0, 0]))
    size = list(p.get("size") or [0.42, 0.012, 0.01])
    rotation = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    mat = _material_from_param(p)
    made = []
    for idx in range(count):
        obj = _create_craft_box(
            f"{p['name_prefix']}_{idx + 1:02d}",
            start + step * idx,
            rotation,
            [float(size[0]), float(size[1]), float(size[2])],
            p.get("collection") or "SUBJECT",
            mat,
            p.get("role", "panel_cutline"),
            p["name_prefix"],
            0.003,
        )
        parented = _parent_if_requested(obj, p.get("parent"))
        if parented:
            obj["bcas_craft_source"] = parented
        made.append(obj.name)
    return {"panel_cutlines": made, "count": count}


def op_create_grille(p):
    """Create repeated slats for vents, speaker grilles, heatsinks, and sci-fi intakes."""
    count = max(1, min(256, int(p.get("count", 8))))
    start = Vector(p.get("start", [0, 0, 0]))
    step = Vector(p.get("step", [0.06, 0, 0]))
    size = list(p.get("slat_size") or [0.035, 0.42, 0.025])
    rotation = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    mat = _material_from_param(p)
    made = []
    for idx in range(count):
        obj = _create_craft_box(
            f"{p['name_prefix']}_{idx + 1:02d}",
            start + step * idx,
            rotation,
            [float(size[0]), float(size[1]), float(size[2])],
            p.get("collection") or "SUBJECT",
            mat,
            p.get("role", "grille_slat"),
            p["name_prefix"],
            0.004,
        )
        parented = _parent_if_requested(obj, p.get("parent"))
        if parented:
            obj["bcas_craft_source"] = parented
        made.append(obj.name)
    return {"grille_slats": made, "count": count}


def op_create_surface_microdetails(p):
    """Create raised micro-relief lines: veins, scratches, wear marks, glints, or fibers."""
    count = max(1, min(256, int(p.get("count", 12))))
    pattern = str(p.get("pattern", "linear")).lower()
    center = Vector(p.get("center", [0, 0, 0]))
    start = Vector(p.get("start", [0, 0, 0]))
    step = Vector(p.get("step", [0.08, 0, 0]))
    direction = Vector(p.get("direction", [1, 0, 0]))
    if direction.length <= 1e-6:
        direction = Vector((1, 0, 0))
    direction.normalize()
    radius = float(p.get("radius", 0.5))
    length = float(p.get("length", 0.18))
    bevel_depth = float(p.get("bevel_depth", 0.004))
    waviness = float(p.get("waviness", 0.015))
    phase = math.radians(float(p.get("phase_degrees", 0.0)))
    rotation = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    coll = p.get("collection") or "SUBJECT"
    mat = _material_from_param(p)
    parent_name = p.get("parent")
    role = p.get("role", "surface_microdetail")
    # Deterministic layout seed for visual repeatability, not security randomness.
    rng = random.Random(int(p.get("seed", 0)))  # nosec B311
    made = []
    for idx in range(count):
        if pattern == "radial":
            angle = phase + (2 * math.pi * idx) / count
            loc = center + Vector((math.sin(angle) * radius, math.cos(angle) * radius, 0.0))
            tangent = Vector((math.cos(angle), -math.sin(angle), 0.0))
        elif pattern == "scatter":
            angle = phase + rng.uniform(0, 2 * math.pi)
            loc = center + Vector((
                math.sin(angle) * rng.uniform(0.1, radius),
                math.cos(angle) * rng.uniform(0.1, radius),
                rng.uniform(-waviness, waviness),
            ))
            tangent = Vector((math.cos(angle), -math.sin(angle), 0.0))
        else:
            loc = start + step * idx
            tangent = rotation.to_matrix() @ direction
        if tangent.length <= 1e-6:
            tangent = direction.copy()
        tangent.normalize()
        normal_lift = Vector((0.0, 0.0, waviness))
        half = tangent * (length * 0.5)
        points = [
            -half,
            normal_lift,
            half,
        ]
        obj = _create_curve_cable(
            f"{p['name_prefix']}_{idx + 1:02d}",
            points,
            bevel_depth,
            coll,
            mat,
        )
        obj.location = loc
        parented = _parent_if_requested(obj, parent_name)
        _tag_craft_detail(obj, role, p["name_prefix"], parented)
        made.append(obj.name)
    return {"surface_microdetails": made, "count": count, "role": role}


# ----------------------------- geometry nodes ------------------------------ #
def op_create_radial_markers(p):
    """Create repeated rectangular markers around a circular dial or gauge."""
    count = max(1, min(96, int(p.get("count", 12))))
    center = Vector(p.get("center", [0, 0, 0.75]))
    radius = float(p.get("radius", 0.8))
    size = p.get("size") or [0.06, 0.18, 0.025]
    dims = Vector((float(size[0]), float(size[1]), float(size[2])))
    coll = p.get("collection") or "SUBJECT"
    mat = bpy.data.materials.get(p.get("material", ""))
    parent_name = p.get("parent")
    role = p.get("role", "radial_marker")
    made = []
    for i in range(count):
        angle = (2 * math.pi * i) / count
        name = f"{p['name_prefix']}_{i + 1:02d}"
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        obj = bpy.context.active_object
        obj.name = name
        obj.data.name = name
        obj.location = center + Vector((math.sin(angle) * radius, math.cos(angle) * radius, 0.0))
        obj.rotation_euler = Euler((0.0, 0.0, -angle))
        obj.dimensions = dims
        bpyutil.link_to_collection(obj, coll)
        with bpy.context.temp_override(active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = obj.modifiers.new(name="Marker Bevel", type="BEVEL")
        bevel.width = float(p.get("bevel_width", 0.008))
        bevel.segments = int(p.get("bevel_segments", 2))
        bevel.harden_normals = True
        if mat:
            obj.data.materials.append(mat)
        parented = _parent_if_requested(obj, parent_name)
        _tag_craft_detail(obj, role, p["name_prefix"], parented)
        made.append(obj.name)
    return {"markers": made, "count": count}


def op_create_linear_markers(p):
    """Create repeated rectangular details along a strap, panel, rail, or trim."""
    count = max(1, min(128, int(p.get("count", 8))))
    start = Vector(p.get("start", [0, 0, 0]))
    step = Vector(p.get("step", [0, 0.2, 0]))
    size = p.get("size") or [0.4, 0.035, 0.025]
    dims = Vector((float(size[0]), float(size[1]), float(size[2])))
    rotation = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    coll = p.get("collection") or "SUBJECT"
    mat = bpy.data.materials.get(p.get("material", ""))
    parent_name = p.get("parent")
    role = p.get("role", "linear_marker")
    made = []
    for i in range(count):
        name = f"{p['name_prefix']}_{i + 1:02d}"
        bpy.ops.mesh.primitive_cube_add(size=1.0)
        obj = bpy.context.active_object
        obj.name = name
        obj.data.name = name
        obj.location = start + step * i
        obj.rotation_euler = rotation
        obj.dimensions = dims
        bpyutil.link_to_collection(obj, coll)
        with bpy.context.temp_override(active_object=obj, selected_objects=[obj],
                                       selected_editable_objects=[obj]):
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        bevel = obj.modifiers.new(name="Linear Marker Bevel", type="BEVEL")
        bevel.width = float(p.get("bevel_width", 0.006))
        bevel.segments = int(p.get("bevel_segments", 1))
        bevel.harden_normals = True
        if mat:
            obj.data.materials.append(mat)
        parented = _parent_if_requested(obj, parent_name)
        _tag_craft_detail(obj, role, p["name_prefix"], parented)
        made.append(obj.name)
    return {"markers": made, "count": count}


def _organic_surface_mesh(name, length, width, curl, bend, taper, segments_u, segments_v):
    """Build a tapered, curved single-sided organic surface mesh."""
    bm = bmesh.new()
    verts = []
    for v_idx in range(segments_v + 1):
        v = v_idx / segments_v
        row = []
        taper_width = width * (1.0 - taper * v)
        taper_width = max(width * 0.12, taper_width)
        y = v * length
        for u_idx in range(segments_u + 1):
            u = (u_idx / segments_u) - 0.5
            edge_falloff = 1.0 - min(abs(u) * 2.0, 1.0)
            x = u * taper_width
            z = math.sin(v * math.pi) * curl
            z += math.sin((u + 0.5) * math.pi) * bend * edge_falloff
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)
    bm.verts.ensure_lookup_table()
    for v_idx in range(segments_v):
        for u_idx in range(segments_u):
            bm.faces.new((
                verts[v_idx][u_idx],
                verts[v_idx][u_idx + 1],
                verts[v_idx + 1][u_idx + 1],
                verts[v_idx + 1][u_idx],
            ))
    obj = _finish_mesh(name, bm, None)
    return obj


def op_create_organic_surface_details(p):
    """Create tapered curved petals, leaves, or soft fold highlights."""
    count = max(1, min(96, int(p.get("count", 8))))
    pattern = str(p.get("pattern", "radial")).lower()
    center = Vector(p.get("center", [0, 0, 1.0]))
    start = Vector(p.get("start", [0, 0, 1.0]))
    step = Vector(p.get("step", [0.14, 0, 0.0]))
    radius = float(p.get("radius", 0.7))
    length = float(p.get("length", 0.6))
    width = float(p.get("width", 0.22))
    curl = float(p.get("curl", 0.08))
    bend = float(p.get("bend", 0.02))
    taper = max(0.0, min(0.92, float(p.get("taper", 0.72))))
    seg_u = max(3, min(16, int(p.get("segments_u", 6))))
    seg_v = max(3, min(18, int(p.get("segments_v", 8))))
    tilt = math.radians(float(p.get("tilt_degrees", 18.0)))
    twist = math.radians(float(p.get("twist_degrees", 0.0)))
    phase = math.radians(float(p.get("phase_degrees", 0.0)))
    rotation = Euler([math.radians(a) for a in p.get("rotation", [0, 0, 0])])
    coll = p.get("collection") or "SUBJECT"
    mat = bpy.data.materials.get(p.get("material", ""))
    thickness = float(p.get("thickness", 0.018))
    made = []
    for i in range(count):
        name = f"{p['name_prefix']}_{i + 1:02d}"
        obj = _organic_surface_mesh(name, length, width, curl, bend, taper, seg_u, seg_v)
        if pattern == "linear":
            obj.location = start + step * i
            obj.rotation_euler = rotation
        else:
            angle = phase + (2 * math.pi * i) / count
            obj.location = center + Vector((math.sin(angle) * radius, math.cos(angle) * radius, 0.0))
            obj.rotation_euler = Euler((tilt, twist, -angle))
        bpyutil.link_to_collection(obj, coll)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        solid = obj.modifiers.new(name="Organic Thickness", type="SOLIDIFY")
        solid.thickness = thickness
        solid.offset = 0.0
        sub = obj.modifiers.new(name="Organic Surface Smooth", type="SUBSURF")
        sub.levels = 1
        sub.render_levels = 1
        if mat:
            obj.data.materials.append(mat)
        _tag_craft_detail(obj, p.get("role", "organic_surface"), p["name_prefix"])
        made.append(obj.name)
    return {"organic_surfaces": made, "count": count}


def _energy_streak_mesh(name, length, width, curl, segments):
    """Build a tapered ribbon streak along local +Y with a slight arcing spine."""
    bm = bmesh.new()
    verts = []
    cols = (-1.0, 0.0, 1.0)
    for v_idx in range(segments + 1):
        v = v_idx / segments
        taper = (1.0 - v) ** 0.72
        row_width = max(width * 0.06, width * taper)
        y = v * length
        z = math.sin(v * math.pi) * curl
        x_sway = math.sin(v * math.pi * 1.35) * curl * 0.28
        row = []
        for col in cols:
            edge_lift = (1.0 - abs(col)) * curl * 0.12
            row.append(bm.verts.new((x_sway + col * row_width * 0.5, y, z + edge_lift)))
        verts.append(row)
    bm.verts.ensure_lookup_table()
    for v_idx in range(segments):
        bm.faces.new((verts[v_idx][0], verts[v_idx][1], verts[v_idx + 1][1], verts[v_idx + 1][0]))
        bm.faces.new((verts[v_idx][1], verts[v_idx][2], verts[v_idx + 1][2], verts[v_idx + 1][1]))
    obj = _finish_mesh(name, bm, None)
    return obj


def op_create_energy_burst_streaks(p):
    """Create cinematic tapered VFX streak ribbons radiating from an energy core."""
    count = max(1, min(160, int(p.get("count", 24))))
    segments = max(3, min(32, int(p.get("segments", 12))))
    # Deterministic visual layout seed, not security-sensitive randomness.
    rng = random.Random(int(p.get("seed", 0)))  # nosec B311
    center = Vector(p.get("center", [0, 0, 1.0]))
    radius_min = float(p.get("radius_min", 0.12))
    radius_max = max(radius_min, float(p.get("radius_max", radius_min + 0.12)))
    length_min = float(p.get("length_min", 0.25))
    length_max = max(length_min, float(p.get("length_max", length_min + 0.25)))
    width = float(p.get("width", 0.035))
    thickness = float(p.get("thickness", 0.006))
    curl = float(p.get("curl", 0.05))
    fan = math.radians(float(p.get("fan_degrees", 240.0)))
    base_angle = math.radians(float(p.get("angle_degrees", 0.0)))
    angle_jitter = math.radians(float(p.get("angle_jitter_degrees", 6.0)))
    tilt = math.radians(float(p.get("tilt_degrees", 0.0)))
    z_jitter = float(p.get("z_jitter", 0.08))
    coll = p.get("collection") or "SUBJECT"
    mat = bpy.data.materials.get(p.get("material", ""))
    made = []
    for i in range(count):
        fraction = 0.5 if count == 1 else i / (count - 1)
        angle = base_angle - fan * 0.5 + fan * fraction + rng.uniform(-angle_jitter, angle_jitter)
        radius = rng.uniform(radius_min, radius_max)
        length = rng.uniform(length_min, length_max)
        obj = _energy_streak_mesh(f"{p['name_prefix']}_{i + 1:02d}", length, width, curl, segments)
        obj.location = center + Vector((
            math.sin(angle) * radius,
            math.cos(angle) * radius,
            rng.uniform(-z_jitter, z_jitter),
        ))
        obj.rotation_euler = Euler((tilt + rng.uniform(-0.08, 0.08), 0.0, -angle))
        bpyutil.link_to_collection(obj, coll)
        for poly in obj.data.polygons:
            poly.use_smooth = True
        solid = obj.modifiers.new(name="Energy Streak Thickness", type="SOLIDIFY")
        solid.thickness = thickness
        solid.offset = 0.0
        sub = obj.modifiers.new(name="Energy Streak Smooth", type="SUBSURF")
        sub.levels = 1
        sub.render_levels = 1
        if mat:
            obj.data.materials.append(mat)
        _tag_craft_detail(obj, p.get("role", "energy_streak"), p["name_prefix"])
        made.append(obj.name)
    return {"energy_streaks": made, "count": count}


def _organic_fluted_body_mesh(name, radius, height, segments, rings, lobes, waist, rim_wave, twist_degrees, cap_bottom):
    """Build a single cohesive lobed soft-surface body."""
    bm = bmesh.new()
    verts = []
    twist = math.radians(twist_degrees)
    for ring_idx in range(rings + 1):
        t = ring_idx / rings
        row = []
        belly = math.sin(t * math.pi)
        profile = 0.34 + 0.38 * t + (0.74 * (belly ** 0.68))
        waist_pull = 1.0 - waist * math.exp(-((t - 0.42) ** 2) / 0.018)
        vertical_lobe_weight = 0.18 + 0.82 * (belly ** 0.55)
        z = t * height
        for seg_idx in range(segments):
            a = (2 * math.pi * seg_idx) / segments
            phase = a + twist * t
            lobe = math.sin(lobes * phase) if lobes else 0.0
            secondary = 0.45 * math.sin((lobes * 2 + 1) * phase + t * math.pi) if lobes else 0.0
            surface_wave = 1.0 + rim_wave * vertical_lobe_weight * (lobe + secondary)
            local_radius = radius * profile * waist_pull * max(0.42, surface_wave)
            oval = 1.0 - 0.16 * math.cos(t * math.pi)
            x = math.sin(a) * local_radius
            y = math.cos(a) * local_radius * oval
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)

    bm.verts.ensure_lookup_table()
    for ring_idx in range(rings):
        for seg_idx in range(segments):
            bm.faces.new((
                verts[ring_idx][seg_idx],
                verts[ring_idx][(seg_idx + 1) % segments],
                verts[ring_idx + 1][(seg_idx + 1) % segments],
                verts[ring_idx + 1][seg_idx],
            ))
    if cap_bottom:
        center = bm.verts.new((0, 0, 0))
        bm.verts.ensure_lookup_table()
        for seg_idx in range(segments):
            bm.faces.new((center, verts[0][seg_idx], verts[0][(seg_idx + 1) % segments]))
    obj = _finish_mesh(name, bm, None)
    return obj


def op_create_organic_fluted_body(p):
    """Create a cohesive fluted organic hero body instead of separate sphere lobes."""
    segments = max(12, min(160, int(p.get("segments", 64))))
    rings = max(4, min(80, int(p.get("rings", 18))))
    lobes = max(0, min(32, int(p.get("lobes", 9))))
    obj = _organic_fluted_body_mesh(
        p["name"],
        float(p.get("radius", 0.72)),
        float(p.get("height", 1.35)),
        segments,
        rings,
        lobes,
        max(0.0, min(0.85, float(p.get("waist", 0.18)))),
        max(0.0, min(0.32, float(p.get("rim_wave", 0.1)))),
        float(p.get("twist_degrees", 18.0)),
        bool(p.get("cap_bottom", True)),
    )
    if p.get("location"):
        obj.location = Vector(p["location"])
    if p.get("rotation"):
        obj.rotation_euler = Euler([math.radians(a) for a in p["rotation"]])
    if p.get("scale"):
        obj.scale = Vector(p["scale"])
    bpyutil.link_to_collection(obj, p.get("collection") or "SUBJECT")
    if bool(p.get("smooth", True)):
        for poly in obj.data.polygons:
            poly.use_smooth = True
    solid = obj.modifiers.new(name="Organic Body Thickness", type="SOLIDIFY")
    solid.thickness = 0.035
    solid.offset = 0.0
    sub = obj.modifiers.new(name="Organic Body Smooth", type="SUBSURF")
    sub.levels = int(p.get("subdivision_levels", 1))
    sub.render_levels = sub.levels
    mat = bpy.data.materials.get(p.get("material", ""))
    if mat:
        obj.data.materials.append(mat)
    return {"created": obj.name, "faces": len(obj.data.polygons), "segments": segments, "rings": rings}


def _faceted_hero_body_mesh(name, radius, height, segments, rings, twist_degrees,
                            shoulder, waist, crown_height, pavilion_height,
                            facet_depth, cap_top, cap_bottom):
    """Build a cut-gem/luxury-product body with readable flat facets."""
    bm = bmesh.new()
    verts = []
    twist = math.radians(twist_degrees)
    crown = max(0.08, min(0.45, crown_height))
    pavilion = max(0.08, min(0.45, pavilion_height))
    for ring_idx in range(rings + 1):
        t = ring_idx / rings
        z = (t - 0.5) * height
        belly = max(0.0, math.sin(t * math.pi))
        crown_bulge = math.exp(-((t - 0.72) ** 2) / (crown * crown))
        pavilion_cut = math.exp(-((t - 0.22) ** 2) / (pavilion * pavilion))
        waist_cut = math.exp(-((t - 0.46) ** 2) / 0.028)
        profile = 0.18 + 0.82 * (belly ** 0.62)
        profile += 0.18 * shoulder * crown_bulge
        profile -= 0.22 * waist * waist_cut
        profile += 0.08 * pavilion_cut
        profile = max(0.12, profile)
        row = []
        for seg_idx in range(segments):
            a = (2 * math.pi * seg_idx) / segments
            phase = a + twist * (t - 0.5)
            major_facet = math.cos(segments * 0.5 * phase)
            minor_facet = math.cos(segments * phase + ring_idx * 0.7)
            cut = 1.0 + facet_depth * (0.58 * major_facet + 0.42 * minor_facet)
            oval = 1.0 - 0.08 * math.cos((t - 0.5) * math.pi)
            local_radius = radius * profile * max(0.72, cut)
            x = math.sin(a) * local_radius
            y = math.cos(a) * local_radius * oval
            row.append(bm.verts.new((x, y, z)))
        verts.append(row)

    bm.verts.ensure_lookup_table()
    for ring_idx in range(rings):
        for seg_idx in range(segments):
            bm.faces.new((
                verts[ring_idx][seg_idx],
                verts[ring_idx][(seg_idx + 1) % segments],
                verts[ring_idx + 1][(seg_idx + 1) % segments],
                verts[ring_idx + 1][seg_idx],
            ))
    if cap_bottom:
        bottom = bm.verts.new((0, 0, -height * 0.5))
        bm.verts.ensure_lookup_table()
        for seg_idx in range(segments):
            bm.faces.new((bottom, verts[0][seg_idx], verts[0][(seg_idx + 1) % segments]))
    if cap_top:
        top = bm.verts.new((0, 0, height * 0.5))
        bm.verts.ensure_lookup_table()
        for seg_idx in range(segments):
            bm.faces.new((top, verts[-1][(seg_idx + 1) % segments], verts[-1][seg_idx]))
    _orient_closed_mesh_outward(bm)
    return _finish_mesh(name, bm, None)


def op_create_faceted_hero_body(p):
    """Create a premium faceted hero body that avoids default sphere silhouettes."""
    segments = max(8, min(128, int(p.get("segments", 48))))
    rings = max(4, min(64, int(p.get("rings", 18))))
    obj = _faceted_hero_body_mesh(
        p["name"],
        float(p.get("radius", 0.88)),
        float(p.get("height", 1.55)),
        segments,
        rings,
        float(p.get("facet_twist_degrees", 14.0)),
        max(0.0, min(1.0, float(p.get("shoulder", 0.55)))),
        max(0.0, min(1.0, float(p.get("waist", 0.25)))),
        float(p.get("crown_height", 0.18)),
        float(p.get("pavilion_height", 0.2)),
        max(0.0, min(0.2, float(p.get("facet_depth", 0.07)))),
        bool(p.get("cap_top", True)),
        bool(p.get("cap_bottom", True)),
    )
    if p.get("location"):
        obj.location = Vector(p["location"])
    if p.get("rotation"):
        obj.rotation_euler = Euler([math.radians(a) for a in p["rotation"]])
    if p.get("scale"):
        obj.scale = Vector(p["scale"])
    bpyutil.link_to_collection(obj, p.get("collection") or "SUBJECT")
    for poly in obj.data.polygons:
        poly.use_smooth = False
    bevel = obj.modifiers.new(name="Facet Edge Catchlights", type="BEVEL")
    bevel.width = max(0.0, min(0.08, float(p.get("bevel_width", 0.012))))
    bevel.segments = 1
    bevel.affect = "EDGES"
    weighted = obj.modifiers.new(name="Facet Weighted Normals", type="WEIGHTED_NORMAL")
    weighted.keep_sharp = True
    mat = bpy.data.materials.get(p.get("material", ""))
    if mat:
        obj.data.materials.append(mat)
    return {"created": obj.name, "faces": len(obj.data.polygons), "segments": segments, "rings": rings}


def _box_detail_mesh(name, location, dimensions, collection, material=None):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    sx, sy, sz = (max(0.001, float(v)) for v in dimensions)
    for vert in bm.verts:
        vert.co.x *= sx
        vert.co.y *= sy
        vert.co.z *= sz
    obj = _finish_mesh(name, bm, collection)
    obj.location = Vector(location)
    if material:
        obj.data.materials.append(material)
    return obj


def _gn_material(recipe):
    name = {
        "GN_PanelWall": "gn_panel_dark_metal",
        "GN_BoltDistributor": "gn_bolt_edge_metal",
        "GN_CableBundle": "gn_cable_dark_rubber",
        "GN_CityWindows": "gn_window_emissive_cells",
        "GN_RockScatter": "gn_rock_cool_stone",
        "GN_TechGreebles": "gn_greeble_graphite",
        "GN_LabelArrows": "gn_label_arrow_emissive",
        "GN_OrbitalRings": "gn_orbital_rim_light",
        "GN_ParticleDots": "gn_particle_dot_emissive",
        "GN_VegetationLow": "gn_leaf_low_green",
    }.get(recipe, "gn_detail_neutral")
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    schema_by_recipe = {
        "GN_CableBundle": {
            "preset": "rubber_dark",
            "pbr": {"base_color": [0.018, 0.02, 0.024, 1], "roughness": 0.82},
        },
        "GN_CityWindows": {
            "preset": "emissive_neon",
            "pbr": {
                "base_color": [0.28, 0.62, 1.0, 1],
                "emission_color": [0.28, 0.62, 1.0, 1],
                "emission_strength": 0.9,
            },
        },
        "GN_LabelArrows": {
            "preset": "emissive_neon",
            "pbr": {
                "base_color": [0.85, 0.92, 1.0, 1],
                "emission_color": [0.85, 0.92, 1.0, 1],
                "emission_strength": 0.75,
            },
        },
        "GN_OrbitalRings": {
            "preset": "emissive_neon",
            "pbr": {
                "base_color": [0.18, 0.78, 0.66, 1],
                "emission_color": [0.18, 0.78, 0.66, 1],
                "emission_strength": 0.72,
            },
        },
        "GN_ParticleDots": {
            "preset": "emissive_neon",
            "pbr": {
                "base_color": [0.75, 0.92, 1.0, 1],
                "emission_color": [0.75, 0.92, 1.0, 1],
                "emission_strength": 0.95,
            },
        },
        "GN_RockScatter": {
            "preset": "stone_concrete",
            "pbr": {"base_color": [0.22, 0.23, 0.24, 1], "roughness": 0.88},
            "procedural": {"noise": True, "noise_scale": 18, "bump_strength": 0.035},
        },
        "GN_VegetationLow": {
            "preset": "matte_plastic",
            "pbr": {"base_color": [0.12, 0.34, 0.18, 1], "roughness": 0.72},
        },
    }
    schema = {"name": name, **schema_by_recipe.get(recipe, {
        "preset": "painted_metal",
        "pbr": {"base_color": [0.055, 0.065, 0.082, 1], "metallic": 0.62, "roughness": 0.38},
        "procedural": {"noise": True, "noise_scale": 28, "bump_strength": 0.01},
    })}
    return _build_material(schema)


def _target_surface_frame(obj, offset):
    dims = [max(0.001, float(v)) for v in obj.dimensions]
    loc = Vector(obj.location)
    normal_axis = min(range(3), key=lambda idx: dims[idx])
    span_axes = [idx for idx in range(3) if idx != normal_axis]
    normal = Vector((0, 0, 0))
    normal[normal_axis] = -1.0 if loc[normal_axis] > 0 else 1.0
    if normal_axis == 2:
        normal[2] = 1.0
    base = loc + normal * (dims[normal_axis] * 0.5 + offset)
    return base, dims, normal_axis, span_axes, normal


def _place_on_surface(base, dims, span_axes, u, v):
    co = Vector(base)
    co[span_axes[0]] += u * dims[span_axes[0]] * 0.44
    co[span_axes[1]] += v * dims[span_axes[1]] * 0.44
    return co


def _mark_gn_detail(obj, recipe, role, source):
    obj["bcas_gn_recipe"] = recipe
    obj["bcas_gn_role"] = role
    obj["bcas_gn_source"] = source
    return obj


def _create_curve_cable(name, points, bevel_depth, collection, material):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 2
    curve.bevel_depth = max(0.001, float(bevel_depth))
    curve.bevel_resolution = 3
    spl = curve.splines.new("POLY")
    spl.points.add(len(points) - 1)
    for point, co in zip(spl.points, points):
        point.co = (float(co.x), float(co.y), float(co.z), 1.0)
    obj = bpy.data.objects.new(name, curve)
    if material:
        curve.materials.append(material)
    bpyutil.link_to_collection(obj, collection or "SUBJECT")
    return obj


def _add_recipe_visual_details(target, group_name, recipe, seed, count, inst_size):
    material = _gn_material(recipe)
    collection = target.users_collection[0].name if target.users_collection else "SUBJECT"
    # Deterministic visual layout seed, not security-sensitive randomness.
    rng = random.Random(seed)  # nosec B311
    made = []
    base, dims, normal_axis, span_axes, normal = _target_surface_frame(target, max(inst_size, 0.02))
    safe_count = max(1, min(int(count), 48))

    if recipe in ("GN_PanelWall", "GN_TechGreebles", "GN_CityWindows"):
        cols = max(2, min(8, int(math.sqrt(safe_count) + 1)))
        rows = max(2, math.ceil(safe_count / cols))
        for idx in range(safe_count):
            col, row = idx % cols, idx // cols
            u = -0.9 + 1.8 * ((col + 0.5) / cols)
            v = -0.9 + 1.8 * ((row + 0.5) / rows)
            co = _place_on_surface(base, dims, span_axes, u, v)
            if recipe == "GN_CityWindows":
                role = "window_cell"
                size_a, size_b, thickness = inst_size * 1.2, inst_size * 1.8, inst_size * 0.25
            elif recipe == "GN_TechGreebles":
                role = "tech_greeble_block"
                size_a = inst_size * rng.uniform(0.8, 1.8)
                size_b = inst_size * rng.uniform(0.45, 1.15)
                thickness = inst_size * rng.uniform(0.35, 0.8)
            else:
                role = "panel_wall_plate"
                size_a, size_b, thickness = inst_size * 3.6, inst_size * 2.2, inst_size
            dimensions = [thickness, thickness, thickness]
            dimensions[span_axes[0]] = size_a
            dimensions[span_axes[1]] = size_b
            dimensions[normal_axis] = thickness
            detail = _box_detail_mesh(f"{group_name}_{role}_{idx + 1:02d}", co, dimensions, collection, material)
            bevel = detail.modifiers.new(name="GN Detail Bevel", type="BEVEL")
            bevel.width = max(0.002, inst_size * 0.08)
            bevel.segments = 1
            made.append(_mark_gn_detail(detail, recipe, role, target.name))
    elif recipe == "GN_CableBundle":
        for idx in range(safe_count):
            start_u = -0.85 + 1.7 * (idx / max(1, safe_count - 1))
            start = _place_on_surface(base, dims, span_axes, start_u, -0.72)
            mid = _place_on_surface(base, dims, span_axes, start_u + rng.uniform(-0.18, 0.18), rng.uniform(-0.1, 0.28))
            end = _place_on_surface(base, dims, span_axes, start_u + rng.uniform(-0.12, 0.12), 0.78)
            cable = _create_curve_cable(
                f"{group_name}_cable_curve_{idx + 1:02d}",
                [start, mid + normal * inst_size * 0.8, end],
                inst_size * 0.35,
                collection,
                material,
            )
            made.append(_mark_gn_detail(cable, recipe, "cable_curve", target.name))
    elif recipe == "GN_OrbitalRings":
        center = Vector(target.location)
        for idx in range(max(1, min(safe_count, 8))):
            size = max(dims) * (0.58 + idx * 0.12)
            ring = _torus(f"{group_name}_orbital_ring_{idx + 1:02d}", size, collection)
            ring.location = center
            ring.rotation_euler = Euler((math.radians(90 + idx * 13), math.radians(idx * 22), 0))
            ring.scale.z = max(0.04, inst_size)
            if material:
                ring.data.materials.append(material)
            made.append(_mark_gn_detail(ring, recipe, "orbital_ring", target.name))
    elif recipe in ("GN_BoltDistributor", "GN_ParticleDots", "GN_RockScatter", "GN_LabelArrows", "GN_VegetationLow"):
        role = {
            "GN_BoltDistributor": "bolt_head",
            "GN_ParticleDots": "particle_dot",
            "GN_RockScatter": "rock_chip",
            "GN_LabelArrows": "label_arrow",
            "GN_VegetationLow": "leaf_card",
        }[recipe]
        for idx in range(safe_count):
            co = _place_on_surface(base, dims, span_axes, rng.uniform(-0.9, 0.9), rng.uniform(-0.9, 0.9))
            if recipe == "GN_BoltDistributor":
                detail = _primitive("cylinder", f"{group_name}_{role}_{idx + 1:02d}", inst_size * 2.2, collection)
                detail.location = co
                detail.scale = Vector((0.65, 0.65, 0.2))
                detail.rotation_euler = Euler((math.radians(90), 0, 0))
            else:
                dims_box = [inst_size, inst_size, inst_size]
                if recipe == "GN_LabelArrows":
                    dims_box[span_axes[0]] = inst_size * 3.2
                    dims_box[span_axes[1]] = inst_size * 0.8
                elif recipe == "GN_VegetationLow":
                    dims_box[span_axes[0]] = inst_size * 0.7
                    dims_box[span_axes[1]] = inst_size * 2.8
                elif recipe == "GN_RockScatter":
                    dims_box = [inst_size * rng.uniform(0.7, 1.8) for _ in range(3)]
                detail = _box_detail_mesh(f"{group_name}_{role}_{idx + 1:02d}", co, dims_box, collection, material)
            if material and getattr(detail.data, "materials", None) and not detail.data.materials:
                detail.data.materials.append(material)
            if detail.type == "MESH":
                bevel = detail.modifiers.new(name="GN Detail Bevel", type="BEVEL")
                bevel.width = max(0.002, inst_size * 0.1)
                bevel.segments = 1
            made.append(_mark_gn_detail(detail, recipe, role, target.name))
    return made


def op_create_geometry_nodes(p):
    """Deterministic recipe-specific geometry-nodes modifier.

    The graph remains lightweight and safe, but the node-group name and custom
    metadata now reflect the requested recipe so inspectors/tests can tell a
    panel wall from bolts, cables, windows, greebles, rings, dots, or vegetation.
    """
    schema = p["schema"]
    obj = bpyutil.get_object(schema["target_object"])
    if not obj or obj.type != "MESH":
        return {"error": "geometry-nodes target must be a mesh"}
    name = schema["node_group_name"]
    recipe = schema.get("recipe") or "GN_TechGreebles"
    inputs = schema.get("inputs") or {}
    seed = int(schema.get("seed", inputs.get("seed", 0)))
    count_key = {
        "GN_PanelWall": "panel_count",
        "GN_BoltDistributor": "bolt_count",
        "GN_CableBundle": "cable_count",
        "GN_CityWindows": "window_count",
        "GN_RockScatter": "rock_count",
        "GN_TechGreebles": "greeble_count",
        "GN_LabelArrows": "arrow_count",
        "GN_OrbitalRings": "ring_count",
        "GN_ParticleDots": "dot_count",
        "GN_VegetationLow": "leaf_count",
    }.get(recipe, "count")
    size_key = {
        "GN_PanelWall": "panel_depth",
        "GN_BoltDistributor": "bolt_size",
        "GN_CableBundle": "cable_radius",
        "GN_CityWindows": "window_size",
        "GN_RockScatter": "rock_size",
        "GN_TechGreebles": "greeble_size",
        "GN_LabelArrows": "arrow_size",
        "GN_OrbitalRings": "ring_size",
        "GN_ParticleDots": "dot_size",
        "GN_VegetationLow": "leaf_size",
    }.get(recipe, "instance_size")
    count = int(inputs.get(count_key) or inputs.get("panel_count") or inputs.get("count") or 24)
    inst_size = float(inputs.get(size_key) or inputs.get("panel_depth") or inputs.get("instance_size") or 0.08)

    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes, links = ng.nodes, ng.links
    n_in = nodes.new("NodeGroupInput")
    n_out = nodes.new("NodeGroupOutput")
    distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
    distribute.name = f"{recipe}_Distribute"
    distribute.inputs["Density"].default_value = max(1.0, count / 4.0)
    if "Seed" in distribute.inputs:
        distribute.inputs["Seed"].default_value = seed
    cube = nodes.new("GeometryNodeMeshCube")
    cube.name = f"{recipe}_InstanceProxy"
    if "Size" in cube.inputs:
        cube.inputs["Size"].default_value = (inst_size, inst_size, inst_size)
    inst = nodes.new("GeometryNodeInstanceOnPoints")
    inst.name = f"{recipe}_InstanceOnPoints"
    realize = nodes.new("GeometryNodeRealizeInstances")
    realize.name = f"{recipe}_Realize"
    join = nodes.new("GeometryNodeJoinGeometry")
    join.name = f"{recipe}_JoinWithBase"
    links.new(n_in.outputs[0], distribute.inputs["Mesh"])
    links.new(distribute.outputs["Points"], inst.inputs["Points"])
    links.new(cube.outputs["Mesh"], inst.inputs["Instance"])
    links.new(inst.outputs["Instances"], realize.inputs["Geometry"])
    links.new(n_in.outputs[0], join.inputs[0])
    links.new(realize.outputs["Geometry"], join.inputs[0])
    links.new(join.outputs[0], n_out.inputs[0])

    mod = obj.modifiers.new(name=name, type="NODES")
    mod.node_group = ng
    detail_objects = _add_recipe_visual_details(obj, name, recipe, seed, count, inst_size)
    obj["gn_seed"] = seed
    obj["gn_recipe"] = recipe
    obj["gn_count"] = count
    obj["gn_instance_size"] = inst_size
    obj["gn_generated_detail_count"] = len(detail_objects)
    obj["gn_generated_roles"] = ",".join(sorted({str(d.get("bcas_gn_role", "")) for d in detail_objects}))
    ng["bcas_recipe"] = recipe
    ng["bcas_seed"] = seed
    ng["bcas_count"] = count
    ng["bcas_instance_size"] = inst_size
    ng["bcas_detail_count"] = len(detail_objects)
    ng["bcas_detail_roles"] = obj["gn_generated_roles"]
    mod["bcas_recipe"] = recipe
    mod["bcas_seed"] = seed
    mod["bcas_count"] = count
    mod["bcas_instance_size"] = inst_size
    mod["bcas_detail_count"] = len(detail_objects)
    mod["bcas_detail_roles"] = obj["gn_generated_roles"]
    return {
        "node_group": name,
        "recipe": recipe,
        "seed": seed,
        "count": count,
        "detail_count": len(detail_objects),
        "detail_roles": obj["gn_generated_roles"],
        "on": obj.name,
    }


def _key_interp_linear(obj):
    if not obj.animation_data or not obj.animation_data.action:
        return
    for fc in getattr(obj.animation_data.action, "fcurves", []) or []:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def _turntable_center(objects, params):
    explicit = (params or {}).get("center")
    if explicit is not None:
        return Vector(explicit)
    if not objects:
        return Vector((0.0, 0.0, 0.0))
    center = Vector((0.0, 0.0, 0.0))
    for obj in objects:
        center += obj.location
    return center / len(objects)


def _scene_camera_path_samples(start_location, end_location, rotation, fs, fe, target=None, samples=9):
    if start_location is None or end_location is None:
        return []
    start = Vector(start_location)
    end = Vector(end_location)
    frames = []
    steps = max(2, int(samples))
    for idx in range(steps):
        t = idx / (steps - 1)
        fr = int(round(fs + (fe - fs) * t))
        position = start.lerp(end, t)
        frames.append({
            "frame": fr,
            "position": [float(v) for v in position],
            "rotation": [float(v) for v in rotation],
            "target": target or "",
        })
    return frames


# ----------------------- animation / vfx / post / rig ---------------------- #
def op_create_animation(p):
    """Keyframe targets per animation schema (turntable / curve-driven / light pulse)."""
    schema = p["schema"]
    scene = bpy.context.scene
    scene.frame_start = int(schema.get("frame_start", 1))
    scene.frame_end = int(schema.get("frame_end", 120))
    scene.render.fps = int(schema.get("fps", 24))
    mode = schema.get("mode", "turntable")
    fs, fe = scene.frame_start, scene.frame_end
    keyed = []
    camera_schema = schema.get("camera") or {}
    camera_obj = bpyutil.get_object(camera_schema.get("name") or (scene.camera.name if scene.camera else ""))
    target_objects = []
    for target_name in schema.get("targets", []):
        target_obj = bpyutil.get_object(target_name)
        if target_obj:
            target_objects.append(target_obj)
    turntable_center = _turntable_center(target_objects, schema.get("params") or {}) if mode == "turntable" else None
    mid_frame = int(round((fs + fe) / 2))
    if mode in ("camera_flythrough", "scroll_linked") and camera_obj:
        start = Vector(camera_schema.get("start_location") or list(camera_obj.location))
        end = Vector(camera_schema.get("end_location") or [camera_obj.location.x * 0.55, camera_obj.location.y * 0.55, camera_obj.location.z + 0.45])
        camera_obj.location = start
        camera_obj.keyframe_insert("location", frame=fs)
        camera_obj.location = end
        camera_obj.keyframe_insert("location", frame=fe)
        _key_interp_linear(camera_obj)
        keyed.append(camera_obj.name)
        camera_path = {
            "schema": "camera_path/0.1",
            "segments": [{"from_scroll": 0.0, "to_scroll": 1.0, "camera_from_frame": fs, "camera_to_frame": fe}],
            "samples": _scene_camera_path_samples(
                start,
                end,
                camera_obj.rotation_euler,
                fs,
                fe,
                camera_schema.get("dof_target"),
                9,
            ),
        }
        scene["camera_path_json"] = json.dumps(camera_path)
    for obj in target_objects:
        tname = obj.name
        if mode == "turntable":
            try:
                bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
            except Exception as exc:
                obj["bcas_animation_preference_warning"] = type(exc).__name__
            base_location = obj.location.copy()
            base_rotation = obj.rotation_euler.copy()
            orbit_offset = base_location - turntable_center
            for frame, angle in ((fs, 0.0), (mid_frame, math.pi), (fe, 2 * math.pi)):
                obj.location = turntable_center + (Matrix.Rotation(angle, 4, "Z") @ orbit_offset)
                obj.rotation_euler = base_rotation.copy()
                obj.rotation_euler[2] = base_rotation[2] + angle
                obj.keyframe_insert("location", frame=frame)
                obj.keyframe_insert("rotation_euler", index=2, frame=frame)
            obj["bcas_turntable_center"] = [float(v) for v in turntable_center]
            obj["bcas_turntable_orbit_radius"] = float(orbit_offset.length)
            _key_interp_linear(obj)
        elif mode == "light_pulse" and obj.type == "LIGHT":
            base = obj.data.energy
            for fr, val in ((fs, base), ((fs + fe) // 2, base * 2.0), (fe, base)):
                obj.data.energy = val
                obj.data.keyframe_insert("energy", frame=fr)
        elif mode == "reveal":
            obj.hide_viewport = True
            obj.hide_render = True
            obj.keyframe_insert("hide_viewport", frame=fs)
            obj.keyframe_insert("hide_render", frame=fs)
            obj.hide_viewport = False
            obj.hide_render = False
            obj.keyframe_insert("hide_viewport", frame=fe)
            obj.keyframe_insert("hide_render", frame=fe)
        elif mode == "exploded_view":
            origin = obj.location.copy()
            direction = origin.normalized() if origin.length > 1e-6 else Vector((0, 0, 1))
            distance = float((schema.get("params") or {}).get("distance", 0.75))
            obj.location = origin
            obj.keyframe_insert("location", frame=fs)
            obj.location = origin + direction * distance
            obj.keyframe_insert("location", frame=fe)
            _key_interp_linear(obj)
        else:
            for path, curve in (schema.get("curves") or {}).items():
                axis = {"rotation_x": 0, "rotation_y": 1, "rotation_z": 2}.get(path)
                if axis is not None:
                    obj.rotation_euler[axis] = float(curve.get("from", 0))
                    obj.keyframe_insert("rotation_euler", index=axis, frame=fs)
                    obj.rotation_euler[axis] = float(curve.get("to", 0))
                    obj.keyframe_insert("rotation_euler", index=axis, frame=fe)
                    _key_interp_linear(obj)
        keyed.append(tname)
    scene.timeline_markers.clear()
    scene.timeline_markers.new("start", frame=fs)
    scene.timeline_markers.new("end", frame=fe)
    scene.frame_set(fs)
    bpy.context.view_layer.update()
    scene["animation_mode"] = mode
    scene["animation_clip_name"] = (schema.get("export") or {}).get("clip_name", schema.get("animation_name"))
    return {"animation": schema.get("animation_name"), "mode": mode, "keyed": keyed,
            "frame_range": [fs, fe], "camera_path": bool(scene.get("camera_path_json"))}


def op_create_vfx(p):
    """Lightweight VFX: emissive energy core, or a capped particle system."""
    schema = p["schema"]
    target = bpyutil.get_object(schema["target"])
    if not target:
        return {"error": f"vfx target not found: {schema['target']}"}
    preset = schema.get("preset", "energy_core_shell")
    params = schema.get("params") or {}
    if preset in ("energy_core_shell", "emissive_core_no_particles", "hologram"):
        mat = _build_material({"name": f"{target.name}_emissive", "preset": "emissive_neon",
                               "pbr": {"base_color": [0.1, 0.4, 1.0, 1.0],
                                       "emission_color": [0.1, 0.4, 1.0, 1.0],
                                       "emission_strength": float(params.get("emission_strength", 4.0))}})
        if target.type == "MESH":
            if target.data.materials:
                target.data.materials[0] = mat
            else:
                target.data.materials.append(mat)
        return {"vfx": schema.get("vfx_name"), "preset": preset, "applied_to": target.name}
    count = min(int(params.get("particle_count", 100)), 2000)
    psys = target.modifiers.new(name=schema.get("vfx_name", "vfx"), type="PARTICLE_SYSTEM")
    settings = psys.particle_system.settings
    settings.count = count
    settings.frame_start = int(params.get("frame_start", 1))
    settings.frame_end = int(params.get("frame_end", 80))
    settings.lifetime = int(params.get("lifetime", 90))
    settings.particle_size = float(params.get("particle_size", 0.045))
    settings.display_percentage = min(100, int(params.get("display_percentage", 100)))
    settings.emit_from = "FACE"
    settings.physics_type = "NEWTON"
    settings.normal_factor = float(params.get("normal_factor", 0.45))
    settings.tangent_factor = float(params.get("tangent_factor", 0.08))
    if hasattr(settings, "render_type"):
        settings.render_type = str(params.get("render_type", "HALO"))
    return {"vfx": schema.get("vfx_name"), "preset": preset, "particle_count": count}


def op_apply_post(p):
    """Color-management 'look' (reliable across versions; compositor varies on 5.0)."""
    schema = p["schema"]
    vs = bpy.context.scene.view_settings
    want = schema.get("view_transform", "Filmic")
    options = {i.identifier for i in type(vs).bl_rna.properties["view_transform"].enum_items}
    for cand in (want, "AgX", "Filmic", "Standard"):
        if cand in options:
            vs.view_transform = cand
            break
    look_opts = {i.identifier for i in type(vs).bl_rna.properties["look"].enum_items}
    if schema.get("look") in look_opts:
        vs.look = schema["look"]
    vs.exposure = float(schema.get("exposure", 0.0))
    vs.gamma = float(schema.get("gamma", 1.0))
    bpy.context.scene["post_preset"] = schema.get("post_preset", "clean_product")
    return {"post": schema.get("post_preset"), "view_transform": vs.view_transform}


def op_create_rig(p):
    """Create named empty controls, parent driven objects, attach simple drivers."""
    schema = p["schema"]
    coll = "RIGS" if "RIGS" in bpy.data.collections else "HELPERS"
    made = []
    for ctrl in schema.get("controls", []):
        empty = bpy.data.objects.new(ctrl["name"], None)
        empty.empty_display_type = "PLAIN_AXES"
        bpyutil.link_to_collection(empty, coll)
        for driven_name in ctrl.get("drives", []):
            driven = bpyutil.get_object(driven_name)
            if driven:
                driven.parent = empty
        made.append(empty.name)
    drivers = []
    for d in schema.get("drivers", []):
        obj = bpyutil.get_object(d["target"].split(".")[0])
        if obj and "location.z" in d["target"]:
            try:
                obj.driver_add("location", 2).driver.expression = "0"
                drivers.append(d["target"])
            except Exception as exc:
                empty = bpy.data.objects.new(f"{schema.get('rig_name', 'rig')}_driver_warning", None)
                empty["bcas_driver_warning"] = type(exc).__name__
                bpyutil.link_to_collection(empty, coll)
    return {"rig": schema.get("rig_name"), "controls": made, "drivers": drivers}


BUILDERS = {
    "ensure_standard_collections": op_ensure_standard_collections,
    "create_collection": op_create_collection,
    "set_scene_metadata": op_set_scene_metadata,
    "create_mesh_primitive": op_create_mesh_primitive,
    "add_modifier": op_add_modifier,
    "add_bevel_modifier": op_add_bevel_modifier,
    "add_subdivision": op_add_subdivision,
    "add_array_modifier": op_add_array_modifier,
    "set_object_transform": op_set_object_transform,
    "apply_transform": op_apply_transform,
    "set_smooth_shading": op_set_smooth_shading,
    "set_origin": op_set_origin,
    "move_to_collection": op_move_to_collection,
    "parent_objects": op_parent_objects,
    "assign_material": op_assign_material,
    "create_material": op_create_material,
    "create_camera": op_create_camera,
    "create_lighting_rig": op_create_lighting_rig,
    "add_light": op_add_light,
    "create_geometry_nodes": op_create_geometry_nodes,
    "create_radial_markers": op_create_radial_markers,
    "create_linear_markers": op_create_linear_markers,
    "create_text_label": op_create_text_label,
    "create_decal_plane": op_create_decal_plane,
    "create_curve_tube": op_create_curve_tube,
    "create_fastener_pattern": op_create_fastener_pattern,
    "create_panel_cutlines": op_create_panel_cutlines,
    "create_grille": op_create_grille,
    "create_surface_microdetails": op_create_surface_microdetails,
    "create_organic_surface_details": op_create_organic_surface_details,
    "create_organic_fluted_body": op_create_organic_fluted_body,
    "create_faceted_hero_body": op_create_faceted_hero_body,
    "create_energy_burst_streaks": op_create_energy_burst_streaks,
    "create_animation": op_create_animation,
    "create_vfx": op_create_vfx,
    "apply_post": op_apply_post,
    "create_rig": op_create_rig,
    "add_constraint": op_add_constraint,
}


def apply_recipe(recipe):
    results = []
    for opn in recipe.get("operations", []):
        builder = BUILDERS.get(opn.get("op"))
        nested_params = opn.get("params")
        flat_params = {k: v for k, v in opn.items() if k not in ("op", "params")}
        if nested_params is None:
            params = flat_params
        elif flat_params:
            params = {**flat_params, "params": nested_params}
        else:
            params = nested_params
        if not builder:
            results.append({"op": opn.get("op"), "error": "no builder"})
            continue
        try:
            results.append({"op": opn["op"], **(builder(params) or {})})
        except Exception as exc:  # keep going; report per-op
            results.append({"op": opn.get("op"), "error": f"{type(exc).__name__}: {exc}"})
    return results
