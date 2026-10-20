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
    if palette_name == "SOURCE":
        return "SOURCE", "source"
    return get_palette(palette_name), palette_name


# ---------------------------------------------------------------------------
# RenderSpec: un solo dataclass para pipeline.render + meta + render_params.
# Antes: la misma lista de ~40 params escrita en render(), meta_dict() y
# preset_to_render_kwargs(). Ahora: de Preset a spec (from_preset), de spec
# a render (render_spec) o a dict/meta. render()/meta_dict() quedan como
# wrappers compatibles (tests + callers antiguos).
# ---------------------------------------------------------------------------
from dataclasses import dataclass, fields


@dataclass
class RenderSpec:
    method: str = "bayer4"
    palette_name: str = "SLIME"
    threshold: float = 128.0
    pixel_size: int = 1
    adjust: Adjust | dict | None = None
    ratio: str = "1:1"
    canvas_w: int = 0
    canvas_h: int = 0
    crop_mode: str = "cover"
    focus_x: float = 50.0
    focus_y: float = 50.0
    crop_zoom: float = 1.0
    pre_blur: float = 0.0
    pre_sharpen: int = 0
    pre_hue: float = 0.0
    pre_denoise: int = 0
    pre_smooth: float = 0.0
    glow_radius: float = 0.0
    glow_intensity: float = 0.0
    grain: float = 0.0
    vignette: float = 0.0
    scanlines: int = 0
    replace_color: str = ""
    custom_palette: list | None = None
    palette_depth: int = 0
    phase: int = 0
    glitch_chroma: int = 0
    glitch_slice_bands: int = 0
    glitch_slice_max: int = 24
    duotone_dark: str = ""
    duotone_light: str = ""
    duotone_mid: float = 50.0
    posterize: int = 0
    split_tone: float = 0.0
    fade: float = 0.0
    glow_threshold: int = 0
    halftone: int = 0
    halftone_shape: str = "dots"
    dust: float = 0.0
    border: int = 0
    border_color: str = "#000000"
    letterbox: int = 0
    pixelsort: int = 0
    wave: int = 0
    mosh: float = 0.0
    grille: int = 0
    jpeg: float = 0.0
    post_blur: float = 0.0
    post_sharpen: int = 0
    fx_stack: list | None = None
    motif: dict | None = None
    drift_pattern: str = "off"
    drift_amount: float = 0.0
    paste_mode: str = "off"
    paste_opacity: float = 0.0
    paste_blend: str = "overlay"

    @staticmethod
    def from_preset(preset, phase: int = 0) -> "RenderSpec":
        """Preset -> spec normalizado. Única conversión (ver render_params)."""
        from app.render_params import (
            normalize_grille,
            normalize_halftone,
            normalize_palette_depth,
            normalize_posterize,
            normalize_scanlines,
            normalize_slice_bands,
        )

        return RenderSpec(
            method=preset.method,
            palette_name=preset.palette,
            threshold=float(preset.threshold),
            pixel_size=int(preset.pixel_size),
            adjust=preset.adjust(),
            ratio=preset.ratio,
            canvas_w=int(getattr(preset, "canvas_w", 0) or 0),
            canvas_h=int(getattr(preset, "canvas_h", 0) or 0),
            crop_mode=preset.crop_mode,
            focus_x=float(preset.focus_x),
            focus_y=float(preset.focus_y),
            crop_zoom=float(preset.crop_zoom),
            pre_blur=float(preset.pre_blur),
            pre_sharpen=int(preset.pre_sharpen),
            pre_hue=float(preset.pre_hue),
            pre_denoise=int(preset.pre_denoise),
            pre_smooth=float(preset.pre_smooth),
            glow_radius=float(preset.glow_radius),
            glow_intensity=float(preset.glow_intensity),
            grain=float(preset.grain),
            vignette=float(preset.vignette),
            scanlines=normalize_scanlines(int(preset.scanlines)),
            replace_color=preset.replace_color,
            custom_palette=preset.custom_palette,
            palette_depth=normalize_palette_depth(int(getattr(preset, "palette_depth", 0) or 0)),
            phase=int(phase),
            glitch_chroma=int(preset.glitch_chroma),
            glitch_slice_bands=normalize_slice_bands(int(preset.glitch_slice_bands)),
            glitch_slice_max=int(preset.glitch_slice_max),
            duotone_dark=str(getattr(preset, "duotone_dark", "")),
            duotone_light=str(getattr(preset, "duotone_light", "")),
            duotone_mid=float(getattr(preset, "duotone_mid", 50.0)),
            posterize=normalize_posterize(int(getattr(preset, "posterize", 0))),
            split_tone=float(getattr(preset, "split_tone", 0.0)),
            fade=float(getattr(preset, "fade", 0.0)),
            glow_threshold=int(getattr(preset, "glow_threshold", 0)),
            halftone=normalize_halftone(int(getattr(preset, "halftone", 0))),
            halftone_shape=str(getattr(preset, "halftone_shape", "dots")),
            dust=float(getattr(preset, "dust", 0.0)),
            border=int(getattr(preset, "border", 0)),
            border_color=str(getattr(preset, "border_color", "#000000")),
            letterbox=int(getattr(preset, "letterbox", 0)),
            pixelsort=int(getattr(preset, "pixelsort", 0)),
            wave=int(getattr(preset, "wave", 0)),
            mosh=float(getattr(preset, "mosh", 0.0)),
            grille=normalize_grille(int(getattr(preset, "grille", 0))),
            jpeg=float(getattr(preset, "jpeg", 0.0) or 0.0),
            post_blur=float(getattr(preset, "post_blur", 0.0) or 0.0),
            post_sharpen=int(getattr(preset, "post_sharpen", 0) or 0),
            fx_stack=(__import__("copy").deepcopy(getattr(preset, "fx_stack", None))
                      if getattr(preset, "fx_stack", None) is not None else None),
            motif=(__import__("copy").deepcopy(getattr(preset, "motif", None))
                   if getattr(preset, "motif", None) is not None else None),
            drift_pattern=str(getattr(preset, "drift_pattern", "off") or "off"),
            drift_amount=float(getattr(preset, "drift_amount", 0.0) or 0.0),
            paste_mode=str(getattr(preset, "paste_mode", "off") or "off"),
            paste_opacity=float(getattr(preset, "paste_opacity", 0.0) or 0.0),
            paste_blend=str(getattr(preset, "paste_blend", "overlay") or "overlay"),
        )

    def as_kwargs(self) -> dict:
        """Spec -> kwargs de render(). Shallow, como la conversión anterior."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def meta(self) -> dict:
        """Bloque params para metadata.json (sin gif/vector: los añade meta_dict)."""
        a = self.adjust if isinstance(self.adjust, Adjust) else Adjust.from_dict(self.adjust)
        _, pal_label = resolve_palette(self.palette_name, self.custom_palette)
        return {
            "method": self.method,
            "palette": pal_label,
            "threshold": float(self.threshold),
            "pixel_size": int(self.pixel_size),
            "adjust": a.to_dict(),
            "ratio": self.ratio,
            "canvas": {"w": int(self.canvas_w or 0), "h": int(self.canvas_h or 0)},
            "crop_mode": self.crop_mode,
            "focus": [float(self.focus_x), float(self.focus_y)],
            "zoom": float(self.crop_zoom),
            "pre": {"blur": float(self.pre_blur), "sharpen": int(self.pre_sharpen),
                    "hue": float(self.pre_hue), "denoise": int(self.pre_denoise),
                    "smooth": float(self.pre_smooth)},
            "post": {
                "glow_radius": float(self.glow_radius),
                "glow_intensity": float(self.glow_intensity),
                "grain": float(self.grain),
                "vignette": float(self.vignette),
                "scanlines": int(self.scanlines),
            },
            "replace_color": self.replace_color or "",
            "custom_palette": [list(c) for c in (self.custom_palette or [])] or None,
            "palette_depth": int(self.palette_depth),
            "phase": int(self.phase),
            "glitch": {"chroma": int(self.glitch_chroma),
                       "slice_bands": int(self.glitch_slice_bands),
                       "slice_max": int(self.glitch_slice_max),
                       "pixelsort": int(self.pixelsort),
                       "wave": int(self.wave),
                       "mosh": float(self.mosh),
                       "grille": int(self.grille)},
            "fx": {"jpeg": float(getattr(self, "jpeg", 0.0) or 0.0),
                   "post_blur": float(getattr(self, "post_blur", 0.0) or 0.0),
                   "post_sharpen": int(getattr(self, "post_sharpen", 0) or 0),
                   "stack": (__import__("copy").deepcopy(self.fx_stack)
                             if self.fx_stack is not None else None)},
        }


def _apply_fx(s: "RenderSpec", img: Image.Image, fid: str) -> Image.Image:
    """Un efecto del stack con los params del spec. Early-return si neutro."""
    if fid == "split_tone":
        return _grade_split_tone(img, strength=float(s.split_tone)) if s.split_tone else img
    if fid == "fade":
        return _grade_fade(img, amount=float(s.fade)) if s.fade else img
    if fid == "glow":
        if s.glow_radius and s.glow_intensity:
            return apply_glow(img, radius=s.glow_radius, intensity=s.glow_intensity,
                              threshold=int(s.glow_threshold))
        return img
    if fid == "grain":
        return apply_grain(img, amount=s.grain) if s.grain else img
    if fid == "halftone":
        return _halftone_dots(img, cell=int(s.halftone), shape=s.halftone_shape) if s.halftone else img
    if fid == "dust":
        return _grain_dust(img, amount=float(s.dust)) if s.dust else img
    if fid == "vignette":
        return apply_vignette(img, strength=s.vignette) if s.vignette else img
    if fid == "scanlines":
        return apply_scanlines(img, every=s.scanlines) if s.scanlines else img
    if fid == "grille":
        return rgb_grille(img, every=int(s.grille)) if s.grille else img
    if fid == "border":
        return _frame_border(img, px=int(s.border), color=s.border_color) if s.border else img
    if fid == "letterbox":
        return _cine_bars(img, pct=int(s.letterbox)) if s.letterbox else img
    if fid == "chroma":
        return chromatic_aberration(img, dx=int(s.glitch_chroma)) if s.glitch_chroma else img
    if fid == "slice":
        if s.glitch_slice_bands:
            return slice_shift(img, bands=int(s.glitch_slice_bands),
                               max_offset=int(s.glitch_slice_max))
        return img
    if fid == "pixelsort":
        return pixel_sort(img, threshold=int(s.pixelsort)) if s.pixelsort else img
    if fid == "wave":
        return _glitch_wave(img, amplitude=int(s.wave)) if s.wave else img
    if fid == "mosh":
        return datamosh(img, amount=float(s.mosh)) if s.mosh else img
    if fid == "jpeg":
        if float(getattr(s, "jpeg", 0.0) or 0.0) > 0:
            from app.fx_jpeg import apply_jpeg

            return apply_jpeg(img, amount=float(s.jpeg))
        return img
    if fid == "post_blur":
        if float(getattr(s, "post_blur", 0.0) or 0.0) > 0:
            from PIL import ImageFilter

            return img.convert("RGB").filter(
                ImageFilter.GaussianBlur(radius=float(s.post_blur)))
        return img
    if fid == "post_sharpen":
        if int(getattr(s, "post_sharpen", 0) or 0) > 0:
            from PIL import ImageFilter

            out = img.convert("RGB")
            for _ in range(max(0, int(s.post_sharpen))):
                out = out.filter(ImageFilter.SHARPEN)
            return out
        return img
    if fid == "pasteup":
        if str(getattr(s, "paste_mode", "off")) not in ("off", "") \
                and float(getattr(s, "paste_opacity", 0.0) or 0.0) > 0:
            from app.pasteup import apply_paste

            return apply_paste(img, mode=str(s.paste_mode),
                               opacity=float(s.paste_opacity),
                               blend=str(getattr(s, "paste_blend", "overlay")))
        return img
    return img  # id desconocido: no-op (forward-compat)


def render_spec(img: Image.Image, spec: RenderSpec) -> Image.Image:
    """Pipeline completo sobre un RenderSpec: canvas -> pre -> grade -> dither -> brand -> STACK.

    El stack post-dither es ordenado y conmutable (v1.2). None = orden
    legacy (byte-idéntico a la cadena fija anterior).
    """
    from app.fx_stack import normalize_stack

    s = spec
    canvas = to_canvas(img, ratio=s.ratio, mode=s.crop_mode, fx=s.focus_x, fy=s.focus_y,
                       zoom=s.crop_zoom, canvas_w=s.canvas_w, canvas_h=s.canvas_h)
    if str(getattr(s, "drift_pattern", "off") or "off") != "off" \
            and float(getattr(s, "drift_amount", 0.0) or 0.0) > 0:
        from app.drift import apply_drift

        canvas = apply_drift(canvas, pattern=str(s.drift_pattern),
                             amount=float(s.drift_amount), phase=int(s.phase))
    if s.pre_blur or s.pre_sharpen or s.pre_hue or s.pre_denoise or s.pre_smooth:
        canvas = apply_pre(canvas, blur=s.pre_blur, sharpen=s.pre_sharpen, hue=s.pre_hue,
                           denoise=s.pre_denoise, smooth=s.pre_smooth)
    if s.duotone_dark or s.duotone_light:
        canvas = gradient_map(canvas, color_dark=s.duotone_dark, color_light=s.duotone_light,
                              mid=float(s.duotone_mid))
    if s.posterize:
        canvas = _grade_posterize(canvas, levels=int(s.posterize))
    pal, _ = resolve_palette(s.palette_name, s.custom_palette)
    if pal == "SOURCE":
        from app.palette_extract import extract_palette

        pal = extract_palette(canvas, n=int(s.palette_depth or 6))
    else:
        from app.render_params import apply_palette_depth

        pal = apply_palette_depth(pal, int(s.palette_depth or 0))
    dithered = apply_method(
        canvas,
        method=s.method,
        palette=pal,
        threshold=float(s.threshold),
        pixel_size=int(s.pixel_size),
        adjust=s.adjust,
        phase=int(s.phase),
        motif=getattr(s, "motif", None),
    )
    if s.replace_color:
        dithered = replace_white(dithered, color=s.replace_color)
    for entry in normalize_stack(s.fx_stack):
        if entry.get("enabled", True):
            dithered = _apply_fx(s, dithered, entry["id"])
    return dithered


def render(img: Image.Image, **kwargs) -> Image.Image:
    """Compat: render sobre kwargs (los tests y callers antiguos)."""
    return render_spec(img, RenderSpec(**kwargs))


def render_preset(img: Image.Image, preset, phase: int = 0) -> Image.Image:
    """Atajo: render_spec(img, RenderSpec.from_preset(preset, phase))."""
    return render_spec(img, RenderSpec.from_preset(preset, phase=phase))


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
    canvas_w: int = 0,
    canvas_h: int = 0,
    vector_export: bool = False,
    vector_cell: int = 8,
    gif_export: bool = False,
    gif_frames: int = 6,
    gif_mode: str = "both",
    gif_fps: int = 8,
    gif_size: int = 480,
    gif_pingpong: bool = False,
) -> dict:
    """Compat (firma posicional intacta para tests): spec + extras gif/vector."""
    spec = RenderSpec(
        method=method, palette_name=palette_name, threshold=threshold,
        pixel_size=pixel_size, adjust=adjust, ratio=ratio,
        canvas_w=canvas_w, canvas_h=canvas_h, crop_mode=crop_mode,
        focus_x=focus_x, focus_y=focus_y, crop_zoom=crop_zoom,
        pre_blur=pre_blur, pre_sharpen=pre_sharpen, pre_hue=pre_hue,
        pre_denoise=pre_denoise, pre_smooth=pre_smooth,
        glow_radius=glow_radius, glow_intensity=glow_intensity,
        grain=grain, vignette=vignette, scanlines=scanlines,
        replace_color=replace_color, custom_palette=custom_palette,
        phase=phase, glitch_chroma=glitch_chroma,
        glitch_slice_bands=glitch_slice_bands, glitch_slice_max=glitch_slice_max,
    )
    m = spec.meta()
    m["gif"] = {"export": bool(gif_export), "frames": int(gif_frames), "mode": gif_mode,
                "fps": int(gif_fps), "size": int(gif_size), "pingpong": bool(gif_pingpong)}
    m["vector_export"] = bool(vector_export)
    m["vector_cell"] = int(vector_cell)
    return m
