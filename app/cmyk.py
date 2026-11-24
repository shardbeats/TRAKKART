"""TRAKKART CMYK halftone (GPL-3.0-only). Numpy + Pillow only.

Simplified print-style halftone: RGB -> CMY + K, each channel screened
with an angled Bayer threshold, then back to RGB. Deterministic;
`phase` rotates screens so it animates (marching dots) like the other
ordered maps. `rosette` picks the screen-offset assignment (standard
C15/M75/Y0/K45, alt swapped, single aligned); `lpi` sizes the dot cell
from the document DPI (cell = dpi/lpi, clamped 2-64px), 0 = legacy
fixed 8px cell.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

#: Named screen-offset assignments (rolls of the Bayer tile per C/M/Y/K).
ROSETTES: dict[str, tuple[int, int, int, int]] = {
    "standard": (0, 13, 29, 47),  # classic rosette, legacy output
    "alt": (47, 29, 13, 0),  # reversed assignment, different moire
    "single": (0, 0, 0, 0),  # aligned screens, no rosette
}


def rosette_shifts(name: str) -> tuple[int, int, int, int]:
    """Shifts for a rosette name (unknown -> standard, legacy compat)."""
    return ROSETTES.get(str(name or "").lower(), ROSETTES["standard"])


def cell_for_lpi(lpi: int, dpi: int = 300) -> int:
    """Dot cell in px for a print ruling (0/negative = legacy fixed 8px)."""
    lpi, dpi = int(lpi or 0), max(72, min(600, int(dpi or 300)))
    if lpi <= 0:
        return 8
    return max(2, min(64, round(dpi / max(1, lpi))))


def _bayer8() -> np.ndarray:
    from app.ordered_maps import BAYER_8X8

    return BAYER_8X8


def _screened(channel: np.ndarray, shift: int, phase: int = 0,
              cell: int = 8) -> np.ndarray:
    """Halftone one 0-255 channel: threshold with offset Bayer of cell px."""
    import numpy as _np

    m = _bayer8()
    if cell != 8:
        m = _np.asarray(Image.fromarray(m).resize((cell, cell), Image.NEAREST))
    # Angles simulated by a different roll per channel (cheap and deterministic).
    tiled = _np.tile(m, ((channel.shape[0] + cell - 1) // cell,
                         (channel.shape[1] + cell - 1) // cell))[:channel.shape[0], :channel.shape[1]]
    tiled = _np.roll(tiled, int(shift) + int(phase), axis=(0, 1))
    thr = tiled / 64.0 * 255.0
    return _np.where(channel > thr, 255.0, 0.0)


def cmyk_halftone(img: Image.Image, threshold: float = 128.0, phase: int = 0,
                  pixel_size: int = 1, rosette: str = "standard",
                  lpi: int = 0, dpi: int = 300) -> Image.Image:
    """CMYK-style halftone -> RGB. threshold = dot gain (global offset)."""
    base = img.convert("RGB")
    if pixel_size > 1:
        sw = max(1, base.width // pixel_size)
        sh = max(1, base.height // pixel_size)
        base = base.resize((sw, sh), Image.NEAREST)
    shifts = rosette_shifts(rosette)
    cell = cell_for_lpi(lpi, dpi)
    arr = np.asarray(base, dtype=np.float32)
    gain = (float(threshold) - 128.0) * 0.8  # +/-102 around neutral
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    k = 255.0 - np.maximum(np.maximum(r, g), b)
    c = (255.0 - r - k)
    m = (255.0 - g - k)
    y = (255.0 - b - k)
    c = np.clip(c + gain, 0, 255)
    m = np.clip(m + gain, 0, 255)
    y = np.clip(y + gain, 0, 255)
    k = np.clip(k + gain, 0, 255)
    cs = _screened(c, shifts[0], phase, cell) / 255.0
    ms = _screened(m, shifts[1], phase, cell) / 255.0
    ys = _screened(y, shifts[2], phase, cell) / 255.0
    ks = _screened(k, shifts[3], phase, cell) / 255.0
    # Multiplicative over white paper (simplified overprint).
    rr = 255.0 * (1.0 - cs) * (1.0 - ks)
    gg = 255.0 * (1.0 - ms) * (1.0 - ks)
    bb = 255.0 * (1.0 - ys) * (1.0 - ks)
    out = np.stack([rr, gg, bb], axis=-1).clip(0, 255).astype(np.uint8)
    res = Image.fromarray(out, mode="RGB")
    if pixel_size > 1:
        res = res.resize((res.width * pixel_size, res.height * pixel_size), Image.NEAREST)
    return res


__all__ = ["ROSETTES", "cell_for_lpi", "cmyk_halftone", "rosette_shifts"]
