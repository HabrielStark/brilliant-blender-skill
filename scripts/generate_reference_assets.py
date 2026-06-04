#!/usr/bin/env python
"""Generate deterministic benchmark reference images."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "benchmarks" / "references"


def _rounded_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def generate_reference_match(path: Path) -> None:
    """Create a production-sized reference for the dark product fidelity task."""
    w, h = 480, 270
    img = Image.new("RGB", (w, h), (2, 4, 9))
    draw = ImageDraw.Draw(img)

    for y in range(h):
        t = y / max(1, h - 1)
        r = int(2 + 18 * (1 - abs(t - 0.55)))
        g = int(4 + 24 * (1 - abs(t - 0.55)))
        b = int(9 + 48 * (1 - abs(t - 0.62)))
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((42, 132, 438, 328), fill=(50, 115, 255, 30))
    gd.ellipse((138, 104, 400, 218), fill=(210, 235, 255, 20))
    glow = glow.filter(ImageFilter.GaussianBlur(28))
    img = Image.alpha_composite(img.convert("RGBA"), glow)
    draw = ImageDraw.Draw(img)

    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse((86, 158, 382, 224), fill=(0, 0, 0, 150))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    _rounded_panel(draw, (118, 80, 358, 174), 15, (7, 11, 19, 255))
    _rounded_panel(draw, (130, 68, 346, 86), 9, (11, 17, 29, 255))
    _rounded_panel(draw, (102, 146, 374, 184), 9, (4, 7, 13, 255))
    _rounded_panel(draw, (138, 96, 332, 148), 8, (1, 4, 10, 255))

    draw.line((132, 76, 334, 74), fill=(230, 246, 255, 255), width=2)
    draw.line((145, 92, 305, 91), fill=(54, 127, 255, 255), width=3)
    draw.line((146, 157, 312, 157), fill=(225, 245, 255, 255), width=3)
    draw.line((348, 92, 358, 160), fill=(72, 146, 255, 255), width=4)
    draw.line((112, 119, 124, 150), fill=(42, 104, 220, 255), width=2)

    for i in range(7):
        y = 101 + i * 7
        draw.line((126, y, 146, y + 2), fill=(22, 38, 61, 255), width=2)
    for i in range(5):
        x = 158 + i * 34
        draw.rounded_rectangle((x, 186, x + 24, 189), radius=2, fill=(160, 210, 255, 140))
    for i in range(4):
        x = 174 + i * 42
        draw.rounded_rectangle((x, 197, x + 22, 199), radius=1, fill=(38, 96, 214, 150))

    draw.ellipse((267, 103, 327, 163), fill=(2, 5, 11, 255), outline=(128, 190, 255, 255), width=3)
    draw.ellipse((280, 116, 314, 150), fill=(0, 1, 5, 255), outline=(25, 70, 140, 255), width=2)
    draw.ellipse((286, 119, 298, 131), fill=(220, 242, 255, 255))
    draw.ellipse((154, 111, 178, 135), fill=(20, 76, 190, 255), outline=(175, 222, 255, 255), width=2)
    draw.ellipse((160, 114, 167, 121), fill=(230, 245, 255, 255))

    highlight = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hd = ImageDraw.Draw(highlight)
    hd.line((126, 80, 342, 78), fill=(255, 255, 255, 90), width=1)
    hd.line((136, 147, 329, 147), fill=(255, 255, 255, 70), width=1)
    hd.line((359, 96, 365, 157), fill=(96, 156, 255, 120), width=2)
    highlight = highlight.filter(ImageFilter.GaussianBlur(1.2))
    img = Image.alpha_composite(img, highlight)

    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path)


def main() -> int:
    generate_reference_match(REFERENCE_DIR / "reference_match.png")
    print((REFERENCE_DIR / "reference_match.png").resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
