"""TRAKKART texture/decay pack (MIT, clean-room). Post-dither, deterministic.

Dot/line print halftone (print style, different from the engine dither),
dust & scratches with fixed seed, solid border and cinematic letterbox.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def halftone(img: Image.Image, cell: int = 0, shape: str = "dots") -> Image.Image:
    """Print screen over the image. 0 = off; cell 3-12px.

    Dots: radial threshold per cell. Lines: threshold by columns (striped).
    """
    c = int(cell)
    if c < 3:
        return img
    c = min(12, c)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    h, w = arr.shape[:2]
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    if shape == "lines":
        phase = (np.arange(w, dtype=np.float32) % c) / c  # 0..1 per column
        mask = (phase[None, :] < lum).astype(np.float32)
    else:  # dots: distance to each cell center
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = (xx % c) / c - 0.5
        dy = (yy % c) / c - 0.5
        r = np.sqrt(dx * dx + dy * dy) * np.sqrt(2.0)  # 0 center .. 1 corner
        mask = (r < lum * 1.05).astype(np.float32)
    out = np.where(mask[..., None] > 0, arr, 0.0)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def dust(img: Image.Image, amount: float = 0.0, seed: int = 0xD57) -> Image.Image:
    """Dust and scratches: random light/dark specks. 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    p = min(0.02, a / 100.0 * 0.02)  # up to 2% of pixels
    rng = np.random.default_rng(int(seed))
    arr = np.array(_rgb(img))
    h, w = arr.shape[:2]
    n = int(h * w * p)
    if n <= 0:
        return img
    ys = rng.integers(0, h, n)
    xs = rng.integers(0, w, n)
    vals = np.where(rng.random(n) < 0.5, 0, 255).astype(np.uint8)
    out = arr.copy()
    out[ys, xs] = vals[:, None]
    # Scratches: a handful of faint vertical streaks.
    for _ in range(int(a // 20)):
        x = int(rng.integers(0, w))
        y0 = int(rng.integers(0, h))
        ln = int(rng.integers(h // 8, h // 3))
        v = 255 if rng.random() < 0.5 else 0
        out[y0:min(h, y0 + ln), max(0, x - 1):min(w, x + 1)] = v
    return Image.fromarray(out)


def _parse_hex(color: str) -> tuple[int, int, int]:
    s = (color or "").strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"not #RRGGBB: {color!r}")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        raise ValueError(f"not #RRGGBB: {color!r}") from None


def border(img: Image.Image, px: int = 0, color: str = "#000000") -> Image.Image:
    """Solid frame around (poster style). 0 = off."""
    b = int(px)
    if b <= 0:
        return img
    b = min(64, b)
    rgb = _parse_hex(color)
    out = Image.new("RGB", (img.width + 2 * b, img.height + 2 * b), rgb)
    out.paste(img.convert("RGB"), (b, b))
    return out


def letterbox(img: Image.Image, pct: int = 0) -> Image.Image:
    """Cinematic black bars top/bottom. pct 0 = off, % of height per side."""
    p = int(pct)
    if p <= 0:
        return img
    p = min(25, p)
    arr = np.array(_rgb(img))
    h = arr.shape[0]
    bar = max(1, round(h * p / 100.0))
    out = arr.copy()
    out[:bar] = 0
    out[h - bar:] = 0
    return Image.fromarray(out)


__all__ = ["halftone", "dust", "border", "letterbox"]
