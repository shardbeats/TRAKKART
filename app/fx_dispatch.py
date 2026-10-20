"""Post-dither FX dispatch (MIT, clean-room). One function per stack effect.

Split out of app/pipeline.py (mechanical move, no logic change):
`apply_fx(spec, img, fid)` runs a single STACK effect with RenderSpec
params, no-op when neutral. Unknown ids stay no-op (forward-compat).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from app.fx import apply_glow, apply_grain, apply_scanlines, apply_vignette
from app.glitch import (
    chromatic_aberration,
    datamosh,
    pixel_sort,
    rgb_grille,
    slice_shift,
)
from app.glitch import wave as _glitch_wave
from app.grade import fade as _grade_fade
from app.grade import split_tone as _grade_split_tone
from app.texture import border as _frame_border
from app.texture import dust as _grain_dust
from app.texture import halftone as _halftone_dots
from app.texture import letterbox as _cine_bars

if TYPE_CHECKING:
    from app.pipeline import RenderSpec


def _split_tone(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _grade_split_tone(img, strength=float(s.split_tone)) if s.split_tone else img


def _fade(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _grade_fade(img, amount=float(s.fade)) if s.fade else img


def _glow(s: "RenderSpec", img: Image.Image) -> Image.Image:
    if s.glow_radius and s.glow_intensity:
        return apply_glow(img, radius=s.glow_radius, intensity=s.glow_intensity,
                          threshold=int(s.glow_threshold))
    return img


def _grain(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return apply_grain(img, amount=s.grain) if s.grain else img


def _halftone(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _halftone_dots(img, cell=int(s.halftone), shape=s.halftone_shape) if s.halftone else img


def _dust(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _grain_dust(img, amount=float(s.dust)) if s.dust else img


def _vignette(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return apply_vignette(img, strength=s.vignette) if s.vignette else img


def _scanlines(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return apply_scanlines(img, every=s.scanlines) if s.scanlines else img


def _grille(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return rgb_grille(img, every=int(s.grille)) if s.grille else img


def _border(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _frame_border(img, px=int(s.border), color=s.border_color) if s.border else img


def _letterbox(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _cine_bars(img, pct=int(s.letterbox)) if s.letterbox else img


def _chroma(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return chromatic_aberration(img, dx=int(s.glitch_chroma)) if s.glitch_chroma else img


def _slice(s: "RenderSpec", img: Image.Image) -> Image.Image:
    if s.glitch_slice_bands:
        return slice_shift(img, bands=int(s.glitch_slice_bands),
                           max_offset=int(s.glitch_slice_max))
    return img


def _pixelsort(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return pixel_sort(img, threshold=int(s.pixelsort)) if s.pixelsort else img


def _wave(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return _glitch_wave(img, amplitude=int(s.wave)) if s.wave else img


def _mosh(s: "RenderSpec", img: Image.Image) -> Image.Image:
    return datamosh(img, amount=float(s.mosh)) if s.mosh else img


def _jpeg(s: "RenderSpec", img: Image.Image) -> Image.Image:
    if float(getattr(s, "jpeg", 0.0) or 0.0) > 0:
        from app.fx_jpeg import apply_jpeg

        return apply_jpeg(img, amount=float(s.jpeg))
    return img


def _post_blur(s: "RenderSpec", img: Image.Image) -> Image.Image:
    if float(getattr(s, "post_blur", 0.0) or 0.0) > 0:
        from PIL import ImageFilter

        return img.convert("RGB").filter(
            ImageFilter.GaussianBlur(radius=float(s.post_blur)))
    return img


def _post_sharpen(s: "RenderSpec", img: Image.Image) -> Image.Image:
    if int(getattr(s, "post_sharpen", 0) or 0) > 0:
        from PIL import ImageFilter

        out = img.convert("RGB")
        for _ in range(max(0, int(s.post_sharpen))):
            out = out.filter(ImageFilter.SHARPEN)
        return out
    return img


def _pasteup(s: "RenderSpec", img: Image.Image) -> Image.Image:
    if str(getattr(s, "paste_mode", "off")) not in ("off", "") \
            and float(getattr(s, "paste_opacity", 0.0) or 0.0) > 0:
        from app.pasteup import apply_paste

        return apply_paste(img, mode=str(s.paste_mode),
                           opacity=float(s.paste_opacity),
                           blend=str(getattr(s, "paste_blend", "overlay")))
    return img


APPLY: dict[str, object] = {
    "split_tone": _split_tone,
    "fade": _fade,
    "glow": _glow,
    "grain": _grain,
    "halftone": _halftone,
    "dust": _dust,
    "vignette": _vignette,
    "scanlines": _scanlines,
    "grille": _grille,
    "border": _border,
    "letterbox": _letterbox,
    "chroma": _chroma,
    "slice": _slice,
    "pixelsort": _pixelsort,
    "wave": _wave,
    "mosh": _mosh,
    "jpeg": _jpeg,
    "post_blur": _post_blur,
    "post_sharpen": _post_sharpen,
    "pasteup": _pasteup,
}


def apply_fx(spec: "RenderSpec", img: Image.Image, fid: str) -> Image.Image:
    """Run one STACK effect. Unknown ids are no-op (forward-compat)."""
    fn = APPLY.get(str(fid))
    if fn is None:
        return img
    return fn(spec, img)


__all__ = ["APPLY", "apply_fx"]
