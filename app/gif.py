"""Animated TRAKKART GIF (MIT, clean-room). Pillow only, no ffmpeg.

Frames: ordered-matrix phase offset (marching) and/or hue cycle.
Max 480px long side for socials. Deterministic (same inputs).
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

GIF_MODES = ("phase", "hue", "both")
GIF_MAX_SIDE = 480


def _fit_small(img: Image.Image, max_side: int = GIF_MAX_SIDE) -> Image.Image:
    r = max_side / max(img.width, img.height)
    if r >= 1.0:
        return img.copy()
    return img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BICUBIC)


def gif_frames(img: Image.Image, preset, frames: int = 6, mode: str = "both") -> list[Image.Image]:
    """Build frames using the pipeline render() with per-frame phase/hue."""
    from app.pipeline import render
    from app.render_params import preset_to_render_kwargs

    if mode not in GIF_MODES:
        mode = "both"
    n = max(2, min(12, int(frames)))
    small = _fit_small(img.convert("RGB"))
    base_kwargs = preset_to_render_kwargs(preset)
    base_hue = float(preset.pre_hue)
    out: list[Image.Image] = []
    for i in range(n):
        kwargs = dict(base_kwargs)
        kwargs["phase"] = i if mode in ("phase", "both") else 0
        if mode in ("hue", "both"):
            kwargs["pre_hue"] = base_hue + round(12.0 * math.sin(2.0 * math.pi * i / n), 2)
        # GIF ya viene reducido: no re-aplicar canvas crop a full-res.
        out.append(render(small, **kwargs))
    return out


def save_gif(frames: list[Image.Image], path: str | Path, fps: int = 8) -> Path:
    """Save an animated GIF with optimized palette. Returns the path."""
    if not frames:
        raise ValueError("no frames")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    paletted = [f.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=64) for f in frames]
    paletted[0].save(
        str(out), save_all=True, append_images=paletted[1:],
        duration=max(1, int(1000 / max(1, int(fps)))), loop=0, optimize=True,
    )
    return out


def estimate_gif(frames: int, w: int, h: int) -> int:
    """Rough weight estimate (bytes) to warn about huge GIFs."""
    return int(frames) * int(w) * int(h) // 2
