"""TRAKKART canvas — ratios and cropping (cover/contain) with safe clamp."""

from __future__ import annotations

from PIL import Image

RATIOS: dict[str, tuple[int, int]] = {
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:2": (3, 2),
    "4:5": (4, 5),
    "16:9": (16, 9),
    "9:16": (9, 16),
}

CROP_MODES = ("cover", "contain")


def ratio_names() -> list[str]:
    return list(RATIOS.keys())


def canvas_size_for(ratio: str, long_side: int = 3000) -> tuple[int, int]:
    """Export dimensions for a ratio (long side = long_side)."""
    rw, rh = RATIOS[ratio]
    if rw >= rh:
        return (long_side, max(1, round(long_side * rh / rw)))
    return (max(1, round(long_side * rw / rh)), long_side)


def crop_cover(img: Image.Image, ratio: str, fx: float = 50.0, fy: float = 50.0,
               zoom: float = 1.0) -> Image.Image:
    """Crop to the ratio (focus 0-100, 50 = center). Clamped if out of range.

    zoom >= 1 crops tighter inside the cover box (visual-crop-editor style);
    zoom == 1 keeps the classic full-bleed cover.
    """
    rw, rh = RATIOS[ratio]
    want = rw / rh
    w, h = img.size
    fx = min(100.0, max(0.0, float(fx)))
    fy = min(100.0, max(0.0, float(fy)))
    zoom = max(1.0, float(zoom))
    if w / h > want:  # wider than needed: bars top/bottom
        cw, ch = round(h * want), h
        x = round((w - cw) * fx / 100.0)
        base = (x, 0, x + cw, ch)
    else:
        cw, ch = w, round(w / want)
        y = round((h - ch) * fy / 100.0)
        base = (0, y, cw, y + ch)
    if zoom <= 1.0:
        return img.crop(base)
    # Tighter box around the same anchor point, clamped to the image.
    bx0, by0, _, _ = base
    cx, cy = bx0 + cw / 2.0, by0 + ch / 2.0
    bw, bh = max(1, round(cw / zoom)), max(1, round(ch / zoom))
    x = min(w - bw, max(0, round(cx - bw / 2.0)))
    y = min(h - bh, max(0, round(cy - bh / 2.0)))
    return img.crop((x, y, x + bw, y + bh))


def crop_box_for(img_w: int, img_h: int, ratio: str, fx: float = 50.0,
                 fy: float = 50.0, zoom: float = 1.0) -> tuple[int, int, int, int]:
    """Source-pixel crop box (x, y, w, h) mirroring crop_cover (for the editor)."""
    rw, rh = RATIOS[ratio]
    want = rw / rh
    fx = min(100.0, max(0.0, float(fx)))
    fy = min(100.0, max(0.0, float(fy)))
    zoom = max(1.0, float(zoom))
    if img_w / img_h > want:
        cw, ch = round(img_h * want), img_h
        x = round((img_w - cw) * fx / 100.0)
        base = (x, 0, cw, ch)
    else:
        cw, ch = img_w, round(img_w / want)
        y = round((img_h - ch) * fy / 100.0)
        base = (0, y, cw, ch)
    if zoom <= 1.0:
        bx, by, bw, bh = base[0], base[1], base[2], base[3]
        return (bx, by, bw, bh)
    bx0, by0 = base[0], base[1]
    cx, cy = bx0 + cw / 2.0, by0 + ch / 2.0
    bw, bh = max(1, round(cw / zoom)), max(1, round(ch / zoom))
    x = min(img_w - bw, max(0, round(cx - bw / 2.0)))
    y = min(img_h - bh, max(0, round(cy - bh / 2.0)))
    return (x, y, bw, bh)


def fit_contain(img: Image.Image, ratio: str, fill: tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
    """Fit the whole image into the ratio with bars (no cropping)."""
    rw, rh = RATIOS[ratio]
    want = rw / rh
    w, h = img.size
    if abs(w / h - want) < 1e-9:
        return img.copy()
    if w / h > want:  # wider image: bars top/bottom
        cw, ch = w, round(w / want)
    else:  # side bars
        cw, ch = round(h * want), h
    canvas = Image.new("RGB", (cw, ch), fill)
    canvas.paste(img, ((cw - w) // 2, (ch - h) // 2))
    return canvas


def to_canvas(
    img: Image.Image,
    ratio: str = "1:1",
    mode: str = "cover",
    fx: float = 50.0,
    fy: float = 50.0,
    zoom: float = 1.0,
) -> Image.Image:
    """Final canvas at the requested ratio. Unknown ratio/mode -> 1:1 cover."""
    if ratio not in RATIOS:
        ratio = "1:1"
    if mode == "contain":
        return fit_contain(img.convert("RGB"), ratio)
    return crop_cover(img.convert("RGB"), ratio, fx, fy, zoom)
