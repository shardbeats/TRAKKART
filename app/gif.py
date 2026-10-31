"""Animated TRAKKART GIF (MIT). Pillow only, no ffmpeg.

Modes:
  phase  = dither-matrix march (clean, ordered methods)
  hue    = hue cycle (sinus, loops perfectly)
  both   = phase + hue (legacy default)
  glitch = CRT glitch anim (chroma + slice + wave) + phase march
   mix    = phase + hue + glitch + grain shimmer (all together)

ED methods (floyd/atkinson/...) ignore `phase`, so glitch/mix keep
them alive via post-fx animation. Everything deterministic:
same inputs -> same bytes (seed + frame index, no random).
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

GIF_MODES = ("phase", "hue", "both", "glitch", "mix", "dissolve", "morph")

# Human-facing labels + one-line explanations (ids stay stable for presets).
GIF_MODE_INFO: dict[str, tuple[str, str]] = {
    "phase": ("March",
              "Matrix march: the dither pattern crawls. Ordered methods only — "
              "frozen on error-diffusion (floyd, atkinson, …)."),
    "hue": ("Hue cycle",
            "Color wash: hue swings on every method, ordered or not."),
    "both": ("March + Hue",
             "Matrix march plus hue cycle. March part needs an ordered method."),
    "glitch": ("CRT wobble",
               "Chroma shift + slice offset + wave. Moves on every method."),
    "mix": ("Full mix",
            "March + hue + wobble + grain shimmer. Maximum motion."),
    "dissolve": ("Disperse",
                 "Dither dots burst into particles and reassemble. Loop-perfect."),
    "morph": ("Morph A->B",
              "Disperse A, reassemble B through one particle cloud. Needs a second image."),
}


def mode_label(mode: str) -> str:
    return GIF_MODE_INFO.get(str(mode), ("?", ""))[0]


def mode_desc(mode: str) -> str:
    return GIF_MODE_INFO.get(str(mode), ("?", ""))[1]


GIF_MAX_SIDE = 480
GIF_MIN_SIDE = 240
GIF_LIMIT_SIDE = 8000  # canvas rules: the anim ships at document size
GIF_MIN_FPS = 2
GIF_MAX_FPS = 60
GIF_MIN_FRAMES = 2
GIF_MAX_FRAMES = 64
# Suggested (editable combos: the list guides, the value is free).
GIF_FPS_SUGGESTED = (8, 12, 24, 30, 48, 60)
GIF_FRAMES_SUGGESTED = (4, 6, 8, 12, 24, 32, 48, 64)
# Full-canvas video preview (customizable, default 1200).
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
    img_b: Image.Image | list | None = None,
    fps: int | None = None,
) -> list[Image.Image]:
    """Build frames from the still image using pipeline render() + post anim.

    `max_side`/`pingpong` default to the preset values (gif_size/gif_pingpong)
    so batch + UI + service share the same look without extra plumbing.
    Unknown modes fall back to "both" (legacy compat).
    Animation comes from phase march + hue cycle + glitch wobble + drift;
    every frame is deterministic (seed + frame index, no random).
    dissolve/morph dispatch to the particle engine (morph without img_b
    falls back to a dissolve of img so strict 0=off still holds).
    `fps` only sets end-hold durations for dissolve/morph (uniform fps
    playback); transition frames ignore it.
    """
    from app.ordered_maps import march_offset
    from app.render_params import normalize_slice_bands

    if mode not in GIF_MODES:
        mode = "both"
    if mode == "dissolve":
        return gif_dissolve_frames(img, preset, frames=frames,
                                   max_side=max_side, pingpong=pingpong, fps=fps)
    if mode == "morph":
        if img_b is None:
            return gif_dissolve_frames(img, preset, frames=frames,
                                       max_side=max_side, pingpong=pingpong, fps=fps)
        return gif_morph_frames(img, img_b, preset, frames=frames,
                                max_side=max_side, pingpong=pingpong, fps=fps)
    n = _clamp_frames(frames)
    side = int(getattr(preset, "gif_size", GIF_MAX_SIDE) if max_side is None else max_side)
    pp = bool(getattr(preset, "gif_pingpong", False)) if pingpong is None else bool(pingpong)
    small = _fit_small(img.convert("RGB"), side)
    # Motion amount: 1.0 = legacy amplitudes (byte-identical), 0 = freeze, up to 3.
    # (NaN clamps to 0.0 via max below.)
    amt = min(3.0, max(0.0, float(getattr(preset, "motion_amount", 1.0) or 0.0)))

    from app.pipeline import render
    from app.render_params import preset_to_render_kwargs

    base_kwargs = preset_to_render_kwargs(preset)
    base_hue = float(preset.pre_hue)

    # Animated post-fx baselines: strict 0=off (MOTION never forces
    # slices/chroma/wave/grain; FX and DATAMOSH panels rule).
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
    march_method = str(getattr(preset, "method", "bayer4"))
    for i in range(n):
        kwargs = dict(base_kwargs)
        kwargs["phase"] = march_offset(march_method, i, n, amt) if want_phase else 0
        # Drift owns its timeline: full traverse per clip, not dither march.
        kwargs["drift_progress"] = float(i) / float(n)
        if want_hue:
            kwargs["pre_hue"] = base_hue + round(14.0 * amt * math.sin(2.0 * math.pi * i / n), 2)
        frame = render(small, **kwargs)

        t = 2.0 * math.pi * i / n
        progress = float(i) / float(n)
        if want_glitch:
            from app.glitch import chromatic_aberration
            from app.glitch import slice_shift_loop, wave_loop
            from app.mosh import MOSH_MODES, apply_mosh

            # Strict 0=off: every channel below only runs when its
            # FX/DATAMOSH value is >0. No forced wobble on clean presets.
            if base_chroma > 0:
                amp_c = int(base_chroma)
                dx = int(round(amp_c * amt * math.sin(t)))
                if dx:
                    frame = chromatic_aberration(frame, dx=dx)
            # Slices: needs bands (>=2) and max offset (>0) from FX.
            # Loop-perfect: fixed seed + sin envelope (progress 0 == 1).
            if base_bands >= 2 and base_max > 0:
                maxoff = int(round(float(base_max) * amt))
                if maxoff > 0:
                    frame = slice_shift_loop(frame, bands=int(base_bands), max_offset=maxoff,
                                             seed=0x6A17, progress=progress)
            # Wave: only when FX wave >0.
            if base_wave > 0:
                amp_w = int(round(float(base_wave) * amt))
                if amp_w > 0:
                    frame = wave_loop(frame, amplitude=amp_w, seed=0x9A9E, progress=progress)
            # Mosh: only if the preset asks for it (too chaotic as default).
            # Loop-perfect: fixed seed, periodic amount envelope.
            if base_mosh > 0:
                mosh_amt = base_mosh * amt * (0.6 + 0.4 * math.sin(t + 1.0))
                mosh_mode = str(getattr(preset, "mosh_mode", "blocks") or "blocks")
                if mosh_mode not in MOSH_MODES:
                    mosh_mode = "blocks"
                mosh_seed = int(getattr(preset, "mosh_seed", 0) or 0)
                mosh_size = int(getattr(preset, "mosh_size", 100) or 100)
                frame = apply_mosh(frame, mode=mosh_mode,
                                   amount=max(0.0, mosh_amt),
                                   seed=mosh_seed, size=mosh_size)

        # Grain shimmer in mix: strict 0=off (no forced grain on clean
        # presets). Loop-perfect breathing so the loop point has no jump.
        if mode == "mix":
            from app.fx import apply_grain

            if base_grain > 0:
                g_eff = float(base_grain) * amt * (0.7 + 0.3 * math.sin(t))
                frame = apply_grain(frame, amount=max(0.0, g_eff), seed=0x7A4B)
            if base_dust > 0:
                from app.texture import dust as grain_dust

                d_eff = float(base_dust) * amt * (0.7 + 0.3 * math.sin(t))
                frame = grain_dust(frame, amount=max(0.0, d_eff), seed=0xD57)
        elif base_grain > 0 or base_dust > 0:
            # Non-mix modes keep the preset grain but breathing (no freeze,
            # no jump cut).
            from app.fx import apply_grain

            t_grain = 2.0 * math.pi * i / n
            if base_grain > 0:
                g_eff = float(base_grain) * amt * (0.7 + 0.3 * math.sin(t_grain))
                frame = apply_grain(frame, amount=max(0.0, g_eff), seed=0x7A4B)
            if base_dust > 0:
                from app.texture import dust as grain_dust

                d_eff = float(base_dust) * amt * (0.7 + 0.3 * math.sin(t_grain))
                frame = grain_dust(frame, amount=max(0.0, d_eff), seed=0xD57)

        out.append(frame)

    if pp:
        out = _pingpong(out)
    return out


#: Hard cap on total built frames (transitions + holds + pads).
MAX_TOTAL_FRAMES = 256


def plan_dissolve(n_req: int, segs: int, fps: int, hold_s: float,
                  target_s: float | None) -> dict:
    """Frame budget honoring a sacred total duration (v1.13).

    n_trans covers transitions (min 2 per segment so every form appears
    assembled); holds duplicate assembled ends; pad fills up to the target
    seconds so exports never come out short. Transitions always win over
    holds/pad; the total never exceeds MAX_TOTAL_FRAMES.
    Returns dict(n_trans, hs, he, pad, total, capped, actual_s).
    """
    fps_v = max(1, int(fps or 8))
    segs_v = max(1, int(segs or 1))
    n_trans = min(GIF_MAX_FRAMES, max(2 * segs_v, max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(n_req)))))
    hold_n = int(round(max(0.0, min(3.0, float(hold_s or 0.0))) * fps_v))
    # Fit holds in the 64-frame transition budget (transitions always win).
    room64 = GIF_MAX_FRAMES - n_trans
    if hold_n * 2 <= room64:
        hs, he = hold_n, hold_n
    elif room64 <= 0:
        hs, he = 0, 0
    else:
        hs, he = room64 // 2, room64 - room64 // 2
    if target_s is None:
        want_total = n_trans + hs + he
    else:
        want_total = max(n_trans + hs + he, int(round(max(0.0, float(target_s)) * fps_v)))
    if want_total <= MAX_TOTAL_FRAMES:
        pad = want_total - (n_trans + hs + he)
        return {"n_trans": n_trans, "hs": hs, "he": he, "pad": pad,
                "total": n_trans + hs + he + pad,
                "capped": False, "actual_s": (n_trans + hs + he + pad) / fps_v}
    room = MAX_TOTAL_FRAMES - n_trans
    hs2, he2 = (0, 0) if room <= 0 else (min(hs, room // 2), 0)
    if room > 0:
        he2 = min(he, room - hs2)
    pad = max(0, MAX_TOTAL_FRAMES - (n_trans + hs2 + he2))
    total = n_trans + hs2 + he2 + pad
    return {"n_trans": n_trans, "hs": hs2, "he": he2, "pad": pad,
            "total": total, "capped": True, "actual_s": total / fps_v}


def _canvas_a(img: Image.Image, preset, side: int) -> Image.Image:
    """A image for dissolve/morph: pipeline canvas when preset, else raw fit.

    Honors the IMAGE section framing (ratio/crop/focus/zoom) so A matches
    the still preview instead of the raw source.
    """
    small = img.convert("RGB")
    if preset is None:
        r = side / max(small.width, small.height)
        if r < 1.0:
            small = small.resize((max(1, round(small.width * r)),
                                  max(1, round(small.height * r))), Image.BICUBIC)
        return small
    from app.canvas import to_canvas

    a = to_canvas(small, ratio=str(getattr(preset, "ratio", "1:1") or "1:1"),
                  mode=str(getattr(preset, "crop_mode", "cover") or "cover"),
                  fx=float(getattr(preset, "focus_x", 50.0) or 50.0),
                  fy=float(getattr(preset, "focus_y", 50.0) or 50.0),
                  zoom=float(getattr(preset, "crop_zoom", 1.0) or 1.0),
                  canvas_w=int(getattr(preset, "canvas_w", 0) or 0),
                  canvas_h=int(getattr(preset, "canvas_h", 0) or 0))
    r = side / max(a.width, a.height)
    if r < 1.0:
        a = a.resize((max(1, round(a.width * r)),
                      max(1, round(a.height * r))), Image.BICUBIC)
    return a


def _split_chain_entries(img_b) -> tuple[list, list]:
    """Normalize chain input to (images, per-image crop dicts).

    Accepts PIL images or {"img": PIL, "fx":.., "fy":.., "zoom":..} dicts
    (MORPH playlist entries). Crops default to center/no-zoom.
    """
    if img_b is None:
        return [], []
    items = list(img_b) if isinstance(img_b, list) else [img_b]
    imgs, crops = [], []
    for it in items:
        if isinstance(it, dict):
            img = it.get("img")
            if img is None:
                continue
            crops.append({"fx": it.get("fx", 50.0), "fy": it.get("fy", 50.0),
                          "zoom": it.get("zoom", 1.0)})
        else:
            img = it
            crops.append({})
        try:
            imgs.append(img.convert("RGB"))
        except Exception:  # noqa: BLE001
            if crops:
                crops.pop()
    return imgs, crops


def gif_dissolve_frames(img: Image.Image, preset=None, frames: int = 8,
                        max_side: int | None = None,
                        pingpong: bool | None = None, seed: int | None = None,
                        wind: tuple[float, float] | None = None,
                        mode: str | None = None, loops: float | None = None,
                        amount: float | None = None,
                        fps: int | None = None) -> list[Image.Image]:
    """Particle disperse loop for one image (Fase 2, solo dispersion).

    Dithers once (preset method/threshold/pixel_size) then marches
    progress=i/n with a breathe envelope (assembled -> dispersed ->
    assembled, loop-perfect). Deterministic by seed. amount 0 returns
    n copies of the dithered still (strict 0=off). `fps` only sets end
    hold durations from dissolve_hold seconds. Reuses save_gif()
    and video_io.write_mp4() for export (same stem _gif.gif / _vid.mp4).
    """
    from app.disintegrate import DISINTEGRATE_MODES, dissolve_frames

    n = _clamp_frames(frames)
    if preset is None:
        side = int(max_side or GIF_MAX_SIDE)
        pp = bool(pingpong or False)
        method, threshold, pixel = "bayer8", 128.0, 1
    else:
        side = int(getattr(preset, "gif_size", GIF_MAX_SIDE) if max_side is None else max_side)
        pp = bool(getattr(preset, "gif_pingpong", False)) if pingpong is None else bool(pingpong)
        method = str(getattr(preset, "method", "bayer8") or "bayer8")
        threshold = float(getattr(preset, "threshold", 128.0) or 128.0)
        pixel = max(1, int(getattr(preset, "pixel_size", 1) or 1))
    seed_v = 0xD15C if seed is None else int(seed)
    if preset is not None and seed is None:
        seed_v = int(getattr(preset, "dissolve_seed", seed_v) or seed_v)
    wind_v = (120.0, -40.0) if wind is None else (float(wind[0]), float(wind[1]))
    if preset is not None and wind is None:
        wx = getattr(preset, "dissolve_wind_x", None)
        wy = getattr(preset, "dissolve_wind_y", None)
        if wx is not None and wy is not None:
            wind_v = (float(wx), float(wy))
    mode_v = "wind" if mode is None else str(mode)
    if preset is not None and mode is None:
        mode_v = str(getattr(preset, "dissolve_mode", mode_v) or mode_v)
    if mode_v not in DISINTEGRATE_MODES:
        mode_v = "wind"
    loops_v = 1.0 if loops is None else float(loops)
    if preset is not None and loops is None:
        loops_v = float(getattr(preset, "dissolve_speed", getattr(preset, "drift_speed", loops_v)) or loops_v)
    amount_v = 1.0 if amount is None else float(amount)
    if preset is not None and amount is None:
        amount_v = float(getattr(preset, "dissolve_amount", amount_v))
    fps_v = max(1, int(fps if fps is not None else getattr(preset, "gif_fps", 8) if preset is not None else 8))
    target_s = float(getattr(preset, "dissolve_length", 0.0) or 0.0) if preset is not None else 0.0
    plan = plan_dissolve(n, 1, fps_v,
                         float(getattr(preset, "dissolve_hold", 0.0) or 0.0) if preset is not None else 0.0,
                         target_s if target_s > 0 else None)
    a = _canvas_a(img, preset, side)
    out = dissolve_frames(a, method=method, threshold=threshold,
                          pixel_size=pixel, frames=plan["n_trans"], seed=seed_v, wind=wind_v,
                          mode=mode_v, loops=loops_v, amount=amount_v,
                          max_side=side, hold_start=plan["hs"], hold_end=plan["he"] + plan["pad"])
    if pp:
        out = _pingpong(out)
    return out


def gif_morph_frames(img_a: Image.Image, img_b=None, preset=None,
                     frames: int = 8, max_side: int | None = None,
                     pingpong: bool | None = None, seed: int | None = None,
                     wind: tuple[float, float] | None = None,
                     mode: str | None = None,
                     amount: float | None = None,
                     fps: int | None = None) -> list[Image.Image]:
    """Swap A -> B (-> C ...) through particle clouds (Fase 5 + v1.8 chain).

    img_b may be a single image or a list (chain A -> B -> C ..., capped
    at MAX_MORPH_IMAGES). Same dither engine for all images (preset
    method/threshold/pixel). Transition frames get a 2-per-segment floor
    so every form appears at least assembled (strict correctness); `fps`
    only sets end hold durations. Deterministic. For a seamless GIF loop
    use pingpong=True (A->B->A).
    """
    from app.disintegrate import DISINTEGRATE_MODES, morph_chain_frames

    n = _clamp_frames(frames)
    if preset is None:
        side = int(max_side or GIF_MAX_SIDE)
        pp = bool(pingpong or False)
        method, threshold, pixel = "bayer8", 128.0, 1
    else:
        side = int(getattr(preset, "gif_size", GIF_MAX_SIDE) if max_side is None else max_side)
        pp = bool(getattr(preset, "gif_pingpong", False)) if pingpong is None else bool(pingpong)
        method = str(getattr(preset, "method", "bayer8") or "bayer8")
        threshold = float(getattr(preset, "threshold", 128.0) or 128.0)
        pixel = max(1, int(getattr(preset, "pixel_size", 1) or 1))
    seed_v = 0xD15C if seed is None else int(seed)
    if preset is not None and seed is None:
        seed_v = int(getattr(preset, "dissolve_seed", seed_v) or seed_v)
    wind_v = (120.0, -40.0) if wind is None else (float(wind[0]), float(wind[1]))
    if preset is not None and wind is None:
        wx = getattr(preset, "dissolve_wind_x", None)
        wy = getattr(preset, "dissolve_wind_y", None)
        if wx is not None and wy is not None:
            wind_v = (float(wx), float(wy))
    mode_v = "wind" if mode is None else str(mode)
    if preset is not None and mode is None:
        mode_v = str(getattr(preset, "dissolve_mode", mode_v) or mode_v)
    if mode_v not in DISINTEGRATE_MODES:
        mode_v = "wind"
    amount_v = 1.0 if amount is None else float(amount)
    if preset is not None and amount is None:
        amount_v = float(getattr(preset, "dissolve_amount", amount_v))
    others, other_crops = _split_chain_entries(img_b)
    if not others:
        return gif_dissolve_frames(img_a, preset, frames=n, max_side=side,
                                   pingpong=pp, seed=seed_v, wind=wind_v,
                                   mode=mode_v, amount=amount_v, fps=fps)
    fps_v = max(1, int(fps if fps is not None else getattr(preset, "gif_fps", 8) if preset is not None else 8))
    target_s = float(getattr(preset, "dissolve_length", 0.0) or 0.0) if preset is not None else 0.0
    plan = plan_dissolve(n, len(others), fps_v,
                         float(getattr(preset, "dissolve_hold", 0.0) or 0.0) if preset is not None else 0.0,
                         target_s if target_s > 0 else None)
    n_trans, hs, he, pad = plan["n_trans"], plan["hs"], plan["he"], plan["pad"]
    a = _canvas_a(img_a, preset, side)
    crops = [{}] + other_crops
    out = morph_chain_frames([a] + others, method=method,
                             threshold=threshold, pixel_size=pixel, frames=n_trans,
                             seed=seed_v, wind=wind_v, mode=mode_v,
                             amount=amount_v, max_side=side,
                             hold_start=hs, hold_end=he + pad, crops=crops)
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
