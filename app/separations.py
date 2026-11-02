"""TRAKKART ink separations (R9, MIT): spot plates for RISO/screen print.

One PNG per palette color (black ink on white) + corner registration
marks on every plate. Offline, Pillow + numpy only, deterministic.

Pipeline fit: plates are separated from the exported main image
("separate what you see", exact canvas size). Pixels map to palette
inks by nearest color, so replace-color/post-fx output still yields
sensible plates (approximated, documented). Pairs with the Vector Pro
black-ink workflow for print shops.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def color_hex(col) -> str:
    """(r, g, b) -> 'RRGGBB' (filename-safe, no #)."""
    r, g, b = (max(0, min(255, int(c))) for c in col)
    return f"{r:02X}{g:02X}{b:02X}"


def sep_name(base: str, index: int, hexcode: str) -> str:
    """`{base}_sep_{01}_{RRGGBB}.png` (1-based plate order = palette order)."""
    return f"{base}_sep_{int(index) + 1:02d}_{hexcode}.png"


def effective_palette(preset, img: Image.Image | None = None) -> list[tuple[int, int, int]]:
    """Palette inks a preset render uses (same resolution as the pipeline).

    Custom > SOURCE (extracted, depth or 6) > BW fast path > named
    (depth-truncated). Without an image, SOURCE falls back to B&W
    (plate-count estimates only; the writer always passes the render).
    """
    from app.pipeline import resolve_palette
    from app.render_params import apply_palette_depth, normalize_palette_depth

    pal, _ = resolve_palette(str(getattr(preset, "palette", "SLIME") or "SLIME"),
                             getattr(preset, "custom_palette", None))
    depth = normalize_palette_depth(int(getattr(preset, "palette_depth", 0) or 0))
    if pal == "SOURCE":
        if img is None:
            return [(0, 0, 0), (255, 255, 255)]
        from app.palette_extract import extract_palette

        pal = extract_palette(img.convert("RGB"), n=int(depth or 6))
    elif pal is None:
        pal = [(0, 0, 0), (255, 255, 255)]
    else:
        pal = apply_palette_depth([tuple(c) for c in pal], depth)
    return [tuple(max(0, min(255, int(c))) for c in col) for col in pal]


def plate_count(preset) -> int:
    """Number of plates without rendering (dialog estimates)."""
    from app.render_params import normalize_palette_depth

    name = str(getattr(preset, "palette", "SLIME") or "SLIME")
    custom = getattr(preset, "custom_palette", None)
    if custom:
        try:
            return max(1, len(list(custom)))
        except TypeError:
            pass
    if name in ("BW",):
        return 2
    if name == "SOURCE":
        return int(normalize_palette_depth(int(getattr(preset, "palette_depth", 0) or 0)) or 6)
    try:
        from app.pipeline import resolve_palette

        pal, _ = resolve_palette(name, None)
        if pal is None:
            return 2
        from app.render_params import apply_palette_depth

        return len(apply_palette_depth(
            [tuple(c) for c in pal],
            normalize_palette_depth(int(getattr(preset, "palette_depth", 0) or 0))))
    except Exception:  # noqa: BLE001
        return 4


def separation_plates(img: Image.Image,
                      colors: list[tuple[int, int, int]]) -> list[tuple[str, Image.Image]]:
    """[(hex, plate)] in palette order. Plate: L mode, white bg, black ink
    where that ink prints (nearest-color assignment, row-chunked)."""
    cols = [tuple(max(0, min(255, int(c))) for c in col) for col in colors]
    if not cols:
        raise ValueError("no colors")
    arr = np.asarray(img.convert("RGB"), dtype=np.float32)
    h = arr.shape[0]
    pal = np.asarray(cols, dtype=np.float32)
    idx = np.empty((h, arr.shape[1]), dtype=np.int64)
    for y0 in range(0, h, 512):
        blk = arr[y0:y0 + 512]
        d2 = ((blk[:, :, None, :] - pal[None, None, :, :]) ** 2).sum(-1)
        idx[y0:y0 + blk.shape[0]] = d2.argmin(-1)
    out = []
    for i, col in enumerate(cols):
        plate = np.full(idx.shape, 255, dtype=np.uint8)
        plate[idx == i] = 0
        out.append((color_hex(col), Image.fromarray(plate, mode="L")))
    return out


def add_registration_marks(plate: Image.Image) -> Image.Image:
    """Corner crosshair-in-circle on every plate (print alignment).

    Marks print in all inks. Keep artwork clear of the corners or the
    marks overprint it (standard quiet-zone practice).
    """
    w, h = plate.size
    m = max(8, min(w, h))
    inset = max(4, m // 25)
    r = max(6, m // 60)
    lw = max(1, m // 500)
    d = ImageDraw.Draw(plate)
    for cx, cy in ((inset, inset), (w - inset, inset),
                   (inset, h - inset), (w - inset, h - inset)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=0, width=lw)
        d.line([cx - r - 2 * lw, cy, cx + r + 2 * lw, cy], fill=0, width=lw)
        d.line([cx, cy - r - 2 * lw, cx, cy + r + 2 * lw], fill=0, width=lw)
    return plate


def estimate_sep(w: int, h: int, n_plates: int) -> int:
    """Rough weight estimate (bytes): bilevel dither noise ~1 bit/px."""
    return max(1, int(w)) * max(1, int(h)) * max(0, int(n_plates)) // 8


def write_separations(img: Image.Image, colors: list[tuple[int, int, int]],
                      out_dir: str | Path, base: str) -> list[Path]:
    """Separate + mark + write every plate. Returns paths in palette order."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, (hexcode, plate) in enumerate(separation_plates(img, colors)):
        p = out_dir / sep_name(base, i, hexcode)
        add_registration_marks(plate).save(str(p))
        paths.append(p)
    return paths


__all__ = [
    "add_registration_marks",
    "color_hex",
    "effective_palette",
    "estimate_sep",
    "plate_count",
    "sep_name",
    "separation_plates",
    "write_separations",
]
