"""TRAKKART canvas — ratios and framing (cover/contain/stretch/blur).

cover   = fill the ratio, crop overflow (focus + zoom).
contain = fit the whole image, black bars (no crop).
stretch = distort to the exact ratio (no crop, no bars).
blur    = fit the whole image over a blurred fill (no crop, no black bars).

Custom mode (Photoshop-style): ratio presets lock the aspect, "custom"
frees W/H entirely (W/H spins are the size; typing them flips to custom).
"""

from __future__ import annotations

from PIL import Image, ImageFilter

RATIOS: dict[str, tuple[int, int]] = {
    "1:1": (1, 1),
    "4:3": (4, 3),
    "3:2": (3, 2),
    "4:5": (4, 5),
    "16:9": (16, 9),
    "9:16": (9, 16),
}

#: Ratio value for free W/H (not in RATIOS on purpose: aspect comes from W/H).
CUSTOM_RATIO = "custom"

#: Hard document bounds shared with the exporter (no import cycle: defined here).
MIN_DIM = 64
MAX_DIM = 8000

CROP_MODES = ("cover", "contain", "stretch", "blur")

MODE_TIPS = {
    "cover": "Fill the ratio, crop overflow (focus + zoom apply)",
    "contain": "Fit whole image, black bars (no crop)",
    "stretch": "Distort to the exact ratio (no crop, no bars)",
    "blur": "Fit whole image over a blurred fill (no black bars)",
}


def ratio_names() -> list[str]:
    return list(RATIOS.keys())


CUSTOM_LABEL = "Custom"


def ratio_label(value: str) -> str:
    """Valor interno -> texto del combo (custom se muestra 'Custom')."""
    return CUSTOM_LABEL if value == CUSTOM_RATIO else value


def ratio_value(label: str) -> str:
    """Texto del combo -> valor interno."""
    return CUSTOM_RATIO if label == CUSTOM_LABEL else label


def canvas_ratios() -> list[str]:
    """Entradas del combo: presets + Custom libre (display; ver ratio_value)."""
    return [*RATIOS.keys(), CUSTOM_LABEL]


def canvas_size_for(ratio: str, long_side: int = 3000) -> tuple[int, int]:
    """Export dimensions for a ratio (long side = long_side)."""
    rw, rh = RATIOS[ratio]
    if rw >= rh:
        return (long_side, max(1, round(long_side * rh / rw)))
    return (max(1, round(long_side * rw / rh)), long_side)


def resolve_frame(ratio: str, long_side: int, canvas_w: int = 0,
                  canvas_h: int = 0) -> tuple[float, int, int]:
    """(aspect, W, H): absolute doc dims. Custom uses explicit W/H, else ratio."""
    if (ratio == CUSTOM_RATIO and MIN_DIM <= int(canvas_w or 0) <= MAX_DIM
            and MIN_DIM <= int(canvas_h or 0) <= MAX_DIM):
        w, h = int(canvas_w), int(canvas_h)
        return w / h, w, h
    r = ratio if ratio in RATIOS else "1:1"
    w, h = canvas_size_for(r, max(MIN_DIM, min(MAX_DIM, int(long_side or 3000))))
    return w / h, w, h


def doc_dimensions(ratio: str, long_side: int, canvas_w: int = 0,
                   canvas_h: int = 0) -> tuple[int, int]:
    """Absolute (W, H) of the document for export/sizing (no source needed)."""
    _, w, h = resolve_frame(ratio, long_side, canvas_w, canvas_h)
    return w, h


def crop_cover(
    img: Image.Image, ratio: str, fx: float = 50.0, fy: float = 50.0,
    zoom: float = 1.0, canvas_w: int = 0, canvas_h: int = 0,
) -> Image.Image:
    """Crop to the ratio (focus 0-100, 50 = center). Clamped if out of range.

    zoom >= 1 crops tighter inside the cover box (visual-crop-editor style);
    zoom == 1 keeps the classic full-bleed cover.
    Custom ratio uses the explicit W/H aspect (source magnitude preserved).
    """
    want, _, _ = resolve_frame(ratio, max(img.size), canvas_w, canvas_h)
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


def crop_box_for(
    img_w: int, img_h: int, ratio: str, fx: float = 50.0,
    fy: float = 50.0, zoom: float = 1.0,
    canvas_w: int = 0, canvas_h: int = 0,
) -> tuple[int, int, int, int]:
    """Source-pixel crop box (x, y, w, h) mirroring crop_cover (for the editor)."""
    want, _, _ = resolve_frame(ratio, max(img_w, img_h), canvas_w, canvas_h)
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


def _scaled_frame(
    ratio: str, canvas_w: int, canvas_h: int, ref_long: int,
) -> tuple[int, int]:
    """Frame dims scaled so the long side == ref_long (source magnitude kept)."""
    want, fw, fh = resolve_frame(ratio, max(ref_long, MIN_DIM), canvas_w, canvas_h)
    if max(fw, fh) == max(ref_long, 1):
        return fw, fh
    f = max(ref_long, 1) / max(fw, fh)
    return max(1, round(fw * f)), max(1, round(fh * f))


def fit_contain(
    img: Image.Image, ratio: str, fill: tuple[int, int, int] = (0, 0, 0),
    canvas_w: int = 0, canvas_h: int = 0,
) -> Image.Image:
    """Fit the whole image into the ratio with bars (no cropping)."""
    want, _, _ = resolve_frame(ratio, max(img.size), canvas_w, canvas_h)
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


def fit_stretch(
    img: Image.Image, ratio: str, canvas_w: int = 0, canvas_h: int = 0,
) -> Image.Image:
    """Distort to the exact ratio at source magnitude (no crop, no bars)."""
    rgb = img.convert("RGB")
    w, h = _scaled_frame(ratio, canvas_w, canvas_h, max(rgb.width, rgb.height))
    if (rgb.width, rgb.height) == (w, h):
        return rgb.copy()
    return rgb.resize((w, h), Image.BICUBIC)


def fit_blur(
    img: Image.Image, ratio: str, canvas_w: int = 0, canvas_h: int = 0,
) -> Image.Image:
    """Fit the whole image over a blurred cover fill (no crop, no black bars)."""
    rgb = img.convert("RGB")
    w, h = _scaled_frame(ratio, canvas_w, canvas_h, max(rgb.width, rgb.height))
    bg = crop_cover(rgb, ratio, canvas_w=canvas_w, canvas_h=canvas_h).resize((w, h), Image.BICUBIC)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=max(8, min(w, h) // 24)))
    dim = Image.new("RGB", (w, h), (0, 0, 0))
    bg = Image.blend(bg, dim, 0.15)
    r = min(w / rgb.width, h / rgb.height)
    nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
    if (nw, nh) != (rgb.width, rgb.height):
        fg = rgb.resize((nw, nh), Image.BICUBIC)
    else:
        fg = rgb
    bg.paste(fg, ((w - nw) // 2, (h - nh) // 2))
    return bg


def to_canvas(
    img: Image.Image,
    ratio: str = "1:1",
    mode: str = "cover",
    fx: float = 50.0,
    fy: float = 50.0,
    zoom: float = 1.0,
    canvas_w: int = 0,
    canvas_h: int = 0,
) -> Image.Image:
    """Final canvas at the requested ratio. Unknown ratio/mode -> 1:1 cover.

    Custom ratio uses the explicit W/H aspect (source magnitude preserved,
    like presets: absolute doc dims only apply at export).
    """
    if ratio not in RATIOS and ratio != CUSTOM_RATIO:
        ratio = "1:1"
    if mode == "contain":
        return fit_contain(img.convert("RGB"), ratio, canvas_w=canvas_w, canvas_h=canvas_h)
    if mode == "stretch":
        return fit_stretch(img.convert("RGB"), ratio, canvas_w=canvas_w, canvas_h=canvas_h)
    if mode == "blur":
        return fit_blur(img.convert("RGB"), ratio, canvas_w=canvas_w, canvas_h=canvas_h)
    return crop_cover(
        img.convert("RGB"), ratio, fx, fy, zoom,
        canvas_w=canvas_w, canvas_h=canvas_h,
    )
