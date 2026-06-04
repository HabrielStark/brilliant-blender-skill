#!/usr/bin/env python
"""Assert that visual benchmark acceptance is reviewed, not evidence-only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise AssertionError(f"missing visual acceptance artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _review_count(review: dict[str, Any] | None) -> int:
    reviews = (review or {}).get("reviews")
    return len(reviews) if isinstance(reviews, list) else 0


def _assert_reviewed_manifest(
    path: Path,
    *,
    label: str,
    schema: str,
    require_embedded_human_review: bool,
) -> None:
    manifest = _load_json(path)
    if manifest.get("schema") != schema:
        raise AssertionError(f"{label} has wrong schema: {manifest.get('schema')!r}")
    if manifest.get("status") != "PASS":
        failures = manifest.get("failures") or []
        raise AssertionError(f"{label} status is not PASS: {failures}")
    if manifest.get("human_review_required") is not True:
        raise AssertionError(f"{label} is evidence-only: human_review_required is not true")
    if manifest.get("failures"):
        raise AssertionError(f"{label} contains failures: {manifest['failures']}")
    task_count = int(manifest.get("task_count", 0) or 0)
    if task_count <= 0:
        raise AssertionError(f"{label} has no reviewed tasks/items")
    human_review = manifest.get("human_review")
    if require_embedded_human_review:
        if not isinstance(human_review, dict):
            raise AssertionError(f"{label} is missing embedded human_review proof")
        if _review_count(human_review) < task_count:
            raise AssertionError(
                f"{label} has too few embedded reviews: {_review_count(human_review)} < {task_count}"
            )


def assert_visual_acceptance(visual_review: Path, blind_eval: Path) -> None:
    _assert_reviewed_manifest(
        visual_review,
        label="visual review pack",
        schema="visual_review_pack/0.1",
        require_embedded_human_review=True,
    )
    _assert_reviewed_manifest(
        blind_eval,
        label="blind visual eval",
        schema="blind_visual_eval/0.1",
        require_embedded_human_review=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--visual-review",
        required=True,
        help="path to reviewed visual_review_pack.json",
    )
    parser.add_argument(
        "--blind-eval",
        required=True,
        help="path to reviewed blind_visual_eval.json",
    )
    args = parser.parse_args(argv)
    assert_visual_acceptance(
        (ROOT / args.visual_review).resolve() if not Path(args.visual_review).is_absolute() else Path(args.visual_review),
        (ROOT / args.blind_eval).resolve() if not Path(args.blind_eval).is_absolute() else Path(args.blind_eval),
    )
    print("VISUAL ACCEPTANCE ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
