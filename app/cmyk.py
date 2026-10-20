"""TRAKKART CMYK halftone (MIT, clean-room). Numpy + Pillow only.

Simplified print-style halftone: RGB -> CMY + K, each channel screened
with an angled Bayer threshold (C 15°, M 75°, Y 0°, K 45° simulated by
map offsets), then back to RGB. Deterministic; `phase` rotates screens
so it animates (marching dots) like the other ordered maps.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _bayer8() -> np.ndarray:
    from app.dither import BAYER_8X8

    return BAYER_8X8


def _screened(channel: np.ndarray, angle_idx: int, phase: int = 0) -> np.ndarray:
    """Halftone one 0-255 channel: threshold with rotated Bayer."""
    import numpy as _np

    m = _bayer8()
    # Ángulos simulados por roll distinto por canal (barato y determinista).
    shifts = (0, 13, 29, 47)
    tiled = _np.tile(m, ((channel.shape[0] + 7) // 8, (channel.shape[1] + 7) // 8))[:channel.shape[0], :channel.shape[1]]
    tiled = _np.roll(tiled, shifts[angle_idx % 4] + int(phase), axis=(0, 1))
    thr = tiled / 64.0 * 255.0
    return _np.where(channel > thr, 255.0, 0.0)


def cmyk_halftone(img: Image.Image, threshold: float = 128.0, phase: int = 0,
                  pixel_size: int = 1) -> Image.Image:
    """CMYK-style halftone -> RGB. threshold = dot gain (global offset)."""
    base = img.convert("RGB")
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)
    arr = np.asarray(base, dtype=np.float32)
    gain = (float(threshold) - 128.0) * 0.8  # +/-102 alrededor del neutro
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    k = 255.0 - np.maximum(np.maximum(r, g), b)
    c = (255.0 - r - k)
    m = (255.0 - g - k)
    y = (255.0 - b - k)
    c = np.clip(c + gain, 0, 255)
    m = np.clip(m + gain, 0, 255)
    y = np.clip(y + gain, 0, 255)
    k = np.clip(k + gain, 0, 255)
    cs = _screened(c, 0, phase) / 255.0
    ms = _screened(m, 1, phase) / 255.0
    ys = _screened(y, 2, phase) / 255.0
    ks = _screened(k, 3, phase) / 255.0
    # Multiplicativo sobre papel blanco (overprint simplificado).
    rr = 255.0 * (1.0 - cs) * (1.0 - ks)
    gg = 255.0 * (1.0 - ms) * (1.0 - ks)
    bb = 255.0 * (1.0 - ys) * (1.0 - ks)
    out = np.stack([rr, gg, bb], axis=-1).clip(0, 255).astype(np.uint8)
    res = Image.fromarray(out, mode="RGB")
    if pixel_size > 1:
        res = res.resize((res.width * pixel_size, res.height * pixel_size), Image.NEAREST)
    return res


__all__ = ["cmyk_halftone"]
