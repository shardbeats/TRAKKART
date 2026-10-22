"""TRAKKART render params — shared normalizations.

The Preset -> render conversion lives in `pipeline.RenderSpec.from_preset`
(this module delegates to it to avoid duplicating the ~40-param list).
The normalizers left here (scanlines/slice/grille/halftone/posterize)
are used by the UI and presets.
"""

from __future__ import annotations

from typing import Any

# Valid values (the UI allows intermediates that get normalized).
VALID_SCANLINES = (0, 2, 3, 4, 6, 8)
VALID_SLICE_BANDS = (0, 2, 3, 4, 6, 8, 12, 16)

# Invalid scan -> nearest valid (used by QSpinBox 0-8).
_SCAN_FIX = {1: 2, 5: 4, 7: 6}
# Invalid slice -> valid (used by QSpinBox 0-16).
_SLICE_FIX = {1: 2, 5: 4, 7: 6, 9: 8, 10: 8, 11: 12, 13: 12, 14: 16, 15: 16}


def normalize_scanlines(value: int) -> int:
    """0,2,3,4,6,8 are valid; 1->2, 5->4, 7->6."""
    v = int(value)
    if v in VALID_SCANLINES:
        return v
    return _SCAN_FIX.get(v, 0)


def normalize_slice_bands(value: int) -> int:
    """0,2,3,4,6,8,12,16 valid; the rest rounds to the nearest valid."""
    v = int(value)
    if v in VALID_SLICE_BANDS:
        return v
    if v in _SLICE_FIX:
        return _SLICE_FIX[v]
    if v < 9:
        return 8
    if v < 14:
        return 12
    return 16


def normalize_grille(value: int) -> int:
    """RGB grille: only 0 (off), 2, 3. 1->2 like scanlines."""
    v = int(value)
    if v in (0, 2, 3):
        return v
    return 2 if v == 1 else 0


def normalize_halftone(value: int) -> int:
    """Halftone: 0 = off, else 3-12 cells (1,2 -> 3)."""
    v = int(value)
    if v <= 0:
        return 0
    return min(12, max(3, v))


def normalize_posterize(value: int) -> int:
    """Posterize: 0 = off, else 2-8 levels (1 -> 2)."""
    v = int(value)
    if v <= 0:
        return 0
    return min(8, max(2, v))


def normalize_palette_depth(value: int) -> int:
    """Depth: 0 = off (full palette), else 2-16 (1 -> 2)."""
    v = int(value)
    if v <= 0:
        return 0
    return min(16, max(2, v))


def apply_palette_depth(palette: list | None | str, depth: int) -> list | None | str:
    """Truncate a palette to `depth` colors (luminance-even sampling).

    depth 0 / None sentinel / shorter-than-depth -> unchanged.
    Keeps dark->light order so ramps stay ramps.
    """
    d = normalize_palette_depth(int(depth or 0))
    if d <= 0 or palette is None or isinstance(palette, str):
        return palette
    pal = list(palette)
    if d >= len(pal):
        return pal
    import numpy as np

    arr = np.asarray(pal, dtype=np.float64)
    lum = 0.299 * arr[:, 0] + 0.587 * arr[:, 1] + 0.114 * arr[:, 2]
    order = np.argsort(lum, kind="stable")
    sorted_pal = [pal[i] for i in order]
    if d == 1:
        return [sorted_pal[len(sorted_pal) // 2]]
    idx = [round(i * (len(sorted_pal) - 1) / (d - 1)) for i in range(d)]
    return [sorted_pal[i] for i in idx]


def preset_to_render_kwargs(preset: Any, phase: int = 0) -> dict:
    """Converts a Preset to `pipeline.render()` kwargs.

    Accepts duck-typing (does not import Preset to avoid cycles).
    Delegates to RenderSpec.from_preset: normalization lives in a
    single place (batch, UI, GIF and worker produce exactly the same).
    """
    from app.pipeline import RenderSpec

    return RenderSpec.from_preset(preset, phase=phase).as_kwargs()


__all__ = [
    "VALID_SCANLINES",
    "VALID_SLICE_BANDS",
    "apply_palette_depth",
    "normalize_palette_depth",
    "normalize_scanlines",
    "normalize_slice_bands",
    "normalize_grille",
    "normalize_halftone",
    "normalize_posterize",
    "preset_to_render_kwargs",
]
