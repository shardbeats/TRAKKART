"""Render service: full-res + lightweight preview orchestration.

The UI only passes (image, preset); the service decides preview
downscale and delegates to pipeline.render / vector / gif.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from app.pipeline import render
from app.render_params import preset_to_render_kwargs

if TYPE_CHECKING:
    from app.presets import Preset

PREVIEW_LONG_SIDE = 640

# Radius-like FX are pixel distances, so they shrink with f to keep
# proportions. Amount-like FX (grain, vignette, wave) are untouched.
RADIUS_KEYS = ("glow_radius", "border", "scanlines", "grille", "halftone", "letterbox")


def compensate_preview_params(kwargs: dict, f: float) -> dict:
    """Scale block/radius params for a preview rendered at factor f (in place)."""
    if f < 1.0:
        kwargs["pixel_size"] = max(1, round(int(kwargs.get("pixel_size", 1)) / f))
        for key in RADIUS_KEYS:
            try:
                kwargs[key] = max(0, round(float(kwargs.get(key, 0)) * f))
            except (TypeError, ValueError):
                continue
    return kwargs


def downscale_for_preview(img: Image.Image, max_side: int = PREVIEW_LONG_SIDE) -> tuple[Image.Image, float]:
    """Return (downscaled image, factor) keeping aspect ratio."""
    long_side = max(img.width, img.height)
    if long_side <= max_side:
        return img, 1.0
    f = max_side / long_side
    small = img.resize(
        (max(1, round(img.width * f)), max(1, round(img.height * f))),
        Image.BICUBIC,
    )
    return small, f


def render_preview_small(img: Image.Image, preset: Preset,
                         max_side: int = PREVIEW_LONG_SIDE) -> Image.Image:
    """Fast render for preview: downscale + compensated pixel units.

    pixel_size is a block size in source pixels, so it grows as 1/f to
    keep the dither readable. Radius-like FX (glow, border, scanlines,
    grille, halftone, letterbox) are pixel distances, so they shrink
    with f to keep proportions. Amount-like FX (grain, vignette, wave)
    are left untouched.
    """
    small, f = downscale_for_preview(img, max_side=max_side)
    kwargs = preset_to_render_kwargs(preset)
    compensate_preview_params(kwargs, f)
    return render(small, **kwargs)


def render_full(img: Image.Image, preset: Preset) -> Image.Image:
    """Full-res render for export (no downscale)."""
    return render(img, **preset_to_render_kwargs(preset))


def should_render_async(img: Image.Image) -> bool:
    """True when a background thread pays off (no numba and large image)."""
    from app.accelerate import has_numba

    return (not has_numba()) and (img.width * img.height > 480 * 480)


__all__ = [
    "PREVIEW_LONG_SIDE",
    "RADIUS_KEYS",
    "compensate_preview_params",
    "downscale_for_preview",
    "render_preview_small",
    "render_full",
    "should_render_async",
]
