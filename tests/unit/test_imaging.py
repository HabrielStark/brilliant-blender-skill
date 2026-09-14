"""Unit tests for image sanity metrics + SSIM (SRS 15.2, 15.3)."""
import numpy as np
import pytest
from PIL import Image

from blender_cinematic.imaging import (
    frame_visual_delta,
    image_sanity,
    images_identical,
    palette_from_names,
    palette_similarity,
    part_readability,
    reference_fidelity_metrics,
    render_sanity_issues,
    salient_palette,
    ssim,
    subject_readability_report,
)


@pytest.fixture
def black(tmp_path):
    p = tmp_path / "black.png"
    Image.new("RGBA", (96, 96), (0, 0, 0, 255)).save(p)
    return p


@pytest.fixture
def structured(tmp_path):
    arr = np.zeros((96, 96, 3), dtype=np.uint8)
    arr[:, :, 2] = np.linspace(10, 120, 96).astype(np.uint8)[None, :]
    arr[30:70, 30:70] = [200, 200, 210]
    arr[34:44, 34:66] = [30, 30, 30]
    p = tmp_path / "good.png"
    Image.fromarray(arr).save(p)
    return p


def test_black_is_hard_fail(black):
    issues = render_sanity_issues(image_sanity(black))
    assert "render is almost entirely black" in issues


def test_structured_is_clean(structured):
    assert render_sanity_issues(image_sanity(structured)) == []


def test_flat_low_detail_render_is_rejected(tmp_path):
    arr = np.full((96, 96, 3), 126, dtype=np.uint8)
    arr[32:64, 32:64] = [138, 138, 138]
    p = tmp_path / "flat_low_detail.png"
    Image.fromarray(arr).save(p)

    issues = render_sanity_issues(image_sanity(p))

    assert "render has no discernible silhouette/detail" in issues
    assert "render is too flat for visual acceptance" in issues


def test_dark_low_detail_render_is_rejected(tmp_path):
    arr = np.full((96, 96, 3), 5, dtype=np.uint8)
    arr[28:68, 28:68] = [24, 26, 30]
    p = tmp_path / "dark_low_detail.png"
    Image.fromarray(arr).save(p)

    issues = render_sanity_issues(image_sanity(p))

    assert "dark render lacks readable subject detail" in issues


def test_white_blowout(tmp_path):
    p = tmp_path / "white.png"
    Image.new("RGBA", (64, 64), (255, 255, 255, 255)).save(p)
    assert any("white" in i for i in render_sanity_issues(image_sanity(p)))


def test_ssim_self_is_one(structured):
    assert ssim(structured, structured) > 0.99


def test_ssim_differs(structured, black):
    assert ssim(structured, black) < 0.8


def test_images_identical(structured, black):
    assert images_identical(structured, structured)
    assert not images_identical(structured, black)


def test_frame_visual_delta_detects_visible_motion(structured, black):
    delta_same = frame_visual_delta(structured, structured)
    delta_diff = frame_visual_delta(structured, black)

    assert delta_same["mean_rgb_delta"] == 0.0
    assert delta_same["changed_pixel_ratio"] == 0.0
    assert delta_diff["mean_rgb_delta"] > 0.05
    assert delta_diff["changed_pixel_ratio"] > 0.1


def test_reference_fidelity_metrics_reward_aligned_structure(tmp_path):
    reference = tmp_path / "reference.png"
    aligned = tmp_path / "aligned.png"
    shifted = tmp_path / "shifted.png"

    ref = np.zeros((96, 96, 3), dtype=np.uint8)
    ref[34:62, 22:74] = [210, 220, 240]
    ref[45:49, 28:68] = [40, 90, 255]
    Image.fromarray(ref).save(reference)

    same = ref.copy()
    same[36:39, 30:66] = [235, 240, 255]
    Image.fromarray(same).save(aligned)

    off = np.zeros((96, 96, 3), dtype=np.uint8)
    off[18:46, 44:92] = [210, 220, 240]
    off[28:32, 50:88] = [40, 90, 255]
    Image.fromarray(off).save(shifted)

    aligned_metrics = reference_fidelity_metrics(aligned, reference)
    shifted_metrics = reference_fidelity_metrics(shifted, reference)

    assert aligned_metrics["saliency_iou"] > shifted_metrics["saliency_iou"]
    assert aligned_metrics["edge_iou"] > shifted_metrics["edge_iou"]
    assert aligned_metrics["saliency_center_delta"] < shifted_metrics["saliency_center_delta"]


def test_metrics_fields(structured):
    m = image_sanity(structured)
    for key in ("width", "height", "mean_brightness", "contrast",
                "pct_near_black", "pct_near_white", "edge_density"):
        assert key in m


def test_named_palette_similarity_accepts_reference_palette():
    expected = palette_from_names(["black", "cold blue", "white highlights"])
    actual = [[5, 6, 9], [72, 118, 250], [240, 242, 255]]
    assert palette_similarity(actual, expected) > 0.95


def test_named_palette_similarity_rejects_wrong_palette():
    expected = palette_from_names(["black", "cold blue", "white highlights"])
    actual = [[220, 20, 20], [30, 180, 60], [120, 80, 20]]
    assert palette_similarity(actual, expected) < 0.55


def test_named_palette_supports_warm_and_aurora_benchmarks():
    assert palette_from_names(["teal", "magenta", "gold", "warm ivory", "sage green", "brass"])


def test_salient_palette_keeps_small_highlights(tmp_path):
    arr = np.zeros((96, 96, 3), dtype=np.uint8)
    arr[:] = [2, 3, 6]
    arr[8:10, 8:70] = [235, 240, 255]
    arr[20:24, 70:86] = [40, 90, 255]
    p = tmp_path / "salient.png"
    Image.fromarray(arr).save(p)
    expected = palette_from_names(["black", "cold blue", "white highlights"])
    assert palette_similarity(salient_palette(p), expected) > 0.8


def test_part_readability_bright_part_on_dark_bg(tmp_path):
    arr = np.zeros((96, 96, 3), dtype=np.uint8)
    arr[:] = [4, 5, 8]
    arr[30:70, 30:70] = [200, 205, 215]
    p = tmp_path / "part.png"
    Image.fromarray(arr).save(p)
    # Camera space is y-up: image rows 30..70 -> cam y 0.27..0.69
    m = part_readability(p, [0.3, 0.27, 0.72, 0.69])
    assert m is not None and m["readable"]
    assert m["separation"] > 0.4


def test_part_readability_dark_on_dark_fails(tmp_path):
    arr = np.zeros((96, 96, 3), dtype=np.uint8)
    arr[:] = [5, 6, 9]
    arr[30:70, 30:70] = [7, 8, 11]
    p = tmp_path / "dark_part.png"
    Image.fromarray(arr).save(p)
    m = part_readability(p, [0.3, 0.27, 0.72, 0.69])
    assert m is not None and not m["readable"]


def test_part_readability_bad_bbox_skipped(tmp_path):
    arr = np.zeros((96, 96, 3), dtype=np.uint8)
    p = tmp_path / "img.png"
    Image.fromarray(arr).save(p)
    assert part_readability(p, None) is None
    assert part_readability(p, [0.1, 0.1]) is None
    # Degenerate / inverted box smaller than min_side_px
    assert part_readability(p, [0.5, 0.5, 0.5001, 0.5001]) is None


def test_subject_readability_report_filters_and_counts(tmp_path):
    arr = np.zeros((96, 96, 3), dtype=np.uint8)
    arr[:] = [4, 5, 8]
    arr[30:70, 30:70] = [210, 215, 225]
    p = tmp_path / "scene.png"
    Image.fromarray(arr).save(p)
    objects = [
        {"name": "hero_body", "collection": "SUBJECT", "in_camera_frame": True,
         "screen_bbox": [0.3, 0.27, 0.72, 0.69], "screen_coverage": 0.18},
        {"name": "hidden_trim", "collection": "SUBJECT", "in_camera_frame": True,
         "screen_bbox": [0.05, 0.05, 0.15, 0.15], "screen_coverage": 0.01},
        {"name": "floor", "collection": "ENVIRONMENT", "in_camera_frame": True,
         "screen_bbox": [0.0, 0.0, 1.0, 1.0], "screen_coverage": 0.9},
        {"name": "offscreen_bit", "collection": "SUBJECT", "in_camera_frame": False,
         "screen_bbox": [0.8, 0.8, 0.95, 0.95], "screen_coverage": 0.01},
    ]
    rep = subject_readability_report(p, objects)
    names = [pt["name"] for pt in rep["parts"]]
    assert "hero_body" in names and "hidden_trim" in names
    assert "floor" not in names and "offscreen_bit" not in names
    assert rep["unreadable_parts"] == ["hidden_trim"]
    # part_names restricts measurement to matching substrings
    rep2 = subject_readability_report(p, objects, part_names=["hero"])
    assert [pt["name"] for pt in rep2["parts"]] == ["hero_body"]
