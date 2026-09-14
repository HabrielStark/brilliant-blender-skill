"""Image-sanity metrics and SSIM (SRS 15.2 / 15.3).

Requires Pillow + numpy (the ``imaging`` extra). SSIM uses scikit-image when
installed, otherwise a self-contained integral-image windowed implementation so
reference comparison works with no heavy/optional dependency and no network
download (SRS 15.3: "tests must pass without huge runtime download").
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image


def _load(path: str | Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(im.convert("RGBA"), dtype=np.float32) / 255.0


def _luma(rgb: np.ndarray) -> np.ndarray:
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def image_sanity(path: str | Path, near_black: float = 0.04, near_white: float = 0.96) -> dict:
    """Render-sanity metrics: brightness, contrast, black/white ratios, edges, alpha."""
    arr = _load(path)
    h, w = arr.shape[:2]
    rgb = arr[..., :3]
    alpha = arr[..., 3]
    luma = _luma(rgb)
    # Edge density via gradient magnitude (silhouette proxy).
    gy, gx = np.gradient(luma)
    grad = np.sqrt(gx ** 2 + gy ** 2)
    edge_density = float((grad > 0.08).mean())
    size = Path(path).stat().st_size if Path(path).exists() else 0
    return {
        "width": int(w),
        "height": int(h),
        "file_size": int(size),
        "mean_brightness": float(luma.mean()),
        "contrast": float(luma.std()),
        "pct_near_black": float((luma <= near_black).mean()),
        "pct_near_white": float((luma >= near_white).mean()),
        "edge_density": edge_density,
        "mean_alpha": float(alpha.mean()),
        "empty_alpha": bool(alpha.max() <= 0.01),
        "channel_means": [float(rgb[..., i].mean()) for i in range(3)],
    }


def dominant_palette(path: str | Path, k: int = 5) -> list[list[int]]:
    """Cheap palette extraction (most frequent quantised colours) for reference match."""
    with Image.open(path) as im:
        small = im.convert("RGB").resize((64, 64))
        q = small.quantize(colors=k)
        pal = q.getpalette()[: k * 3]
    return [pal[i:i + 3] for i in range(0, len(pal), 3)]


def salient_palette(path: str | Path, k: int = 8) -> list[list[int]]:
    """Dominant colours plus small but important highlight/accent colours."""
    colours = dominant_palette(path, k=k)
    with Image.open(path) as im:
        arr = np.asarray(im.convert("RGB").resize((96, 96)), dtype=np.float32)
    luma = _luma(arr / 255.0)
    blue_excess = arr[..., 2] - np.maximum(arr[..., 0], arr[..., 1])
    masks = [
        luma >= np.quantile(luma, 0.985),
        blue_excess >= np.quantile(blue_excess, 0.985),
        luma <= np.quantile(luma, 0.08),
    ]
    for mask in masks:
        if bool(mask.any()):
            colours.append([int(v) for v in np.clip(arr[mask].mean(axis=0), 0, 255)])
    return colours


_NAMED_COLOURS = {
    "black": [4, 5, 8],
    "dark": [12, 12, 16],
    "cold blue": [70, 115, 255],
    "blue": [70, 120, 255],
    "teal": [40, 210, 190],
    "magenta": [230, 70, 190],
    "purple": [135, 80, 230],
    "white": [235, 240, 255],
    "white highlights": [235, 240, 255],
    "silver": [170, 180, 195],
    "red": [220, 45, 35],
    "green": [40, 180, 100],
    "gold": [230, 175, 55],
    "warm ivory": [230, 220, 185],
    "sage green": [90, 165, 120],
    "brass": [205, 145, 65],
    "soft gray": [155, 155, 148],
}


def palette_from_names(names: list[str]) -> list[list[int]]:
    """Map common style palette words to RGB anchors for reference benchmarks."""
    out = []
    for raw in names:
        key = str(raw).strip().lower()
        if key in _NAMED_COLOURS:
            out.append(_NAMED_COLOURS[key])
    return out


def palette_similarity(actual: list[list[int]], expected: list[list[int]]) -> float:
    """Nearest-colour palette similarity in [0, 1]."""
    if not actual or not expected:
        return 0.0
    a = np.asarray(actual, dtype=np.float32) / 255.0
    e = np.asarray(expected, dtype=np.float32) / 255.0
    scores = []
    for target in e:
        dist = np.sqrt(((a - target) ** 2).sum(axis=1)).min()
        scores.append(max(0.0, 1.0 - float(dist) / np.sqrt(3.0)))
    return float(np.clip(np.mean(scores), 0.0, 1.0))


def images_identical(a: str | Path, b: str | Path, tol: float = 1e-4) -> bool:
    ia, ib = _load(a), _load(b)
    if ia.shape != ib.shape:
        return False
    return bool(np.abs(ia - ib).mean() < tol)


def frame_visual_delta(a: str | Path, b: str | Path) -> dict:
    """Image difference metrics for proving an animation visibly changes frames."""
    ia, ib = _load(a), _load(b)
    if ia.shape != ib.shape:
        with Image.open(b) as im:
            resized = im.convert("RGBA").resize((ia.shape[1], ia.shape[0]))
        ib = np.asarray(resized, dtype=np.float32) / 255.0
    rgb_delta = np.abs(ia[..., :3] - ib[..., :3])
    luma_delta = np.abs(_luma(ia[..., :3]) - _luma(ib[..., :3]))
    return {
        "mean_rgb_delta": float(rgb_delta.mean()),
        "max_rgb_delta": float(rgb_delta.max()),
        "mean_luma_delta": float(luma_delta.mean()),
        "changed_pixel_ratio": float((luma_delta > 0.035).mean()),
    }


def _resize_rgba_like(source: str | Path, shape: tuple[int, int]) -> np.ndarray:
    with Image.open(source) as im:
        resized = im.convert("RGBA").resize((shape[1], shape[0]))
    return np.asarray(resized, dtype=np.float32) / 255.0


def _edge_map(luma: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(luma)
    grad = np.sqrt(gx ** 2 + gy ** 2)
    threshold = max(0.025, float(np.quantile(grad, 0.88)))
    return grad >= threshold


def _saliency_mask(luma: np.ndarray) -> np.ndarray:
    edge = _edge_map(luma)
    threshold = max(0.06, float(np.quantile(luma, 0.70)))
    return edge | (luma >= threshold)


def _mask_centroid(mask: np.ndarray) -> tuple[float, float]:
    if not bool(mask.any()):
        return 0.5, 0.5
    ys, xs = np.nonzero(mask)
    h, w = mask.shape
    return float(xs.mean() / max(1, w - 1)), float(ys.mean() / max(1, h - 1))


def _mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(a, b).sum() / union)


def reference_fidelity_metrics(actual: str | Path, reference: str | Path) -> dict:
    """Spatial/image metrics for proving a render matches a reference composition."""
    ia = _load(actual)
    ib = _load(reference)
    if ia.shape != ib.shape:
        ib = _resize_rgba_like(reference, ia.shape[:2])
    la = _luma(ia[..., :3])
    lb = _luma(ib[..., :3])
    actual_saliency = _saliency_mask(la)
    reference_saliency = _saliency_mask(lb)
    actual_edges = _edge_map(la)
    reference_edges = _edge_map(lb)
    acx, acy = _mask_centroid(actual_saliency)
    rcx, rcy = _mask_centroid(reference_saliency)
    return {
        "saliency_iou": _mask_iou(actual_saliency, reference_saliency),
        "edge_iou": _mask_iou(actual_edges, reference_edges),
        "saliency_center_delta": float(np.sqrt((acx - rcx) ** 2 + (acy - rcy) ** 2)),
        "saliency_coverage_delta": float(abs(actual_saliency.mean() - reference_saliency.mean())),
        "mean_brightness_delta": float(abs(la.mean() - lb.mean())),
        "contrast_delta": float(abs(la.std() - lb.std())),
        "edge_density_delta": float(abs(actual_edges.mean() - reference_edges.mean())),
    }


def part_readability(path: str | Path, bbox, min_side_px: int = 4) -> dict | None:
    """Readability of one camera-space part bbox inside a rendered preview.

    ``bbox`` is ``[minx, miny, maxx, maxy]`` normalised camera space (y up, as
    produced by ``world_to_camera_view``). A part reads when it has internal
    contrast, internal edge detail, or clear luminance separation from the
    ring immediately around it. Dark-on-dark parts that merge into the
    background fail all three signals.
    """
    if not bbox or len(bbox) != 4:
        return None
    arr = _load(path)[..., :3]
    luma = _luma(arr)
    h, w = luma.shape
    x0 = int(np.clip(float(bbox[0]), 0.0, 1.0) * w)
    x1 = int(np.clip(float(bbox[2]), 0.0, 1.0) * w)
    y_top = int(np.clip(1.0 - float(bbox[3]), 0.0, 1.0) * h)
    y_bot = int(np.clip(1.0 - float(bbox[1]), 0.0, 1.0) * h)
    if x1 - x0 < min_side_px or y_bot - y_top < min_side_px:
        return None
    crop = luma[y_top:y_bot, x0:x1]
    gy, gx = np.gradient(crop)
    edge_density = float((np.sqrt(gx ** 2 + gy ** 2) > 0.08).mean())
    contrast = float(crop.std())
    pad = max(2, int(0.08 * max(x1 - x0, y_bot - y_top)))
    rx0, rx1 = max(0, x0 - pad), min(w, x1 + pad)
    ry0, ry1 = max(0, y_top - pad), min(h, y_bot + pad)
    ring = luma[ry0:ry1, rx0:rx1]
    mask = np.ones(ring.shape, dtype=bool)
    mask[y_top - ry0:y_bot - ry0, x0 - rx0:x1 - rx0] = False
    surround = float(ring[mask].mean()) if mask.any() else float(luma.mean())
    separation = abs(float(crop.mean()) - surround)
    return {
        "contrast": round(contrast, 4),
        "edge_density": round(edge_density, 4),
        "separation": round(separation, 4),
        "mean_luma": round(float(crop.mean()), 4),
        "surround_luma": round(surround, 4),
        "readable": bool(contrast >= 0.035 or edge_density >= 0.02 or separation >= 0.045),
    }


def subject_readability_report(
    path: str | Path,
    objects,
    min_coverage: float = 0.0005,
    part_names: list[str] | None = None,
) -> dict:
    """Per-part readability for camera-visible SUBJECT objects.

    ``part_names`` optionally restricts measurement to named-part keywords
    (same substring matching as the benchmark named-part gates). Parts whose
    crop is too small to measure are skipped, not failed.
    """
    parts = []
    for obj in objects or []:
        if obj.get("collection") != "SUBJECT" or not obj.get("in_camera_frame"):
            continue
        bbox = obj.get("screen_bbox")
        if not bbox:
            continue
        if float(obj.get("screen_coverage", 0.0) or 0.0) < min_coverage:
            continue
        name = str(obj.get("name", ""))
        if part_names and not any(str(p).lower() in name.lower() for p in part_names):
            continue
        m = part_readability(path, bbox)
        if m is None:
            continue
        parts.append({"name": name, **m})
    unreadable = [p["name"] for p in parts if not p["readable"]]
    return {
        "parts": parts,
        "measured_parts": len(parts),
        "readable_parts": len(parts) - len(unreadable),
        "unreadable_parts": unreadable,
    }


def _integral(img: np.ndarray) -> np.ndarray:
    return np.pad(img, ((1, 0), (1, 0)), mode="constant").cumsum(0).cumsum(1)


def _box_mean(img: np.ndarray, w: int) -> np.ndarray:
    ii = _integral(img)
    s = ii[w:, w:] - ii[:-w, w:] - ii[w:, :-w] + ii[:-w, :-w]
    return s / (w * w)


def _ssim_numpy(a: np.ndarray, b: np.ndarray, win: int = 7) -> float:
    win = min(win, a.shape[0], a.shape[1])
    if win < 3:
        # Too small for a window: fall back to global SSIM.
        mua, mub = a.mean(), b.mean()
        va, vb = a.var(), b.var()
        cov = ((a - mua) * (b - mub)).mean()
        c1, c2 = 0.01 ** 2, 0.03 ** 2
        return float(((2 * mua * mub + c1) * (2 * cov + c2)) /
                     ((mua ** 2 + mub ** 2 + c1) * (va + vb + c2)))
    c1, c2 = 0.01 ** 2, 0.03 ** 2
    mua, mub = _box_mean(a, win), _box_mean(b, win)
    maa, mbb, mab = _box_mean(a * a, win), _box_mean(b * b, win), _box_mean(a * b, win)
    va, vb, cov = maa - mua ** 2, mbb - mub ** 2, mab - mua * mub
    ssim_map = ((2 * mua * mub + c1) * (2 * cov + c2)) / ((mua ** 2 + mub ** 2 + c1) * (va + vb + c2))
    return float(np.clip(ssim_map.mean(), -1.0, 1.0))


def ssim(a: str | Path, b: str | Path) -> float:
    """Structural similarity in [0,1]-ish; resizes b to match a, grayscale."""
    ia, ib = _load(a), _load(b)
    la, lb = _luma(ia[..., :3]), _luma(ib[..., :3])
    if la.shape != lb.shape:
        with Image.open(b) as im:
            resized = im.convert("L").resize((la.shape[1], la.shape[0]))
        lb = np.asarray(resized, dtype=np.float32) / 255.0
    try:
        from skimage.metrics import structural_similarity  # type: ignore
        return float(structural_similarity(la, lb, data_range=1.0))
    except Exception:
        return _ssim_numpy(la, lb)


def render_sanity_issues(metrics: dict) -> list[str]:
    """Translate metrics into hard-fail/warning reasons (SRS 10.3)."""
    issues: list[str] = []
    if metrics.get("file_size", 0) == 0:
        issues.append("render file is empty")
    if metrics["pct_near_black"] > 0.97:
        issues.append("render is almost entirely black")
    if metrics["pct_near_white"] > 0.97:
        issues.append("render is almost entirely white/blown out")
    if metrics["contrast"] < 0.02:
        issues.append("render has almost no contrast (flat/empty)")
    if metrics["edge_density"] < 0.006:
        issues.append("render has no discernible silhouette/detail")
    if metrics["contrast"] < 0.055 and metrics["edge_density"] < 0.012:
        issues.append("render is too flat for visual acceptance")
    if metrics["pct_near_black"] > 0.65 and metrics["edge_density"] < 0.018:
        issues.append("dark render lacks readable subject detail")
    if metrics.get("empty_alpha"):
        issues.append("render alpha channel is fully empty")
    return issues
