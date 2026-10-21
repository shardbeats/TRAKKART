"""Optional TRAKKART accelerator (MIT, clean-room).

If numba is installed, ED kernels use @njit (10-50x). Otherwise,
automatic fallback to pure numpy. The base exe does NOT bundle numba.
"""

from __future__ import annotations

import numpy as np

try:
    from numba import njit, prange  # noqa: F401

    _NUMBA = True
except ImportError:  # pragma: no cover - environment without numba
    _NUMBA = False

    def njit(*args, **kwargs):  # type: ignore[no-redef]
        def decorator(fn):
            return fn

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

    prange = range  # type: ignore[no-redef]


def has_numba() -> bool:
    return _NUMBA


@njit(cache=True, nogil=True)
def ed_bw(lum, dys, dxs, wts, threshold):  # pragma: no cover - numba nopython: invisible to coverage.py, verified by parity tests
    """B&W diffusion over float32 in-place. Returns uint8 0/255."""
    h, w = lum.shape
    n = dys.shape[0]
    for y in range(h):
        for x in range(w):
            old = np.float64(lum[y, x])
            new = 255.0 if old > threshold else 0.0
            lum[y, x] = new
            err = old - new
            for k in range(n):
                nx = x + dxs[k]
                ny = y + dys[k]
                if 0 <= nx < w and ny < h:
                    # Emulate numpy: float32 += python-float (f64 product, f32 add)
                    lum[ny, nx] = np.float32(lum[ny, nx] + np.float32(err * wts[k]))
    out = np.empty((h, w), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            v = lum[y, x]
            out[y, x] = 255 if v > 254.5 else (0 if v < 0.5 else np.uint8(v + 0.5))
    return out


@njit(cache=True, nogil=True)
def ed_color(arr, pal, dys, dxs, wts):  # pragma: no cover - numba nopython: invisible to coverage.py, verified by parity tests
    """Palette diffusion over float32 in-place. Returns uint8 RGB."""
    h, w, _ = arr.shape
    p = pal.shape[0]
    n = dys.shape[0]
    for y in range(h):
        for x in range(w):
            r0 = np.float64(arr[y, x, 0])
            g0 = np.float64(arr[y, x, 1])
            b0 = np.float64(arr[y, x, 2])
            best = 0
            bd = 1e30
            for i in range(p):
                dr = r0 - pal[i, 0]
                dg = g0 - pal[i, 1]
                db = b0 - pal[i, 2]
                d = dr * dr + dg * dg + db * db
                if d < bd:
                    bd = d
                    best = i
            nr = np.float64(pal[best, 0])
            ng = np.float64(pal[best, 1])
            nb = np.float64(pal[best, 2])
            arr[y, x, 0] = nr
            arr[y, x, 1] = ng
            arr[y, x, 2] = nb
            er = r0 - nr
            eg = g0 - ng
            eb = b0 - nb
            for k in range(n):
                nx = x + dxs[k]
                ny = y + dys[k]
                if 0 <= nx < w and ny < h:
                    arr[ny, nx, 0] = np.float32(arr[ny, nx, 0] + np.float32(er * wts[k]))
                    arr[ny, nx, 1] = np.float32(arr[ny, nx, 1] + np.float32(eg * wts[k]))
                    arr[ny, nx, 2] = np.float32(arr[ny, nx, 2] + np.float32(eb * wts[k]))
    out = np.empty((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            for c in range(3):
                v = arr[y, x, c]
                out[y, x, c] = 255 if v > 254.5 else (0 if v < 0.5 else np.uint8(v + 0.5))
    return out


def coeffs_to_arrays(coeffs: list[tuple[int, int, float]]):
    """Convert [(dy,dx,w),...] tables to numpy arrays for njit."""
    dys = np.array([c[0] for c in coeffs], dtype=np.int64)
    dxs = np.array([c[1] for c in coeffs], dtype=np.int64)
    wts = np.array([c[2] for c in coeffs], dtype=np.float64)
    return dys, dxs, wts
