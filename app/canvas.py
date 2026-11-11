"""TRAKKART canvas — ratios and framing (cover/contain/stretch/blur).

cover   = fill the ratio, crop overflow (focus + zoom).
contain = fit the whole image, black bars (no crop).
stretch = distort to the exact ratio (no crop, no bars).
blur    = fit the whole image over a blurred fill (no crop, no black bars).

Custom mode (editor-style): ratio presets lock the aspect, "custom"
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

#: Soft ceiling for a still export, in megapixels. Above this the Document
#: panel and the export dialog warn (RAM + render time); nothing is blocked.
#: 36 MP keeps every social/print preset comfortable while flagging 8k docs.
OUTPUT_MP_BUDGET = 36

#: Sources at or below this side keep hard edges when stretched/blurred:
#: a tiny logo blown up with BICUBIC turns into mush, NEAREST keeps its inks.
TINY_SOURCE_SIDE = 64

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
    """Internal value -> combo text (custom shows 'Custom')."""
    return CUSTOM_LABEL if value == CUSTOM_RATIO else value


def ratio_value(label: str) -> str:
    """Combo text -> internal value."""
    return CUSTOM_RATIO if label == CUSTOM_LABEL else label


def canvas_ratios() -> list[str]:
    """Combo entries: presets + free Custom (display; see ratio_value)."""
    return [*RATIOS.keys(), CUSTOM_LABEL]


def output_megapixels(w: int, h: int) -> float:
    """Document size in megapixels (one decimal), 0.0 for empty/invalid dims."""
    try:
        return round(max(0, int(w)) * max(0, int(h)) / 1_000_000.0, 1)
    except (TypeError, ValueError):
        return 0.0


def output_budget_note(w: int, h: int) -> str | None:
    """Warning line when the document exceeds OUTPUT_MP_BUDGET, else None.

    Soft guard only: the export still runs (the user asked for that size),
    but the UI tells them why a big still is slow and RAM-heavy.
    """
    mp = output_megapixels(w, h)
    if mp <= OUTPUT_MP_BUDGET:
        return None
    return (f"{mp:g} MP is above the {OUTPUT_MP_BUDGET} MP output budget: "
            "rendering and export may be slow and RAM-heavy.")


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
        cw, ch = max(1, round(h * want)), h
        x = round((w - cw) * fx / 100.0)
        base = (x, 0, x + cw, ch)
    else:
        cw, ch = w, max(1, round(w / want))
        y = round((h - ch) * fy / 100.0)
        base = (0, y, cw, y + ch)
    if zoom <= 1.0:
        return img.crop(base)
    # Zoomed box positioned directly by fx/fy (same contract as the visual
    # editor): corners and edges reachable, no forced recenter. Delegates so
    # the dialog frame and the pipeline can never disagree.
    bx, by, bw, bh = crop_box_for(w, h, ratio, fx, fy, zoom,
                                  canvas_w=canvas_w, canvas_h=canvas_h)
    return img.crop((bx, by, bx + bw, by + bh))


def crop_box_for(
    img_w: int, img_h: int, ratio: str, fx: float = 50.0,
    fy: float = 50.0, zoom: float = 1.0,
    canvas_w: int = 0, canvas_h: int = 0,
) -> tuple[int, int, int, int]:
    """Source-pixel crop box (x, y, w, h) mirroring crop_cover (for the editor).

    fx/fy describe the (possibly zoomed) box inside its own slack, so any
    spot is reachable: corners and edges, not just the center. zoom == 1
    keeps the classic full-bleed cover box.
    """
    want, _, _ = resolve_frame(ratio, max(img_w, img_h), canvas_w, canvas_h)
    fx = min(100.0, max(0.0, float(fx)))
    fy = min(100.0, max(0.0, float(fy)))
    zoom = max(1.0, float(zoom))
    if img_w / img_h > want:
        base_cw, base_ch = round(img_h * want), img_h
    else:
        base_cw, base_ch = img_w, round(img_w / want)
    bw, bh = max(1, round(base_cw / zoom)), max(1, round(base_ch / zoom))
    x = round((img_w - bw) * fx / 100.0)
    y = round((img_h - bh) * fy / 100.0)
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
    """Fit the whole image into the ratio with bars (no cropping).

    The working canvas never grows past the document long side (or the
    source long side when no document is known): contain used to expand
    a landscape photo into a 4000x7111 sheet of black bars for a 9:16
    doc, which burned RAM/time and made SVG grids look monstrous. The
    image is centered at native detail or scaled down to fit the capped
    canvas; composition is identical to the old padded result once both
    are sized to the document.
    """
    want, _, _ = resolve_frame(ratio, max(img.size), canvas_w, canvas_h)
    w, h = img.size
    exact = abs(w / h - want) < 1e-9
    if exact:
        cw, ch = w, h
    elif w / h > want:  # wider image: bars top/bottom
        cw, ch = w, max(1, round(w / want))
    else:  # side bars
        cw, ch = max(1, round(h * want)), h
    try:
        cap = max(int(canvas_w or 0), int(canvas_h or 0))
    except (TypeError, ValueError):
        cap = 0
    if cap <= 0:
        cap = max(w, h)
    if max(cw, ch) > cap:
        s = cap / float(max(cw, ch))
        cw, ch = max(1, round(cw * s)), max(1, round(ch * s))
    if exact and (cw, ch) == (w, h):
        return img.copy()
    # Natural contain never needs to upscale; this rescales only when the
    # capped canvas is smaller than the padded one.
    r = min(cw / w, ch / h)
    nw, nh = max(1, round(w * r)), max(1, round(h * r))
    fg = img.resize((nw, nh), Image.BICUBIC) if (nw, nh) != (w, h) else img
    canvas = Image.new("RGB", (cw, ch), fill)
    canvas.paste(fg, ((cw - nw) // 2, (ch - nh) // 2))
    return canvas


def _resample(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Resize a canvas frame, keeping hard edges for tiny sources.

    Stretching a 32px logo with BICUBIC blends its inks into mush; NEAREST
    keeps the original colors (the dither dots stay readable). Normal-size
    sources keep the smooth BICUBIC path.
    """
    w, h = int(size[0]), int(size[1])
    if (w, h) == img.size:
        return img
    if max(img.size) <= TINY_SOURCE_SIDE:
        return img.resize((w, h), Image.NEAREST)
    return img.resize((w, h), Image.BICUBIC)


def fit_stretch(
    img: Image.Image, ratio: str, canvas_w: int = 0, canvas_h: int = 0,
) -> Image.Image:
    """Distort to the exact ratio at source magnitude (no crop, no bars)."""
    rgb = img.convert("RGB")
    w, h = _scaled_frame(ratio, canvas_w, canvas_h, max(rgb.width, rgb.height))
    return _resample(rgb, (w, h))


def fit_blur(
    img: Image.Image, ratio: str, canvas_w: int = 0, canvas_h: int = 0,
) -> Image.Image:
    """Fit the whole image over a blurred cover fill (no crop, no black bars)."""
    rgb = img.convert("RGB")
    w, h = _scaled_frame(ratio, canvas_w, canvas_h, max(rgb.width, rgb.height))
    bg = _resample(crop_cover(rgb, ratio, canvas_w=canvas_w, canvas_h=canvas_h), (w, h))
    # Radius proportional to the canvas: the old 8px floor erased tiny frames
    # (a 64x36 canvas became a flat smear); 1px keeps it safe on any size.
    radius = max(1.0, min(w, h) / 24.0)
    bg = bg.filter(ImageFilter.GaussianBlur(radius=radius))
    dim = Image.new("RGB", (w, h), (0, 0, 0))
    bg = Image.blend(bg, dim, 0.15)
    r = min(w / rgb.width, h / rgb.height)
    nw, nh = max(1, round(rgb.width * r)), max(1, round(rgb.height * r))
    fg = _resample(rgb, (nw, nh))
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
