"""Blind visual review packet generation for skill evals.

This module hides task ids and benchmark scores from the reviewer while keeping
the prompt, preview, and human-rating contract visible. It deliberately stays
pure Python and does not import ``bpy``.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .visual_review import flatten_summary, load_summary
from .workspace import WorkspaceResolver

REQUIRED_RATINGS = (
    "prompt_fit",
    "visual_quality",
    "composition_camera",
    "material_lighting",
    "detail_precision",
    "anti_slop",
    "ship_readiness",
)


def load_tasks(tasks_dir: str | Path) -> dict[str, dict[str, Any]]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(Path(tasks_dir).glob("*.json"))
    }


def _blind_id(task_id: str, seed: int) -> str:
    digest = hashlib.sha256(f"{seed}:{task_id}".encode("utf-8")).hexdigest()
    return f"BVR-{digest[:8].upper()}"


def _blind_sort_key(task_id: str, seed: int) -> str:
    return hashlib.sha256(f"blind-order:{seed}:{task_id}".encode("utf-8")).hexdigest()


def _markdown_path(path: str | None, base: Path) -> str:
    if not path:
        return ""
    try:
        rel = os.path.relpath(Path(path), start=base)
    except ValueError:
        rel = str(path)
    return rel.replace("\\", "/")


def _load_human_review(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _review_failures(items: list[dict[str, Any]], human_review: dict[str, Any] | None) -> list[str]:
    if not human_review:
        return ["blind human visual review required but no review JSON was provided"]
    reviews = human_review.get("reviews")
    if not isinstance(reviews, list):
        return ["blind human visual review must contain a reviews list"]
    by_blind = {str(item.get("blind_id")): item for item in reviews if isinstance(item, dict)}
    failures: list[str] = []
    for item in items:
        blind_id = str(item["blind_id"])
        review = by_blind.get(blind_id)
        if not review:
            failures.append(f"{blind_id}: missing blind review")
            continue
        if review.get("approved") is not True:
            failures.append(f"{blind_id}: blind review not approved")
        ratings = review.get("ratings") if isinstance(review.get("ratings"), dict) else {}
        missing = [key for key in REQUIRED_RATINGS if key not in ratings]
        if missing:
            failures.append(f"{blind_id}: missing blind review ratings: {', '.join(missing)}")
            continue
        weak = [key for key in REQUIRED_RATINGS if float(ratings.get(key, 0) or 0) < 4.0]
        if weak:
            failures.append(f"{blind_id}: blind review ratings below 4/5: {', '.join(weak)}")
    return failures


def build_blind_eval(
    summary: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    *,
    source: str | Path | None = None,
    seed: int = 20260603,
    human_review: dict[str, Any] | None = None,
    require_human_signoff: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = flatten_summary(summary)
    order = sorted(rows, key=lambda row: _blind_sort_key(str(row.get("task_id") or ""), seed))
    items: list[dict[str, Any]] = []
    mapping: list[dict[str, Any]] = []
    failures: list[str] = []

    for row in order:
        task_id = str(row.get("task_id") or "")
        task = tasks.get(task_id, {})
        manifest = task.get("manifest") or {}
        blind_id = _blind_id(task_id, seed)
        preview = row.get("skill_preview")
        item = {
            "blind_id": blind_id,
            "prompt": task.get("prompt") or manifest.get("brief") or "",
            "brief": manifest.get("brief") or "",
            "category": task.get("category") or "",
            "style": manifest.get("style") or {},
            "target": manifest.get("target") or {},
            "preview": preview,
            "review_focus": [
                "Does the scene satisfy the prompt without generic primitive slop?",
                "Is the composition/camera intentional and readable?",
                "Do materials, lighting, and details feel authored rather than accidental?",
                "Would this be shippable as an open-source skill benchmark example?",
            ],
        }
        if not preview or not Path(preview).is_file():
            failures.append(f"{blind_id}: preview missing")
        items.append(item)
        mapping.append({
            "blind_id": blind_id,
            "task_id": task_id,
            "skill_score": row.get("skill_score"),
            "score_delta": row.get("score_delta"),
            "preview": preview,
        })

    if require_human_signoff:
        failures.extend(_review_failures(items, human_review))

    manifest = {
        "schema": "blind_visual_eval/0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source) if source else None,
        "seed": seed,
        "status": "PASS" if items and not failures else "FAIL",
        "task_count": len(items),
        "human_review_required": require_human_signoff,
        "human_review": human_review if require_human_signoff else None,
        "failures": failures,
        "items": items,
    }
    private_mapping = {
        "schema": "blind_visual_eval_mapping/0.1",
        "generated_at": manifest["generated_at"],
        "source": manifest["source"],
        "seed": seed,
        "mapping": mapping,
    }
    return manifest, private_mapping


def blind_review_template(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "blind_visual_review/0.1",
        "reviewer": "",
        "generated_from": manifest.get("source"),
        "seed": manifest.get("seed"),
        "reviews": [
            {
                "blind_id": item.get("blind_id"),
                "approved": False,
                "ratings": {key: 0 for key in REQUIRED_RATINGS},
                "defects": [],
                "notes": "",
            }
            for item in manifest.get("items", [])
        ],
    }


def render_markdown(manifest: dict[str, Any], out_dir: str | Path) -> str:
    out = Path(out_dir)
    lines = [
        "# Blind Visual Eval",
        "",
        f"- Status: {manifest['status']}",
        f"- Items: {manifest['task_count']}",
        f"- Human signoff required: {manifest['human_review_required']}",
        f"- Seed: {manifest['seed']}",
        f"- Generated: {manifest['generated_at']}",
        "",
        "Reviewers see anonymized ids, prompts, style intent, and previews only.",
        "Do not use the private mapping until after ratings are complete.",
        "",
    ]
    if manifest["failures"]:
        lines += ["## Failures", ""]
        lines += [f"- {failure}" for failure in manifest["failures"]]
        lines.append("")
    lines += [
        "## Rating Contract",
        "",
        "Each item must be approved and score at least 4/5 on: "
        + ", ".join(REQUIRED_RATINGS)
        + ".",
        "",
        "## Items",
        "",
        "| Blind ID | Prompt | Preview |",
        "|---|---|---|",
    ]
    for item in manifest["items"]:
        preview = _markdown_path(item.get("preview"), out)
        preview_link = f"[preview]({preview})" if preview else "missing"
        prompt = str(item.get("prompt") or "").replace("|", "/")
        lines.append(f"| {item['blind_id']} | {prompt} | {preview_link} |")
    lines += ["", "## Contact Sheet", "", "![blind contact sheet](blind_contact_sheet.png)", ""]
    for item in manifest["items"]:
        preview = _markdown_path(item.get("preview"), out)
        if preview:
            lines += [f"### {item['blind_id']}", "", f"![{item['blind_id']}]({preview})", ""]
    return "\n".join(lines)


def make_contact_sheet(
    manifest: dict[str, Any],
    *,
    thumb_size: tuple[int, int] = (320, 180),
    columns: int = 2,
) -> bytes:
    items = manifest["items"]
    label_h = 34
    pad = 16
    columns = max(1, columns)
    cell_w = thumb_size[0]
    cell_h = thumb_size[1] + label_h
    rows = max(1, (len(items) + columns - 1) // columns)
    sheet = Image.new(
        "RGB",
        (columns * cell_w + (columns + 1) * pad, rows * cell_h + (rows + 1) * pad),
        (12, 12, 14),
    )
    draw = ImageDraw.Draw(sheet)
    for idx, item in enumerate(items):
        x = pad + (idx % columns) * (cell_w + pad)
        y = pad + (idx // columns) * (cell_h + pad)
        preview = item.get("preview")
        framed = Image.new("RGB", thumb_size, (0, 0, 0))
        if preview and Path(preview).is_file():
            with Image.open(preview) as image:
                tile = image.convert("RGB")
                tile.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                framed.paste(tile, ((thumb_size[0] - tile.width) // 2, (thumb_size[1] - tile.height) // 2))
        else:
            draw.text((x + 12, y + thumb_size[1] // 2 - 8), "missing preview", fill=(235, 235, 235))
        sheet.paste(framed, (x, y))
        draw.text((x, y + thumb_size[1] + 8), str(item["blind_id"]), fill=(235, 235, 235))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


def write_blind_eval_pack(
    summary_path: str | Path,
    tasks_dir: str | Path,
    out_dir: str | Path,
    resolver: WorkspaceResolver,
    *,
    seed: int = 20260603,
    human_review_path: str | Path | None = None,
    require_human_signoff: bool = False,
) -> dict[str, Any]:
    summary_path = Path(summary_path).resolve()
    out = resolver.ensure_dir(out_dir)
    manifest, mapping = build_blind_eval(
        load_summary(summary_path),
        load_tasks(tasks_dir),
        source=summary_path,
        seed=seed,
        human_review=_load_human_review(human_review_path),
        require_human_signoff=require_human_signoff,
    )
    preview_dir = resolver.ensure_dir(out / "blind_previews")
    private_by_id = {entry["blind_id"]: entry for entry in mapping["mapping"]}
    for item in manifest["items"]:
        original_preview = item.get("preview")
        if not original_preview or not Path(original_preview).is_file():
            continue
        blind_preview = preview_dir / f"{item['blind_id']}.png"
        resolver.write_bytes(blind_preview, Path(original_preview).read_bytes())
        item["preview"] = str(blind_preview)
        private_by_id[str(item["blind_id"])]["blind_preview"] = str(blind_preview)
    manifest_path = resolver.write_text(out / "blind_visual_eval.json", json.dumps(manifest, indent=2))
    mapping_path = resolver.write_text(out / "private_mapping.json", json.dumps(mapping, indent=2))
    markdown_path = resolver.write_text(out / "blind_visual_eval.md", render_markdown(manifest, out))
    sheet_path = resolver.write_bytes(out / "blind_contact_sheet.png", make_contact_sheet(manifest))
    template_path = resolver.write_text(
        out / "blind_review_template.json",
        json.dumps(blind_review_template(manifest), indent=2),
    )
    manifest["artifacts"] = {
        "manifest": str(manifest_path),
        "markdown": str(markdown_path),
        "contact_sheet": str(sheet_path),
        "review_template": str(template_path),
        "private_mapping": str(mapping_path),
    }
    return manifest
