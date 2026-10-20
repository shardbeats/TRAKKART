"""TRAKKART render params — single source of truth.

Antes: `MainWindow._render_kwargs()`, `MainWindow.current_params()`,
`PreviewWorker.current_params_snapshot()`, `batch._render_one()`,
`gif.gif_frames()` y `pipeline.meta_dict()` duplicaban la misma lista
de ~25 parámetros. Cualquier cambio había que hacerlo en 6 sitios.

Ahora: `Preset.to_render_kwargs()` (vía `preset_to_render_kwargs()`)
es la única conversión Preset -> kwargs de `pipeline.render()`.
Las normalizaciones de scanlines/slice también viven aquí.
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


def preset_to_render_kwargs(preset: Any, phase: int = 0) -> dict:
    """Convierte un Preset a kwargs de `pipeline.render()`.

    Acepta duck-typing (no importa Preset para evitar ciclos).
    Normaliza scanlines/slice para que batch, UI, GIF y worker
    produzcan exactamente lo mismo.
    """
    return {
        "method": preset.method,
        "palette_name": preset.palette,
        "threshold": float(preset.threshold),
        "pixel_size": int(preset.pixel_size),
        "adjust": preset.adjust(),
        "ratio": preset.ratio,
        "crop_mode": preset.crop_mode,
        "focus_x": float(preset.focus_x),
        "focus_y": float(preset.focus_y),
        "crop_zoom": float(preset.crop_zoom),
        "pre_blur": float(preset.pre_blur),
        "pre_sharpen": int(preset.pre_sharpen),
        "pre_hue": float(preset.pre_hue),
        "pre_denoise": int(preset.pre_denoise),
        "pre_smooth": float(preset.pre_smooth),
        "glow_radius": float(preset.glow_radius),
        "glow_intensity": float(preset.glow_intensity),
        "grain": float(preset.grain),
        "vignette": float(preset.vignette),
        "scanlines": normalize_scanlines(int(preset.scanlines)),
        "replace_color": preset.replace_color,
        "custom_palette": preset.custom_palette,
        "phase": int(phase),
        "glitch_chroma": int(preset.glitch_chroma),
        "glitch_slice_bands": normalize_slice_bands(int(preset.glitch_slice_bands)),
        "glitch_slice_max": int(preset.glitch_slice_max),
        "duotone_dark": str(getattr(preset, "duotone_dark", "")),
        "duotone_light": str(getattr(preset, "duotone_light", "")),
        "duotone_mid": float(getattr(preset, "duotone_mid", 50.0)),
        "posterize": normalize_posterize(int(getattr(preset, "posterize", 0))),
        "split_tone": float(getattr(preset, "split_tone", 0.0)),
        "fade": float(getattr(preset, "fade", 0.0)),
        "glow_threshold": int(getattr(preset, "glow_threshold", 0)),
        "halftone": normalize_halftone(int(getattr(preset, "halftone", 0))),
        "halftone_shape": str(getattr(preset, "halftone_shape", "dots")),
        "dust": float(getattr(preset, "dust", 0.0)),
        "border": int(getattr(preset, "border", 0)),
        "border_color": str(getattr(preset, "border_color", "#000000")),
        "letterbox": int(getattr(preset, "letterbox", 0)),
        "pixelsort": int(getattr(preset, "pixelsort", 0)),
        "wave": int(getattr(preset, "wave", 0)),
        "mosh": float(getattr(preset, "mosh", 0.0)),
        "grille": normalize_grille(int(getattr(preset, "grille", 0))),
    }


__all__ = [
    "VALID_SCANLINES",
    "VALID_SLICE_BANDS",
    "normalize_scanlines",
    "normalize_slice_bands",
    "normalize_grille",
    "normalize_halftone",
    "normalize_posterize",
    "preset_to_render_kwargs",
]
