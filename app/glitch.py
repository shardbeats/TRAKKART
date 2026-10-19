"""TRAKKART glitch pack (MIT, clean-room). Pure numpy, deterministic.

chromatic_aberration: shifts R right and B left (wrap).
slice_shift: splits into N horizontal bands and shifts each (fixed seed).
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def chromatic_aberration(img: Image.Image, dx: int = 0, dy: int = 0) -> Image.Image:
    dx, dy = int(dx), int(dy)
    if dx == 0 and dy == 0:
        return img
    arr = np.array(img.convert("RGB"))
    out = arr.copy()
    out[..., 0] = np.roll(np.roll(arr[..., 0], dx, axis=1), dy, axis=0)
    out[..., 2] = np.roll(np.roll(arr[..., 2], -dx, axis=1), -dy, axis=0)
    return Image.fromarray(out)


def slice_shift(
    img: Image.Image, bands: int = 0, max_offset: int = 24, seed: int = 0x6A17
) -> Image.Image:
    """Shift horizontal bands with pseudo-random offsets (fixed seed)."""
    bands = int(bands)
    if bands < 2:
        return img
    arr = np.array(img.convert("RGB"))
    h = arr.shape[0]
    rng = np.random.default_rng(int(seed))
    offsets = rng.integers(-int(max_offset), int(max_offset) + 1, size=bands)
    edges = np.linspace(0, h, bands + 1).astype(int)
    out = arr.copy()
    for i in range(bands):
        y0, y1 = int(edges[i]), int(edges[i + 1])
        if y1 > y0:
            out[y0:y1] = np.roll(arr[y0:y1], int(offsets[i]), axis=1)
    return Image.fromarray(out)
