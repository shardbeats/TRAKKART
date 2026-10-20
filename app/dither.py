"""TRAKKART dither engine (MIT, clean-room).

Ordered: bayer2/4/8/16, halftone/cluster/pattern/checker/ign/cross/bluenoise
(own maps or standard math). Error-diffusion: floyd/atkinson/burkes/sierra/
jjn/stucki/stevenson/shiaufan/filterlite/sierralite/sierra3 via app/kernels.py.
Hilbert: error diffusion along a space-filling curve (Riemersma-style).

Numpy + Pillow only. No numba, no opencv, no GPU.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.adjust import Adjust, apply_adjust
from app.kernels import COEFFS, ED_METHODS, run_kernel

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

# nombre -> (matriz, divisor de normalizacion)
_ORDERED_DEFS: dict[str, tuple[np.ndarray, float]] = {
    "bayer4": (BAYER_4X4, 16.0),
    "bayer8": (BAYER_8X8, 64.0),
    "bayer16": (BAYER_16X16, 256.0),
    "bayer2": (_bayer_2n(2), 4.0),
    "halftone": (HALFTONE_4X4, 16.0),
    "cluster": (CLUSTER_4X4, 16.0),
    "pattern": (_PATTERN_8X8, 256.0),
    "checker": (np.array([[0, 1], [1, 0]], dtype=np.float32), 2.0),
}

ORDERED_MAPS = ("bayer4", "bayer8", "bayer16", "bayer2", "halftone", "cluster",
                "pattern", "cross", "bluenoise", "checker", "ign")

_BLUE_BASE: np.ndarray | None = None
_CROSS_CACHE: dict[tuple[int, int], np.ndarray] = {}


def _blue_base_tile() -> np.ndarray:
    """Máscara base 64x64 (una sola vez). Antes se cacheaba por (h,w):
    cada tamaño distinto generaba y retenía un array full-res -> leak."""
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
    """Original crosshatch pattern with sines. Deterministic + cacheado.

    El sin() por render costaba ~10-30ms en 1080p; ahora se memoiza por tamaño.
    """
    key = (h, w)
    cached = _CROSS_CACHE.get(key)
    if cached is not None:
        return cached
    ys = np.arange(h, dtype=np.float32)[:, None]
    xs = np.arange(w, dtype=np.float32)[None, :]
    wave = np.sin(xs * 0.35) + np.sin(ys * 0.35) + np.sin((xs + ys) * 0.18)
    out = (wave - wave.min()) / max(wave.max() - wave.min(), 1e-6) * 255.0
    # Evita crecimiento sin cota: conserva solo los últimos 8 tamaños.
    if len(_CROSS_CACHE) >= 8:
        _CROSS_CACHE.pop(next(iter(_CROSS_CACHE)))
    _CROSS_CACHE[key] = out
    return out


def _ign(h: int, w: int) -> np.ndarray:
    """Interleaved Gradient Noise (Jorge Jimenez, fórmula pública).

    Ruido azulado barato sin tablas: f(n) = fract(52.98 * fract(dot(p))).
    Determinista; `phase` lo desplaza para animar (marching sin coste).
    """
    ys = np.arange(h, dtype=np.float64)[:, None]
    xs = np.arange(w, dtype=np.float64)[None, :]
    d = xs * 0.06711056 + ys * 0.00583715
    f = d - np.floor(d)
    return (52.9829189 * f - np.floor(52.9829189 * f)).astype(np.float32) * 255.0


def _threshold_bias(map_name: str, h: int, w: int, threshold: float, phase: int = 0) -> np.ndarray:
    """Additive bias on a 0-255 scale per map and threshold. phase rotates the matrix."""
    spread = 255.0 - abs(float(threshold) - 127.5) * 2.0
    spread = float(np.clip(spread, 32.0, 255.0))
    if map_name == "cross":
        return (np.roll(_crosshatch(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "bluenoise":
        return (np.roll(_blue_noise(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
    if map_name == "ign":
        return (np.roll(_ign(h, w), int(phase), axis=(0, 1)) / 255.0 - 0.5) * spread
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


def _nearest_palette(lum_or_rgb: np.ndarray, palette: list[tuple]) -> np.ndarray:
    """Map each pixel to the closest color (euclidean RGB).

    Por chunks de 50k px: la versión anterior materializaba (N,P,3)
    float32 de golpe -> 3000x3000 con 4 colores = ~1GB y OOM.
    """
    pal = np.asarray(palette, dtype=np.float32)  # (P, 3)
    flat = lum_or_rgb.reshape(-1, 3).astype(np.float32)
    out = np.empty_like(flat, dtype=np.uint8)
    chunk = 50_000
    for i in range(0, flat.shape[0], chunk):
        block = flat[i:i + chunk]
        # (C, P) distancias sin sqrt
        diff = block[:, None, :] - pal[None, :, :]
        idx = np.argmin(np.einsum("cpd,cpd->cp", diff, diff), axis=1)
        out[i:i + chunk] = pal[idx]
    return out.reshape(lum_or_rgb.shape).astype(np.uint8)


def ordered(
    img: Image.Image,
    palette: list[tuple] | None = None,
    map_name: str = "bayer4",
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
    phase: int = 0,
) -> Image.Image:
    """Generic ordered dither. phase rotates the matrix (for animation)."""
    base = apply_adjust(img.convert("RGB"), adjust)
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)

    arr = np.array(base, dtype=np.float32)
    h, w = arr.shape[:2]
    bias = _threshold_bias(map_name if map_name in ORDERED_MAPS else "bayer4", h, w, threshold, phase)

    if palette is None:
        lum = arr.mean(axis=2)
        out = np.where(lum + bias > float(threshold), 255, 0).astype(np.uint8)
        res = Image.fromarray(out, mode="L").convert("RGB")
    else:
        noisy = np.clip(arr + bias[:, :, None], 0, 255)
        res = Image.fromarray(_nearest_palette(noisy, palette), mode="RGB")

    if pixel_size > 1:
        res = res.resize((res.width * pixel_size, res.height * pixel_size), Image.NEAREST)
    return res


def ordered_bayer(
    img: Image.Image,
    palette: list[tuple] | None = None,
    matrix: str = "4x4",
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
) -> Image.Image:
    """Compat: Bayer 4x4/8x8. Use ordered() for newer maps."""
    name = "bayer8" if matrix == "8x8" else "bayer4"
    return ordered(img, palette=palette, map_name=name, threshold=threshold, pixel_size=pixel_size, adjust=adjust)


def error_diffusion(
    img: Image.Image,
    kernel: str = "floyd",
    palette: list[tuple] | None = None,
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
    backend: str = "auto",
) -> Image.Image:
    """Generic error diffusion (floyd/atkinson/burkes/sierra/jjn/stucki/stevenson + nuevos)."""
    if kernel not in COEFFS:
        kernel = "floyd"
    base = apply_adjust(img.convert("RGB"), adjust)
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)
    res = run_kernel(base, kernel, palette, float(threshold), backend=backend)
    if pixel_size > 1:
        res = res.resize((res.width * pixel_size, res.height * pixel_size), Image.NEAREST)
    return res


def hilbert_diffusion(
    img: Image.Image,
    palette: list[tuple] | None = None,
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
) -> Image.Image:
    """Hilbert-ordered error diffusion (Riemersma-style, sin vetas de barrido)."""
    from app.kernels import diffuse_hilbert

    base = apply_adjust(img.convert("RGB"), adjust)
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)
    if palette is None:
        lum = np.array(base.convert("L"), dtype=np.float32)
        out = diffuse_hilbert(lum, None, threshold=float(threshold))
        res = Image.fromarray(out, mode="L").convert("RGB")
    else:
        arr = np.array(base, dtype=np.float32)
        res = Image.fromarray(
            diffuse_hilbert(arr, palette, threshold=float(threshold)), mode="RGB")
    if pixel_size > 1:
        res = res.resize((res.width * pixel_size, res.height * pixel_size), Image.NEAREST)
    return res


def floyd_steinberg(
    img: Image.Image,
    palette: list[tuple] | None = None,
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
) -> Image.Image:
    """Compat: Floyd-Steinberg (delegates to the generic engine, same output)."""
    return error_diffusion(img, kernel="floyd", palette=palette, threshold=threshold, pixel_size=pixel_size, adjust=adjust)


METHODS = (
    "bayer2", "bayer4", "bayer8", "bayer16",
    "halftone", "cluster", "pattern", "cross", "bluenoise",
    "checker", "ign",
    "floyd", "atkinson", "burkes", "sierra", "jjn", "stucki", "stevenson",
    "shiaufan", "filterlite", "sierralite", "sierra3",
    "hilbert",
)


def apply_method(
    img: Image.Image,
    method: str = "bayer4",
    palette: list[tuple] | None = None,
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
    phase: int = 0,
) -> Image.Image:
    if method in ED_METHODS:
        return error_diffusion(img, kernel=method, palette=palette, threshold=threshold, pixel_size=pixel_size, adjust=adjust)
    if method in ORDERED_MAPS:
        return ordered(img, palette=palette, map_name=method, threshold=threshold, pixel_size=pixel_size, adjust=adjust, phase=phase)
    if method == "hilbert":
        return hilbert_diffusion(img, palette=palette, threshold=threshold, pixel_size=pixel_size, adjust=adjust)
    return ordered_bayer(img, palette=palette, matrix="4x4", threshold=threshold, pixel_size=pixel_size, adjust=adjust)
