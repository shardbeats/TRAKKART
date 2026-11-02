"""TRAKKART particle disperse + morph (dither-boy style, MIT). Numpy + Pillow only.

Single-image loop (dissolve_frames: assembled -> dispersed -> assembled)
plus one-shot swap (morph_frames: A -> B through one shared particle cloud).

Loop-perfect dissolve: the turbulence pattern is fixed per clip (seeded
once) and only its amplitude breathes with sin(pi*frac), so progress 0 == 1.
Deterministic: same inputs + frame = same pixels (default_rng(seed)).
Strict 0=off: amount 0 returns the still (identity; hard cut for morph).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from app.ordered_maps import BAYER_8X8  # noqa: F401 (re-exported via fields)
from app.particles.color import (darkness_map, dither_bw, inked_points,  # noqa: F401
                                 morph_ink, points_from_dither, sample_colors,
                                 tint_dots, tint_strength, _darkness_of)
from app.particles.fields import (_bayer_rank, _field_offset, _pinned_frac,  # noqa: F401
                                  _rain_profile, ease_env, stagger_delays)
from app.particles.raster import (_paint_layer, dot_sizes, frame_dot_sizes,  # noqa: F401
                                  ghost_entries, render_points, trail_decay)
from app.particles.modes import (DISINTEGRATE_MODES, EASE_MODES, MAX_MORPH_IMAGES,
                                 MAX_POINTS, MAX_TRAIL, STAGGER_MODES, TRAVEL_SPAN)


def _fit_cover(im: Image.Image, w: int, h: int, fx: float = 50.0,
               fy: float = 50.0, zoom: float = 1.0) -> Image.Image:
    """Cover-fit to exact WxH (IMAGE-section semantics, no distortion).

    Same crop_cover the pipeline uses (focus 0-100 + zoom >= 1).
    """
    from app.canvas import CUSTOM_RATIO, crop_cover

    box = crop_cover(im.convert("RGB"), CUSTOM_RATIO, float(fx), float(fy),
                     max(1.0, float(zoom)), canvas_w=int(w), canvas_h=int(h))
    if box.size != (int(w), int(h)):
        box = box.resize((max(1, int(w)), max(1, int(h))), Image.BICUBIC)
    return box


def _refit_coords(coords: np.ndarray, hh: int, ww: int, h: int, w: int) -> np.ndarray:
    """Clip out-of-range points (defensive: same dither op => same shape)."""
    if len(coords) == 0:
        return coords
    out = coords.copy()
    out[:, 0] = np.clip(out[:, 0], 0, h - 1)
    out[:, 1] = np.clip(out[:, 1], 0, w - 1)
    return out


def block_visible(coords: np.ndarray, h: int, w: int, progress: float = 0.0,
                  loops: float = 1.0, stagger: str = "off", ease: str = "sine",
                  pixel_size: int = 1, seed: int = 0xD15C) -> np.ndarray:
    """Bool mask of dots that print this frame (blocks mode: no cloud,
    pop by pixel_size cells in bayer-rank order). Loop-perfect: every dot
    prints at the joints (frac 0 == 1 -> env 0). `seed` is accepted for
    call symmetry and ignored (rank grid + geometry are deterministic)."""
    del seed
    n = int(len(coords))
    if n == 0:
        return np.ones(0, dtype=bool)
    st = str(stagger or "off")
    if st not in STAGGER_MODES:
        st = "off"
    px = max(1, int(pixel_size or 1))
    f = np.asarray(coords, dtype=np.float64)
    delays = stagger_delays(f, h, w, st)
    frac = _pinned_frac(progress, loops, delays)
    env = ease_env(frac, ease)
    rank = _bayer_rank(np.floor(f[:, 0] / px), np.floor(f[:, 1] / px))
    # Peak anchor: the densest ~15% of cells persist through full
    # disperse (a pure rank >= env would flash blank white mid-loop).
    return rank >= np.asarray(env, dtype=np.float64) * 0.85


#: Stagger window re-exported from app.particles.modes (single home).


def _smootherstep(t: np.ndarray) -> np.ndarray:
    """Per-particle travel mixer 0 -> 1 (zero velocity at both joints)."""
    x = np.clip(np.asarray(t, dtype=np.float64), 0.0, 1.0)
    return (x * x * x * (x * (x * 6.0 - 15.0) + 10.0)).astype(np.float64)


def match_travel(ca: np.ndarray, cb: np.ndarray, h: int, w: int,
                 seed: int = 0xD15C) -> tuple[np.ndarray, np.ndarray]:
    """Seeded-greedy 1:1 destination assignment A -> B (F3 travel/pour).

    Returns (src, dst) float32 (y,x) of equal length: the smaller set is
    padded by seeded resampling of its own points, then A's points (in
    seeded-shuffle order) each take their nearest free B point via a
    uniform grid with expanding-ring search (seeded fallback when the
    ring cap misses, so dense clusters degrade gracefully). Any
    bijection keeps the leg joints byte-exact; the pairing only shapes
    the mid-flight pour. Deterministic for a given seed.
    """
    a = np.asarray(ca, dtype=np.float32).reshape(-1, 2)
    b = np.asarray(cb, dtype=np.float32).reshape(-1, 2)
    na, nb = int(len(a)), int(len(b))
    if na == 0 or nb == 0:
        return a.copy(), b.copy()
    rng = np.random.default_rng(int(seed))
    if na < nb:
        a = np.concatenate([a, a[rng.integers(0, na, nb - na)]])
    elif nb < na:
        b = np.concatenate([b, b[rng.integers(0, nb, na - nb)]])
    n = int(len(a))
    ext = max(1.0, float(max(int(h), int(w))))
    cell = max(2.0, ext / math.sqrt(max(1, n)))
    inv = 1.0 / cell
    from collections import defaultdict

    grid: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i in range(n):
        grid[(int(b[i, 0] * inv), int(b[i, 1] * inv))].append(i)
    alive = np.ones(n, dtype=bool)
    match = np.empty(n, dtype=np.int64)
    order = rng.permutation(n)
    rmax = 24
    for k in (int(v) for v in order):
        ay, ax = float(a[k, 0]), float(a[k, 1])
        cy, cx = int(ay * inv), int(ax * inv)
        best, bestd = -1, float("inf")
        for r in range(rmax + 1):
            if r == 0:
                ring = ((cy, cx),)
            else:
                ring = ([(cy - r, cx + dx) for dx in range(-r, r + 1)]
                        + [(cy + r, cx + dx) for dx in range(-r, r + 1)]
                        + [(cy + dy, cx - r) for dy in range(-r + 1, r)]
                        + [(cy + dy, cx + r) for dy in range(-r + 1, r)])
            for key in ring:
                for i in grid.get(key, ()):
                    if not alive[i]:
                        continue
                    dy = float(b[i, 0]) - ay
                    dx = float(b[i, 1]) - ax
                    d2 = dy * dy + dx * dx
                    if d2 < bestd:
                        bestd, best = d2, i
            if best >= 0 and bestd <= (float(r) * cell) ** 2:
                break
        if best < 0:  # dense cluster beyond the ring cap: seeded fallback
            rest = np.flatnonzero(alive)
            best = int(rest[int(rng.integers(0, len(rest)))]) if len(rest) else 0
            if not len(rest):
                match[k] = 0
                continue
        match[k] = best
        alive[best] = False
    return a, b[match]


def travel_positions(src: np.ndarray, dst: np.ndarray, h: int, w: int,
                     progress: float = 0.0, seed: int = 0xD15C,
                     wind: tuple[float, float] = (120.0, -40.0),
                     mode: str = "wind", loops: float = 1.0,
                     amount: float = 1.0, stagger: str = "off",
                     ease: str = "sine", travel: float = 1.0,
                     pixel_size: int = 1) -> np.ndarray:
    """Pour positions for one morph frame: dots TRAVEL src -> dst.

    Mixer s(q) is a per-particle smootherstep over a stagger-shifted
    q (joints stay exact: s(0) = 0, s(1) = 1 for every particle), plus
    the field cloud gated by the loop envelope (zero at both joints).
    travel scales the pour (1 = full destination matching). amount 0
    is handled by the caller (strict 0=off: hard cut, no travel).
    """
    s0 = np.asarray(src, dtype=np.float32)
    d0 = np.asarray(dst, dtype=np.float32)
    n = int(len(s0))
    if n == 0:
        return s0.copy()
    st = str(stagger or "off")
    if st not in STAGGER_MODES:
        st = "off"
    ez = str(ease or "sine")
    if ez not in EASE_MODES:
        ez = "sine"
    tv = max(0.0, min(1.0, float(travel)))
    q = max(0.0, min(1.0, float(progress)))
    delays = stagger_delays(s0, h, w, st)
    qi = np.clip(q * (1.0 + TRAVEL_SPAN) - delays * TRAVEL_SPAN, 0.0, 1.0)
    s = _smootherstep(qi).astype(np.float32)
    base = (1.0 - s)[:, None] * s0 + s[:, None] * d0
    amt = max(0.0, min(2.0, float(amount or 0.0)))
    ce = float(ease_env(np.mod(q, 1.0), ez))
    if amt > 0 and ce > 0 and tv > 0:
        md = str(mode or "wind")
        if md not in DISINTEGRATE_MODES:
            md = "wind"
        off = _field_offset(s0, h, w, md, wind, amt, int(seed), qi,
                            max(1, int(pixel_size or 1)))
        base = base + off * (ce * (1.0 - 0.5 * tv))
    out = base
    out[:, 0] = np.clip(out[:, 0], 0, h - 1)
    out[:, 1] = np.clip(out[:, 1], 0, w - 1)
    return out


def disperse_positions(coords: np.ndarray, h: int, w: int, progress: float = 0.0,
                       seed: int = 0xD15C, wind: tuple[float, float] = (120.0, -40.0),
                       mode: str = "wind", loops: float = 1.0,
                       amount: float = 1.0, stagger: str = "off",
                       ease: str = "sine", pixel_size: int = 1) -> np.ndarray:
    """Loop-perfect positions for one frame.

    progress in [0, 1), loops traversals per clip. Fields × stagger × ease
    (F1): the offset field is closed-form per particle, the release is
    staggered per particle (frac_i, loop-safe via %1), the envelope is
    shaped per choice. wind/off/sine renders the legacy bytes exactly.
    amount 0 freezes everything (identity).
    """
    if mode not in DISINTEGRATE_MODES:
        mode = "wind"
    st = str(stagger or "off")
    if st not in STAGGER_MODES:
        st = "off"
    ez = str(ease or "sine")
    if ez not in EASE_MODES:
        ez = "sine"
    amt = max(0.0, min(2.0, float(amount or 0.0)))
    if amt <= 0 or len(coords) == 0:
        return np.asarray(coords, dtype=np.float32).copy()
    loops = max(0.25, min(4.0, float(loops or 1.0)))
    if mode in ("wind", "random") and st == "off" and ez == "sine":
        # Legacy fast path (byte-identical): scalar envelope, same RNG order.
        frac = (float(progress) * float(loops)) % 1.0
        env = math.sin(math.pi * frac)
        n = int(len(coords))
        rng = np.random.default_rng(int(seed))
        if mode == "random":
            spread = 90.0 * amt
            turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
            # (y,x) order: wind tuple is (wx, wy) -> (dy, dx).
            off = turb * env
        else:
            wx, wy = float(wind[0]), float(wind[1])
            spread = 28.0 * amt
            turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
            base = np.array([[wy * amt, wx * amt]], dtype=np.float32)
            off = (base + turb) * env
        out = coords.astype(np.float32) + off
        out[:, 0] = np.clip(out[:, 0], 0, h - 1)
        out[:, 1] = np.clip(out[:, 1], 0, w - 1)
        return out
    n = int(len(coords))
    delays = stagger_delays(coords, h, w, st)
    frac = _pinned_frac(progress, loops, delays)
    env = ease_env(frac, ez).astype(np.float32)
    if mode == "blocks":
        off = np.zeros((n, 2), dtype=np.float32)  # blocks pop, they never drift
    else:
        off = _field_offset(coords, h, w, mode, wind, amt, int(seed),
                            frac, max(1, int(pixel_size or 1)))
        off = off * env[:, None]
    out = coords.astype(np.float32) + off
    out[:, 0] = np.clip(out[:, 0], 0, h - 1)
    out[:, 1] = np.clip(out[:, 1], 0, w - 1)
    return out


#: Motion-trail buffer cap re-exported from app.particles.modes.


def iter_dissolve(img: Image.Image, method: str = "bayer8",
                  threshold: float = 128.0, pixel_size: int = 1,
                  frames: int = 8, seed: int = 0xD15C,
                  wind: tuple[float, float] = (120.0, -40.0),
                  mode: str = "wind", loops: float = 1.0,
                  amount: float = 1.0,
                  max_side: int = 480,
                  hold_start: int = 0, hold_end: int = 0,
                  stagger: str = "off", ease: str = "sine",
                  dotsize: int = 1, tint: float = 0.0, trail: int = 0,
                  shade: bool = False, adjust=None, palette=None,
                  palette_depth: int = 0):
    """Yield dissolve frames one by one (streaming: O(1) RAM for long MP4).

    Same pixels as dissolve_frames(), no list kept alive. Lets MP4 stream
    long clips (up to 3600f) without the 256-frame list cap blowing RAM.
    `dotsize` 1..4 swells dots with the envelope (1 = legacy 1px).
    `tint` 0..1 tints dots with their source colors, gated by the loop
    envelope (0 = legacy BW; joints stay black = byte-exact stills).
    `trail` 0..8 pastes fading ghost dots (0 = legacy; joints stay
    ghost-free = byte-exact stills).
    `shade` sizes dots by source darkness — Heckel-style attenuation
    (False = uniform swell; joints stay 1px either way).
    `adjust` (Adjust|dict|None) grades the source first (identity =
    same pixels, legacy byte-identical). `palette` (None|"SOURCE"|inks)
    follows the palette: dots print the inks at full strength mid-flight
    (None = legacy BW; joints land exact either way).
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES
    from collections import deque

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    small = img.convert("RGB")
    r = side / max(small.width, small.height)
    if r < 1.0:
        small = small.resize((max(1, round(small.width * r)),
                              max(1, round(small.height * r))), Image.BICUBIC)
    from app.adjust import apply_adjust

    work = apply_adjust(small, adjust)
    still, coords, ink_col, h, w = morph_ink(
        work, method, threshold, pixel_size, palette, palette_depth)
    tv = max(0.0, min(1.0, float(tint or 0.0)))
    if max(0.0, min(2.0, float(amount or 0.0))) <= 0.0:
        tv = 0.0  # strict 0=off: frozen still, tint has nothing to paint
    chroma = ink_col is not None
    if chroma:
        tv = 1.0  # palette inks print at full strength mid-flight
    trail_n = max(0, min(MAX_TRAIL, int(trail or 0)))
    trail_on = trail_n > 0 and max(0.0, min(2.0, float(amount or 0.0))) > 0.0
    hist: deque = deque(maxlen=trail_n if trail_n > 0 else 1)
    color_mode = tv > 0.0
    shade_on = bool(shade)
    rgb_src = (sample_colors(work, h, w)
               if (tv > 0 or shade_on) and len(coords) else None)
    base_col = rgb_src
    home_col = ink_col
    home_dark = None
    if home_col is None and base_col is not None:
        home_col = base_col[np.clip(coords[:, 0], 0, h - 1),
                            np.clip(coords[:, 1], 0, w - 1)].astype(np.float64)
    if shade_on and rgb_src is not None and len(coords):
        home_dark = _darkness_of(rgb_src.astype(np.float64), coords, h, w)
    for _ in range(max(0, int(hold_start))):
        yield still.copy()
    for i in range(n):
        progress = float(i) / float(n)
        env = float(ease_env(np.mod(progress, 1.0), ease if ease in EASE_MODES else "sine"))
        if home_col is None:
            cols = None
        elif chroma:
            cols = home_col  # palette inks at full strength (joints = holds)
        else:
            cols = tint_dots(home_col, tint_strength(tv, env))
        ghosts = ghost_entries(hist, trail_n, env, color_mode) if trail_on else []
        shade_map = home_dark
        if mode == "blocks":
            mask = block_visible(coords, h, w, progress=progress, loops=loops,
                                 stagger=stagger, ease=ease,
                                 pixel_size=pixel_size, seed=seed)
            pos = coords.astype(np.float32)[mask]
            sizes = frame_dot_sizes(coords, h, w, progress=progress, loops=loops,
                                    stagger=stagger, ease=ease, dotsize=dotsize,
                                    shade=shade_map)
            sizes = None if sizes is None else np.asarray(sizes)[mask]
            cols = None if cols is None else np.asarray(cols)[mask]
            ghost_base = None if home_col is None else np.asarray(home_col)[mask]
        else:
            pos = disperse_positions(coords, h, w, progress=progress, seed=seed,
                                     wind=wind, mode=mode, loops=loops, amount=amount,
                                     stagger=stagger, ease=ease, pixel_size=pixel_size)
            sizes = frame_dot_sizes(coords, h, w, progress=progress, loops=loops,
                                    stagger=stagger, ease=ease, dotsize=dotsize,
                                    shade=shade_map)
            ghost_base = home_col
        if trail_on:
            hist.append((np.asarray(pos, dtype=np.float32),
                         None if ghost_base is None else np.asarray(ghost_base),
                         None if sizes is None else np.asarray(sizes)))
        yield render_points(pos, h, w, sizes, cols, ghosts)
    for _ in range(max(0, int(hold_end))):
        yield still.copy()


def dissolve_frames(img: Image.Image, method: str = "bayer8",
                    threshold: float = 128.0, pixel_size: int = 1,
                    frames: int = 8, seed: int = 0xD15C,
                    wind: tuple[float, float] = (120.0, -40.0),
                    mode: str = "wind", loops: float = 1.0,
                    amount: float = 1.0,
                    max_side: int = 480,
                    hold_start: int = 0, hold_end: int = 0,
                    stagger: str = "off", ease: str = "sine",
                    dotsize: int = 1, tint: float = 0.0, trail: int = 0,
                    shade: bool = False, adjust=None, palette=None,
                    palette_depth: int = 0) -> list[Image.Image]:
    """Full disperse loop for one image (assembled -> dispersed -> assembled).

    Dithers once at max_side, then marches progress=i/n. amount 0 returns
    n copies of the dithered still (identity, strict 0=off). hold_start /
    hold_end prepend / append assembled copies so the form reads before
    it bursts (loop joint stays assembled -> seamless). `dotsize` 1..4
    swells dots with the envelope (1 = legacy 1px). `tint` 0..1 colors
    dots from the source (0 = legacy BW). `trail` 0..8 pastes fading
    ghost dots (0 = legacy). `shade` sizes dots by source darkness
    (False = uniform swell). `adjust` grades first (identity = legacy).
    `palette` (None|"SOURCE"|inks) prints the inks (None = legacy BW).
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    small = img.convert("RGB")
    r = side / max(small.width, small.height)
    if r < 1.0:
        small = small.resize((max(1, round(small.width * r)),
                              max(1, round(small.height * r))), Image.BICUBIC)
    return list(iter_dissolve(img, method=method, threshold=threshold,
                pixel_size=pixel_size, frames=n, seed=seed,
                wind=wind, mode=mode, loops=loops, amount=amount,
                max_side=side, hold_start=hold_start,
                hold_end=hold_end, stagger=stagger, ease=ease,
                dotsize=dotsize, tint=tint, trail=trail, shade=shade,
                adjust=adjust, palette=palette,
                palette_depth=palette_depth))


def morph_frames(img_a: Image.Image, img_b: Image.Image, method: str = "bayer8",
                 threshold: float = 128.0, pixel_size: int = 1,
                 frames: int = 8, seed: int = 0xD15C,
                 wind: tuple[float, float] = (120.0, -40.0),
                 mode: str = "wind", amount: float = 1.0,
                 max_side: int = 480,
                 hold_start: int = 0, hold_end: int = 0,
                 hold_joint: int = 0,
                 crops: list[dict] | None = None,
                 stagger: str = "off", ease: str = "sine",
                 dotsize: int = 1, travel: float = 0.0, tint: float = 0.0,
                 trail: int = 0, shade: bool = False, adjust=None,
                 palette=None, palette_depth: int = 0) -> list[Image.Image]:
    """One-shot swap A -> B through a shared particle cloud (Fase 5).

    Both images are fitted to the same HxW (B resized to A), dithered
    with the same engine, then: progress<0.5 renders dispersed A,
    progress>=0.5 renders dispersed B, envelope sin(pi*progress) so both
    ends are assembled and the middle is a full cloud. amount 0 returns
    A copies then B copies (hard cut, strict 0=off).
    """
    chained = morph_chain_frames([img_a, img_b], method=method, threshold=threshold,
                                 pixel_size=pixel_size, frames=frames, seed=seed,
                                 wind=wind, mode=mode, amount=amount, max_side=max_side,
                                 hold_start=hold_start, hold_end=hold_end,
                                 hold_joint=hold_joint, crops=crops,
                                 stagger=stagger, ease=ease, dotsize=dotsize,
                                 travel=travel, tint=tint, trail=trail,
                                 shade=shade, adjust=adjust, palette=palette,
                                 palette_depth=palette_depth)
    return chained


#: Hard cap on chain length re-exported from app.particles.modes.


def iter_morph_chain(imgs: list[Image.Image], method: str = "bayer8",
                     threshold: float = 128.0, pixel_size: int = 1,
                     frames: int = 8, seed: int = 0xD15C,
                     wind: tuple[float, float] = (120.0, -40.0),
                     mode: str = "wind", amount: float = 1.0,
                     max_side: int = 480,
                     hold_start: int = 0, hold_end: int = 0,
                     hold_joint: int | list | tuple = 0,
                     crops: list[dict] | None = None,
                     loop: bool = False,
                     stagger: str = "off", ease: str = "sine",
                     dotsize: int = 1, travel: float = 0.0, tint: float = 0.0,
                     trail: int = 0, shade: bool = False, adjust=None,
                     palette=None, palette_depth: int = 0):
    """Yield chain frames one by one (streaming: O(1) RAM).

    Same pixels as morph_chain_frames(), no list kept alive.
    With loop=True the last form morphs back into the first (closed
    loop, no hard cut): the closing leg reuses the first form's exact
    dithered still/coords, so the loop joint is byte-identical.
    With travel > 0 (F3, non-blocks legs only) dots pour src -> dst
    through a seeded-greedy 1:1 assignment instead of cloud-reform;
    travel = 0 keeps the legacy path byte-identical.
    With tint > 0 (F4) dots carry their source colors, gated by the
    loop envelope (tint = 0 keeps the legacy BW path byte-identical).
    With trail > 0 (F5) past dots linger as fading ghosts, gated by the
    loop envelope (trail = 0 keeps the legacy path byte-identical).
    With shade on (F6) dots swell by source darkness (off = uniform).
    """
    from collections import deque

    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    if len(imgs) < 2:
        raise ValueError("chain needs at least 2 images")
    imgs = list(imgs[:MAX_MORPH_IMAGES])
    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    a = imgs[0].convert("RGB")
    r = side / max(a.width, a.height)
    if r < 1.0:
        a = a.resize((max(1, round(a.width * r)),
                      max(1, round(a.height * r))), Image.BICUBIC)
    fitted = [a]
    for k, im in enumerate(imgs[1:]):
        crop = (crops[k + 1] if crops and k + 1 < len(crops) else None) or {}
        try:
            fx = float(crop.get("fx", 50.0))
            fy = float(crop.get("fy", 50.0))
            zm = max(1.0, float(crop.get("zoom", 1.0)))
        except (TypeError, ValueError):
            fx, fy, zm = 50.0, 50.0, 1.0
        fitted.append(_fit_cover(im, a.width, a.height, fx, fy, zm))
    from app.adjust import apply_adjust

    worked = [apply_adjust(im, adjust) for im in fitted]
    coord_list: list[np.ndarray] = []
    col_list: list = []
    still_list: list[Image.Image] = []
    still_arr_list: list = []
    h = w = 0
    for im in worked:
        still, coords, cols, hh, ww = morph_ink(
            im, method, threshold, pixel_size, palette, palette_depth)
        if not coord_list:
            h, w = hh, ww  # dithered size rules (pixel_size floors odd sides)
        if (hh, ww) == (h, w):
            coord_list.append(coords)
            col_list.append(cols)
            still_list.append(still)
            still_arr_list.append(np.asarray(still.convert("RGB")))
        else:
            coord_list.append(_refit_coords(coords, hh, ww, h, w))
            col_list.append(None if cols is None else _refit_coords(cols, hh, ww, h, w))
            still_list.append(still if still.size == (w, h)
                              else still.resize((w, h), Image.BICUBIC))
            still_arr_list.append(np.asarray(still_list[-1].convert("RGB")))
    segs = len(fitted) - 1
    loop_v = bool(loop) and len(fitted) >= 2
    legs = segs + (1 if loop_v else 0)
    base, rem = divmod(n, legs)
    dithered_all = [s.copy() for s in still_list]
    for _ in range(max(0, int(hold_start))):
        yield dithered_all[0].copy()
    if isinstance(hold_joint, (list, tuple)):
        hj_list = [max(0, int(v)) for v in list(hold_joint)]
    else:
        hj_list = [max(0, int(hold_joint))] * max(0, legs - 1)
    for k in range(legs):
        nk = base + (1 if k < rem else 0)
        if nk <= 0:
            if k < legs - 1:
                hj_k = hj_list[k] if k < len(hj_list) else (hj_list[-1] if hj_list else 0)
                for _ in range(hj_k):
                    yield dithered_all[(k + 1) % len(dithered_all)].copy()
            continue
        closing = loop_v and k == legs - 1
        ca = coord_list[k] if not closing else coord_list[-1]
        cb = coord_list[k + 1] if not closing else coord_list[0]
        amt_v = max(0.0, min(2.0, float(amount or 0.0)))
        travel_on = (float(travel or 0.0) > 0.0 and amt_v > 0.0
                     and str(mode or "wind") != "blocks"
                     and len(ca) > 0 and len(cb) > 0)
        tv = max(0.0, min(1.0, float(tint or 0.0)))
        if amt_v <= 0.0:
            tv = 0.0  # strict 0=off: frozen stills, tint has nothing to paint
        trail_n = max(0, min(MAX_TRAIL, int(trail or 0)))
        trail_on = trail_n > 0 and amt_v > 0.0
        hist: deque = deque(maxlen=trail_n if trail_n > 0 else 1)
        color_mode = tv > 0.0
        tsrc = tdst = None
        tsrc_col = tdst_col = None
        leg_col_a = leg_col_b = None
        tsrc_dark = tdst_dark = None
        leg_dark_a = leg_dark_b = None
        if travel_on:
            tsrc, tdst = match_travel(ca, cb, h, w, seed=int(seed) + k)
        shade_on = bool(shade)
        cola_full = col_list[k] if not closing else col_list[-1]
        colb_full = col_list[k + 1] if not closing else col_list[0]
        chroma = cola_full is not None or colb_full is not None
        if chroma:
            tv = 1.0  # palette inks print at full strength (joints = holds)
            color_mode = True
            leg_col_a, leg_col_b = cola_full, colb_full
            arr_ink_a = still_arr_list[k] if not closing else still_arr_list[-1]
            arr_ink_b = still_arr_list[k + 1] if not closing else still_arr_list[0]
            if travel_on:
                assert tsrc is not None and tdst is not None
                tsrc_col = arr_ink_a[np.clip(tsrc[:, 0].astype(np.int64), 0, h - 1),
                                     np.clip(tsrc[:, 1].astype(np.int64), 0, w - 1)].astype(np.float64)
                tdst_col = arr_ink_b[np.clip(tdst[:, 0].astype(np.int64), 0, h - 1),
                                     np.clip(tdst[:, 1].astype(np.int64), 0, w - 1)].astype(np.float64)
        if not chroma and (tv > 0.0 or shade_on):
            fa = worked[k] if not closing else worked[-1]
            fb = worked[k + 1] if not closing else worked[0]
            arr_a = sample_colors(fa, h, w)
            arr_b = sample_colors(fb, h, w)
            if tv > 0.0:
                leg_col_a = arr_a[np.clip(ca[:, 0], 0, h - 1),
                                  np.clip(ca[:, 1], 0, w - 1)].astype(np.float64)
                leg_col_b = arr_b[np.clip(cb[:, 0], 0, h - 1),
                                  np.clip(cb[:, 1], 0, w - 1)].astype(np.float64)
                if travel_on:
                    assert tsrc is not None and tdst is not None
                    tsrc_col = arr_a[np.clip(tsrc[:, 0].astype(np.int64), 0, h - 1),
                                     np.clip(tsrc[:, 1].astype(np.int64), 0, w - 1)].astype(np.float64)
                    tdst_col = arr_b[np.clip(tdst[:, 0].astype(np.int64), 0, h - 1),
                                     np.clip(tdst[:, 1].astype(np.int64), 0, w - 1)].astype(np.float64)
            if shade_on:
                leg_dark_a = _darkness_of(arr_a.astype(np.float64), ca, h, w)
                leg_dark_b = _darkness_of(arr_b.astype(np.float64), cb, h, w)
                if travel_on:
                    assert tsrc is not None and tdst is not None
                    tsrc_dark = _darkness_of(arr_a.astype(np.float64), tsrc, h, w)
                    tdst_dark = _darkness_of(arr_b.astype(np.float64), tdst, h, w)
        ez_leg = ease if ease in EASE_MODES else "sine"
        for j in range(nk):
            q = float(j) / float(max(1, nk - 1))
            env = float(ease_env(np.mod(q, 1.0), ez_leg))
            ghosts = ghost_entries(hist, trail_n, env, color_mode) if trail_on else []
            ghost_base = None
            if mode == "blocks":
                pick = ca if q < 0.5 else cb
                mask = block_visible(pick, h, w, progress=q,
                                     loops=1.0, stagger=stagger, ease=ease,
                                     pixel_size=pixel_size, seed=int(seed) + k)
                pos = pick.astype(np.float32)[mask]
                dark_pick = (leg_dark_a if (q < 0.5 and leg_dark_a is not None)
                             else (leg_dark_b if leg_dark_b is not None else None))
                sizes = frame_dot_sizes(pick, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize, shade=dark_pick)
                sizes = None if sizes is None else np.asarray(sizes)[mask]
                # NOTE: never name this `base`: that name holds the
                # per-leg frame budget from divmod above (multi-leg crash).
                pick_col = (leg_col_a if (q < 0.5 and leg_col_a is not None)
                            else (leg_col_b if leg_col_b is not None else None))
                if pick_col is None:
                    cols = None
                elif chroma:
                    cols = np.asarray(pick_col)[mask]  # inks at full strength
                else:
                    cols = tint_dots(pick_col[mask], tint_strength(tv, env))
                if pick_col is not None:
                    ghost_base = np.asarray(pick_col)[mask]
            elif travel_on:
                assert tsrc is not None and tdst is not None
                pos = travel_positions(tsrc, tdst, h, w, progress=q,
                                       seed=int(seed) + k,
                                       wind=wind, mode=mode, loops=1.0,
                                       amount=amount, stagger=stagger,
                                       ease=ease, travel=travel,
                                       pixel_size=pixel_size)
                st = str(stagger or "off")
                st = st if st in STAGGER_MODES else "off"
                delays = stagger_delays(tsrc, h, w, st)
                qi = np.clip(q * (1.0 + TRAVEL_SPAN) - delays * TRAVEL_SPAN, 0.0, 1.0)
                sm = _smootherstep(qi).astype(np.float64)[:, None]
                dark_sm = None
                if shade_on and tsrc_dark is not None and tdst_dark is not None:
                    dark_sm = ((1.0 - sm) * tsrc_dark[:, None]
                               + sm * tdst_dark[:, None])[:, 0]
                sizes = frame_dot_sizes(tsrc, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize, shade=dark_sm)
                cols = None
                if tsrc_col is not None and tdst_col is not None:
                    mix = (1.0 - sm) * tsrc_col + sm * tdst_col
                    cols = mix if chroma else tint_dots(mix, tint_strength(tv, env))
                    ghost_base = np.asarray(mix)
            elif q < 0.5:
                pos = disperse_positions(ca, h, w, progress=q, seed=int(seed) + k,
                                         wind=wind, mode=mode, loops=1.0, amount=amount,
                                         stagger=stagger, ease=ease, pixel_size=pixel_size)
                sizes = frame_dot_sizes(ca, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize, shade=leg_dark_a)
                if leg_col_a is None:
                    cols = None
                elif chroma:
                    cols = leg_col_a
                else:
                    cols = tint_dots(leg_col_a, tint_strength(tv, env))
                ghost_base = leg_col_a
            else:
                pos = disperse_positions(cb, h, w, progress=q, seed=int(seed) + k + 1,
                                         wind=wind, mode=mode, loops=1.0, amount=amount,
                                         stagger=stagger, ease=ease, pixel_size=pixel_size)
                sizes = frame_dot_sizes(cb, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize, shade=leg_dark_b)
                if leg_col_b is None:
                    cols = None
                elif chroma:
                    cols = leg_col_b
                else:
                    cols = tint_dots(leg_col_b, tint_strength(tv, env))
                ghost_base = leg_col_b
            if trail_on:
                hist.append((np.asarray(pos, dtype=np.float32),
                             None if ghost_base is None else np.asarray(ghost_base),
                             None if sizes is None else np.asarray(sizes)))
            yield render_points(pos, h, w, sizes, cols, ghosts)
        if k < legs - 1:
            hj_k = hj_list[k] if k < len(hj_list) else (hj_list[-1] if hj_list else 0)
            for _ in range(hj_k):
                yield dithered_all[(k + 1) % len(dithered_all)].copy()
    for _ in range(max(0, int(hold_end))):
        yield dithered_all[0 if loop_v else -1].copy()


def morph_chain_frames(imgs: list[Image.Image], method: str = "bayer8",
                       threshold: float = 128.0, pixel_size: int = 1,
                       frames: int = 8, seed: int = 0xD15C,
                       wind: tuple[float, float] = (120.0, -40.0),
                       mode: str = "wind", amount: float = 1.0,
                       max_side: int = 480,
                       hold_start: int = 0, hold_end: int = 0,
                       hold_joint: int | list | tuple = 0,
                       crops: list[dict] | None = None,
                       loop: bool = False,
                       stagger: str = "off", ease: str = "sine",
                       dotsize: int = 1, travel: float = 0.0, tint: float = 0.0,
                       trail: int = 0, shade: bool = False, adjust=None,
                       palette=None, palette_depth: int = 0) -> list[Image.Image]:
    """Chain swap A -> B -> C ... through particle clouds (v1.8 Fase 1).

    All images fitted to the same HxW (rest cover-fit to A), dithered with
    the same engine. Frames split per segment; each segment marches q over
    [0, 1] inclusive (assembled -> cloud -> assembled) so joints meet
    assembled with no pop. hold_start / hold_end freeze the first / last
    form; hold_joint freezes every interior form so each one reads
    (int = same for all joints, list/tuple = per-joint exact share).
    amount 0 gives hard cuts (strict 0=off). Deterministic per segment
    seed (seed + k). With loop=True the last form morphs back into the
    first (closed loop, no hard cut). With travel > 0 (F3) non-blocks
    legs pour src -> dst via seeded-greedy matching (0 = legacy cloud).
    With tint > 0 (F4) dots carry source colors (0 = legacy BW).
    With trail > 0 (F5) past dots linger as fading ghosts (0 = legacy).
    With shade on (F6) dots swell by source darkness (off = uniform).
    With adjust set, sources grade first (identity = legacy).
    With palette set (F7: "SOURCE"|inks), dots print the inks at full
    strength (None = legacy BW).
    """
    return list(iter_morph_chain(imgs, method=method, threshold=threshold,
                pixel_size=pixel_size, frames=frames, seed=seed,
                wind=wind, mode=mode, amount=amount,
                max_side=max_side, hold_start=hold_start,
                hold_end=hold_end, hold_joint=hold_joint,
                crops=crops, loop=loop,
                stagger=stagger, ease=ease, dotsize=dotsize,
                travel=travel, tint=tint, trail=trail, shade=shade,
                adjust=adjust, palette=palette,
                palette_depth=palette_depth))


__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MAX_POINTS", "MAX_MORPH_IMAGES", "dither_bw",
           "points_from_dither", "disperse_positions", "block_visible",
           "match_travel", "travel_positions",
           "stagger_delays", "ease_env", "render_points",
           "dissolve_frames", "morph_frames", "morph_chain_frames",
           "iter_dissolve", "iter_morph_chain"]
