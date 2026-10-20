"""TRAKKART render params — normalizaciones compartidas.

La conversión Preset -> render vive en `pipeline.RenderSpec.from_preset`
(este módulo delega en él para no duplicar la lista de ~40 params).
Aquí quedan los normalizadores (scanlines/slice/grille/halftone/posterize)
usados por UI y presets.
"""

from __future__ import annotations

from typing import Any

# Valores válidos (la UI permite intermedios que se normalizan).
VALID_SCANLINES = (0, 2, 3, 4, 6, 8)
VALID_SLICE_BANDS = (0, 2, 3, 4, 6, 8, 12, 16)

# scan inválido -> válido más cercano (usado por QSpinBox 0-8).
_SCAN_FIX = {1: 2, 5: 4, 7: 6}
# slice inválido -> válido (usado por QSpinBox 0-16).
_SLICE_FIX = {1: 2, 5: 4, 7: 6, 9: 8, 10: 8, 11: 12, 13: 12, 14: 16, 15: 16}


def normalize_scanlines(value: int) -> int:
    """0,2,3,4,6,8 son válidos; 1->2, 5->4, 7->6."""
    v = int(value)
    if v in VALID_SCANLINES:
        return v
    return _SCAN_FIX.get(v, 0)


def normalize_slice_bands(value: int) -> int:
    """0,2,3,4,6,8,12,16 válidos; el resto se redondea al válido cercano."""
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
    """RGB grille: solo 0 (off), 2, 3. 1->2 como scanlines."""
    v = int(value)
    if v in (0, 2, 3):
        return v
    return 2 if v == 1 else 0


def normalize_halftone(value: int) -> int:
    """Halftone: 0 = off, si no celdas 3-12 (1,2 -> 3)."""
    v = int(value)
    if v <= 0:
        return 0
    return min(12, max(3, v))


def normalize_posterize(value: int) -> int:
    """Posterize: 0 = off, si no niveles 2-8 (1 -> 2)."""
    v = int(value)
    if v <= 0:
        return 0
    return min(8, max(2, v))


def normalize_palette_depth(value: int) -> int:
    """Depth: 0 = off (full palette), si no 2-16 (1 -> 2)."""
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
    """Convierte un Preset a kwargs de `pipeline.render()`.

    Acepta duck-typing (no importa Preset para evitar ciclos).
    Delega en RenderSpec.from_preset: la normalización vive en un
    solo sitio (batch, UI, GIF y worker producen exactamente lo mismo).
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
