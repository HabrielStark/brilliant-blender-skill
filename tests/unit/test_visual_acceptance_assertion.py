import json

import pytest

from scripts.assert_visual_acceptance import assert_visual_acceptance


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _review(count=1):
    return {
        "schema": "human_visual_review/0.1",
        "reviewer": "test",
        "reviews": [
            {
                "task_id": f"task_{idx}",
                "blind_id": f"BVR-{idx}",
                "approved": True,
                "ratings": {"ship_readiness": 4},
            }
            for idx in range(count)
        ],
    }


def test_visual_acceptance_assertion_requires_reviewed_passing_packs(tmp_path):
    visual = tmp_path / "visual_review_pack.json"
    blind = tmp_path / "blind_visual_eval.json"
    _write_json(
        visual,
        {
            "schema": "visual_review_pack/0.1",
            "status": "PASS",
            "task_count": 1,
            "human_review_required": True,
            "human_review": _review(),
            "failures": [],
        },
    )
    _write_json(
        blind,
        {
            "schema": "blind_visual_eval/0.1",
            "status": "PASS",
            "task_count": 1,
            "human_review_required": True,
            "human_review": _review(),
            "failures": [],
        },
    )

    assert_visual_acceptance(visual, blind)


def test_visual_acceptance_assertion_rejects_unreviewed_pass(tmp_path):
    visual = tmp_path / "visual_review_pack.json"
    blind = tmp_path / "blind_visual_eval.json"
    _write_json(
        visual,
        {
            "schema": "visual_review_pack/0.1",
            "status": "PASS",
            "task_count": 1,
            "human_review_required": False,
            "failures": [],
        },
    )
    _write_json(
        blind,
        {
            "schema": "blind_visual_eval/0.1",
            "status": "PASS",
            "task_count": 1,
            "human_review_required": True,
            "human_review": _review(),
            "failures": [],
        },
    )

    with pytest.raises(AssertionError, match="evidence-only"):
        assert_visual_acceptance(visual, blind)


def test_visual_acceptance_assertion_rejects_missing_embedded_review(tmp_path):
    visual = tmp_path / "visual_review_pack.json"
    blind = tmp_path / "blind_visual_eval.json"
    _write_json(
        visual,
        {
            "schema": "visual_review_pack/0.1",
            "status": "PASS",
            "task_count": 1,
            "human_review_required": True,
            "human_review": _review(),
            "failures": [],
        },
    )
    _write_json(
        blind,
        {
            "schema": "blind_visual_eval/0.1",
            "status": "PASS",
            "task_count": 1,
            "human_review_required": True,
            "failures": [],
        },
    )

    with pytest.raises(AssertionError, match="embedded human_review"):
        assert_visual_acceptance(visual, blind)
