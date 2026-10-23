"""TRAKKART error-diffusion kernels (MIT).

Standard coefficient tables (public error-diffusion math).
The `_diffuse` engine is original work, row-vectorized like the v0.4 Floyd.
Hilbert-ordered diffusion (Riemersma-style) lives here too: same error
fractions, but the image is walked along a Hilbert curve instead of rows.
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
    # Shiau-Fan 5x3 in its usual published form (sums to 42): dense and smooth,
    # halfway between Burkes and Stucki in aggressiveness.
    "shiaufan": [
        (0, 1, 8 / 42), (0, 2, 4 / 42),
        (1, -2, 2 / 42), (1, -1, 4 / 42), (1, 0, 8 / 42), (1, 1, 4 / 42), (1, 2, 2 / 42),
        (2, -2, 1 / 42), (2, -1, 2 / 42), (2, 0, 4 / 42), (2, 1, 2 / 42), (2, 2, 1 / 42),
    ],
    # Filter Lite: super fast (2 taps), fine halftone-like grain.
    "filterlite": [(0, 1, 7 / 8), (1, 0, 1 / 8)],
    # Sierra Lite: the classic 2-row minimum (divisor 4).
    "sierralite": [(0, 1, 2 / 4), (1, -1, 1 / 4), (1, 0, 1 / 4)],
    # Full 3-row Sierra-3 (divisor 32), the smoothest of the line.
    "sierra3": [
        (0, 1, 5 / 32), (0, 2, 3 / 32),
        (1, -2, 2 / 32), (1, -1, 4 / 32), (1, 0, 5 / 32), (1, 1, 4 / 32), (1, 2, 2 / 32),
        (2, -1, 2 / 32), (2, 0, 3 / 32), (2, 1, 2 / 32),
    ],
}

ED_METHODS = (
    "floyd", "atkinson", "burkes", "sierra", "jjn", "stucki", "stevenson",
    "shiaufan", "filterlite", "sierralite", "sierra3",
)


from app.accelerate import coeffs_to_arrays, ed_bw, ed_color, has_numba

BACKENDS = ("auto", "numpy", "numba")


def _backend(name: str) -> str:
    if name not in BACKENDS:
        return "auto"
    if name == "numba" and not has_numba():
        raise RuntimeError("numba not installed: pip install numba")
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
    # Numpy fallback: palette as array + vectorized per-row search.
    # Before: double python loop (y,x) + python loop over palette -> ~50x slower.
    pc = np.asarray(palette, dtype=np.float32)  # (P, 3)
    h, w, _ = arr.shape
    max_dy = max(dy for dy, _, _ in coeffs)
    for y in range(h):
        row = arr[y]
        nxt = [arr[y + k] if y + k < h else None for k in range(1, max_dy + 1)]
        for x in range(w):
            px = row[x]  # view (3,)
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


# ---------------------------------------------------------------------------
# Hilbert-ordered diffusion (Riemersma-style). Walks the image along a
# Hilbert curve instead of rows: the error spreads to the next
# pixels of the curve (Floyd fractions). No horizontal streaks.
# ---------------------------------------------------------------------------

_HILBERT_CACHE: dict[tuple[int, int], np.ndarray] = {}
_HILBERT_CHUNK = 1 << 18  # 256k-point chunks: bounded memory (~12MB)


def _d2xy_chunk(d: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    """Hilbert distance -> (x, y). Vectorized (public d2xy algorithm)."""
    x = np.zeros_like(d)
    y = np.zeros_like(d)
    s = 1
    t = d.copy()
    while s < n:
        rx = (t // 2) & 1
        ry = (t ^ rx) & 1
        m0 = ry == 0
        m1 = m0 & (rx == 1)
        x = np.where(m1, s - 1 - x, x)
        y = np.where(m1, s - 1 - y, y)
        nx = np.where(m0, y, x)
        ny = np.where(m0, x, y)
        x, y = nx, ny
        x = x + s * rx
        y = y + s * ry
        t //= 4
        s *= 2
    return x, y


def hilbert_order(h: int, w: int) -> np.ndarray:
    """Flat (y*w+x) indices in Hilbert order. Cached by size."""
    key = (int(h), int(w))
    cached = _HILBERT_CACHE.get(key)
    if cached is not None:
        return cached
    n = 1
    while n < max(h, w):
        n *= 2
    parts: list[np.ndarray] = []
    for start in range(0, n * n, _HILBERT_CHUNK):
        d = np.arange(start, min(start + _HILBERT_CHUNK, n * n), dtype=np.int64)
        xs, ys = _d2xy_chunk(d, n)
        ok = (xs < w) & (ys < h)
        parts.append((ys[ok].astype(np.int64) * w + xs[ok].astype(np.int64)))
    order = np.concatenate(parts) if parts else np.zeros(0, dtype=np.int64)
    if len(_HILBERT_CACHE) >= 4:
        _HILBERT_CACHE.pop(next(iter(_HILBERT_CACHE)))
    _HILBERT_CACHE[key] = order
    return order


# Floyd fractions to the next 4 of the curve (sum to 1).
_HILBERT_WTS = (7 / 16, 3 / 16, 5 / 16, 1 / 16)


def diffuse_hilbert(
    arr: np.ndarray,
    palette: list[tuple] | None,
    threshold: float = 128.0,
) -> np.ndarray:
    """Diffuse in Hilbert order. arr float32 (H,W) gray or (H,W,3) RGB.

    Returns uint8. Sequential by construction (like all ED): for
    large full-res, numba is recommended in the other engines; here the
    numpy-vectorized walk makes up for the order.
    """
    order = hilbert_order(arr.shape[0], arr.shape[1])
    n = len(order)
    if palette is None:
        buf = np.array(arr, dtype=np.float32).reshape(-1).copy()
        t = float(threshold)
        out = np.empty(n, dtype=np.uint8)
        wts = _HILBERT_WTS
        for pos in range(n):
            idx = int(order[pos])
            old = float(buf[idx])
            new = 255.0 if old > t else 0.0
            out[pos] = 255 if new > 127 else 0
            buf[idx] = new
            err = old - new
            if err:
                for k in range(1, 5):
                    j = pos + k
                    if j < n:
                        buf[int(order[j])] += err * wts[k - 1]
        res = np.empty_like(buf, dtype=np.uint8)
        res[order] = out
        h, w = arr.shape[:2]
        return res.reshape(h, w)
    pc = np.asarray(palette, dtype=np.float32)
    buf = np.array(arr, dtype=np.float32).reshape(-1, 3).copy()
    out = np.empty((n, 3), dtype=np.uint8)
    wts = _HILBERT_WTS
    for pos in range(n):
        idx = int(order[pos])
        px = buf[idx]
        r0, g0, b0 = float(px[0]), float(px[1]), float(px[2])
        d = np.sum((pc - px) ** 2, axis=1)
        best = int(np.argmin(d))
        nr, ng, nb = float(pc[best, 0]), float(pc[best, 1]), float(pc[best, 2])
        out[pos] = (nr, ng, nb)
        buf[idx] = (nr, ng, nb)
        er, eg, eb = r0 - nr, g0 - ng, b0 - nb
        if er or eg or eb:
            for k in range(1, 5):
                j = pos + k
                if j < n:
                    tgt = buf[int(order[j])]
                    tgt[0] += er * wts[k - 1]
                    tgt[1] += eg * wts[k - 1]
                    tgt[2] += eb * wts[k - 1]
    res = np.empty_like(buf)
    res[order] = out.astype(np.float32)
    h, w = arr.shape[:2]
    return np.clip(res.reshape(h, w, 3), 0, 255).astype(np.uint8)
