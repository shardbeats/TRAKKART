"""TRAKKART error-diffusion kernels (MIT, clean-room).

Standard coefficient tables (public error-diffusion math).
The `_diffuse` engine is original work, row-vectorized like the v0.4 Floyd.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

# (dy, dx, weight). Weights sum ~= 1 except lossy diffusions (Atkinson).
COEFFS: dict[str, list[tuple[int, int, float]]] = {
    "floyd": [(0, 1, 7 / 16), (1, -1, 3 / 16), (1, 0, 5 / 16), (1, 1, 1 / 16)],
    "atkinson": [
        (0, 1, 1 / 8), (0, 2, 1 / 8),
        (1, -1, 1 / 8), (1, 0, 1 / 8), (1, 1, 1 / 8),
        (2, 0, 1 / 8),
    ],
    "burkes": [
        (0, 1, 8 / 32), (0, 2, 4 / 32),
        (1, -2, 2 / 32), (1, -1, 4 / 32), (1, 0, 8 / 32), (1, 1, 4 / 32), (1, 2, 2 / 32),
    ],
    "sierra": [
        (0, 1, 2 / 4),
        (1, -1, 1 / 4), (1, 0, 1 / 4),
    ],
    "jjn": [
        (0, 1, 7 / 48), (0, 2, 5 / 48),
        (1, -2, 3 / 48), (1, -1, 5 / 48), (1, 0, 7 / 48), (1, 1, 5 / 48), (1, 2, 3 / 48),
        (2, -2, 1 / 48), (2, -1, 3 / 48), (2, 0, 5 / 48), (2, 1, 3 / 48), (2, 2, 1 / 48),
    ],
    "stucki": [
        (0, 1, 8 / 42), (0, 2, 4 / 42),
        (1, -2, 2 / 42), (1, -1, 4 / 42), (1, 0, 8 / 42), (1, 1, 4 / 42), (1, 2, 2 / 42),
        (2, -2, 1 / 42), (2, -1, 2 / 42), (2, 0, 4 / 42), (2, 1, 2 / 42), (2, 2, 1 / 42),
    ],
    "stevenson": [
        (0, 2, 32 / 200),
        (1, -3, 12 / 200), (1, -1, 26 / 200), (1, 1, 30 / 200), (1, 3, 16 / 200),
        (2, -2, 12 / 200), (2, 0, 26 / 200), (2, 2, 12 / 200),
        (3, -3, 5 / 200), (3, -1, 12 / 200), (3, 1, 12 / 200), (3, 3, 5 / 200),
    ],
}

ED_METHODS = ("floyd", "atkinson", "burkes", "sierra", "jjn", "stucki", "stevenson")


from app.accelerate import coeffs_to_arrays, ed_bw, ed_color, has_numba

BACKENDS = ("auto", "numpy", "numba")


def _backend(name: str) -> str:
    if name not in BACKENDS:
        return "auto"
    if name == "numba" and not has_numba():
        raise RuntimeError("numba no instalado: pip install numba")
    return name


def diffuse_bw(lum: np.ndarray, coeffs: list[tuple[int, int, float]], threshold: float,
               backend: str = "auto") -> np.ndarray:
    """Diffuse float32 luminance in-place. Return uint8 0/255."""
    h, w = lum.shape
    t = float(threshold)
    backend = _backend(backend)
    if backend == "numba" or (backend == "auto" and has_numba()):
        dys, dxs, wts = coeffs_to_arrays(coeffs)
        return ed_bw(np.ascontiguousarray(lum, dtype=np.float32), dys, dxs, wts, t)
    max_dy = max(dy for dy, _, _ in coeffs)
    for y in range(h):
        row = lum[y]
        nxt = [lum[y + k] if y + k < h else None for k in range(1, max_dy + 1)]
        for x in range(w):
            old = float(row[x])
            new = 255.0 if old > t else 0.0
            row[x] = new
            err = old - new
            for dy, dx, wt in coeffs:
                nx = x + dx
                if not 0 <= nx < w:
                    continue
                if dy == 0:
                    if dx > 0:
                        row[nx] += err * wt
                elif nxt[dy - 1] is not None:
                    nxt[dy - 1][nx] += err * wt
    return np.clip(lum, 0, 255).astype(np.uint8)


def diffuse_color(
    arr: np.ndarray, palette: list[tuple], coeffs: list[tuple[int, int, float]],
    backend: str = "auto",
) -> np.ndarray:
    """Diffuse float32 RGB in-place toward the palette. Return uint8."""
    backend = _backend(backend)
    if backend == "numba" or (backend == "auto" and has_numba()):
        pal = np.asarray(palette, dtype=np.float32)
        dys, dxs, wts = coeffs_to_arrays(coeffs)
        return ed_color(np.ascontiguousarray(arr, dtype=np.float32), pal, dys, dxs, wts)
    # Fallback numpy: paleta como array + búsqueda vectorizada por fila.
    # Antes: doble loop python (y,x) + loop python sobre paleta -> ~50x más lento.
    pc = np.asarray(palette, dtype=np.float32)  # (P, 3)
    h, w, _ = arr.shape
    max_dy = max(dy for dy, _, _ in coeffs)
    for y in range(h):
        row = arr[y]
        nxt = [arr[y + k] if y + k < h else None for k in range(1, max_dy + 1)]
        for x in range(w):
            px = row[x]  # vista (3,)
            d = np.sum((pc - px) ** 2, axis=1)
            best = int(np.argmin(d))
            nr, ng, nb = float(pc[best, 0]), float(pc[best, 1]), float(pc[best, 2])
            r0, g0, b0 = float(px[0]), float(px[1]), float(px[2])
            px[0], px[1], px[2] = nr, ng, nb
            er, eg, eb = r0 - nr, g0 - ng, b0 - nb
            for dy, dx, wt in coeffs:
                nx = x + dx
                if not 0 <= nx < w:
                    continue
                if dy == 0:
                    if dx > 0:
                        row[nx, 0] += er * wt
                        row[nx, 1] += eg * wt
                        row[nx, 2] += eb * wt
                elif nxt[dy - 1] is not None:
                    tgt = nxt[dy - 1]
                    tgt[nx, 0] += er * wt
                    tgt[nx, 1] += eg * wt
                    tgt[nx, 2] += eb * wt
    return np.clip(arr, 0, 255).astype(np.uint8)


def run_kernel(
    img: Image.Image,
    kernel: str,
    palette: list[tuple] | None,
    threshold: float,
    backend: str = "auto",
) -> Image.Image:
    """Apply an ED kernel to the already-downscaled image. Return PIL."""
    coeffs = COEFFS[kernel]
    if palette is None:
        lum = np.array(img.convert("L"), dtype=np.float32)
        out = diffuse_bw(lum, coeffs, threshold, backend=backend)
        return Image.fromarray(out, mode="L").convert("RGB")
    arr = np.array(img.convert("RGB"), dtype=np.float32)
    return Image.fromarray(diffuse_color(arr, palette, coeffs, backend=backend), mode="RGB")
