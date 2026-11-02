"""Particle source colors: dots, inks, tint (R2-p3, verbatim move).

Pure functions moved from app.disintegrate (no logic change).
app.disintegrate re-exports them so existing imports keep working.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from app.particles.modes import MAX_POINTS


def dither_bw(img: Image.Image, method: str = "bayer8",
              threshold: float = 128.0, pixel_size: int = 1) -> Image.Image:
    """BW dither of the input (Bayer or Floyd-Steinberg family).

    Uses the main engine (app.dither.apply_method, palette=None) so the
    look matches the still pipeline. Limited grayscale is out of scope
    for Fase 1 (BW only).
    """
    from app.dither import apply_method

    return apply_method(img.convert("RGB"), method=method, palette=None,
                        threshold=float(threshold), pixel_size=max(1, int(pixel_size)))


def points_from_dither(dithered: Image.Image) -> tuple[np.ndarray, int, int]:
    """Active (black) coords of a BW dithered image.

    Returns (coords (N,2) as (y,x) int32, H, W). Deterministic stride
    subsample when N exceeds MAX_POINTS (keeps spatial distribution).
    """
    arr = np.asarray(dithered.convert("L"), dtype=np.uint8)
    h, w = arr.shape[:2]
    ys, xs = np.nonzero(arr < 128)
    coords = np.stack([ys.astype(np.int32), xs.astype(np.int32)], axis=1)
    if len(coords) > MAX_POINTS:
        step = int(math.ceil(len(coords) / MAX_POINTS))
        coords = coords[::step].copy()
    return coords, int(h), int(w)


def _darkness_of(arr: np.ndarray, coords: np.ndarray, h: int, w: int) -> np.ndarray:
    """Per-dot darkness 0..1 from an (h,w,3) uint8 array (1 = black source)."""
    ys = np.clip(np.asarray(coords)[:, 0].astype(np.int64), 0, h - 1)
    xs = np.clip(np.asarray(coords)[:, 1].astype(np.int64), 0, w - 1)
    lum = (0.299 * arr[ys, xs, 0] + 0.587 * arr[ys, xs, 1]
           + 0.114 * arr[ys, xs, 2]) / 255.0
    return np.clip(1.0 - lum, 0.0, 1.0)


def inked_points(still: Image.Image) -> tuple[np.ndarray, np.ndarray, int, int]:
    """(coords, colors, h, w) of dark pixels of a still (luminance < 128).

    Same stride cap + deterministic order as points_from_dither, plus
    per-dot RGB colors. Only used for chromatic palette stills; BW keeps
    the legacy points_from_dither path byte-identical.
    """
    arr = np.asarray(still.convert("RGB"))
    h, w = arr.shape[0], arr.shape[1]
    lum = (0.299 * arr[:, :, 0].astype(np.float64)
           + 0.587 * arr[:, :, 1].astype(np.float64)
           + 0.114 * arr[:, :, 2].astype(np.float64))
    ys, xs = np.nonzero(lum < 128)
    coords = np.stack([ys.astype(np.int32), xs.astype(np.int32)], axis=1)
    cols = arr[ys, xs].astype(np.float64)
    if len(coords) > MAX_POINTS:
        step = int(math.ceil(len(coords) / MAX_POINTS))
        coords = coords[::step].copy()
        cols = cols[::step].copy()
    return coords, cols, int(h), int(w)


def morph_ink(work: Image.Image, method: str = "bayer8",
              threshold: float = 128.0, pixel_size: int = 1,
              paint=None, depth: int = 0):
    """Still + dots + dot colors for one morph form (F7 palette following).

    `paint`: None (legacy BW: BW dither + black dots, byte-identical),
    "SOURCE" (original hues: auto-extracted inks like the pipeline), or
    a concrete ink list (palette-dithered still, dots carry the inks).
    A BW-equivalent extract falls back to the legacy path.
    Returns (still_rgb, coords, cols_or_None, h, w); cols is None only
    for the legacy path (tint then works on source colors as in F4).
    """
    from app.dither import apply_method

    if paint is not None and paint != "SOURCE" and len(list(paint)) == 0:
        paint = None
    inks = None
    if paint == "SOURCE":
        from app.palette_extract import extract_palette

        inks = extract_palette(work.convert("RGB"), n=int(depth or 6))
    elif paint is not None:
        inks = [tuple(max(0, min(255, int(c))) for c in col) for col in paint]
    if inks is not None and (len(inks) == 0 or (
            len(inks) == 2
            and {tuple(c) for c in inks} == {(0, 0, 0), (255, 255, 255)})):
        inks = None  # degenerate BW: legacy path, byte-identical
    if inks is None:
        d = dither_bw(work, method=method, threshold=threshold,
                      pixel_size=pixel_size)
        coords, h, w = points_from_dither(d)
        return d.convert("RGB"), coords, None, h, w
    still = apply_method(work.convert("RGB"), method=method, palette=inks,
                         threshold=float(threshold), pixel_size=int(pixel_size))
    coords, cols, h, w = inked_points(still)
    return still.convert("RGB"), coords, cols, h, w


def sample_colors(img: Image.Image, h: int, w: int) -> np.ndarray:
    """(h,w,3) uint8 source colors in coord space.

    Resizes when the dithered grid differs from the source (pixel_size
    floors odd sides), so per-dot colors index exactly like coords.
    """
    rgb = img.convert("RGB")
    if rgb.size != (int(w), int(h)):
        rgb = rgb.resize((max(1, int(w)), max(1, int(h))), Image.BICUBIC)
    return np.asarray(rgb, dtype=np.uint8)


def darkness_map(img: Image.Image, coords: np.ndarray, h: int, w: int) -> np.ndarray:
    """Per-dot darkness 0..1 of the source at each coord (Heckel shading).

    Samples in coord space (resizes when the dithered grid differs from
    the source, same rule as sample_colors).
    """
    return _darkness_of(sample_colors(img, h, w).astype(np.float64),
                        coords, h, w)


def tint_strength(tint: float, env: float) -> float:
    """Dot tint weight 0..1: preset tint gated by the loop envelope.

    Zero at both joints, so tinted clips open and land on the exact BW
    still (all joint byte-exactness invariants hold with tint on).
    """
    return max(0.0, min(1.0, float(tint or 0.0))) * max(0.0, min(1.0, float(env)))


def tint_dots(base_col: np.ndarray, strength: float) -> np.ndarray | None:
    """(n,3) uint8 dot colors, or None when strength is 0 (legacy BW path).

    strength 0 returns None so the BW rasterizer runs byte-identical;
    otherwise dots are base_col * strength over black.
    """
    if not (float(strength) > 0.0):
        return None
    cols = (np.asarray(base_col, dtype=np.float64)
            * max(0.0, min(1.0, float(strength))))
    return np.clip(np.round(cols), 0, 255).astype(np.uint8)


__all__ = ["dither_bw", "points_from_dither", "inked_points", "morph_ink",
           "sample_colors", "darkness_map", "tint_strength", "tint_dots",
           "_darkness_of"]
