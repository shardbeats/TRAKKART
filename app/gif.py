"""Animated TRAKKART GIF (MIT, clean-room). Pillow only, no ffmpeg.

Modes:
  phase  = dither-matrix march (clean, ordered methods)
  hue    = hue cycle (sinus, loops perfectly)
  both   = phase + hue (legacy default)
  glitch = CRT glitch anim (chroma + slice + wave) + phase march
  mix    = phase + hue + glitch + grain shimmer (todo junto)

ED methods (floyd/atkinson/...) ignore `phase`, so glitch/mix keep
them alive via post-fx animation. Everything deterministic:
same inputs -> same bytes (seed + frame index, no random).
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

GIF_MODES = ("phase", "hue", "both", "glitch", "mix")
GIF_MAX_SIDE = 480
GIF_MIN_SIDE = 240
GIF_LIMIT_SIDE = 1920
GIF_MIN_FPS = 2
GIF_MAX_FPS = 24
GIF_MIN_FRAMES = 2
GIF_MAX_FRAMES = 12
# Video preview a canvas completo (personalizable, default 1200).
VIDEO_DEFAULT_SIZE = 1200
VIDEO_MIN_SIZE = 480
VIDEO_MAX_SIZE = 1920


def _fit_small(img: Image.Image, max_side: int = GIF_MAX_SIDE) -> Image.Image:
    side = max(64, min(GIF_LIMIT_SIDE, int(max_side or GIF_MAX_SIDE)))
    r = side / max(img.width, img.height)
    if r >= 1.0:
        return img.copy()
    return img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.BICUBIC)


def _clamp_frames(frames: int) -> int:
    return max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))


def _pingpong(seq: list) -> list:
    """Forward-backward loop so the GIF has no jump cut. 6 -> 10 frames."""
    if len(seq) <= 2:
        return list(seq)
    return list(seq) + list(reversed(seq[1:-1]))


def gif_frames(
    img: Image.Image,
    preset,
    frames: int = 6,
    mode: str = "both",
    max_side: int | None = None,
    pingpong: bool | None = None,
) -> list[Image.Image]:
    """Build frames using the pipeline render() + deterministic post anim.

    `max_side`/`pingpong` default to the preset values (gif_size/gif_pingpong)
    so batch + UI + service share the same look without extra plumbing.
    Unknown modes fall back to "both" (legacy compat).
    """
    from app.render_params import normalize_slice_bands

    if mode not in GIF_MODES:
        mode = "both"
    n = _clamp_frames(frames)
    side = int(getattr(preset, "gif_size", GIF_MAX_SIDE) if max_side is None else max_side)
    pp = bool(getattr(preset, "gif_pingpong", False)) if pingpong is None else bool(pingpong)
    small = _fit_small(img.convert("RGB"), side)

    from app.pipeline import render
    from app.render_params import preset_to_render_kwargs

    base_kwargs = preset_to_render_kwargs(preset)
    base_hue = float(preset.pre_hue)

    # Animated post-fx baselines (0 = subtle default for glitch/mix so
    # even a clean preset still moves).
    base_chroma = int(getattr(preset, "glitch_chroma", 0) or 0)
    base_bands = normalize_slice_bands(int(getattr(preset, "glitch_slice_bands", 0) or 0))
    base_max = int(getattr(preset, "glitch_slice_max", 24) or 0)
    base_wave = int(getattr(preset, "wave", 0) or 0)
    base_mosh = float(getattr(preset, "mosh", 0.0) or 0.0)
    base_grain = float(getattr(preset, "grain", 0.0) or 0.0)
    base_dust = float(getattr(preset, "dust", 0.0) or 0.0)

    want_phase = mode in ("phase", "both", "glitch", "mix")
    want_hue = mode in ("hue", "both", "mix")
    want_glitch = mode in ("glitch", "mix")

    # The base render stays static; animation happens per-frame below.
    # Zero the animated channels so the effect does not stack twice.
    base_kwargs["glitch_chroma"] = 0
    base_kwargs["glitch_slice_bands"] = 0
    base_kwargs["wave"] = 0
    base_kwargs["mosh"] = 0.0
    base_kwargs["grain"] = 0.0
    base_kwargs["dust"] = 0.0

    out: list[Image.Image] = []
    for i in range(n):
        kwargs = dict(base_kwargs)
        kwargs["phase"] = int(i * 2) if want_phase else 0
        if want_hue:
            kwargs["pre_hue"] = base_hue + round(14.0 * math.sin(2.0 * math.pi * i / n), 2)
        frame = render(small, **kwargs)

        if want_glitch:
            from app.glitch import chromatic_aberration, datamosh, slice_shift
            from app.glitch import wave as glitch_wave

            t = 2.0 * math.pi * i / n
            # Chroma: preset amplitude, or subtle 3px wobble if preset is clean.
            amp_c = base_chroma if base_chroma > 0 else 3
            dx = int(round(amp_c * math.sin(t)))
            if dx:
                frame = chromatic_aberration(frame, dx=dx)
            # Slices: preset bands, or 4 light bands if clean.
            bands = base_bands if base_bands >= 2 else 4
            maxoff = base_max if base_max > 0 else 8
            # Deterministic per-frame offsets (seed + i), no drift.
            frame = slice_shift(frame, bands=bands, max_offset=maxoff, seed=0x6A17 + i)
            # Wave: preset amplitude, or gentle 2px CRT wobble if clean.
            amp_w = base_wave if base_wave > 0 else 2
            frame = glitch_wave(frame, amplitude=amp_w, seed=0x9A9E + i)
            # Mosh: only if the preset asks for it (too chaotic as default).
            if base_mosh > 0:
                amt = base_mosh * (0.6 + 0.4 * math.sin(t + 1.0))
                frame = datamosh(frame, amount=max(0.0, amt), seed=0x405 + i)

        # Grain shimmer: animated seed so mix feels alive without flicker.
        # Static grain would freeze; seeded-per-frame keeps the dither readable.
        if mode == "mix":
            from app.fx import apply_grain

            g = base_grain if base_grain > 0 else 4.0
            frame = apply_grain(frame, amount=g, seed=0x7A4B + i)
            if base_dust > 0:
                from app.texture import dust as grain_dust

                frame = grain_dust(frame, amount=base_dust, seed=0xD57 + i)
        elif base_grain > 0 or base_dust > 0:
            # Non-mix modes keep the preset grain but animated (no freeze).
            from app.fx import apply_grain

            if base_grain > 0:
                frame = apply_grain(frame, amount=base_grain, seed=0x7A4B + i)
            if base_dust > 0:
                from app.texture import dust as grain_dust

                frame = grain_dust(frame, amount=base_dust, seed=0xD57 + i)

        out.append(frame)

    if pp:
        out = _pingpong(out)
    return out


def save_gif(
    frames: list[Image.Image],
    path: str | Path,
    fps: int = 8,
    loop: int = 0,
) -> Path:
    """Save an animated GIF with a shared palette (no per-frame flicker).

    The first frame donates a 128-color palette; the rest quantize
    against it with dither=NONE so the dither look stays intact.
    """
    if not frames:
        raise ValueError("no frames")
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = max(GIF_MIN_FPS, min(GIF_MAX_FPS, int(fps)))
    rgb = [f.convert("RGB") for f in frames]
    # Shared palette: median-cut on the first frame, reused by all.
    base_pal = rgb[0].quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE)
    paletted = [rgb[0].quantize(colors=128, method=Image.MEDIANCUT, dither=Image.NONE)]
    for f in rgb[1:]:
        paletted.append(f.quantize(palette=base_pal, dither=Image.NONE))
    paletted[0].save(
        str(out), save_all=True, append_images=paletted[1:],
        duration=max(1, int(1000 / fps)), loop=int(loop), optimize=True,
    )
    return out


def estimate_gif(frames: int, w: int, h: int) -> int:
    """Rough weight estimate (bytes) to warn about huge GIFs."""
    return int(frames) * int(w) * int(h) // 2
