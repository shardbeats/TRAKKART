"""TRAKKART particle disperse (dither-boy style, MIT). Numpy + Pillow only.

Single-image loop (no morph yet): BW dither -> active points -> per-frame
positions with a breathe envelope (assembled -> dispersed -> assembled).

Loop-perfect: the turbulence pattern is fixed per clip (seeded once) and
only its amplitude breathes with sin(pi*frac), so progress 0 == 1.
Deterministic: same inputs + frame = same pixels (default_rng(seed)).
Strict 0=off: amount 0 returns the dithered still for every frame.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

DISINTEGRATE_MODES = ("wind", "random")

#: Hard cap on rasterized points per frame (perf: vectorized scatter).
MAX_POINTS = 120_000


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


def disperse_positions(coords: np.ndarray, h: int, w: int, progress: float = 0.0,
                       seed: int = 0xD15C, wind: tuple[float, float] = (120.0, -40.0),
                       mode: str = "wind", loops: float = 1.0,
                       amount: float = 1.0) -> np.ndarray:
    """Loop-perfect positions for one frame.

    progress in [0, 1), loops traversals per clip. Envelope
    e = sin(pi*frac) with frac = (progress*loops) % 1: 0 at the loop
    joint (assembled), 1 mid-clip (fully dispersed). Turbulence is fixed
    per clip (seeded once); wind adds a directional offset. amount 0
    freezes everything (identity).
    """
    if mode not in DISINTEGRATE_MODES:
        mode = "wind"
    amt = max(0.0, min(2.0, float(amount or 0.0)))
    if amt <= 0 or len(coords) == 0:
        return np.asarray(coords, dtype=np.float32).copy()
    loops = max(0.25, min(4.0, float(loops or 1.0)))
    frac = (float(progress) * float(loops)) % 1.0
    env = math.sin(math.pi * frac)
    n = int(len(coords))
    rng = np.random.default_rng(int(seed))
    if mode == "random":
        spread = 90.0 * amt
        turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
        # (y,x) order: wind tuple is (wx, wy) -> (dy, dx).
        off = turb * env
    else:
        wx, wy = float(wind[0]), float(wind[1])
        spread = 28.0 * amt
        turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
        base = np.array([[wy * amt, wx * amt]], dtype=np.float32)
        off = (base + turb) * env
    out = coords.astype(np.float32) + off
    out[:, 0] = np.clip(out[:, 0], 0, h - 1)
    out[:, 1] = np.clip(out[:, 1], 0, w - 1)
    return out


def render_points(positions: np.ndarray, h: int, w: int) -> Image.Image:
    """Rasterize float (y,x) points to a BW RGB image (white bg, black dots)."""
    canvas = np.full((h, w), 255, dtype=np.uint8)
    if len(positions):
        ys = np.clip(positions[:, 0].astype(np.int32), 0, h - 1)
        xs = np.clip(positions[:, 1].astype(np.int32), 0, w - 1)
        canvas[ys, xs] = 0
    return Image.fromarray(canvas, mode="L").convert("RGB")


def dissolve_frames(img: Image.Image, method: str = "bayer8",
                    threshold: float = 128.0, pixel_size: int = 1,
                    frames: int = 8, seed: int = 0xD15C,
                    wind: tuple[float, float] = (120.0, -40.0),
                    mode: str = "wind", loops: float = 1.0,
                    amount: float = 1.0,
                    max_side: int = 480) -> list[Image.Image]:
    """Full disperse loop for one image (assembled -> dispersed -> assembled).

    Dithers once at max_side, then marches progress=i/n. amount 0 returns
    n copies of the dithered still (identity, strict 0=off).
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    small = img.convert("RGB")
    r = side / max(small.width, small.height)
    if r < 1.0:
        small = small.resize((max(1, round(small.width * r)),
                              max(1, round(small.height * r))), Image.BICUBIC)
    dithered = dither_bw(small, method=method, threshold=threshold,
                         pixel_size=pixel_size)
    coords, h, w = points_from_dither(dithered)
    out: list[Image.Image] = []
    for i in range(n):
        progress = float(i) / float(n)
        pos = disperse_positions(coords, h, w, progress=progress, seed=seed,
                                 wind=wind, mode=mode, loops=loops, amount=amount)
        out.append(render_points(pos, h, w))
    return out


def morph_frames(img_a: Image.Image, img_b: Image.Image, method: str = "bayer8",
                 threshold: float = 128.0, pixel_size: int = 1,
                 frames: int = 8, seed: int = 0xD15C,
                 wind: tuple[float, float] = (120.0, -40.0),
                 mode: str = "wind", amount: float = 1.0,
                 max_side: int = 480) -> list[Image.Image]:
    """One-shot swap A -> B through a shared particle cloud (Fase 5).

    Both images are fitted to the same HxW (B resized to A), dithered
    with the same engine, then: progress<0.5 renders dispersed A,
    progress>=0.5 renders dispersed B, envelope sin(pi*progress) so both
    ends are assembled and the middle is a full cloud. amount 0 returns
    A copies then B copies (hard cut, strict 0=off).
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    a = img_a.convert("RGB")
    r = side / max(a.width, a.height)
    if r < 1.0:
        a = a.resize((max(1, round(a.width * r)),
                      max(1, round(a.height * r))), Image.BICUBIC)
    b = img_b.convert("RGB").resize((a.width, a.height), Image.BICUBIC)
    da = dither_bw(a, method=method, threshold=threshold, pixel_size=pixel_size)
    db = dither_bw(b, method=method, threshold=threshold, pixel_size=pixel_size)
    ca, h, w = points_from_dither(da)
    cb, _, _ = points_from_dither(db)
    out: list[Image.Image] = []
    for i in range(n):
        progress = float(i) / float(n)
        if progress < 0.5:
            pos = disperse_positions(ca, h, w, progress=progress, seed=seed,
                                     wind=wind, mode=mode, loops=1.0, amount=amount)
        else:
            pos = disperse_positions(cb, h, w, progress=progress, seed=seed + 1,
                                     wind=wind, mode=mode, loops=1.0, amount=amount)
        out.append(render_points(pos, h, w))
    return out


__all__ = ["DISINTEGRATE_MODES", "MAX_POINTS", "dither_bw",
           "points_from_dither", "disperse_positions", "render_points",
           "dissolve_frames", "morph_frames"]
