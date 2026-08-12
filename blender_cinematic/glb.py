"""Minimal pure-Python GLB (binary glTF) parser/validator (SRS 12.4 web.validate_glb).

Parses the GLB container per the glTF 2.0 spec (12-byte header + JSON/BIN chunks)
and reports structure + size. This gives real validation with no Node/browser
dependency; the Node + three.js path is an additional runtime cross-check.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

_MAGIC = 0x46546C67  # 'glTF'
_JSON_CHUNK = 0x4E4F534A  # 'JSON'
_BIN_CHUNK = 0x004E4942  # 'BIN\0'


def parse_glb(path: str | Path) -> dict:
    data = Path(path).read_bytes()
    if len(data) < 12:
        raise ValueError("file too small to be a GLB")
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != _MAGIC:
        raise ValueError("not a GLB file (bad magic)")
    if version != 2:
        raise ValueError(f"unsupported GLB version {version}")
    if length != len(data):
        raise ValueError(f"declared length {length} != actual {len(data)}")
    offset = 12
    gltf_json: dict | None = None
    bin_len = 0
    while offset < len(data):
        header_offset = offset
        remaining = len(data) - offset
        if remaining < 8:
            raise ValueError(
                f"truncated GLB chunk header at offset {header_offset}: "
                f"expected 8 bytes, found {remaining}"
            )
        clen, ctype = struct.unpack_from("<II", data, offset)
        offset += 8
        if clen % 4:
            raise ValueError(
                f"GLB chunk at offset {header_offset} has unaligned length {clen}"
            )
        remaining = len(data) - offset
        if clen > remaining:
            raise ValueError(
                f"truncated GLB chunk at offset {header_offset}: "
                f"declared {clen} bytes, found {remaining}"
            )
        chunk = data[offset:offset + clen]
        offset += clen
        if ctype == _JSON_CHUNK:
            gltf_json = json.loads(chunk.decode("utf-8"))
        elif ctype == _BIN_CHUNK:
            bin_len = clen
    if gltf_json is None:
        raise ValueError("GLB missing JSON chunk")
    return {"json": gltf_json, "bin_length": bin_len, "total_length": length}


def inspect_glb(path: str | Path) -> dict:
    p = Path(path)
    g = parse_glb(p)
    j = g["json"]
    images = j.get("images", [])
    # external (uri) image references are missing-texture risks for the web
    external = [im.get("uri") for im in images if im.get("uri") and not im["uri"].startswith("data:")]
    return {
        "size_bytes": p.stat().st_size,
        "size_mb": round(p.stat().st_size / (1024 * 1024), 3),
        "nodes": len(j.get("nodes", [])),
        "meshes": len(j.get("meshes", [])),
        "materials": len(j.get("materials", [])),
        "animations": len(j.get("animations", [])),
        "animation_names": [a.get("name") for a in j.get("animations", [])],
        "cameras": len(j.get("cameras", [])),
        "images": len(images),
        "external_images": external,
        "extensions_used": j.get("extensionsUsed", []),
        "generator": (j.get("asset") or {}).get("generator"),
    }


def validate_glb(path: str | Path, max_mb: float | None = None,
                 require_animation: bool = False) -> dict:
    """Structural validation; returns {ok, info, errors, warnings}."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        info = inspect_glb(path)
    except Exception as exc:
        return {"ok": False, "info": None, "errors": [f"parse failed: {exc}"], "warnings": []}

    if info["nodes"] == 0:
        errors.append("GLB has no nodes (empty scene)")
    if info["meshes"] == 0:
        warnings.append("GLB has no meshes")
    if max_mb is not None and info["size_mb"] > max_mb:
        errors.append(f"GLB {info['size_mb']}MB exceeds budget {max_mb}MB")
    if require_animation and info["animations"] == 0:
        errors.append("animation required but GLB contains no animation clips")
    if info["external_images"]:
        errors.append(f"GLB references external textures (won't load standalone): {info['external_images']}")
    return {"ok": not errors, "info": info, "errors": errors, "warnings": warnings}
