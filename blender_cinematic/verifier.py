"""Verifier-response parsing: turn a fresh-eyes verifier report into
validated, allowlisted repair ops.

The verifier protocol (references/agent-orchestration.md) asks the reviewing
agent for a human-readable verdict plus a structured JSON block whose defects
carry ``suggested_ops``. This module extracts that block, filters the ops
through the same recipe validator every other path uses, and returns only ops
that would pass ``apply_recipe`` — so the builder→verifier→repair loop is
fully mechanical instead of relying on the orchestrator to translate prose.

Pure Python (no bpy); safe to unit-test without Blender.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .recipes import validate_recipe

_VERDICT_RE = re.compile(r"^\s*VERDICT\s*:\s*(PASS|FAIL)\b", re.IGNORECASE | re.MULTILINE)
_LEDGER_RE = re.compile(
    r"^\s{0,4}([A-Za-z0-9_ /-]+?)\s*:\s*(present|missing|unidentifiable|placeholder)\s*$",
    re.IGNORECASE | re.MULTILINE)
_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _json_blocks(text: str) -> list[dict[str, Any]]:
    """Candidate JSON objects: fenced blocks first, then any bare {...}
    containing a 'defects' or 'verdict' key."""
    blocks: list[dict[str, Any]] = []
    for m in _FENCE_RE.finditer(text):
        try:
            blocks.append(json.loads(m.group(1)))
        except (json.JSONDecodeError, TypeError):
            continue
    if blocks:
        return blocks
    # bare-object fallback: scan for balanced-brace spans containing a key
    seen_spans: set[tuple[int, int]] = set()
    for key in ('"defects"', '"verdict"'):
        start = text.find(key)
        while start != -1:
            open_brace = text.rfind("{", 0, start)
            if open_brace == -1:
                break
            depth = 0
            for i in range(open_brace, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        if (open_brace, i) not in seen_spans:
                            seen_spans.add((open_brace, i))
                            try:
                                blocks.append(json.loads(text[open_brace:i + 1]))
                            except (json.JSONDecodeError, TypeError):
                                pass
                        break
            start = text.find(key, start + 1)
    return blocks


def _resolve_hint(hint: str, object_names: list[str]) -> str | None:
    """Best-match an object's actual name from a free-text hint.

    Score = number of hint words (len>=3) found as substrings of the object
    name. Requires a unique argmax — ambiguous hints stay unresolved rather
    than guessing at the wrong object.
    """
    words = [w for w in re.split(r"[^a-z0-9]+", hint.lower()) if len(w) >= 3]
    if not words or not object_names:
        return None
    scored = sorted(
        ((sum(1 for w in words if w in name.lower()), name)
         for name in object_names),
        key=lambda t: -t[0])
    if not scored or scored[0][0] == 0:
        return None
    if len(scored) > 1 and scored[1][0] == scored[0][0]:
        return None  # ambiguous tie — safer to drop than guess
    return scored[0][1]


def _hint_param(op_name: str, params: dict) -> str | None:
    """Which param should receive a resolved object name for this op —
    'target' for object-aimed ops, 'name' for named-object ops."""
    from .recipes import OPERATION_SPECS
    spec = OPERATION_SPECS.get(op_name)
    if not spec:
        return None
    required, optional = spec["required"], spec["optional"]
    for cand in ("target", "name"):
        if cand in required or cand in optional:
            return cand
    return None


def _apply_hints(op: dict, object_names: list[str]) -> dict:
    """Rewrite name_hint/target_hint into the op's real param when it resolves
    to exactly one scene object. Returns the (possibly modified) op."""
    hint = op.get("name_hint") or op.get("target_hint")
    if not hint or not object_names:
        return op
    resolved = _resolve_hint(str(hint), object_names)
    if resolved is None:
        return op
    param = _hint_param(op.get("op", ""), op)
    if param:
        op = {**op, param: resolved}
        op.pop("name_hint", None)
        op.pop("target_hint", None)
    return op


def _coerce_op(op: dict, object_names: list[str],
               part_hint: str | None = None) -> dict:
    """Best-effort mechanical coercion of near-miss verifier ops.

    A vision-only verifier writes *intent*, not schema: it omits the
    ``schema:`` wrapper, says ``name`` where the spec wants ``target``, or
    uses ``energy`` instead of ``power`` for lights. Coerce the structural
    mismatches; leave semantic gaps (prose locations, missing parts) for
    the validator to drop honestly.
    """
    from .recipes import OPERATION_SPECS
    op = dict(op)
    spec = OPERATION_SPECS.get(op.get("op", ""))
    if spec is None:
        return op
    required, optional = spec["required"], spec["optional"]

    # name -> target for ops that target an object but lack a `name` param
    if "name" in op and "target" in required | optional and "name" not in required | optional:
        op["target"] = op.pop("name")

    # flat params -> schema wrapper for ops that require one
    if "schema" in required and "schema" not in op:
        schema = {k: v for k, v in op.items() if k != "op"}
        op = {"op": op["op"], "schema": schema}

    schema = op.get("schema")
    if isinstance(schema, dict):
        schema = dict(schema)
        op["schema"] = schema
        if op["op"] == "add_light":
            # verifier vocabulary -> Light fields
            if "light_type" in schema and "type" not in schema:
                schema["type"] = schema.pop("light_type")
            if "energy" in schema and "power" not in schema:
                schema["power"] = schema.pop("energy")
            if "position" in schema:
                pos = schema.pop("position")
                if isinstance(pos, (list, tuple)) and len(pos) == 3:
                    schema.setdefault("location", list(pos))
                elif isinstance(pos, str):
                    schema.setdefault("position_role", pos)
            if not schema.get("name"):
                schema["name"] = f"verifier_light_{abs(hash(json.dumps(schema, sort_keys=True, default=str))) % 10000}"
        elif op["op"] == "create_camera":
            if "name" in schema and "camera_name" not in schema:
                schema["camera_name"] = schema.pop("name")
        elif op["op"] == "create_material":
            if not schema.get("name"):
                schema["name"] = "verifier_material"
            # emission: [r,g,b] -> pbr.emission_color
            if isinstance(schema.get("emission"), (list, tuple)):
                pbr = dict(schema.get("pbr") or {})
                pbr.setdefault("emission_color", list(schema.pop("emission")))
                schema["pbr"] = pbr
            if isinstance(schema.get("emission_strength"), (int, float)):
                pbr = dict(schema.get("pbr") or {})
                pbr.setdefault("emission_strength", schema.pop("emission_strength"))
                schema["pbr"] = pbr
            # a defect's part hint is the natural target when it resolves
            if not schema.get("target_objects") and part_hint:
                resolved = _resolve_hint(part_hint, object_names)
                if resolved:
                    schema["target_objects"] = [resolved]
        elif op["op"] == "create_vfx":
            if not schema.get("vfx_name"):
                schema["vfx_name"] = "verifier_vfx"
    return op


def parse_verifier_response(text: str,
                            object_names: list[str] | None = None) -> dict[str, Any]:
    """Parse a verifier report into verdict + ledger + validated ops.

    ``object_names`` (from the latest scene_inspect) lets free-text
    ``name_hint``/``target_hint`` fields resolve to real object names — a
    vision-only verifier can't see names, so hints are how it points at
    objects. Unresolved or schema-invalid ops land in ``dropped_ops``.

    Returns::

        {
          "verdict": "PASS" | "FAIL" | None,
          "ledger": {"window": "present", ...},
          "defects": [ {part, defect, view, suggested_ops, ...} ],
          "ops": [ validated allowlisted ops, in defect order ],
          "dropped_ops": [ {"op": ..., "errors": [...]} ],
        }
    """
    text = text or ""
    verdict_m = _VERDICT_RE.search(text)
    verdict = verdict_m.group(1).upper() if verdict_m else None
    ledger = {m.group(1).strip(): m.group(2).lower() for m in _LEDGER_RE.finditer(text)}
    # ledger regex can catch the VERDICT line itself — drop it
    ledger.pop("VERDICT", None)
    ledger.pop("verdict", None)

    defects: list[dict[str, Any]] = []
    for block in _json_blocks(text):
        raw = block.get("defects")
        if isinstance(raw, list):
            defects.extend(d for d in raw if isinstance(d, dict))
        if verdict is None and isinstance(block.get("verdict"), str):
            if block["verdict"].strip().upper() in ("PASS", "FAIL"):
                verdict = block["verdict"].strip().upper()

    ops: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for d in defects:
        for op in d.get("suggested_ops") or []:
            if not isinstance(op, dict) or "op" not in op:
                dropped.append({"op": op, "errors": ["not an op dict"]})
                continue
            op = _apply_hints(dict(op), object_names or [])
            op = _coerce_op(op, object_names or [],
                            part_hint=d.get("part"))
            res = validate_recipe({"operations": [op]})
            errors = [i.message for i in res.issues
                      if getattr(i, "severity", "") == "error"]
            if errors:
                dropped.append({"op": op.get("op"), "errors": errors})
            else:
                ops.append(op)
    return {"verdict": verdict, "ledger": ledger, "defects": defects,
            "ops": ops, "dropped_ops": dropped}
