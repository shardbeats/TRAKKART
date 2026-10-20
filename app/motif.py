"""TRAKKART Motif engine (MIT, clean-room). Numpy only.

Custom pattern builder: 4 luminance bands (shadows / mids / lights / brights)
each map to a shape + size. Builds a 32x32 threshold matrix tiled by
dither.ordered(); saved inside the preset as a plain dict (offline share
safe). Deterministic; `phase` rolls the matrix (animates).

Band config: {"bands": [{"shape": str, "size": int 1-4}, x4]}.
Shapes: dot | line | cross | square | ring | diag. Unknown -> dot.
"""

from __future__ import annotations

import numpy as np

SHAPES = ("dot", "line", "cross", "square", "ring", "diag")
BAND_NAMES = ("shadows", "mids", "lights", "brights")


def default_config() -> dict:
    return {"bands": [
        {"shape": "dot", "size": 2},
        {"shape": "line", "size": 2},
        {"shape": "cross", "size": 2},
        {"shape": "square", "size": 2},
    ]}


def normalize_config(raw: dict | None) -> dict:
    cfg = {"bands": []}
    bands = (raw or {}).get("bands", []) if isinstance(raw, dict) else []
    for i in range(4):
        try:
            b = bands[i] if i < len(bands) else {}
        except (TypeError, IndexError):
            b = {}
        shape = str(b.get("shape", default_config()["bands"][i]["shape"]))
        if shape not in SHAPES:
            shape = "dot"
        try:
            size = max(1, min(4, int(b.get("size", 2))))
        except (TypeError, ValueError):
            size = 2
        cfg["bands"].append({"shape": shape, "size": size})
    return cfg


def _shape_tile(shape: str, size: int, n: int = 8) -> np.ndarray:
    """8x8 tile 0-255 para una forma (size 1-4 = grosor/densidad)."""
    t = np.zeros((n, n), dtype=np.float32)
    s = max(1, min(4, int(size)))
    if shape == "dot":
        r = s  # radio en celdas
        c = n // 2
        ys, xs = np.mgrid[0:n, 0:n]
        t = ((xs - c + 0.5) ** 2 + (ys - c + 0.5) ** 2 <= r * r).astype(np.float32) * 255.0
    elif shape == "line":
        t[::max(1, 5 - s), :] = 255.0  # horizontales cada 4..1 filas
    elif shape == "cross":
        t[n // 2 - s + 1:n // 2 + s, :] = 200.0
        t[:, n // 2 - s + 1:n // 2 + s] = 255.0
    elif shape == "square":
        t[:s, :] = t[-s:, :] = t[:, :s] = t[:, -s:] = 255.0
        t[1:-1, 1:-1] = np.maximum(t[1:-1, 1:-1],
                                   _shape_tile("dot", s, n)[1:-1, 1:-1] * 0.5)
    elif shape == "ring":
        c = n // 2
        ys, xs = np.mgrid[0:n, 0:n]
        d = np.sqrt((xs - c + 0.5) ** 2 + (ys - c + 0.5) ** 2)
        t = ((np.abs(d - (s + 1.0)) < 0.9)).astype(np.float32) * 255.0
    elif shape == "diag":
        ys, xs = np.mgrid[0:n, 0:n]
        t = ((((xs + ys) // max(1, 5 - s)) % 2) == 0).astype(np.float32) * 255.0
    return t


def build_matrix(config: dict | None, n: int = 32) -> np.ndarray:
    """32x32 matrix: cada cuadrante 16x16 = una banda (orden oscuridad)."""
    cfg = normalize_config(config)
    mat = np.zeros((n, n), dtype=np.float32)
    half = n // 2
    for i, band in enumerate(cfg["bands"]):
        tile = _shape_tile(band["shape"], band["size"], 8)
        reps = (half + 7) // 8
        big = np.tile(tile, (reps, reps))[:half, :half]
        # Nivel base por banda (sombras = umbral bajo ... brillos = alto).
        level = (i + 1) / 4.0 * 160.0 + 40.0  # 80, 120, 160, 200
        quad = np.clip(big * 0.35 + level, 0, 255)
        y0, x0 = (i // 2) * half, (i % 2) * half
        mat[y0:y0 + half, x0:x0 + half] = quad
    return mat


__all__ = ["BAND_NAMES", "SHAPES", "build_matrix", "default_config", "normalize_config"]
