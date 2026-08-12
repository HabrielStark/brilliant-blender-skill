"""Unit tests for the rubric/hard-fail evaluator and iteration manager (SRS 10, 15.5, 43.2)."""
from blender_cinematic.constants import REQUIRED_COLLECTIONS
from blender_cinematic.evaluation import IterationEval, score_iteration
from blender_cinematic.iteration import IterationManager
from blender_cinematic.linters import lint_scene


def _scene():
    return {
        "collections": list(REQUIRED_COLLECTIONS),
        "objects": [{"name": "watch_case", "type": "MESH", "collection": "SUBJECT",
                     "faces": 4200, "materials": ["brushed"], "scale": [1, 1, 1], "smooth": True,
                     "modifiers": [{"type": "BEVEL", "show_render": True}],
                     "in_camera_frame": True, "screen_coverage": 0.6}],
        "active_camera": {"name": "camera_hero", "lens_mm": 70, "dof": True,
                          "focus_target": "watch_case", "inside_geometry": False},
        "cameras": ["camera_hero"],
        "lights": [{"name": "key", "type": "AREA", "energy": 450, "color": [1, 1, 1]}],
        "materials": [{"name": "brushed", "metallic": 1.0, "roughness": 0.34,
                       "users": 1, "is_default": False}],
        "metadata": {"final_camera": "camera_hero"},
    }


GOOD_METRICS = {"mean_brightness": 0.3, "contrast": 0.2, "pct_near_black": 0.2,
                "pct_near_white": 0.05, "edge_density": 0.05, "file_size": 5000,
                "empty_alpha": False}


def test_good_scene_scores_pass():
    s = _scene()
    ev = score_iteration(1, s, lint_scene(s, {"output_mode": "still"}), GOOD_METRICS,
                         {"output_mode": "still", "style": {"mood": "premium"}},
                         budget={"quality_profile": "balanced", "budget_faces": 2_000_000})
    assert ev.scores["total"] >= 80
    assert not ev.hard_fail and ev.passed


def test_black_render_hard_fails():
    s = _scene()
    black = dict(GOOD_METRICS, mean_brightness=0.0, contrast=0.0,
                 pct_near_black=0.99, edge_density=0.0)
    ev = score_iteration(1, s, lint_scene(s, {"output_mode": "still"}), black, {"output_mode": "still"})
    assert ev.hard_fail and not ev.passed


def test_no_camera_hard_fails():
    s = _scene()
    s["active_camera"] = None
    s["cameras"] = []
    ev = score_iteration(1, s, lint_scene(s, {"output_mode": "still"}), GOOD_METRICS, {"output_mode": "still"})
    assert ev.hard_fail
    assert "no active camera" in ev.hard_fail_reasons


def test_camera_overcrop_hard_fails():
    s = _scene()
    s["objects"][0]["screen_coverage"] = 0.995
    ev = score_iteration(1, s, lint_scene(s, {"output_mode": "still"}), GOOD_METRICS, {"output_mode": "still"})
    assert ev.hard_fail
    assert "subject is cut off by camera frame" in ev.hard_fail_reasons


def test_any_lint_error_hard_fails_even_with_high_score():
    s = _scene()
    s["objects"][0]["flipped_normals"] = True
    ev = score_iteration(1, s, lint_scene(s, {"output_mode": "still"}), GOOD_METRICS, {"output_mode": "still"})
    assert ev.scores["total"] < 80
    assert ev.hard_fail
    assert not ev.passed
    assert "flipped/broken normals: watch_case" in ev.hard_fail_reasons


def test_reference_match_requires_real_reference_metrics():
    s = _scene()
    ev = score_iteration(
        1,
        s,
        lint_scene(s, {"output_mode": "reference_match", "references": ["reference.png"]}),
        GOOD_METRICS,
        {"output_mode": "reference_match", "references": ["reference.png"]},
    )

    assert ev.hard_fail
    assert "reference match requested but no reference metrics were provided" in ev.hard_fail_reasons


def test_iteration_manager_stops_on_pass():
    mgr = IterationManager(output_mode="still", min_iterations=1)
    mgr.record(IterationEval(1, False, {"total": 85}))
    cont, reason = mgr.should_continue()
    assert not cont and "passed" in reason


def test_iteration_manager_budget_per_mode():
    assert IterationManager(output_mode="still").max_iterations == 3
    assert IterationManager(output_mode="interactive_web").max_iterations == 10


def test_iteration_manager_stalls():
    mgr = IterationManager(output_mode="interactive_web", min_iterations=1, stall_limit=3)
    for i in range(5):
        mgr.record(IterationEval(i + 1, False, {"total": 50}))
    cont, reason = mgr.should_continue()
    assert not cont and "improvement" in reason


def test_iteration_summary_prefers_pass_over_higher_hard_fail():
    mgr = IterationManager(output_mode="scene_repair", min_iterations=1)
    mgr.record(IterationEval(1, True, {"total": 92}, hard_fail_reasons=["subject not visible"]))
    mgr.record(IterationEval(2, False, {"total": 72}))
    summary = mgr.summary()
    assert summary["passed"] is False
    assert summary["latest_iteration"] == 2
    assert summary["latest_passed"] is False
    assert summary["best_iteration"] == 2
    assert summary["best_score"] == 72


def test_iteration_manager_rejects_duplicate_or_decreasing_numbers():
    mgr = IterationManager()
    mgr.record(IterationEval(2, False, {"total": 50}))
    for number in (2, 1):
        try:
            mgr.record(IterationEval(number, False, {"total": 51}))
        except ValueError as exc:
            assert "must increase" in str(exc)
        else:
            raise AssertionError("non-increasing iteration was accepted")
