"""TRAKKART glitch pack (MIT). Pure numpy, deterministic.

chromatic_aberration: shifts R right and B left (wrap).
slice_shift: splits into N horizontal bands and shifts each (fixed seed).
pixel_sort: sorts bright runs within each row (seeded tie-break).
wave: sine displacement of rows ( CRT wobble).
datamosh: random block offsets (fixed seed).
rgb_grille: vertical RGB aperture grille (CRT companion to scanlines).
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


def pixel_sort(img: Image.Image, threshold: int = 0, seed: int = 0x9150) -> Image.Image:
    """Sorts the bright runs of each row from dark to light.

    threshold 0 = off. Only reorders pixels brighter than threshold,
    so the dither look stretches into streaks (cheap trendy effect:
    O(rows · width log width)).
    """
    t = int(threshold)
    if t <= 0:
        return img
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    lum = (0.299 * arr[..., 0].astype(np.float32) + 0.587 * arr[..., 1].astype(np.float32)
           + 0.114 * arr[..., 2].astype(np.float32))
    out = arr.copy()
    rng = np.random.default_rng(int(seed))
    for y in range(h):
        row_lum = lum[y]
        mask = row_lum > t
        if not mask.any() or mask.all():
            # All or nothing bright: sorting everything avoids a dull edge case.
            idx = np.argsort(row_lum, kind="stable")
            out[y] = arr[y][idx]
            continue
        x = 0
        while x < w:
            if not mask[x]:
                x += 1
                continue
            x0 = x
            while x < w and mask[x]:
                x += 1
            seg = np.arange(x0, x)
            order = np.argsort(row_lum[seg], kind="stable")
            # Deterministic but non-monotonic tie-break: shifts the run.
            shift = int(rng.integers(0, max(1, len(seg))))
            order = np.roll(order, shift)
            out[y][seg] = arr[y][seg[order]]
    return Image.fromarray(out)


def wave(img: Image.Image, amplitude: int = 0, seed: int = 0x9A9E) -> Image.Image:
    """Sine displacement by row (CRT wobble). 0 = off."""
    a = int(amplitude)
    if a <= 0:
        return img
    a = min(30, a)
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    rng = np.random.default_rng(int(seed))
    phase = float(rng.uniform(0.0, 6.2831853))
    wave_len = max(32.0, w / 6.0)
    offsets = (np.sin(np.arange(h, dtype=np.float32) / wave_len * 6.2831853 + phase) * a).astype(int)
    out = np.empty_like(arr)
    for y in range(h):
        out[y] = np.roll(arr[y], int(offsets[y]), axis=0)
    return Image.fromarray(out)


def datamosh(img: Image.Image, amount: float = 0.0, seed: int = 0x405) -> Image.Image:
    """Randomly shifted blocks (datamosh). 0 = off.

    Compat: the implementation lives in app.mosh (mosh_blocks, byte-identical).
    """
    from app.mosh import mosh_blocks

    return mosh_blocks(img, amount=amount, seed=seed)


def rgb_grille(img: Image.Image, every: int = 0) -> Image.Image:
    """RGB aperture grille: R/G/B columns. 0 = off (2 or 3 valid)."""
    e = int(every)
    if e not in (2, 3):
        return img
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    h, w = arr.shape[:2]
    phase = np.arange(w, dtype=np.int32) % e
    mask = np.ones_like(arr)
    if e == 2:
        # Alternate R-tinted / cyan columns to fake the grille.
        # (One array per indexing: mixing bool + list breaks in numpy.)
        odd = phase == 1
        mask[:, phase == 0, 1:] *= 0.55
        mask[:, odd, 0] *= 0.55
        mask[:, odd, 2] *= 0.55
    else:
        for c in range(3):
            keep = (phase % 3) == c
            dim = np.ones(w, dtype=np.float32)
            dim[~keep] = 0.45
            mask[:, :, c] *= dim[None, :]
    return Image.fromarray(np.clip(arr * mask, 0, 255).astype(np.uint8))
