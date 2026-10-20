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

from app.ordered_maps import threshold_bias


ORDERED_MAPS = ("bayer4", "bayer8", "bayer16", "bayer32", "bayer2", "halftone", "cluster",
                "pattern", "cross", "bluenoise", "checker", "ign",
                "lines", "columns", "diag", "grid",
                "white_noise", "blocks", "scan_bayer", "wave_map", "motif")

GLITCH_DITHER = ("white_noise", "blocks", "scan_bayer", "wave_map")
SPECIAL_RENDER = ("cmyk", "ascii", "edges")


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
    motif: dict | None = None,
) -> Image.Image:
    """Generic ordered dither. phase rotates the matrix (for animation)."""
    base = apply_adjust(img.convert("RGB"), adjust)
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)

    arr = np.array(base, dtype=np.float32)
    h, w = arr.shape[:2]
    bias = threshold_bias(
        map_name if map_name in ORDERED_MAPS else "bayer4",
        h, w, threshold, phase, motif=motif,
    )

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


def edges_dither(
    img: Image.Image,
    palette: list[tuple] | None = None,
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
    phase: int = 0,
) -> Image.Image:
    """Edge-detect + bayer overlay (special): contornos ditherizados sobre base."""
    from PIL import ImageFilter

    base = apply_adjust(img.convert("RGB"), adjust)
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)
    edge = base.convert("L").filter(ImageFilter.FIND_EDGES)
    edge_arr = np.asarray(edge, dtype=np.float32)
    lum = np.array(base.convert("L"), dtype=np.float32)
    h, w = lum.shape
    bias = threshold_bias("bayer8", h, w, threshold, phase)
    dith = np.where(lum + bias > float(threshold), 255.0, 0.0)
    ink = np.clip(edge_arr * 1.5, 0, 255)
    out_lum = np.clip(dith * 0.55 + (255.0 - ink) * 0.45, 0, 255)
    if palette is None:
        res = Image.fromarray(np.where(out_lum > float(threshold), 255, 0).astype(np.uint8),
                              mode="L").convert("RGB")
    else:
        gray3 = np.stack([out_lum, out_lum, out_lum], axis=-1)
        res = Image.fromarray(_nearest_palette(gray3, palette), mode="RGB")
    if pixel_size > 1:
        res = res.resize((res.width * pixel_size, res.height * pixel_size), Image.NEAREST)
    return res


METHODS = (
    "bayer2", "bayer4", "bayer8", "bayer16", "bayer32",
    "halftone", "cluster", "pattern", "cross", "bluenoise",
    "checker", "ign", "lines", "columns", "diag", "grid",
    "white_noise", "blocks", "scan_bayer", "wave_map", "motif",
    "floyd", "atkinson", "burkes", "sierra", "jjn", "stucki", "stevenson",
    "shiaufan", "filterlite", "sierralite", "sierra3",
    "hilbert",
    "cmyk", "ascii", "edges",
)


def apply_method(
    img: Image.Image,
    method: str = "bayer4",
    palette: list[tuple] | None = None,
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
    phase: int = 0,
    motif: dict | None = None,
) -> Image.Image:
    if method in ED_METHODS:
        return error_diffusion(img, kernel=method, palette=palette, threshold=threshold, pixel_size=pixel_size, adjust=adjust)
    if method == "cmyk":
        from app.cmyk import cmyk_halftone

        # CMYK ignora la paleta por diseño (tinta de imprenta); threshold = dot gain.
        base = apply_adjust(img.convert("RGB"), adjust)
        return cmyk_halftone(base, threshold=float(threshold), phase=int(phase),
                             pixel_size=int(pixel_size))
    if method == "ascii":
        from app.ascii import ascii_render

        base = apply_adjust(img.convert("RGB"), adjust)
        return ascii_render(base, palette=palette, threshold=float(threshold),
                            pixel_size=int(pixel_size), phase=int(phase))
    if method == "edges":
        return edges_dither(img, palette=palette, threshold=threshold,
                            pixel_size=pixel_size, adjust=adjust, phase=phase)
    if method in ORDERED_MAPS:
        return ordered(img, palette=palette, map_name=method, threshold=threshold, pixel_size=pixel_size, adjust=adjust, phase=phase, motif=motif)
    if method == "hilbert":
        return hilbert_diffusion(img, palette=palette, threshold=threshold, pixel_size=pixel_size, adjust=adjust)
    return ordered_bayer(img, palette=palette, matrix="4x4", threshold=threshold, pixel_size=pixel_size, adjust=adjust)
