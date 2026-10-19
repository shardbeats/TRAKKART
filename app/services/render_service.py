"""Render service: full-res + lightweight preview orchestration.

La UI solo pasa (imagen, preset); el servicio decide downscale para
preview y delega en pipeline.render / vector / gif.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image

from app.pipeline import render
from app.render_params import preset_to_render_kwargs

if TYPE_CHECKING:
    from app.presets import Preset

PREVIEW_LONG_SIDE = 640


def downscale_for_preview(img: Image.Image, max_side: int = PREVIEW_LONG_SIDE) -> tuple[Image.Image, float]:
    """Devuelve (imagen reducida, factor) manteniendo aspecto."""
    long_side = max(img.width, img.height)
    if long_side <= max_side:
        return img, 1.0
    f = max_side / long_side
    small = img.resize(
        (max(1, round(img.width * f)), max(1, round(img.height * f))),
        Image.BICUBIC,
    )
    return small, f


def render_preview_small(img: Image.Image, preset: Preset) -> Image.Image:
    """Render rápido para preview: downscale + pixel compensado."""
    small, f = downscale_for_preview(img)
    kwargs = preset_to_render_kwargs(preset)
    if f < 1.0:
        kwargs["pixel_size"] = max(1, round(int(kwargs["pixel_size"]) / f))
    return render(small, **kwargs)


def render_full(img: Image.Image, preset: Preset) -> Image.Image:
    """Render full-res para export (sin downscale)."""
    return render(img, **preset_to_render_kwargs(preset))


def should_render_async(img: Image.Image) -> bool:
    """True si conviene hilo de fondo (sin numba e imagen grande)."""
    from app.accelerate import has_numba

    return (not has_numba()) and (img.width * img.height > 480 * 480)


__all__ = [
    "PREVIEW_LONG_SIDE",
    "downscale_for_preview",
    "render_preview_small",
    "render_full",
    "should_render_async",
]
