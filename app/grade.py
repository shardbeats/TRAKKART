"""TRAKKART grade pack (MIT, clean-room). Pre/post-dither color grading.

Duotone and posterize run BEFORE the dither (on continuous tone, like the
adjustments: the dither works over the grade). Split-tone and fade
run after (they work well on flat art). All deterministic, numpy+Pillow.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def _luminance(arr: np.ndarray) -> np.ndarray:
    """Rec.601 luminance in 0-1."""
    return (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    s = (color or "").strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def gradient_map(
    img: Image.Image,
    color_dark: str = "",
    color_light: str = "",
    mid: float = 50.0,
) -> Image.Image:
    """Duotone: luminance -> color_dark..color_light gradient, cut at mid%.

    Empty in either = off. The midpoint moves the cut (GIMP: color stops).
    """
    c0 = _parse_hex(color_dark)
    c1 = _parse_hex(color_light)
    if c0 is None or c1 is None:
        return img
    t = float(np.clip(mid, 0.0, 100.0)) / 100.0
    # Smooth ±7.5% transition around the midpoint (less banding).
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)
    x = np.clip((lum - (t - 0.075)) / 0.15, 0.0, 1.0)
    k = x * x * (3.0 - 2.0 * x)  # smoothstep
    a = np.array(c0, dtype=np.float32)[None, None, :]
    b = np.array(c1, dtype=np.float32)[None, None, :]
    return Image.fromarray(np.clip(a + (b - a) * k[..., None], 0, 255).astype(np.uint8))


def posterize(img: Image.Image, levels: int = 0) -> Image.Image:
    """Reduces to `levels` tones per channel. 0 or <2 = off."""
    lv = int(levels)
    if lv < 2:
        return img
    lv = min(8, lv)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    q = np.round(arr / 255.0 * (lv - 1)) / (lv - 1) * 255.0
    return Image.fromarray(np.clip(q, 0, 255).astype(np.uint8))


# Fixed cinematic pair, documented (the fine custom one is the duotone).
_SPLIT_WARM = np.array([255.0, 170.0, 90.0], dtype=np.float32)
_SPLIT_COOL = np.array([70.0, 100.0, 255.0], dtype=np.float32)


def split_tone(img: Image.Image, strength: float = 0.0) -> Image.Image:
    """Cool shadows + warm highlights by luminance. 0 = off."""
    s = float(strength) / 100.0
    if s <= 0:
        return img
    s = min(1.0, s)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)[..., None]
    warm = _SPLIT_WARM[None, None, :] * lum
    cool = _SPLIT_COOL[None, None, :] * (1.0 - lum)
    graded = arr * (1.0 - s) + (arr * 0.5 + (warm + cool) * 0.25) * s
    return Image.fromarray(np.clip(graded, 0, 255).astype(np.uint8))


def fade(img: Image.Image, amount: float = 0.0) -> Image.Image:
    """Matte look: lifts blacks proportionally. 0 = off."""
    s = float(amount) / 100.0
    if s <= 0:
        return img
    s = min(1.0, s)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    lum = _luminance(arr)
    lift = s * 64.0 * (1.0 - lum) ** 2  # shadows only, like the film matte
    return Image.fromarray(np.clip(arr + lift[..., None], 0, 255).astype(np.uint8))


__all__ = ["gradient_map", "posterize", "split_tone", "fade"]
