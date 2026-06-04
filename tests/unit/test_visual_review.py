import json

from PIL import Image

from blender_cinematic.visual_review import (
    build_review_manifest,
    flatten_summary,
    write_review_pack,
)
from blender_cinematic.workspace import WorkspaceResolver


def _png(path, color=(20, 40, 80)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), color).save(path)


def _structured_png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (96, 54), (92, 102, 112))
    px = img.load()
    for y in range(54):
        for x in range(96):
            if 18 < x < 76 and 10 < y < 44:
                shade = 150 + ((x + y) % 30)
                px[x, y] = (shade, shade + 8, min(255, shade + 18))
            if x in (18, 76) or y in (10, 44):
                px[x, y] = (18, 24, 30)
            if 35 < x < 70 and 24 < y < 30:
                px[x, y] = (230, 232, 220)
            if (x + y) % 17 == 0 and 20 < x < 78 and 12 < y < 42:
                px[x, y] = (28, 36, 48)
    img.save(path)


def _result(task_id, passed, score, artifacts, failures=None):
    result = {
        "task_id": task_id,
        "visual_score": score,
        "artifacts": artifacts,
    }
    result["pass"] = passed
    if failures is not None:
        result["failures"] = failures
    return result


def test_visual_review_manifest_requires_skill_pass_preview_and_delta(tmp_path):
    preview = tmp_path / "skill.png"
    _structured_png(preview)
    summary = [{
        "skill_plus_tools": _result("hero", True, 91, [str(preview)], []),
        "baseline_no_skill": _result("hero", False, 31, [None], ["no active camera"]),
    }]

    manifest = build_review_manifest(summary, min_score_delta=40)

    assert manifest["status"] == "PASS"
    assert manifest["skill_pass_count"] == 1
    assert flatten_summary(summary)[0]["score_delta"] == 60


def test_visual_review_manifest_fails_weak_delta(tmp_path):
    preview = tmp_path / "skill.png"
    _png(preview)
    summary = [{
        "skill_plus_tools": _result("hero", True, 70, [str(preview)]),
        "baseline_no_skill": _result("hero", False, 45, [None]),
    }]

    manifest = build_review_manifest(summary, min_score_delta=40)

    assert manifest["status"] == "FAIL"
    assert any("score delta" in failure for failure in manifest["failures"])


def test_write_review_pack_writes_markdown_json_and_contact_sheet(tmp_path):
    preview = tmp_path / "artifacts" / "hero" / "iterations" / "iter_01_preview.png"
    _structured_png(preview)
    summary = [{
        "skill_plus_tools": _result("hero", True, 92, [str(preview)], []),
        "baseline_no_skill": _result("hero", False, 20, [None], ["no active camera"]),
    }]
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    resolver = WorkspaceResolver([tmp_path])

    manifest = write_review_pack(summary_path, tmp_path / "review", resolver)

    assert manifest["status"] == "PASS"
    assert (tmp_path / "review" / "visual_review_pack.md").is_file()
    assert (tmp_path / "review" / "visual_review_pack.json").is_file()
    assert (tmp_path / "review" / "contact_sheet.png").is_file()


def test_visual_review_manifest_fails_repeated_dark_blue_style_cluster(tmp_path):
    rows = []
    for idx in range(4):
        preview = tmp_path / f"skill_{idx}.png"
        _png(preview, (8, 16, 42))
        rows.append({
            "skill_plus_tools": _result(f"task_{idx}", True, 92, [str(preview)], []),
            "baseline_no_skill": _result(f"task_{idx}", False, 20, [None], ["baseline weak"]),
        })

    manifest = build_review_manifest(rows, max_style_cluster_fraction=0.5)

    assert manifest["status"] == "FAIL"
    assert any("style collapse: dark_blue_cyan" in failure for failure in manifest["failures"])
    assert "dark_blue_cyan" in manifest["rows"][0]["visual_style_tags"]


def test_visual_review_manifest_fails_repeated_dark_family_even_without_cyan(tmp_path):
    rows = []
    colors = [(22, 20, 18), (30, 24, 20), (38, 35, 31), (42, 38, 32), (220, 210, 190)]
    for idx, color in enumerate(colors):
        preview = tmp_path / f"skill_{idx}.png"
        _png(preview, color)
        rows.append({
            "skill_plus_tools": _result(f"task_{idx}", True, 92, [str(preview)], []),
            "baseline_no_skill": _result(f"task_{idx}", False, 20, [None], ["baseline weak"]),
        })

    manifest = build_review_manifest(rows, max_theme_family_fraction=0.5)

    assert manifest["status"] == "FAIL"
    assert any("style family collapse: dark_family" in failure for failure in manifest["failures"])


def test_visual_review_manifest_can_require_human_signoff(tmp_path):
    preview = tmp_path / "skill.png"
    _structured_png(preview)
    summary = [{
        "skill_plus_tools": _result("hero", True, 92, [str(preview)], []),
        "baseline_no_skill": _result("hero", False, 20, [None], ["no active camera"]),
    }]

    missing = build_review_manifest(summary, require_human_signoff=True)

    assert missing["status"] == "FAIL"
    assert any("human visual review required" in failure for failure in missing["failures"])

    approved = build_review_manifest(
        summary,
        require_human_signoff=True,
        human_review={
            "schema": "human_visual_review/0.1",
            "reviewer": "test",
            "reviews": [{
                "task_id": "hero",
                "approved": True,
                "ratings": {
                    "identity": 4,
                    "composition": 5,
                    "material_craft": 4,
                    "detail_read": 4,
                    "ship_readiness": 4,
                },
                "defects": [],
            }],
        },
    )

    assert approved["status"] == "PASS"


def test_visual_review_manifest_fails_flat_low_detail_preview(tmp_path):
    preview = tmp_path / "flat.png"
    _png(preview, (90, 92, 94))
    summary = [{
        "skill_plus_tools": _result("flat_hero", True, 96, [str(preview)], []),
        "baseline_no_skill": _result("flat_hero", False, 20, [None], ["baseline weak"]),
    }]

    manifest = build_review_manifest(summary)

    assert manifest["status"] == "FAIL"
    assert any("preview contrast" in failure for failure in manifest["failures"])
    assert any("preview edge/detail density" in failure for failure in manifest["failures"])


def test_visual_review_manifest_fails_passing_adversarial_baseline(tmp_path):
    preview = tmp_path / "skill.png"
    _png(preview, (80, 90, 100))
    summary = [{
        "skill_plus_tools": _result("hero", True, 92, [str(preview)], []),
        "baseline_no_skill": _result("hero", False, 20, [None], ["no active camera"]),
        "adversarial_slop_named_cubes": _result("hero", True, 88, [str(preview)], []),
    }]

    manifest = build_review_manifest(summary)

    assert manifest["status"] == "FAIL"
    assert manifest["adversarial_count"] == 1
    assert any("adversarial baseline" in failure for failure in manifest["failures"])
