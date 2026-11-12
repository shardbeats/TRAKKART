"""TRAKKART pipeline: canvas -> pre -> grade -> dither -> brand -> post.

Order (signal chain): adjustments and grade run BEFORE the dither
on continuous tone; texture and glitch run after over the dither.
"""

from __future__ import annotations

from PIL import Image

from app.adjust import Adjust
from app.canvas import to_canvas
from app.dither import apply_method
from app.fx import (
    apply_pre,
    normalize_custom_palette,
    replace_white,
)
from app.fx_dispatch import apply_fx as _apply_fx
from app.grade import gradient_map
from app.grade import posterize as _grade_posterize
from app.palettes import get_palette


def resolve_palette(palette_name: str, custom: list | None):
    from app.palette_library import is_bw

    custom_pal = normalize_custom_palette(custom)
    if custom_pal is not None:
        if is_bw(custom_pal):
            return None, "BW"  # equals pure B&W: fast path, no branches in the UI
        return custom_pal, "custom"
    if palette_name == "SOURCE":
        return "SOURCE", "source"
    return get_palette(palette_name), palette_name


# ---------------------------------------------------------------------------
# RenderSpec: one dataclass for pipeline.render + meta + render_params.
# Before: the same ~40-param list written in render(), meta_dict() and
# preset_to_render_kwargs(). Now: Preset to spec (from_preset), spec
# to render (render_spec) or to dict/meta. render()/meta_dict() stay as
# compatible wrappers (tests + old callers).
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
    grain_seed: int = 0x7A4B
    vignette: float = 0.0
    scanlines: int = 0
    replace_color: str = ""
    custom_palette: list | None = None
    palette_depth: int = 0
    phase: int = 0
    glitch_chroma: int = 0
    glitch_slice_bands: int = 0
    glitch_slice_max: int = 24
    glitch_slice_seed: int = 0x6A17
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
    dust_seed: int = 0xD57
    border: int = 0
    border_color: str = "#000000"
    letterbox: int = 0
    pixelsort: int = 0
    pixelsort_seed: int = 0x9150
    wave: int = 0
    wave_seed: int = 0x9A9E
    mosh: float = 0.0
    mosh_mode: str = "blocks"
    mosh_seed: int = 0
    mosh_size: int = 100
    grille: int = 0
    jpeg: float = 0.0
    post_blur: float = 0.0
    post_sharpen: int = 0
    fx_stack: list | None = None
    motif: dict | None = None
    ascii: dict | None = None
    drift_pattern: str = "off"
    drift_amount: float = 0.0
    drift_progress: float | None = None
    drift_loops: float = 1.0
    drift_position: float = 50.0
    drift_seed: int = 0xD81F
    paste_mode: str = "off"
    paste_opacity: float = 0.0
    paste_blend: str = "overlay"
    paste_seed: int = 0x9A57

    @staticmethod
    def from_preset(preset, phase: int = 0, drift_progress: float | None = None) -> "RenderSpec":
        """Preset -> normalized spec. Single conversion (see render_params)."""
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
            grain_seed=int(getattr(preset, "grain_seed", 0x7A4B) or 0),
            vignette=float(preset.vignette),
            scanlines=normalize_scanlines(int(preset.scanlines)),
            replace_color=preset.replace_color,
            custom_palette=preset.custom_palette,
            palette_depth=normalize_palette_depth(int(getattr(preset, "palette_depth", 0) or 0)),
            phase=int(phase),
            glitch_chroma=int(preset.glitch_chroma),
            glitch_slice_bands=normalize_slice_bands(int(preset.glitch_slice_bands)),
            glitch_slice_max=int(preset.glitch_slice_max),
            glitch_slice_seed=int(getattr(preset, "glitch_slice_seed", 0x6A17) or 0),
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
            dust_seed=int(getattr(preset, "dust_seed", 0xD57) or 0),
            border=int(getattr(preset, "border", 0)),
            border_color=str(getattr(preset, "border_color", "#000000")),
            letterbox=int(getattr(preset, "letterbox", 0)),
            pixelsort=int(getattr(preset, "pixelsort", 0)),
            pixelsort_seed=int(getattr(preset, "pixelsort_seed", 0x9150) or 0),
            wave=int(getattr(preset, "wave", 0)),
            wave_seed=int(getattr(preset, "wave_seed", 0x9A9E) or 0),
            mosh=float(getattr(preset, "mosh", 0.0)),
            mosh_mode=str(getattr(preset, "mosh_mode", "blocks") or "blocks"),
            mosh_seed=int(getattr(preset, "mosh_seed", 0) or 0),
            mosh_size=int(getattr(preset, "mosh_size", 100) or 100),
            grille=normalize_grille(int(getattr(preset, "grille", 0))),
            jpeg=float(getattr(preset, "jpeg", 0.0) or 0.0),
            post_blur=float(getattr(preset, "post_blur", 0.0) or 0.0),
            post_sharpen=int(getattr(preset, "post_sharpen", 0) or 0),
            fx_stack=(__import__("copy").deepcopy(getattr(preset, "fx_stack", None))
                      if getattr(preset, "fx_stack", None) is not None else None),
            motif=(__import__("copy").deepcopy(getattr(preset, "motif", None))
                   if getattr(preset, "motif", None) is not None else None),
            ascii=(__import__("copy").deepcopy(getattr(preset, "ascii", None))
                   if getattr(preset, "ascii", None) is not None else None),
            drift_pattern=str(getattr(preset, "drift_pattern", "off") or "off"),
            drift_amount=float(getattr(preset, "drift_amount", 0.0) or 0.0),
            drift_progress=(None if drift_progress is None else float(drift_progress)),
            drift_loops=float(getattr(preset, "drift_speed", 1.0) or 1.0),
            drift_position=float(getattr(preset, "drift_position", 50.0)),
            drift_seed=int(getattr(preset, "drift_seed", 0xD81F) or 0),
            paste_mode=str(getattr(preset, "paste_mode", "off") or "off"),
            paste_opacity=float(getattr(preset, "paste_opacity", 0.0) or 0.0),
            paste_blend=str(getattr(preset, "paste_blend", "overlay") or "overlay"),
            paste_seed=int(getattr(preset, "paste_seed", 0x9A57) or 0),
        )

    def as_kwargs(self) -> dict:
        """Spec -> render() kwargs. Shallow, like the previous conversion."""
        return {f.name: getattr(self, f.name) for f in fields(self)}

    def meta(self) -> dict:
        """Params block for metadata.json (no gif/vector: meta_dict adds them)."""
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
                "grain_seed": int(getattr(self, "grain_seed", 0x7A4B) or 0),
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
                       "slice_seed": int(getattr(self, "glitch_slice_seed", 0x6A17) or 0),
                       "pixelsort": int(self.pixelsort),
                       "pixelsort_seed": int(getattr(self, "pixelsort_seed", 0x9150) or 0),
                       "wave": int(self.wave),
                       "wave_seed": int(getattr(self, "wave_seed", 0x9A9E) or 0),
                       "mosh": float(self.mosh),
                       "mosh_mode": str(getattr(self, "mosh_mode", "blocks")),
                       "mosh_seed": int(getattr(self, "mosh_seed", 0) or 0),
                       "mosh_size": int(getattr(self, "mosh_size", 100) or 100),
                       "grille": int(self.grille)},
            "fx": {"jpeg": float(getattr(self, "jpeg", 0.0) or 0.0),
                   "post_blur": float(getattr(self, "post_blur", 0.0) or 0.0),
                   "post_sharpen": int(getattr(self, "post_sharpen", 0) or 0),
                   "stack": (__import__("copy").deepcopy(self.fx_stack)
                             if self.fx_stack is not None else None)},
            "grade": {
                "duotone": [str(getattr(self, "duotone_dark", "")),
                            str(getattr(self, "duotone_light", "")),
                            float(getattr(self, "duotone_mid", 50.0))],
                "posterize": int(getattr(self, "posterize", 0) or 0),
                "split_tone": float(getattr(self, "split_tone", 0.0) or 0.0),
                "fade": float(getattr(self, "fade", 0.0) or 0.0),
                "glow_threshold": int(getattr(self, "glow_threshold", 0) or 0),
            },
            "texture": {
                "halftone": int(getattr(self, "halftone", 0) or 0),
                "halftone_shape": str(getattr(self, "halftone_shape", "dots")),
                "dust": float(getattr(self, "dust", 0.0) or 0.0),
                "dust_seed": int(getattr(self, "dust_seed", 0xD57) or 0),
                "border": int(getattr(self, "border", 0) or 0),
                "border_color": str(getattr(self, "border_color", "#000000")),
                "letterbox": int(getattr(self, "letterbox", 0) or 0),
            },
            "drift": {
                "pattern": str(getattr(self, "drift_pattern", "off") or "off"),
                "amount": float(getattr(self, "drift_amount", 0.0) or 0.0),
                "loops": float(getattr(self, "drift_loops", 1.0) or 1.0),
                "position": float(getattr(self, "drift_position", 50.0)),
                "seed": int(getattr(self, "drift_seed", 0xD81F) or 0),
            },
            "paste": {
                "mode": str(getattr(self, "paste_mode", "off") or "off"),
                "opacity": float(getattr(self, "paste_opacity", 0.0) or 0.0),
                "blend": str(getattr(self, "paste_blend", "overlay") or "overlay"),
                "seed": int(getattr(self, "paste_seed", 0x9A57) or 0),
            },
            "motif": (__import__("copy").deepcopy(self.motif)
                      if self.motif is not None else None),
            "ascii": (__import__("copy").deepcopy(self.ascii)
                      if getattr(self, "ascii", None) is not None else None),
        }


def render_spec(img: Image.Image, spec: RenderSpec) -> Image.Image:
    """Full pipeline over a RenderSpec: canvas -> pre -> grade -> dither -> brand -> STACK.

    The post-dither stack is ordered and switchable (v1.2). None = order
    legacy (byte-identical to the previous fixed chain).
    """
    from app.fx_stack import normalize_stack

    s = spec
    canvas = to_canvas(img, ratio=s.ratio, mode=s.crop_mode, fx=s.focus_x, fy=s.focus_y,
                       zoom=s.crop_zoom, canvas_w=s.canvas_w, canvas_h=s.canvas_h)
    if str(getattr(s, "drift_pattern", "off") or "off") != "off" \
            and float(getattr(s, "drift_amount", 0.0) or 0.0) > 0:
        from app.drift import apply_drift_loop

        if getattr(s, "drift_progress", None) is not None:
            canvas = apply_drift_loop(canvas, pattern=str(s.drift_pattern),
                                      amount=float(s.drift_amount),
                                      progress=float(s.drift_progress),
                                      seed=int(getattr(s, "drift_seed", 0xD81F) or 0),
                                      loops=float(getattr(s, "drift_loops", 1.0) or 1.0))
        else:
            # Still: frozen traverse at drift_position (50 = mid, visible).
            try:
                pos = max(0.0, min(100.0, float(getattr(s, "drift_position", 50.0)))) / 100.0
            except (TypeError, ValueError):
                pos = 0.5
            canvas = apply_drift_loop(canvas, pattern=str(s.drift_pattern),
                                      amount=float(s.drift_amount), progress=pos,
                                      seed=int(getattr(s, "drift_seed", 0xD81F) or 0),
                                      loops=1.0)
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
        ascii=getattr(s, "ascii", None),
    )
    if s.replace_color:
        dithered = replace_white(dithered, color=s.replace_color)
    for entry in normalize_stack(s.fx_stack):
        if entry.get("enabled", True):
            dithered = _apply_fx(s, dithered, entry["id"])
    return dithered


def render(img: Image.Image, **kwargs) -> Image.Image:
    """Compat: render over kwargs (tests and old callers)."""
    return render_spec(img, RenderSpec(**kwargs))


def render_preset(img: Image.Image, preset, phase: int = 0) -> Image.Image:
    """Shortcut: render_spec(img, RenderSpec.from_preset(preset, phase))."""
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
    ascii: dict | None = None,
) -> dict:
    """Compat (positional signature intact for tests): spec + gif/vector extras."""
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
        phase=phase, ascii=ascii, glitch_chroma=glitch_chroma,
        glitch_slice_bands=glitch_slice_bands, glitch_slice_max=glitch_slice_max,
    )
    m = spec.meta()
    m["gif"] = {"export": bool(gif_export), "frames": int(gif_frames), "mode": gif_mode,
                "fps": int(gif_fps), "size": int(gif_size), "pingpong": bool(gif_pingpong)}
    m["vector_export"] = bool(vector_export)
    m["vector_cell"] = int(vector_cell)
    return m
