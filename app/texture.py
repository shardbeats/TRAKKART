"""TRAKKART texture/decay pack (MIT, clean-room). Post-dither, determinista.

Halftone de puntos/lineas (estilo imprenta, distinto del dither del motor),
dust & scratches con seed fija, borde solido y letterbox cinematografico.
"""

from __future__ import annotations

import numpy as np
from PIL import Image


def _rgb(img: Image.Image) -> Image.Image:
    return img.convert("RGB")


def halftone(img: Image.Image, cell: int = 0, shape: str = "dots") -> Image.Image:
    """Trama de imprenta sobre la imagen. 0 = off; cell 3-12px.

    Dots: umbral radial por celda. Lines: umbral por columnas (rayado).
    """
    c = int(cell)
    if c < 3:
        return img
    c = min(12, c)
    arr = np.asarray(_rgb(img), dtype=np.float32)
    h, w = arr.shape[:2]
    lum = (0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]) / 255.0
    if shape == "lines":
        phase = (np.arange(w, dtype=np.float32) % c) / c  # 0..1 por columna
        mask = (phase[None, :] < lum).astype(np.float32)
    else:  # dots: distancia al centro de cada celda
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        dx = (xx % c) / c - 0.5
        dy = (yy % c) / c - 0.5
        r = np.sqrt(dx * dx + dy * dy) * np.sqrt(2.0)  # 0 centro .. 1 esquina
        mask = (r < lum * 1.05).astype(np.float32)
    out = np.where(mask[..., None] > 0, arr, 0.0)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def dust(img: Image.Image, amount: float = 0.0, seed: int = 0xD57) -> Image.Image:
    """Polvo y arañazos: motas claras/oscuras aleatorias. 0 = off."""
    a = float(amount)
    if a <= 0:
        return img
    p = min(0.02, a / 100.0 * 0.02)  # hasta 2% de píxeles
    rng = np.random.default_rng(int(seed))
    arr = np.array(_rgb(img))
    h, w = arr.shape[:2]
    n = int(h * w * p)
    if n <= 0:
        return img
    ys = rng.integers(0, h, n)
    xs = rng.integers(0, w, n)
    vals = np.where(rng.random(n) < 0.5, 0, 255).astype(np.uint8)
    out = arr.copy()
    out[ys, xs] = vals[:, None]
    # Arañazos: un puñado de rayas verticales tenues.
    for _ in range(int(a // 20)):
        x = int(rng.integers(0, w))
        y0 = int(rng.integers(0, h))
        ln = int(rng.integers(h // 8, h // 3))
        v = 255 if rng.random() < 0.5 else 0
        out[y0:min(h, y0 + ln), max(0, x - 1):min(w, x + 1)] = v
    return Image.fromarray(out)


def _parse_hex(color: str) -> tuple[int, int, int]:
    s = (color or "").strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"not #RRGGBB: {color!r}")
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        raise ValueError(f"not #RRGGBB: {color!r}") from None


def border(img: Image.Image, px: int = 0, color: str = "#000000") -> Image.Image:
    """Marco sólido alrededor (estilo póster). 0 = off."""
    b = int(px)
    if b <= 0:
        return img
    b = min(64, b)
    rgb = _parse_hex(color)
    out = Image.new("RGB", (img.width + 2 * b, img.height + 2 * b), rgb)
    out.paste(img.convert("RGB"), (b, b))
    return out


def letterbox(img: Image.Image, pct: int = 0) -> Image.Image:
    """Barras negras de cine arriba/abajo. pct 0 = off, % de alto por lado."""
    p = int(pct)
    if p <= 0:
        return img
    p = min(25, p)
    arr = np.array(_rgb(img))
    h = arr.shape[0]
    bar = max(1, round(h * p / 100.0))
    out = arr.copy()
    out[:bar] = 0
    out[h - bar:] = 0
    return Image.fromarray(out)


__all__ = ["halftone", "dust", "border", "letterbox"]
