"""TRAKKART ASCII mode (MIT, clean-room). Pillow only.

Luminance blocks -> charset ramp chars drawn with the default bitmap
font, recolored by cell mean color (or palette-nearest when a palette
is given). Deterministic; `phase` rotates the ramp offset so it marches
for animation (like Bayer phase). Vector export falls back to rects
(grid re-render), so ASCII stays vector-compatible (no crash).
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RAMP = "@%#*+=-:. "


def ascii_render(img: Image.Image, palette: list | None = None, threshold: float = 128.0,
                 pixel_size: int = 1, phase: int = 0, cell: int = 8) -> Image.Image:
    """Render ASCII art. cell = char cell px (default 8)."""
    base = img.convert("RGB")
    w, h = base.size
    cw = max(1, w // max(4, int(cell)))
    ch = max(1, h // max(4, int(cell)))
    small = base.resize((cw, ch), Image.BICUBIC)
    arr = np.asarray(small, dtype=np.float32)
    lum = arr.mean(axis=2)
    # threshold desplaza la rampa (más/menos tinta).
    shift = (float(threshold) - 128.0) / 128.0 * (len(RAMP) / 2.0)
    idx = np.clip(((lum / 255.0) * (len(RAMP) - 1) + shift).round(), 0, len(RAMP) - 1).astype(int)
    if phase:
        idx = (idx + int(phase)) % len(RAMP)
    try:
        font = ImageFont.load_default(size=cell)
    except TypeError:  # Pillow < 10 sin size
        font = ImageFont.load_default()
    out_w, out_h = cw * cell, ch * cell
    canvas = Image.new("RGB", (out_w, out_h), (0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    pal = np.asarray(palette, dtype=np.float32) if palette else None
    for y in range(ch):
        for x in range(cw):
            ch_idx = int(idx[y, x])
            glyph = RAMP[ch_idx]
            rgb = tuple(int(v) for v in arr[y, x])
            if pal is not None:
                d = ((pal - arr[y, x]) ** 2).sum(axis=1)
                rgb = tuple(int(v) for v in pal[int(d.argmin())])
            draw.text((x * cell, y * cell), glyph, font=font, fill=rgb)
    if pixel_size > 1:
        canvas = canvas.resize((canvas.width * pixel_size, canvas.height * pixel_size), Image.NEAREST)
    return canvas


__all__ = ["RAMP", "ascii_render"]
