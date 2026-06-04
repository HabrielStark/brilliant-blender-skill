import json

from PIL import Image

from blender_cinematic.blind_review import build_blind_eval, write_blind_eval_pack
from blender_cinematic.workspace import WorkspaceResolver


def _png(path, color=(60, 80, 110)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), color).save(path)


def _result(task_id, passed, score, artifacts):
    return {
        "task_id": task_id,
        "pass": passed,
        "visual_score": score,
        "artifacts": artifacts,
        "failures": [],
    }


def test_blind_eval_hides_task_ids_and_scores_from_public_items(tmp_path):
    preview = tmp_path / "preview.png"
    _png(preview)
    summary = [{
        "skill_plus_tools": _result("hero_task", True, 95, [str(preview)]),
        "baseline_no_skill": _result("hero_task", False, 22, [None]),
    }]
    tasks = {
        "hero_task": {
            "prompt": "Make a premium watch hero scene",
            "category": "product",
            "manifest": {"brief": "watch", "style": {"mood": "premium"}, "target": {"final_format": ["png"]}},
        }
    }

    manifest, mapping = build_blind_eval(summary, tasks, seed=7)

    assert manifest["status"] == "PASS"
    assert manifest["items"][0]["prompt"] == "Make a premium watch hero scene"
    assert "task_id" not in manifest["items"][0]
    assert "skill_score" not in manifest["items"][0]
    assert mapping["mapping"][0]["task_id"] == "hero_task"
    assert mapping["mapping"][0]["skill_score"] == 95


def test_blind_eval_requires_strong_human_signoff_when_enabled(tmp_path):
    preview = tmp_path / "preview.png"
    _png(preview)
    summary = [{
        "skill_plus_tools": _result("hero_task", True, 95, [str(preview)]),
        "baseline_no_skill": _result("hero_task", False, 22, [None]),
    }]
    tasks = {"hero_task": {"prompt": "Make a premium watch hero scene", "manifest": {}}}

    missing, _ = build_blind_eval(summary, tasks, seed=7, require_human_signoff=True)
    blind_id = missing["items"][0]["blind_id"]

    assert missing["status"] == "FAIL"
    assert any("required" in failure for failure in missing["failures"])

    approved, _ = build_blind_eval(
        summary,
        tasks,
        seed=7,
        require_human_signoff=True,
        human_review={
            "schema": "blind_visual_review/0.1",
            "reviewer": "test",
            "reviews": [{
                "blind_id": blind_id,
                "approved": True,
                "ratings": {
                    "prompt_fit": 4,
                    "visual_quality": 5,
                    "composition_camera": 4,
                    "material_lighting": 4,
                    "detail_precision": 4,
                    "anti_slop": 5,
                    "ship_readiness": 4,
                },
            }],
        },
    )

    assert approved["status"] == "PASS"


def test_write_blind_eval_pack_writes_public_packet_and_private_mapping(tmp_path):
    preview = tmp_path / "preview.png"
    _png(preview)
    summary = [{
        "skill_plus_tools": _result("hero_task", True, 95, [str(preview)]),
        "baseline_no_skill": _result("hero_task", False, 22, [None]),
    }]
    summary_path = tmp_path / "summary.json"
    summary_path.write_text(json.dumps(summary), encoding="utf-8")
    task_path = tmp_path / "tasks" / "hero_task.json"
    task_path.parent.mkdir()
    task_path.write_text(
        json.dumps({"prompt": "Make a premium watch hero scene", "manifest": {"brief": "watch"}}),
        encoding="utf-8",
    )
    resolver = WorkspaceResolver([tmp_path])

    manifest = write_blind_eval_pack(summary_path, task_path.parent, tmp_path / "blind", resolver)

    assert manifest["status"] == "PASS"
    assert (tmp_path / "blind" / "blind_visual_eval.md").is_file()
    public_json = json.loads((tmp_path / "blind" / "blind_visual_eval.json").read_text(encoding="utf-8"))
    private_json = json.loads((tmp_path / "blind" / "private_mapping.json").read_text(encoding="utf-8"))
    assert "task_id" not in public_json["items"][0]
    assert "hero_task" not in public_json["items"][0]["preview"]
    assert "blind_previews" in public_json["items"][0]["preview"]
    assert private_json["mapping"][0]["task_id"] == "hero_task"
    assert "blind_preview" in private_json["mapping"][0]
