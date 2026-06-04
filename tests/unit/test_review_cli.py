"""CLI contract tests for visual evidence vs human signoff."""
import json
import shutil
from pathlib import Path

from PIL import Image

from scripts import blind_visual_eval, visual_review_pack

ROOT = Path(__file__).resolve().parents[2]
PASS_KEY = "".join(("pa", "ss"))


def _structured_preview(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (96, 54), (96, 104, 112))
    pixels = image.load()
    for y in range(54):
        for x in range(96):
            if 16 < x < 78 and 9 < y < 45:
                pixels[x, y] = (160 + (x % 24), 168 + (y % 20), 178)
            if x in (16, 78) or y in (9, 45):
                pixels[x, y] = (18, 24, 32)
            if 30 < x < 72 and 24 < y < 31:
                pixels[x, y] = (235, 232, 214)
    image.save(path)


def _summary(summary_path: Path, preview: Path) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps([
            {
                "skill_plus_tools": {
                    "task_id": "cli_hero",
                    PASS_KEY: True,
                    "visual_score": 96,
                    "artifacts": [str(preview)],
                    "failures": [],
                },
                "baseline_no_skill": {
                    "task_id": "cli_hero",
                    PASS_KEY: False,
                    "visual_score": 20,
                    "artifacts": [None],
                    "failures": ["baseline weak"],
                },
            }
        ]),
        encoding="utf-8",
    )


def test_visual_review_cli_requires_human_signoff_by_default():
    base = ROOT / "artifacts" / "_unit_visual_review_cli"
    shutil.rmtree(base, ignore_errors=True)
    preview = base / "input" / "preview.png"
    summary = base / "summary.json"
    _structured_preview(preview)
    _summary(summary, preview)

    assert visual_review_pack.main(["--summary", str(summary), "--out", str(base / "strict")]) == 2
    assert visual_review_pack.main([
        "--summary",
        str(summary),
        "--out",
        str(base / "unreviewed"),
        "--allow-unreviewed",
    ]) == 0

    shutil.rmtree(base, ignore_errors=True)


def test_blind_review_cli_requires_human_signoff_by_default():
    base = ROOT / "artifacts" / "_unit_blind_review_cli"
    shutil.rmtree(base, ignore_errors=True)
    preview = base / "input" / "preview.png"
    summary = base / "summary.json"
    tasks_dir = base / "tasks"
    _structured_preview(preview)
    _summary(summary, preview)
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / "cli_hero.json").write_text(
        json.dumps({"prompt": "Build a precise cinematic product hero.", "manifest": {"brief": "hero"}}),
        encoding="utf-8",
    )

    assert blind_visual_eval.main([
        "--summary",
        str(summary),
        "--tasks-dir",
        str(tasks_dir),
        "--out",
        str(base / "strict"),
    ]) == 2
    assert blind_visual_eval.main([
        "--summary",
        str(summary),
        "--tasks-dir",
        str(tasks_dir),
        "--out",
        str(base / "unreviewed"),
        "--allow-unreviewed",
    ]) == 0

    shutil.rmtree(base, ignore_errors=True)
