"""TRAKKART effects (MIT, clean-room). Pillow + numpy pre/post processing.

All original work. No opencv, no numba.
"""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageFilter


def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def apply_pre(
    img: Image.Image,
    blur: float = 0.0,
    sharpen: int = 0,
    hue: float = 0.0,
    denoise: int = 0,
    smooth: float = 0.0,
) -> Image.Image:
    out = _rgb(img)
    if float(blur) > 0:
        out = out.filter(ImageFilter.GaussianBlur(radius=float(blur)))
    for _ in range(max(0, int(sharpen))):
        out = out.filter(ImageFilter.SHARPEN)
    out = apply_denoise(out, denoise)
    out = apply_smooth(out, smooth)
    out = apply_hue(out, hue)
    return out


def apply_hue(img: Image.Image, degrees: float = 0.0) -> Image.Image:
    """Rotate hue in HSV (vectorized numpy, original implementation)."""
    if float(degrees) == 0:
        return img
    arr = np.array(_rgb(img), dtype=np.float32) / 255.0
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin
    h = np.zeros_like(r)
    m = delta != 0
    mr = m & (cmax == r)
    mg = m & (cmax == g)
    mb = m & (cmax == b)
    h[mr] = (((g[mr] - b[mr]) / delta[mr]) % 6.0) / 6.0
    h[mg] = ((b[mg] - r[mg]) / delta[mg] + 2.0) / 6.0
    h[mb] = ((r[mb] - g[mb]) / delta[mb] + 4.0) / 6.0
    h = (h + float(degrees) / 360.0) % 1.0
    s = np.where(cmax == 0, 0.0, delta / np.maximum(cmax, 1e-9))
    v = cmax
    i = (h * 6.0).astype(np.int32) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p = v * (1.0 - s)
    q = v * (1.0 - f * s)
    t = v * (1.0 - (1.0 - f) * s)
    out = np.empty_like(arr)
    for sector, (cr, cg, cb) in enumerate([(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)]):
        msk = i == sector
        out[..., 0][msk] = cr[msk]
        out[..., 1][msk] = cg[msk]
        out[..., 2][msk] = cb[msk]
    return Image.fromarray((out * 255.0).clip(0, 255).astype(np.uint8))


def apply_denoise(img: Image.Image, strength: int = 0) -> Image.Image:
    """Median filter (Pillow). strength 1-5 -> 3x3 to 11x11 window."""
    s = int(strength)
    if s <= 0:
        return img
    size = max(3, min(11, 2 * s + 1))
    if size % 2 == 0:
        size += 1
    return _rgb(img).filter(ImageFilter.MedianFilter(size=size))


def apply_smooth(img: Image.Image, strength: float = 0.0) -> Image.Image:
    """Extra light blur (Pillow). strength 1-5 -> radius 0.5-2.5."""
    s = float(strength)
    if s <= 0:
        return img
    return _rgb(img).filter(ImageFilter.GaussianBlur(radius=s * 0.5))


def apply_glow(img: Image.Image, radius: float = 0.0, intensity: float = 0.0,
               threshold: int = 0) -> Image.Image:
    """Screen blend with a blurred copy. Threshold: only values above it bloom.

    threshold 0 = everything glows (classic behavior).
    High threshold = only brights bloom (halo look for dither).
    """
    if float(radius) <= 0 or float(intensity) <= 0:
        return img
    base = _rgb(img)
    blurred = base.filter(ImageFilter.GaussianBlur(radius=float(radius)))
    a = np.asarray(base, dtype=np.float32)
    b = np.asarray(blurred, dtype=np.float32) * (float(intensity) / 100.0)
    out = a + b - a * b / 255.0
    t = int(threshold)
    if t > 0:
        lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[..., None]
        k = np.clip((lum - t) / max(255 - t, 1), 0.0, 1.0)
        k = k * k * (3.0 - 2.0 * k)  # smoothstep: el glow entra fundido
        out = a + (out - a) * k
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def apply_grain(img: Image.Image, amount: float = 0.0, seed: int = 0x7A4B) -> Image.Image:
    """Uniform +-amount noise with fixed seed (deterministic)."""
    if float(amount) <= 0:
        return img
    rng = np.random.default_rng(int(seed))
    arr = np.asarray(_rgb(img), dtype=np.float32)
    noise = rng.uniform(-float(amount), float(amount), arr.shape).astype(np.float32)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype(np.uint8))


def apply_vignette(img: Image.Image, strength: float = 0.0) -> Image.Image:
    """Radial darkening. strength 0-100."""
    if float(strength) <= 0:
        return img
    arr = np.asarray(_rgb(img), dtype=np.float32)
    h, w = arr.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dx = (xs - w / 2.0) / (w / 2.0)
    dy = (ys - h / 2.0) / (h / 2.0)
    d = np.sqrt(dx * dx + dy * dy) / np.sqrt(2.0)
    mask = 1.0 - np.clip(d, 0.0, 1.0) ** 2 * (float(strength) / 100.0)
    return Image.fromarray(np.clip(arr * mask[..., None], 0, 255).astype(np.uint8))


def apply_scanlines(img: Image.Image, every: int = 0, darken: float = 0.4) -> Image.Image:
    """Darken 1 of every `every` rows (CRT look). every<2 = off."""
    if int(every) < 2:
        return img
    arr = np.array(_rgb(img), dtype=np.float32)
    arr[int(every) - 1 :: int(every)] *= 1.0 - float(darken)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def parse_hex(color: str) -> tuple[int, int, int] | None:
    s = (color or "").strip().lstrip("#")
    if len(s) != 6:
        return None
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return None


def replace_white(img: Image.Image, color: str = "") -> Image.Image:
    """Map near-white pixels (>=250 on all 3 channels) to the brand color."""
    rgb = parse_hex(color)
    if rgb is None:
        return img
    arr = np.array(_rgb(img))
    mask = arr.min(axis=2) >= 250
    if not mask.any():
        return img
    out = arr.copy()
    out[mask] = rgb
    return Image.fromarray(out)


def normalize_custom_palette(raw: list | None) -> list[tuple[int, int, int]] | None:
    """Validate custom palette [[r,g,b],...] (2-16 colors) or return None."""
    if not raw:
        return None
    pal: list[tuple[int, int, int]] = []
    for c in raw:
        try:
            r, g, b = int(c[0]), int(c[1]), int(c[2])
        except (TypeError, IndexError, ValueError):
            raise ValueError(f"invalid custom color: {c!r}")
        if not all(0 <= v <= 255 for v in (r, g, b)):
            raise ValueError(f"custom color out of 0-255: {c!r}")
        pal.append((r, g, b))
    if not 2 <= len(pal) <= 16:
        raise ValueError(f"custom palette needs 2-16 colors, got {len(pal)}")
    return pal
