"""Visual benchmark review-pack generation.

This module turns benchmark JSON into human-reviewable evidence: a verdict,
score deltas against the naive baseline, preview links, and a contact sheet.
It deliberately stays pure Python and does not import ``bpy``.
"""
from __future__ import annotations

import io
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageStat

from .imaging import image_sanity
from .workspace import WorkspaceResolver


def load_summary(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _first_artifact(result: dict[str, Any], suffixes: tuple[str, ...]) -> str | None:
    for artifact in result.get("artifacts") or []:
        if isinstance(artifact, str) and artifact.lower().endswith(suffixes):
            return artifact
    return None


def flatten_summary(summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for entry in summary:
        skill = entry.get("skill_plus_tools") or {}
        baseline = entry.get("baseline_no_skill") or {}
        adversarial = {k: v for k, v in entry.items() if str(k).startswith("adversarial_slop_")}
        task_id = skill.get("task_id") or baseline.get("task_id")
        skill_score = skill.get("visual_score")
        baseline_score = baseline.get("visual_score")
        delta = None
        if isinstance(skill_score, (int, float)) and isinstance(baseline_score, (int, float)):
            delta = float(skill_score) - float(baseline_score)
        rows.append({
            "task_id": task_id,
            "skill_pass": bool(skill.get("pass")),
            "skill_score": skill_score,
            "skill_preview": _first_artifact(skill, (".png", ".jpg", ".jpeg")),
            "skill_glb": _first_artifact(skill, (".glb", ".gltf")),
            "skill_failures": skill.get("failures") or [],
            "baseline_present": bool(baseline),
            "baseline_pass": bool(baseline.get("pass")) if baseline else None,
            "baseline_score": baseline_score,
            "baseline_preview": _first_artifact(baseline, (".png", ".jpg", ".jpeg")),
            "baseline_failures": baseline.get("failures") or [],
            "score_delta": delta,
            "adversarial_modes": [
                {
                    "mode": mode,
                    "pass": bool(result.get("pass")),
                    "score": result.get("visual_score"),
                    "failures": result.get("failures") or [],
                    "preview": _first_artifact(result, (".png", ".jpg", ".jpeg")),
                }
                for mode, result in sorted(adversarial.items())
            ],
        })
    return rows


def _style_tags_for_preview(path: str | None) -> list[str]:
    if not path or not Path(path).is_file():
        return ["missing_preview"]
    try:
        with Image.open(path) as im:
            rgb = im.convert("RGB").resize((64, 64))
            stat = ImageStat.Stat(rgb)
            mean = [v / 255.0 for v in stat.mean[:3]]
            brightness = sum(mean) / 3.0
            blue_bias = mean[2] - ((mean[0] + mean[1]) / 2.0)
            red_bias = mean[0] - ((mean[1] + mean[2]) / 2.0)
    except OSError:
        return ["unreadable_preview"]

    tags = []
    if brightness < 0.18:
        tags.append("very_dark")
    elif brightness < 0.32:
        tags.append("dark")
    elif brightness > 0.72:
        tags.append("bright")
    if blue_bias > 0.04:
        tags.append("blue_cyan_bias")
    if red_bias > 0.04:
        tags.append("warm_red_bias")
    if ("very_dark" in tags or "dark" in tags) and "blue_cyan_bias" in tags:
        tags.append("dark_blue_cyan")
    return tags or ["neutral"]


def style_tags_for_preview(path: str | None) -> list[str]:
    return _style_tags_for_preview(path)


def _artist_quality_for_preview(
    path: str | None,
    *,
    min_artist_contrast: float,
    min_artist_edge_density: float,
    max_preview_near_black_fraction: float,
    max_preview_near_white_fraction: float,
) -> tuple[dict[str, Any], list[str]]:
    if not path or not Path(path).is_file():
        return {}, ["preview missing for artist-quality analysis"]
    try:
        metrics = image_sanity(path)
    except OSError:
        return {}, ["preview unreadable for artist-quality analysis"]

    failures: list[str] = []
    if float(metrics.get("contrast", 0.0)) < min_artist_contrast:
        failures.append(
            f"preview contrast {metrics.get('contrast', 0.0):.4f} < min {min_artist_contrast:.4f}"
        )
    if float(metrics.get("edge_density", 0.0)) < min_artist_edge_density:
        failures.append(
            "preview edge/detail density "
            f"{metrics.get('edge_density', 0.0):.4f} < min {min_artist_edge_density:.4f}"
        )
    if float(metrics.get("pct_near_black", 0.0)) > max_preview_near_black_fraction:
        failures.append(
            "preview near-black area "
            f"{metrics.get('pct_near_black', 0.0):.3f} > max {max_preview_near_black_fraction:.3f}"
        )
    if float(metrics.get("pct_near_white", 0.0)) > max_preview_near_white_fraction:
        failures.append(
            "preview near-white area "
            f"{metrics.get('pct_near_white', 0.0):.3f} > max {max_preview_near_white_fraction:.3f}"
        )
    return metrics, failures


def _load_human_review(path: str | Path | None) -> dict[str, Any] | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _human_review_failures(
    rows: list[dict[str, Any]],
    human_review: dict[str, Any] | None,
    *,
    require_human_signoff: bool,
) -> list[str]:
    if not require_human_signoff:
        return []
    if not human_review:
        return ["human visual review required but no human_review.json was provided"]
    reviews = human_review.get("reviews")
    if not isinstance(reviews, list):
        return ["human visual review must contain a reviews list"]
    by_task = {str(item.get("task_id")): item for item in reviews if isinstance(item, dict)}
    required_ratings = ("identity", "composition", "material_craft", "detail_read", "ship_readiness")
    failures: list[str] = []
    for row in rows:
        task = str(row.get("task_id") or "<unknown>")
        review = by_task.get(task)
        if not review:
            failures.append(f"{task}: missing human visual review")
            continue
        if review.get("approved") is not True:
            failures.append(f"{task}: human visual review not approved")
        ratings = review.get("ratings") if isinstance(review.get("ratings"), dict) else {}
        missing = [key for key in required_ratings if key not in ratings]
        if missing:
            failures.append(f"{task}: missing human review ratings: {', '.join(missing)}")
            continue
        weak = [key for key in required_ratings if float(ratings.get(key, 0) or 0) < 4.0]
        if weak:
            failures.append(f"{task}: human review ratings below 4/5: {', '.join(weak)}")
    return failures


def build_review_manifest(
    summary: list[dict[str, Any]],
    *,
    source: str | Path | None = None,
    min_score_delta: float = 40.0,
    require_baseline_fail: bool = True,
    require_skill_preview: bool = True,
    max_style_cluster_fraction: float = 0.62,
    min_style_cluster_tasks: int = 4,
    max_theme_family_fraction: float = 0.55,
    min_artist_contrast: float = 0.045,
    min_artist_edge_density: float = 0.006,
    max_preview_near_black_fraction: float = 0.92,
    max_preview_near_white_fraction: float = 0.92,
    human_review: dict[str, Any] | None = None,
    require_human_signoff: bool = False,
) -> dict[str, Any]:
    rows = flatten_summary(summary)
    failures: list[str] = []
    style_clusters: dict[str, list[str]] = {}
    theme_families: dict[str, set[str]] = {
        "dark_family": set(),
        "blue_cyan_family": set(),
    }
    for row in rows:
        task = row.get("task_id") or "<unknown>"
        tags = _style_tags_for_preview(row.get("skill_preview"))
        row["visual_style_tags"] = tags
        artist_metrics, artist_failures = _artist_quality_for_preview(
            row.get("skill_preview"),
            min_artist_contrast=min_artist_contrast,
            min_artist_edge_density=min_artist_edge_density,
            max_preview_near_black_fraction=max_preview_near_black_fraction,
            max_preview_near_white_fraction=max_preview_near_white_fraction,
        )
        row["artist_quality_metrics"] = artist_metrics
        row["artist_quality_failures"] = artist_failures
        for failure in artist_failures:
            failures.append(f"{task}: {failure}")
        for tag in tags:
            style_clusters.setdefault(tag, []).append(str(task))
        if any(tag in tags for tag in ("dark", "very_dark", "dark_blue_cyan")):
            theme_families["dark_family"].add(str(task))
        if any(tag in tags for tag in ("blue_cyan_bias", "dark_blue_cyan")):
            theme_families["blue_cyan_family"].add(str(task))
        if not row["skill_pass"]:
            failures.append(f"{task}: skill_plus_tools failed")
        if require_skill_preview:
            preview = row.get("skill_preview")
            if not preview or not Path(preview).is_file():
                failures.append(f"{task}: skill preview missing")
        if require_baseline_fail and row["baseline_present"] and row["baseline_pass"]:
            failures.append(f"{task}: baseline unexpectedly passed")
        if row["baseline_present"] and row["score_delta"] is not None:
            if row["score_delta"] < min_score_delta:
                failures.append(
                    f"{task}: score delta {row['score_delta']:.1f} < min {min_score_delta:.1f}"
                )
        for adversarial in row.get("adversarial_modes") or []:
            if adversarial.get("pass"):
                failures.append(f"{task}: adversarial baseline {adversarial.get('mode')} unexpectedly passed")
    if rows and max_style_cluster_fraction > 0:
        task_count = len(rows)
        for tag, tasks in sorted(style_clusters.items()):
            if tag in {"neutral", "dark", "blue_cyan_bias", "missing_preview", "unreadable_preview"}:
                continue
            fraction = len(tasks) / task_count
            if len(tasks) >= min_style_cluster_tasks and fraction > max_style_cluster_fraction:
                failures.append(
                    f"style collapse: {tag} appears in {len(tasks)}/{task_count} previews "
                    f"(max {max_style_cluster_fraction:.2f}): {', '.join(tasks)}"
                )
        if max_theme_family_fraction > 0:
            for family, tasks_set in sorted(theme_families.items()):
                tasks = sorted(tasks_set)
                fraction = len(tasks) / task_count
                if len(tasks) >= min_style_cluster_tasks and fraction > max_theme_family_fraction:
                    failures.append(
                        f"style family collapse: {family} appears in {len(tasks)}/{task_count} previews "
                        f"(max {max_theme_family_fraction:.2f}): {', '.join(tasks)}"
                    )
    failures.extend(
        _human_review_failures(
            rows,
            human_review,
            require_human_signoff=require_human_signoff,
        )
    )
    pass_count = sum(1 for row in rows if row["skill_pass"])
    baseline_fail_count = sum(
        1 for row in rows if row["baseline_present"] and row["baseline_pass"] is False
    )
    adversarial_count = sum(len(row.get("adversarial_modes") or []) for row in rows)
    adversarial_fail_count = sum(
        1
        for row in rows
        for adversarial in (row.get("adversarial_modes") or [])
        if adversarial.get("pass") is False
    )
    return {
        "schema": "visual_review_pack/0.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(source) if source else None,
        "status": "PASS" if rows and not failures else "FAIL",
        "task_count": len(rows),
        "skill_pass_count": pass_count,
        "baseline_fail_count": baseline_fail_count,
        "adversarial_count": adversarial_count,
        "adversarial_fail_count": adversarial_fail_count,
        "min_score_delta": min_score_delta,
        "max_style_cluster_fraction": max_style_cluster_fraction,
        "min_style_cluster_tasks": min_style_cluster_tasks,
        "max_theme_family_fraction": max_theme_family_fraction,
        "min_artist_contrast": min_artist_contrast,
        "min_artist_edge_density": min_artist_edge_density,
        "max_preview_near_black_fraction": max_preview_near_black_fraction,
        "max_preview_near_white_fraction": max_preview_near_white_fraction,
        "theme_families": {k: sorted(v) for k, v in theme_families.items()},
        "style_clusters": style_clusters,
        "human_review_required": require_human_signoff,
        "human_review": human_review,
        "failures": failures,
        "rows": rows,
    }


def _markdown_path(path: str | None, base: Path) -> str:
    if not path:
        return ""
    try:
        rel = os.path.relpath(Path(path), start=base)
    except ValueError:
        rel = str(path)
    return rel.replace("\\", "/")


def render_markdown(manifest: dict[str, Any], out_dir: str | Path) -> str:
    out = Path(out_dir)
    lines = [
        "# Visual Benchmark Review Pack",
        "",
        f"- Status: {manifest['status']}",
        f"- Tasks: {manifest['skill_pass_count']}/{manifest['task_count']} skill PASS",
        f"- Baseline contrast: {manifest['baseline_fail_count']} baseline FAIL",
        f"- Adversarial contrast: {manifest['adversarial_fail_count']}/{manifest['adversarial_count']} adversarial FAIL",
        f"- Minimum score delta: {manifest['min_score_delta']}",
        f"- Max repeated style cluster fraction: {manifest['max_style_cluster_fraction']}",
        f"- Minimum preview contrast: {manifest['min_artist_contrast']}",
        f"- Minimum preview edge/detail density: {manifest['min_artist_edge_density']}",
        f"- Human signoff required: {manifest['human_review_required']}",
        f"- Generated: {manifest['generated_at']}",
        "",
        "## Required Human Review",
        "",
        "Open `contact_sheet.png` and inspect every preview. A PASS here means the",
        "structured skill beat the naive baseline and satisfied measurable visual gates;",
        "it does not replace human taste review for new scene families.",
        "",
    ]
    if manifest["failures"]:
        lines += ["## Failures", ""]
        lines += [f"- {failure}" for failure in manifest["failures"]]
        lines.append("")
    lines += [
        "## Score Table",
        "",
        "| Task | Skill | Baseline | Delta | Preview | Artist metrics | Skill failures | Baseline failures |",
        "|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in manifest["rows"]:
        preview = _markdown_path(row.get("skill_preview"), out)
        preview_link = f"[preview]({preview})" if preview else "missing"
        skill = f"{'PASS' if row['skill_pass'] else 'FAIL'} {row.get('skill_score')}"
        if row["baseline_present"]:
            baseline = f"{'PASS' if row['baseline_pass'] else 'FAIL'} {row.get('baseline_score')}"
        else:
            baseline = "missing"
        delta = "" if row.get("score_delta") is None else f"{row['score_delta']:.1f}"
        sf = "<br>".join(row.get("skill_failures") or ["none"])
        bf = "<br>".join(row.get("baseline_failures") or ["none"])
        tags = ", ".join(row.get("visual_style_tags") or [])
        metrics = row.get("artist_quality_metrics") or {}
        artist = (
            "missing"
            if not metrics
            else (
                f"contrast {float(metrics.get('contrast', 0.0)):.3f}<br>"
                f"edge {float(metrics.get('edge_density', 0.0)):.3f}<br>"
                f"black {float(metrics.get('pct_near_black', 0.0)):.3f}"
            )
        )
        artist_failures = row.get("artist_quality_failures") or []
        if artist_failures:
            artist += "<br>FAIL: " + "<br>".join(artist_failures)
        lines.append(
            f"| {row.get('task_id')} | {skill}<br>{tags} | {baseline} | {delta} | {preview_link} | {artist} | {sf} | {bf} |"
        )
    lines += ["", "## Preview Contact Sheet", "", "![contact sheet](contact_sheet.png)", ""]
    for row in manifest["rows"]:
        preview = _markdown_path(row.get("skill_preview"), out)
        if preview:
            lines += [f"### {row.get('task_id')}", "", f"![{row.get('task_id')}]({preview})", ""]
    return "\n".join(lines)


def _placeholder(size: tuple[int, int], label: str) -> Image.Image:
    img = Image.new("RGB", size, (24, 24, 26))
    draw = ImageDraw.Draw(img)
    draw.text((12, size[1] // 2 - 8), label[:80], fill=(230, 230, 230))
    return img


def make_contact_sheet(
    manifest: dict[str, Any],
    *,
    thumb_size: tuple[int, int] = (320, 180),
    columns: int = 2,
) -> bytes:
    rows = manifest["rows"]
    label_h = 42
    pad = 16
    columns = max(1, columns)
    cell_w = thumb_size[0]
    cell_h = thumb_size[1] + label_h
    sheet_w = columns * cell_w + (columns + 1) * pad
    sheet_rows = max(1, math.ceil(len(rows) / columns))
    sheet_h = sheet_rows * cell_h + (sheet_rows + 1) * pad
    sheet = Image.new("RGB", (sheet_w, sheet_h), (12, 12, 14))
    draw = ImageDraw.Draw(sheet)
    for idx, row in enumerate(rows):
        x = pad + (idx % columns) * (cell_w + pad)
        y = pad + (idx // columns) * (cell_h + pad)
        preview = row.get("skill_preview")
        if preview and Path(preview).is_file():
            with Image.open(preview) as im:
                tile = im.convert("RGB")
                tile.thumbnail(thumb_size, Image.Resampling.LANCZOS)
                framed = Image.new("RGB", thumb_size, (0, 0, 0))
                ox = (thumb_size[0] - tile.width) // 2
                oy = (thumb_size[1] - tile.height) // 2
                framed.paste(tile, (ox, oy))
        else:
            framed = _placeholder(thumb_size, "missing preview")
        sheet.paste(framed, (x, y))
        status = "PASS" if row["skill_pass"] else "FAIL"
        score = row.get("skill_score")
        delta = row.get("score_delta")
        delta_text = "" if delta is None else f" delta {delta:.1f}"
        label = f"{row.get('task_id')} | {status} {score}{delta_text}"
        draw.text((x, y + thumb_size[1] + 8), label[:95], fill=(235, 235, 235))
    buf = io.BytesIO()
    sheet.save(buf, format="PNG")
    return buf.getvalue()


def human_review_template(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "human_visual_review/0.1",
        "reviewer": "",
        "generated_from": manifest.get("source"),
        "reviews": [
            {
                "task_id": row.get("task_id"),
                "approved": False,
                "ratings": {
                    "identity": 0,
                    "composition": 0,
                    "material_craft": 0,
                    "detail_read": 0,
                    "ship_readiness": 0,
                },
                "defects": [],
                "notes": "",
            }
            for row in manifest.get("rows", [])
        ],
    }


def write_review_pack(
    summary_path: str | Path,
    out_dir: str | Path,
    resolver: WorkspaceResolver,
    *,
    min_score_delta: float = 40.0,
    human_review_path: str | Path | None = None,
    require_human_signoff: bool = False,
) -> dict[str, Any]:
    summary_path = Path(summary_path).resolve()
    out = resolver.ensure_dir(out_dir)
    manifest = build_review_manifest(
        load_summary(summary_path),
        source=summary_path,
        min_score_delta=min_score_delta,
        human_review=_load_human_review(human_review_path),
        require_human_signoff=require_human_signoff,
    )
    markdown = render_markdown(manifest, out)
    manifest_path = resolver.write_text(out / "visual_review_pack.json", json.dumps(manifest, indent=2))
    markdown_path = resolver.write_text(out / "visual_review_pack.md", markdown)
    sheet_path = resolver.write_bytes(out / "contact_sheet.png", make_contact_sheet(manifest))
    human_template_path = resolver.write_text(
        out / "human_review_template.json",
        json.dumps(human_review_template(manifest), indent=2),
    )
    manifest["artifacts"] = {
        "manifest": str(manifest_path),
        "markdown": str(markdown_path),
        "contact_sheet": str(sheet_path),
        "human_review_template": str(human_template_path),
    }
    return manifest
