"""TRAKKART pipeline: canvas -> pre -> grade -> dither -> brand -> post.

Orden (signal chain): los adjustments y el grade van ANTES del dither
sobre tono continuo; textura y glitch van después sobre el dither.
"""

from __future__ import annotations

from PIL import Image

from app.adjust import Adjust
from app.canvas import to_canvas
from app.dither import apply_method
from app.fx import (
    apply_glow,
    apply_grain,
    apply_pre,
    apply_scanlines,
    apply_vignette,
    normalize_custom_palette,
    replace_white,
)
from app.glitch import (
    chromatic_aberration,
    datamosh,
    pixel_sort,
    rgb_grille,
    slice_shift,
)
from app.glitch import wave as _glitch_wave
from app.grade import fade as _grade_fade
from app.grade import gradient_map
from app.grade import posterize as _grade_posterize
from app.grade import split_tone as _grade_split_tone
from app.palettes import get_palette
from app.texture import border as _frame_border
from app.texture import dust as _grain_dust
from app.texture import halftone as _halftone_dots
from app.texture import letterbox as _cine_bars


def resolve_palette(palette_name: str, custom: list | None):
    from app.palette_library import is_bw

    custom_pal = normalize_custom_palette(custom)
    if custom_pal is not None:
        if is_bw(custom_pal):
            return None, "BW"  # equivale al B&W puro: ruta rápida, sin ramas en la UI
        return custom_pal, "custom"
    return get_palette(palette_name), palette_name


def render(
    img: Image.Image,
    method: str = "bayer4",
    palette_name: str = "SLIME",
    threshold: float = 128.0,
    pixel_size: int = 1,
    adjust: Adjust | dict | None = None,
    ratio: str = "1:1",
    crop_mode: str = "cover",
    focus_x: float = 50.0,
    focus_y: float = 50.0,
    crop_zoom: float = 1.0,
    pre_blur: float = 0.0,
    pre_sharpen: int = 0,
    pre_hue: float = 0.0,
    pre_denoise: int = 0,
    pre_smooth: float = 0.0,
    glow_radius: float = 0.0,
    glow_intensity: float = 0.0,
    grain: float = 0.0,
    vignette: float = 0.0,
    scanlines: int = 0,
    replace_color: str = "",
    custom_palette: list | None = None,
    phase: int = 0,
    glitch_chroma: int = 0,
    glitch_slice_bands: int = 0,
    glitch_slice_max: int = 24,
    duotone_dark: str = "",
    duotone_light: str = "",
    duotone_mid: float = 50.0,
    posterize: int = 0,
    split_tone: float = 0.0,
    fade: float = 0.0,
    glow_threshold: int = 0,
    halftone: int = 0,
    halftone_shape: str = "dots",
    dust: float = 0.0,
    border: int = 0,
    border_color: str = "#000000",
    letterbox: int = 0,
    pixelsort: int = 0,
    wave: int = 0,
    mosh: float = 0.0,
    grille: int = 0,
) -> Image.Image:
    """Pipeline completo: canvas -> pre -> grade -> dither -> brand -> post.

    Cada etapa con valor neutro se salta (las funciones ya tienen
    early-return, aquí se hace explícito para legibilidad y evitar
    llamadas numpy innecesarias).
    """
    canvas = to_canvas(img, ratio=ratio, mode=crop_mode, fx=focus_x, fy=focus_y,
                       zoom=crop_zoom)
    if pre_blur or pre_sharpen or pre_hue or pre_denoise or pre_smooth:
        canvas = apply_pre(canvas, blur=pre_blur, sharpen=pre_sharpen, hue=pre_hue,
                           denoise=pre_denoise, smooth=pre_smooth)
    if duotone_dark or duotone_light:
        canvas = gradient_map(canvas, color_dark=duotone_dark, color_light=duotone_light,
                              mid=float(duotone_mid))
    if posterize:
        canvas = _grade_posterize(canvas, levels=int(posterize))
    pal, _ = resolve_palette(palette_name, custom_palette)
    dithered = apply_method(
        canvas,
        method=method,
        palette=pal,
        threshold=float(threshold),
        pixel_size=int(pixel_size),
        adjust=adjust,
        phase=int(phase),
    )
    if replace_color:
        dithered = replace_white(dithered, color=replace_color)
    if split_tone:
        dithered = _grade_split_tone(dithered, strength=float(split_tone))
    if fade:
        dithered = _grade_fade(dithered, amount=float(fade))
    if glow_radius and glow_intensity:
        dithered = apply_glow(dithered, radius=glow_radius, intensity=glow_intensity,
                              threshold=int(glow_threshold))
    if grain:
        dithered = apply_grain(dithered, amount=grain)
    if halftone:
        dithered = _halftone_dots(dithered, cell=int(halftone), shape=halftone_shape)
    if dust:
        dithered = _grain_dust(dithered, amount=float(dust))
    if vignette:
        dithered = apply_vignette(dithered, strength=vignette)
    if scanlines:
        dithered = apply_scanlines(dithered, every=scanlines)
    if grille:
        dithered = rgb_grille(dithered, every=int(grille))
    if border:
        dithered = _frame_border(dithered, px=int(border), color=border_color)
    if letterbox:
        dithered = _cine_bars(dithered, pct=int(letterbox))
    if glitch_chroma:
        dithered = chromatic_aberration(dithered, dx=int(glitch_chroma))
    if glitch_slice_bands:
        dithered = slice_shift(dithered, bands=int(glitch_slice_bands),
                               max_offset=int(glitch_slice_max))
    if pixelsort:
        dithered = pixel_sort(dithered, threshold=int(pixelsort))
    if wave:
        dithered = _glitch_wave(dithered, amplitude=int(wave))
    if mosh:
        dithered = datamosh(dithered, amount=float(mosh))
    return dithered


def render_preset(img: Image.Image, preset, phase: int = 0) -> Image.Image:
    """Atajo: render(img, **preset_to_render_kwargs(preset, phase))."""
    from app.render_params import preset_to_render_kwargs

    return render(img, **preset_to_render_kwargs(preset, phase=phase))


def meta_dict(
    method: str,
    palette_name: str,
    threshold: float,
    pixel_size: int,
    adjust: Adjust | dict | None = None,
    ratio: str = "1:1",
    crop_mode: str = "cover",
    focus_x: float = 50.0,
    focus_y: float = 50.0,
    crop_zoom: float = 1.0,
    pre_blur: float = 0.0,
    pre_sharpen: int = 0,
    pre_hue: float = 0.0,
    pre_denoise: int = 0,
    pre_smooth: float = 0.0,
    glow_radius: float = 0.0,
    glow_intensity: float = 0.0,
    grain: float = 0.0,
    vignette: float = 0.0,
    scanlines: int = 0,
    replace_color: str = "",
    custom_palette: list | None = None,
    phase: int = 0,
    glitch_chroma: int = 0,
    glitch_slice_bands: int = 0,
    glitch_slice_max: int = 24,
    vector_export: bool = False,
    vector_cell: int = 8,
    gif_export: bool = False,
    gif_frames: int = 6,
    gif_mode: str = "both",
) -> dict:
    a = adjust if isinstance(adjust, Adjust) else Adjust.from_dict(adjust)
    _, pal_label = resolve_palette(palette_name, custom_palette)
    return {
        "method": method,
        "palette": pal_label,
        "threshold": float(threshold),
        "pixel_size": int(pixel_size),
        "adjust": a.to_dict(),
        "ratio": ratio,
        "crop_mode": crop_mode,
        "focus": [float(focus_x), float(focus_y)],
        "zoom": float(crop_zoom),
        "pre": {"blur": float(pre_blur), "sharpen": int(pre_sharpen),
                "hue": float(pre_hue), "denoise": int(pre_denoise), "smooth": float(pre_smooth)},
        "post": {
            "glow_radius": float(glow_radius),
            "glow_intensity": float(glow_intensity),
            "grain": float(grain),
            "vignette": float(vignette),
            "scanlines": int(scanlines),
        },
        "replace_color": replace_color or "",
        "custom_palette": [list(c) for c in (custom_palette or [])] or None,
        "phase": int(phase),
        "glitch": {"chroma": int(glitch_chroma), "slice_bands": int(glitch_slice_bands),
                   "slice_max": int(glitch_slice_max)},
        "gif": {"export": bool(gif_export), "frames": int(gif_frames), "mode": gif_mode},
        "vector_export": bool(vector_export),
        "vector_cell": int(vector_cell),
    }
