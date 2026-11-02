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


def _dissolve_style(preset) -> tuple[str, str]:
    """(stagger, ease) from a preset (F1 defaults = legacy: off/sine)."""
    from app.disintegrate import EASE_MODES, STAGGER_MODES

    st = str(getattr(preset, "dissolve_stagger", "off") or "off") if preset is not None else "off"
    ez = str(getattr(preset, "dissolve_ease", "sine") or "sine") if preset is not None else "sine"
    return (st if st in STAGGER_MODES else "off", ez if ez in EASE_MODES else "sine")


def _dissolve_tint(preset) -> float:
    """Source-color dot tint 0..1 (F4, default 0 = legacy BW)."""
    if preset is None:
        return 0.0
    return min(1.0, max(0.0, float(getattr(preset, "dissolve_tint", 0.0) or 0.0)))


def _dissolve_trail(preset) -> int:
    """Ghost-dot trail frames 0..8 (F5, default 0 = legacy)."""
    if preset is None:
        return 0
    from app.disintegrate import MAX_TRAIL

    return max(0, min(MAX_TRAIL, int(getattr(preset, "dissolve_trail", 0) or 0)))


def _dissolve_shade(preset) -> bool:
    """Heckel dot-size by darkness (F6, default off = uniform swell)."""
    if preset is None:
        return False
    return bool(getattr(preset, "dissolve_shade", False))


def _dissolve_paint(preset):
    """Palette inks for morph following (F7) or None (legacy BW).

    Mirrors separations.effective_palette resolution (custom > SOURCE
    extract > named + depth) but returns None for the BW fast path so
    the legacy engine stays byte-identical. "SOURCE" defers extraction
    to the engine (per fitted image).
    """
    if preset is None:
        return None
    from app.pipeline import resolve_palette
    from app.render_params import apply_palette_depth, normalize_palette_depth

    pal, _ = resolve_palette(str(getattr(preset, "palette", "SLIME") or "SLIME"),
                             getattr(preset, "custom_palette", None))
    if pal is None:
        return None
    if pal == "SOURCE":
        return "SOURCE"
    depth = normalize_palette_depth(int(getattr(preset, "palette_depth", 0) or 0))
    inks = [tuple(max(0, min(255, int(c))) for c in col)
            for col in apply_palette_depth([tuple(c) for c in pal], depth)]
    return inks or None


def _dissolve_adjust(preset):
    """IMAGE adjust for the morph engine (None = legacy identical)."""
    if preset is None:
        return None
    try:
        return preset.adjust()
    except Exception:  # noqa: BLE001
        return None


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
#: GIF/preview stay here (RAM + format + browsers choke past ~25MB).
MAX_TOTAL_FRAMES = 256
#: MP4 streams frame by frame (O(1) RAM), so long hold-heavy clips
#: still export: 60s * 60fps = 3600 frames max.
MAX_MP4_FRAMES = 3600


def plan_dissolve(n_req: int, segs: int, fps: int, hold_s: float,
                  target_s: float | None = None,
                  cap: int | None = None, loop: bool = False) -> dict:
    """Frame budget where Hold mandates and Length is derived.

    Total = transitions + requested holds, nothing else: there is no pad
    to a sacred total (Hold-manda). Every Hold tick adds still frames, so
    the slider is never dead. `target_s` is accepted for backward
    compat but IGNORED (old presets carrying dissolve_length render
    without padding; their stored value is just not honored anymore).
    n_trans covers transitions (min 2 per segment so every form appears
    assembled). Holds duplicate assembled forms: start + end + one per
    interior joint (v1.14: every form reads, not just the last one),
    shared equally across ALL forms (differ by at most 1 frame).
    Transitions always win over holds: when the requested holds do not
    fit `cap` they shrink to it (capped=True). The total never exceeds
    `cap` (default MAX_TOTAL_FRAMES=256 for GIF/preview; MP4 streaming
    passes MAX_MP4_FRAMES=3600 so long hold-heavy clips still stream).
    With loop=True the chain closes (last morphs back into first for a
    seamless loop): one extra leg, and A's share is split between the
    opening and closing holds so no form reads double.
    Returns dict(n_trans, hs, he, hj, holds, pad, total, capped,
    actual_s, cap, loop). `holds` is the exact per-position list
    ([start, joints..., end]; loop splits A across both ends);
    hs/he/hj mirror it (hj = first joint, representative when the
    remainder spills unevenly by 1). `pad` is always 0 (kept key).
    """
    cap_v = int(cap) if cap else MAX_TOTAL_FRAMES
    cap_v = max(GIF_MAX_FRAMES, cap_v)
    fps_v = max(1, int(fps or 8))
    segs_v = max(1, int(segs or 1))
    loop_v = bool(loop)
    legs = segs_v + (1 if loop_v else 0)
    forms = segs_v + 1  # unique images: A + chain
    joints = max(0, segs_v - 1)
    n_trans = min(GIF_MAX_FRAMES, max(2 * legs, max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(n_req)))))
    # Hold mandates: requested still frames per form, uncapped by the
    # 64-frame transition budget (that cap is what made the slider dead
    # under a sacred Length). Only the output `cap` can shrink holds,
    # transitions always win.
    per = int(round(max(0.0, min(3.0, float(hold_s or 0.0))) * fps_v))
    room = max(0, cap_v - n_trans)
    req = per * forms
    capped = req > room
    # Share still time equally across every unique form so no single
    # image hogs the clip. Remainder round-robin starts at the end
    # (legacy bias), then start, then joints in play order.
    q, r = divmod(min(req, room), max(1, forms))
    shares = [q] * forms
    order = [forms - 1, 0] + list(range(1, forms - 1))
    for i in range(r):
        shares[order[i % forms]] += 1
    if loop_v:
        # A's share lives at both loop ends (they are adjacent in loop
        # playback): split it so A reads the same total as every form.
        a_half, a_rest = divmod(max(0, int(shares[0])), 2)
        holds = [a_half] + shares[1:] + [a_half + a_rest]
    else:
        holds = list(shares)
    hs, he = holds[0], holds[-1]
    hj = holds[1] if len(holds) > 1 else 0
    total = n_trans + sum(holds)
    return {"n_trans": n_trans, "hs": hs, "he": he, "hj": hj, "holds": holds,
            "pad": 0, "total": total, "joints": joints, "cap": cap_v,
            "capped": capped, "actual_s": total / fps_v, "loop": loop_v}


def hold_for_target(n_req: int, segs: int, fps: int, target_s: float,
                    loop: bool = False) -> tuple[float, float, bool]:
    """Hold per form (seconds) so the derived total reaches target_s.

    BPM->Length solver (R3): target = bars * 240 / bpm (4/4). Hold is
    capped at 3.0s; transitions alone may already overshoot a tiny
    target (then hold 0 and fits=False: fewer Frames needed).
    Returns (hold_s, actual_s, fits).
    """
    from math import ceil

    fps_v = max(1, int(fps or 8))
    want = int(round(max(0.0, float(target_s or 0.0)) * fps_v))
    base = plan_dissolve(n_req, segs, fps_v, 0.0, None, loop=loop)
    nt = int(base["n_trans"])
    forms = max(1, int(segs or 1) + 1)
    need = want - nt
    if need <= 0:
        return (0.0, nt / fps_v, nt <= want)
    per = min(int(ceil(need / forms)), 3 * fps_v)
    hold = per / fps_v
    plan = plan_dissolve(n_req, segs, fps_v, hold, None, loop=loop)
    return (hold, float(plan["actual_s"]), int(plan["total"]) >= want)


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


def iter_dissolve_frames(img: Image.Image, preset=None, frames: int = 8,
                         max_side: int | None = None,
                         seed: int | None = None,
                         wind: tuple[float, float] | None = None,
                         mode: str | None = None, loops: float | None = None,
                         amount: float | None = None,
                         fps: int | None = None,
                         cap: int | None = None):
    """Yield dissolve frames one by one (streaming: O(1) RAM for long MP4).

    Same pixels as gif_dissolve_frames(pingpong=False). No ping-pong here:
    reversing a 3600-frame stream would need the whole list in RAM; short
    clips (<=256f) keep ping-pong via the list path.
    """
    from app.disintegrate import DISINTEGRATE_MODES, iter_dissolve

    n = _clamp_frames(frames)
    if preset is None:
        side = int(max_side or GIF_MAX_SIDE)
        method, threshold, pixel = "bayer8", 128.0, 1
    else:
        side = int(getattr(preset, "gif_size", GIF_MAX_SIDE) if max_side is None else max_side)
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
    stagger_v, ease_v = _dissolve_style(preset)
    dotsize_v = max(1, int(getattr(preset, "dissolve_dotsize", 1) or 1)) if preset is not None else 1
    loops_v = 1.0 if loops is None else float(loops)
    if preset is not None and loops is None:
        loops_v = float(getattr(preset, "dissolve_speed", getattr(preset, "drift_speed", loops_v)) or loops_v)
    amount_v = 1.0 if amount is None else float(amount)
    if preset is not None and amount is None:
        amount_v = float(getattr(preset, "dissolve_amount", amount_v))
    fps_v = max(1, int(fps if fps is not None else getattr(preset, "gif_fps", 8) if preset is not None else 8))
    # Hold-manda: dissolve_length ignored (Length is derived), no target pad
    plan = plan_dissolve(n, 1, fps_v,
                         float(getattr(preset, "dissolve_hold", 0.0) or 0.0) if preset is not None else 0.0,
                         None,  # Hold-manda: no Length pad
                         cap=cap if cap else MAX_MP4_FRAMES)
    a = _canvas_a(img, preset, side)
    yield from iter_dissolve(a, method=method, threshold=threshold,
                             pixel_size=pixel, frames=plan["n_trans"], seed=seed_v, wind=wind_v,
                             mode=mode_v, loops=loops_v, amount=amount_v,
                             max_side=side, hold_start=plan["hs"],
                             hold_end=plan["he"], stagger=stagger_v, ease=ease_v,
                             dotsize=dotsize_v, tint=_dissolve_tint(preset),
                             trail=_dissolve_trail(preset),
                             shade=_dissolve_shade(preset),
                             adjust=_dissolve_adjust(preset),
                             palette=_dissolve_paint(preset),
                             palette_depth=int(getattr(preset, "palette_depth", 0) or 0))


def _morph_loop(preset, loop: bool | None) -> bool:
    """Loop flag: explicit param wins, else the preset (default off)."""
    if loop is not None:
        return bool(loop)
    if preset is None:
        return False
    return bool(getattr(preset, "dissolve_loop", False))


def iter_morph_frames(img_a: Image.Image, img_b=None, preset=None,
                      frames: int = 8, max_side: int | None = None,
                      seed: int | None = None,
                      wind: tuple[float, float] | None = None,
                      mode: str | None = None,
                      amount: float | None = None,
                      fps: int | None = None,
                      cap: int | None = None,
                      loop: bool | None = None):
    """Yield morph chain frames one by one (streaming: O(1) RAM for long MP4)."""
    from app.disintegrate import DISINTEGRATE_MODES, iter_morph_chain

    n = _clamp_frames(frames)
    if preset is None:
        side = int(max_side or GIF_MAX_SIDE)
        method, threshold, pixel = "bayer8", 128.0, 1
    else:
        side = int(getattr(preset, "gif_size", GIF_MAX_SIDE) if max_side is None else max_side)
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
    stagger_v, ease_v = _dissolve_style(preset)
    dotsize_v = max(1, int(getattr(preset, "dissolve_dotsize", 1) or 1)) if preset is not None else 1
    travel_v = min(1.0, max(0.0, float(getattr(preset, "dissolve_travel", 0.0) or 0.0))) if preset is not None else 0.0
    amount_v = 1.0 if amount is None else float(amount)
    if preset is not None and amount is None:
        amount_v = float(getattr(preset, "dissolve_amount", amount_v))
    others, other_crops = _split_chain_entries(img_b)
    if not others:
        yield from iter_dissolve_frames(img_a, preset, frames=n, max_side=side,
                                        seed=seed_v, wind=wind_v, mode=mode_v,
                                        amount=amount_v, fps=fps, cap=cap)
        return
    fps_v = max(1, int(fps if fps is not None else getattr(preset, "gif_fps", 8) if preset is not None else 8))
    # Hold-manda: dissolve_length ignored (Length is derived), no target pad
    loop_v = _morph_loop(preset, loop)
    plan = plan_dissolve(n, len(others), fps_v,
                         float(getattr(preset, "dissolve_hold", 0.0) or 0.0) if preset is not None else 0.0,
                         None,  # Hold-manda: no Length pad
                         cap=cap if cap else MAX_MP4_FRAMES, loop=loop_v)
    a = _canvas_a(img_a, preset, side)
    crops = [{}] + other_crops
    yield from iter_morph_chain([a] + others, method=method,
                                threshold=threshold, pixel_size=pixel, frames=plan["n_trans"],
                                seed=seed_v, wind=wind_v, mode=mode_v,
                                amount=amount_v, max_side=side,
                                hold_start=plan["hs"], hold_end=plan["he"],
                                hold_joint=plan["holds"][1:-1], crops=crops,
                                loop=loop_v, stagger=stagger_v, ease=ease_v,
                                dotsize=dotsize_v, travel=travel_v,
                                tint=_dissolve_tint(preset),
                                trail=_dissolve_trail(preset),
                                shade=_dissolve_shade(preset),
                                adjust=_dissolve_adjust(preset),
                                palette=_dissolve_paint(preset),
                                palette_depth=int(getattr(preset, "palette_depth", 0) or 0))


def gif_dissolve_frames(img: Image.Image, preset=None, frames: int = 8,
                        max_side: int | None = None,
                        pingpong: bool | None = None, seed: int | None = None,
                        wind: tuple[float, float] | None = None,
                        mode: str | None = None, loops: float | None = None,
                        amount: float | None = None,
                        fps: int | None = None,
                        cap: int | None = None) -> list[Image.Image]:
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
    stagger_v, ease_v = _dissolve_style(preset)
    dotsize_v = max(1, int(getattr(preset, "dissolve_dotsize", 1) or 1)) if preset is not None else 1
    loops_v = 1.0 if loops is None else float(loops)
    if preset is not None and loops is None:
        loops_v = float(getattr(preset, "dissolve_speed", getattr(preset, "drift_speed", loops_v)) or loops_v)
    amount_v = 1.0 if amount is None else float(amount)
    if preset is not None and amount is None:
        amount_v = float(getattr(preset, "dissolve_amount", amount_v))
    fps_v = max(1, int(fps if fps is not None else getattr(preset, "gif_fps", 8) if preset is not None else 8))
    # Hold-manda: dissolve_length ignored (Length is derived), no target pad
    plan = plan_dissolve(n, 1, fps_v,
                         float(getattr(preset, "dissolve_hold", 0.0) or 0.0) if preset is not None else 0.0,
                         None,  # Hold-manda: no Length pad
                         cap=cap if cap else MAX_TOTAL_FRAMES)
    _check_gif_budget(plan["total"], side, side)  # approx (long side); exact check in save_gif
    a = _canvas_a(img, preset, side)
    out = dissolve_frames(a, method=method, threshold=threshold,
                          pixel_size=pixel, frames=plan["n_trans"], seed=seed_v, wind=wind_v,
                          mode=mode_v, loops=loops_v, amount=amount_v,
                          max_side=side, hold_start=plan["hs"], hold_end=plan["he"],
                          stagger=stagger_v, ease=ease_v, dotsize=dotsize_v,
                          tint=_dissolve_tint(preset),
                          trail=_dissolve_trail(preset),
                          shade=_dissolve_shade(preset),
                          adjust=_dissolve_adjust(preset),
                          palette=_dissolve_paint(preset),
                          palette_depth=int(getattr(preset, "palette_depth", 0) or 0))
    if pp:
        out = _pingpong(out)
    return out


def gif_morph_frames(img_a: Image.Image, img_b=None, preset=None,
                     frames: int = 8, max_side: int | None = None,
                     pingpong: bool | None = None, seed: int | None = None,
                     wind: tuple[float, float] | None = None,
                     mode: str | None = None,
                     amount: float | None = None,
                     fps: int | None = None,
                     cap: int | None = None,
                     loop: bool | None = None) -> list[Image.Image]:
    """Swap A -> B (-> C ...) through particle clouds (Fase 5 + v1.8 chain).

    img_b may be a single image or a list (chain A -> B -> C ..., capped
    at MAX_MORPH_IMAGES). Same dither engine for all images (preset
    method/threshold/pixel). Transition frames get a 2-per-leg floor
    so every form appears at least assembled (strict correctness); `fps`
    only sets end hold durations. Deterministic. With loop=True the last
    form morphs back into the first (closed loop, no hard cut, no
    ping-pong needed); without it use pingpong=True (A->B->A) for a
    seamless GIF loop.
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
    stagger_v, ease_v = _dissolve_style(preset)
    dotsize_v = max(1, int(getattr(preset, "dissolve_dotsize", 1) or 1)) if preset is not None else 1
    travel_v = min(1.0, max(0.0, float(getattr(preset, "dissolve_travel", 0.0) or 0.0))) if preset is not None else 0.0
    amount_v = 1.0 if amount is None else float(amount)
    if preset is not None and amount is None:
        amount_v = float(getattr(preset, "dissolve_amount", amount_v))
    others, other_crops = _split_chain_entries(img_b)
    if not others:
        return gif_dissolve_frames(img_a, preset, frames=n, max_side=side,
                                   pingpong=pp, seed=seed_v, wind=wind_v,
                                   mode=mode_v, amount=amount_v, fps=fps,
                                   cap=cap)
    fps_v = max(1, int(fps if fps is not None else getattr(preset, "gif_fps", 8) if preset is not None else 8))
    # Hold-manda: dissolve_length ignored (Length is derived), no target pad
    loop_v = _morph_loop(preset, loop)
    plan = plan_dissolve(n, len(others), fps_v,
                         float(getattr(preset, "dissolve_hold", 0.0) or 0.0) if preset is not None else 0.0,
                         None,  # Hold-manda: no Length pad
                         cap=cap if cap else MAX_TOTAL_FRAMES, loop=loop_v)
    _check_gif_budget(plan["total"], side, side)  # approx (long side); exact check in save_gif
    a = _canvas_a(img_a, preset, side)
    crops = [{}] + other_crops
    out = morph_chain_frames([a] + others, method=method,
                             threshold=threshold, pixel_size=pixel, frames=plan["n_trans"],
                             seed=seed_v, wind=wind_v, mode=mode_v,
                             amount=amount_v, max_side=side,
                             hold_start=plan["hs"], hold_end=plan["he"],
                             hold_joint=plan["holds"][1:-1],
                             crops=crops, loop=loop_v,
                             stagger=stagger_v, ease=ease_v, dotsize=dotsize_v,
                             travel=travel_v, tint=_dissolve_tint(preset),
                             trail=_dissolve_trail(preset),
                             shade=_dissolve_shade(preset),
                             adjust=_dissolve_adjust(preset),
                             palette=_dissolve_paint(preset),
                             palette_depth=int(getattr(preset, "palette_depth", 0) or 0))
    if pp and not loop_v:
        # Closed loop already seamless; mirroring it would just double it.
        out = _pingpong(out)
    return out


#: RAM budget for a GIF frame list (pixels): beyond this save_gif would
#: transiently hold ~4 bytes/px (caller list + paletted copy) and OOM a
#: typical machine. Checked with planned totals (builders, approx) and
#: exact dims (save_gif): fewer Frames/Hold, smaller canvas, or WebP/MP4.
MAX_GIF_PIXELS = 1_200_000_000


def _check_gif_budget(n_frames: int, w: int, h: int) -> None:
    total = max(0, int(n_frames)) * max(1, int(w)) * max(1, int(h))
    if total > MAX_GIF_PIXELS:
        gb = total * 4 / 1_000_000_000
        raise MemoryError(
            f"GIF needs ~{gb:.1f}GB transient RAM for {int(n_frames)} frames "
            f"at {int(w)}x{int(h)} (budget {MAX_GIF_PIXELS // 1_000_000}MP): "
            "fewer Frames/Hold, smaller canvas, or WebP/MP4 instead")


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


def estimate_gif(n_trans: int, w: int, h: int, n_hold_forms: int = 0) -> int:
    """Hold-collapse-aware weight estimate (bytes).

    R8: Pillow fuses identical hold frames (measured: a 20f hold-heavy
    clip collapses ~37x under the old flat frames*w*h//2). Transitions
    cost a full frame each; every still form costs ~1 fused frame.
    The default (0 hold forms) keeps transition-only counts exact.
    """
    px = max(1, int(w)) * max(1, int(h))
    return px * max(0, int(n_trans)) // 2 + px * max(0, int(n_hold_forms)) // 2


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


def estimate_webp(n_trans: int, w: int, h: int, n_hold_forms: int = 0) -> int:
    """Rough weight estimate (bytes): ~1/3 of the GIF at equal quality."""
    return estimate_gif(n_trans, w, h, n_hold_forms) // 3


#: Calibrated H.264 cost at quality=8 (measured 256px bayer8, x264/yuv420p):
#: dithered transition frames are near-incompressible noise (~0.43 B/px),
#: duplicated assembled holds collapse to near-zero (~0.011 B/px, ~40x).
MP4_BYTES_PER_PX_TRANS = 0.43
MP4_BYTES_PER_PX_HOLD = 0.011

#: MP4 long-side choices (main image always stays at canvas size).
MP4_SIZES = ("Canvas", "1080p", "720p")


def _even_down(n: int) -> int:
    """Round down to an even int, floor 2 (H.264/yuv420p needs multiples of 2)."""
    return max(2, int(n) & ~1)


def mp4_dims(doc_w: int, doc_h: int, size_opt: str | int = "1080p") -> tuple[int, int]:
    """MP4 frame dims preserving aspect (long side per option).

    Always even (H.264/yuv420p requires multiples of 2; imageio would
    otherwise rescale to a multiple of 16, e.g. 1080x1920 -> 1088x1920).
    Rounds down to even so the long side never exceeds the request.
    """
    dw, dh = max(1, int(doc_w)), max(1, int(doc_h))
    if isinstance(size_opt, int) or str(size_opt).isdigit():
        long_side = max(64, int(size_opt))
    elif str(size_opt) == "720p":
        long_side = 720
    elif str(size_opt) == "Canvas":
        return (_even_down(dw), _even_down(dh))
    else:
        long_side = 1080
    r = long_side / max(dw, dh)
    if r >= 1.0:
        return (_even_down(dw), _even_down(dh))
    return (_even_down(round(dw * r)), _even_down(round(dh * r)))


def estimate_mp4(w: int, h: int, n_trans: int, n_hold: int) -> int:
    """Content-aware MP4 weight estimate (bytes).

    Transitions are dither noise (expensive); holds are duplicated stills
    (cheap). The old flat 0.12 B/px/frame overestimated hold-heavy clips
    ~8x and hid that 3000px/60fps is impagable even when honest.
    """
    px = max(1, int(w)) * max(1, int(h))
    return int(px * (max(0, int(n_trans)) * MP4_BYTES_PER_PX_TRANS
                     + max(0, int(n_hold)) * MP4_BYTES_PER_PX_HOLD))
