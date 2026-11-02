"""Optional TRAKKART accelerator (MIT).

If numba is installed, ED kernels use @njit (10-50x). Otherwise,
automatic fallback to pure numpy. numba imports LAZILY (P1): the
0.4s import cost moves from startup to the first ED render (which
compiles anyway), so the app opens fast everywhere.
"""

from __future__ import annotations

import threading

import numpy as np

_NUMBA = None  # None = undecided (probe on first use); tests may force True/False
_compiled: dict[str, object] = {}
_lock = threading.Lock()


def has_numba() -> bool:
    """Cached import probe (one import ever; monkeypatchable via _NUMBA)."""
    global _NUMBA
    if _NUMBA is None:
        try:
            import numba  # noqa: F401

            _NUMBA = True
        except ImportError:
            _NUMBA = False
    return bool(_NUMBA)


def _ed_bw_impl(lum, dys, dxs, wts, threshold):
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


def _ed_color_impl(arr, pal, dys, dxs, wts):
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


_IMPLS = {"bw": _ed_bw_impl, "color": _ed_color_impl}


def _dispatch(name: str, args: tuple):
    """njit-compiled impl (cached, first ED render) or pure python fallback."""
    if not has_numba():
        return _IMPLS[name](*args)
    fn = _compiled.get(name)
    if fn is None:
        with _lock:
            fn = _compiled.get(name)
            if fn is None:
                from numba import njit

                fn = njit(_IMPLS[name], cache=True, nogil=True)
                _compiled[name] = fn
    return fn(*args)


def ed_bw(lum, dys, dxs, wts, threshold):
    """B&W diffusion entry point (numba when present, else pure python)."""
    return _dispatch("bw", (lum, dys, dxs, wts, threshold))


def ed_color(arr, pal, dys, dxs, wts):
    """Palette diffusion entry point (numba when present, else pure python)."""
    return _dispatch("color", (arr, pal, dys, dxs, wts))


def coeffs_to_arrays(coeffs: list[tuple[int, int, float]]):
    """Convert [(dy,dx,w),...] tables to numpy arrays for njit."""
    dys = np.array([c[0] for c in coeffs], dtype=np.int64)
    dxs = np.array([c[1] for c in coeffs], dtype=np.int64)
    wts = np.array([c[2] for c in coeffs], dtype=np.float64)
    return dys, dxs, wts


__all__ = ["coeffs_to_arrays", "ed_bw", "ed_color", "has_numba"]
