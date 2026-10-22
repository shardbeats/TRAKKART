"""Ordered threshold maps (MIT, clean-room). Public-domain math + original masks.

Split out of app/dither.py (mechanical move, one rename:
`_threshold_bias` -> `threshold_bias`). dither.py keeps the dispatch
config (ORDERED_MAPS / METHODS) and re-exports test-facing names.
"""

from __future__ import annotations

import numpy as np


# Standard Bayer matrices (public domain, known math).
BAYER_4X4 = np.array(
    [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ],
    dtype=np.float32,
)

BAYER_8X8 = np.array(
    [
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21],
    ],
    dtype=np.float32,
)


def _bayer_2n(n: int) -> np.ndarray:
    """Generate n×n Bayer by recursion (n must be a power of 2). Standard math."""
    m = np.array([[0, 2], [3, 1]], dtype=np.float32)
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return m


BAYER_16X16 = _bayer_2n(16)
BAYER_32X32 = _bayer_2n(32)

# Line/grille screens (standard math, originals at scale).
_LINES_8X8 = np.fromfunction(lambda i, j: (i % 8) * 32.0, (8, 8)).astype(np.float32)
_COLUMNS_8X8 = np.fromfunction(lambda i, j: (j % 8) * 32.0, (8, 8)).astype(np.float32)
_DIAG_8X8 = np.fromfunction(lambda i, j: ((i + j) % 8) * 32.0, (8, 8)).astype(np.float32)
_GRID_4X4 = np.array(
    [[0, 0, 0, 16], [0, 16, 16, 16], [0, 16, 8, 16], [16, 16, 16, 16]],
    dtype=np.float32)

# Classic ordered matrices (public domain): halftone diamond and
# 4x4 cluster from the literature, plus an original diagonal pattern.
HALFTONE_4X4 = np.array(
    [
        [7, 13, 11, 4],
        [12, 16, 14, 8],
        [10, 15, 6, 2],
        [5, 9, 3, 1],
    ],
    dtype=np.float32,
)

CLUSTER_4X4 = np.array(
    [
        [12, 5, 6, 13],
        [4, 0, 1, 7],
        [11, 3, 2, 8],
        [15, 10, 9, 14],
    ],
    dtype=np.float32,
)

_PATTERN_8X8 = np.fromfunction(lambda i, j: ((i + j) % 8) * 32.0, (8, 8)).astype(np.float32)

# name -> (matrix, normalization divisor)
_ORDERED_DEFS: dict[str, tuple[np.ndarray, float]] = {
    "bayer4": (BAYER_4X4, 16.0),
    "bayer8": (BAYER_8X8, 64.0),
    "bayer16": (BAYER_16X16, 256.0),
    "bayer32": (BAYER_32X32, 1024.0),
    "bayer2": (_bayer_2n(2), 4.0),
    "halftone": (HALFTONE_4X4, 16.0),
    "cluster": (CLUSTER_4X4, 16.0),
    "pattern": (_PATTERN_8X8, 256.0),
    "checker": (np.array([[0, 1], [1, 0]], dtype=np.float32), 2.0),
    "lines": (_LINES_8X8, 256.0),
    "columns": (_COLUMNS_8X8, 256.0),
    "diag": (_DIAG_8X8, 256.0),
    "grid": (_GRID_4X4, 16.0),
}

_BLUE_BASE: np.ndarray | None = None
_CROSS_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _blue_base_tile() -> np.ndarray:
    """Base 64x64 mask (built once). It used to be cached per (h,w):
    each distinct size generated and held a full-res array -> leak."""
    global _BLUE_BASE
    if _BLUE_BASE is None:
        from PIL import Image, ImageFilter

        rng = np.random.default_rng(0x7A4B)
        tile = 64
        base = rng.integers(0, 256, (tile, tile)).astype(np.uint8)
        soft = np.array(
            Image.fromarray(base).filter(ImageFilter.GaussianBlur(radius=2)),
            dtype=np.float32,
        )
        _BLUE_BASE = np.clip(base.astype(np.float32) - soft + 128.0, 0, 255)
    return _BLUE_BASE


def _blue_noise(h: int, w: int) -> np.ndarray:
    """Original pseudo-blue-noise mask: seeded RNG + blur. Deterministic."""
    return _tile_matrix(_blue_base_tile(), h, w)


def _crosshatch(h: int, w: int) -> np.ndarray:
    """Original crosshatch pattern with sines. Deterministic + cached.

    The sin() per render cost ~10-30ms at 1080p; now memoized by size.
    """
    key = (h, w)
    cached = _CROSS_CACHE.get(key)
    if cached is not None:
        return cached
    ys = np.arange(h, dtype=np.float32)[:, None]
    xs = np.arange(w, dtype=np.float32)[None, :]
    wave = np.sin(xs * 0.35) + np.sin(ys * 0.35) + np.sin((xs + ys) * 0.18)
    out = (wave - wave.min()) / max(wave.max() - wave.min(), 1e-6) * 255.0
    # Avoid unbounded growth: keep only the last 8 sizes.
    if len(_CROSS_CACHE) >= 8:
        _CROSS_CACHE.pop(next(iter(_CROSS_CACHE)))
    _CROSS_CACHE[key] = out
    return out


def _ign(h: int, w: int) -> np.ndarray:
    """Interleaved Gradient Noise (Jorge Jimenez, public formula).

    Cheap bluish noise without tables: f(n) = fract(52.98 * fract(dot(p))).
    Deterministic; `phase` shifts it for animation (marching at no cost).
    """
    ys = np.arange(h, dtype=np.float64)[:, None]
    xs = np.arange(w, dtype=np.float64)[None, :]
    d = xs * 0.06711056 + ys * 0.00583715
    f = d - np.floor(d)
    return (52.9829189 * f - np.floor(52.9829189 * f)).astype(np.float32) * 255.0


def _white_noise(h: int, w: int) -> np.ndarray:
    """Uniform 0-255 white noise with fixed seed. Deterministic."""
    rng = np.random.default_rng(0xC0FFEE)
    return rng.integers(0, 256, (h, w)).astype(np.float32)


def _blocks(h: int, w: int) -> np.ndarray:
    """Random 4x4 blocks (glitch): one threshold per block. Deterministic."""
    rng = np.random.default_rng(0xB10C)
    bh, bw = (h + 3) // 4, (w + 3) // 4
    small = rng.integers(0, 256, (bh, bw)).astype(np.float32)
    return np.repeat(np.repeat(small, 4, axis=0), 4, axis=1)[:h, :w]


def _scan_bayer(h: int, w: int) -> np.ndarray:
    """Bayer8 modulated by scanlines (every 3rd row darkens): CRT look."""
    tiled = _tile_matrix(BAYER_8X8, h, w)
    rows = (np.arange(h, dtype=np.float32)[:, None] % 3 == 2) * 48.0
    return np.clip(tiled * 4.0 - rows, 0, 255)


def _wave_map(h: int, w: int) -> np.ndarray:
    """Sine-warped Bayer8 (marching waves with phase)."""
    ys = np.arange(h, dtype=np.float32)[:, None]
    xs = np.arange(w, dtype=np.float32)[None, :]
    warp = (np.sin(xs * 0.12) * 3.0 + np.sin(ys * 0.09) * 3.0)
    tiled = _tile_matrix(BAYER_8X8, h + 8, w + 8)
    yi = np.clip((ys + warp).astype(int) % (h + 8), 0, h + 7)
    xi = np.clip((xs - warp).astype(int) % (w + 8), 0, w + 7)
    return tiled[yi, xi] * 4.0


_MOTIF_CACHE: dict[str, np.ndarray] = {}


def _motif_map(h: int, w: int, config: dict | None = None) -> np.ndarray:
    """Custom motif map (cached by config)."""
    import json

    from app.motif import build_matrix, normalize_config

    key = json.dumps(normalize_config(config), sort_keys=True)
    base = _MOTIF_CACHE.get(key)
    if base is None:
        base = build_matrix(normalize_config(config))
        if len(_MOTIF_CACHE) >= 8:
            _MOTIF_CACHE.pop(next(iter(_MOTIF_CACHE)))
        _MOTIF_CACHE[key] = base
    return _tile_matrix(base, h, w)


def threshold_bias(map_name: str, h: int, w: int, threshold: float, phase: int = 0,
                   motif: dict | None = None) -> np.ndarray:
    """Additive bias on a 0-255 scale per map and threshold. phase rotates the matrix."""
    spread = 255.0 - abs(float(threshold) - 127.5) * 2.0
    spread = float(np.clip(spread, 32.0, 255.0))
    if map_name == "cross":
        return (np.roll(_crosshatch(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "bluenoise":
        return (np.roll(_blue_noise(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "ign":
        return (np.roll(_ign(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "white_noise":
        return (np.roll(_white_noise(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "blocks":
        return (np.roll(_blocks(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "scan_bayer":
        return (np.roll(_scan_bayer(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "wave_map":
        return (np.roll(_wave_map(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "motif":
        return (np.roll(_motif_map(h, w, motif), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    mat, div = _ORDERED_DEFS.get(map_name, _ORDERED_DEFS["bayer4"])
    tiled = _tile_matrix(mat, h, w)
    if phase:
        tiled = np.roll(tiled, int(phase), axis=(0, 1))
    return (tiled / div - 0.5) * spread


def _tile_matrix(mat: np.ndarray, h: int, w: int) -> np.ndarray:
    """Repeat the matrix until it covers h x w."""
    mh, mw = mat.shape
    reps_y = (h + mh - 1) // mh
    reps_x = (w + mw - 1) // mw
    return np.tile(mat, (reps_y, reps_x))[:h, :w]


def march_offset(method: str, frame: int, n_frames: int, amt: float = 1.0) -> int:
    """Phase offset for frame `i` of `n` so the march loops seamlessly.

    Tiled matrices crawl exactly `loops` full periods per loop
    (`loops` from the motion amount, min 1; 0 freezes). Function masks
    have no clean period, so they keep the legacy small crawl.
    """
    amt = min(3.0, max(0.0, float(amt or 0.0)))
    if amt <= 0:
        return 0
    i = max(0, int(frame))
    n = max(1, int(n_frames))
    loops = max(1, int(round(amt)))
    entry = _ORDERED_DEFS.get(str(method))
    if entry is not None:
        period = int(entry[0].shape[0])
        return int(round(period * loops * (i % n) / n))
    return int(round(2 * amt * i))
