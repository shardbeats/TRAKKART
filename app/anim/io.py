"""Animation writers: GIF/WebP file output (R2-anim, verbatim move).

Moved from app.gif (no logic change). app.gif re-exports them.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from app.anim.limits import (GIF_LIMIT_SIDE, GIF_MAX_FPS, GIF_MAX_SIDE,
                             GIF_MIN_FPS)
from app.anim.plan import _check_gif_budget


def _fit_small(img: Image.Image, max_side: int = GIF_MAX_SIDE) -> Image.Image:
    side = max(64, min(GIF_LIMIT_SIDE, int(max_side or GIF_MAX_SIDE)))
    r = side / max(img.width, img.height)
    if r >= 1.0:
        return img.copy()
    return img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BICUBIC)


def _pingpong(seq: list) -> list:
    """Forward-backward loop so the GIF has no jump cut. 6 -> 10 frames."""
    if len(seq) <= 2:
        return list(seq)
    return list(seq) + list(reversed(seq[1:-1]))


def save_gif(
    frames: list[Image.Image],
    path: str | Path,
    fps: int = 8,
    loop: int = 0,
) -> Path:
    """Save an animated GIF with a shared palette (no per-frame flicker).

    The first frame donates a 128-color palette; the rest quantize
    against it with dither=NONE so the dither look stays intact.
    Quantizes incrementally (no RGB double-list: peak ~1/3 + 1 frame);
    the first frame's palette is reused, not recomputed. Byte-identical
    to the old double-list build for the same inputs.
    """
    if not frames:
        raise ValueError("no frames")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(GIF_MIN_FPS, min(GIF_MAX_FPS, int(fps)))
    w0, h0 = frames[0].size
    _check_gif_budget(len(frames), w0, h0)
    first = frames[0] if frames[0].mode == "RGB" else frames[0].convert("RGB")
    base_pal = first.quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE)
    paletted = [base_pal]
    for f in frames[1:]:
        rgb = f if f.mode == "RGB" else f.convert("RGB")
        paletted.append(rgb.quantize(palette=base_pal, dither=Image.NONE))
        del rgb
    del first
    paletted[0].save(
        str(out), save_all=True, append_images=paletted[1:],
        duration=max(1, int(1000 / fps)), loop=int(loop), optimize=True,
    )
    return out


def save_webp(
    frames: list[Image.Image],
    path: str | Path,
    fps: int = 8,
    loop: int = 0,
    quality: int = 80,
) -> Path:
    """Save an animated WebP (R7): same frames as the GIF, ~1/3 the weight.

    Pillow only, no new deps. Full color (no 128-color quantize), plays
    in every current browser. `minimize_size` reuses encoding tables
    across the duplicated hold frames particle clips are full of.
    """
    if not frames:
        raise ValueError("no frames")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(GIF_MIN_FPS, min(GIF_MAX_FPS, int(fps)))
    rgb = [f if f.mode == "RGB" else f.convert("RGB") for f in frames]
    rgb[0].save(
        str(out), save_all=True, append_images=rgb[1:],
        duration=max(1, int(1000 / fps)), loop=int(loop),
        minimize_size=True, quality=max(1, min(100, int(quality))),
    )
    return out


__all__ = ["_fit_small", "_pingpong", "save_gif", "save_webp"]
