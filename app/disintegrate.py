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

from app.ordered_maps import BAYER_8X8

DISINTEGRATE_MODES = ("wind", "random", "burst", "suction", "vortex",
                      "rain", "rise", "wave", "ripple", "flow", "blocks")
#: Release stagger: per-particle phase shift (loop-safe via %1).
STAGGER_MODES = ("off", "rank", "radial", "scan", "sweep")
#: Loop envelope shape (all close at the joints: env(0) == env(1) == 0).
EASE_MODES = ("sine", "cubic", "linear", "elastic", "bounce")

#: Hard cap on rasterized points per frame (perf: vectorized scatter).
MAX_POINTS = 120_000


def dither_bw(img: Image.Image, method: str = "bayer8",
              threshold: float = 128.0, pixel_size: int = 1) -> Image.Image:
    """BW dither of the input (Bayer or Floyd-Steinberg family).

    Uses the main engine (app.dither.apply_method, palette=None) so the
    look matches the still pipeline. Limited grayscale is out of scope
    for Fase 1 (BW only).
    """
    from app.dither import apply_method

    return apply_method(img.convert("RGB"), method=method, palette=None,
                        threshold=float(threshold), pixel_size=max(1, int(pixel_size)))


def points_from_dither(dithered: Image.Image) -> tuple[np.ndarray, int, int]:
    """Active (black) coords of a BW dithered image.

    Returns (coords (N,2) as (y,x) int32, H, W). Deterministic stride
    subsample when N exceeds MAX_POINTS (keeps spatial distribution).
    """
    arr = np.asarray(dithered.convert("L"), dtype=np.uint8)
    h, w = arr.shape[:2]
    ys, xs = np.nonzero(arr < 128)
    coords = np.stack([ys.astype(np.int32), xs.astype(np.int32)], axis=1)
    if len(coords) > MAX_POINTS:
        step = int(math.ceil(len(coords) / MAX_POINTS))
        coords = coords[::step].copy()
    return coords, int(h), int(w)


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


def _pinned_frac(progress: float, loops: float, delays: np.ndarray) -> np.ndarray:
    """Joint-pinned staggered phase: full pour waves mid-loop, zero shift
    at both joints (holds meet assembled). Loop-safe by the %1."""
    frac = (float(progress) * max(0.25, min(4.0, float(loops or 1.0)))) % 1.0
    return np.mod(frac + np.asarray(delays, dtype=np.float64) * math.sin(math.pi * frac), 1.0)


def dot_sizes(env, maxsize: int = 1):
    """Per-dot render size 1..maxsize from the envelope (None = legacy 1px).

    Dots swell as they fly (Heckel-style attenuation by envelope) and
    land back at 1px, so joints stay byte-sharp under holds.
    """
    m = max(1, int(maxsize or 1))
    if m <= 1:
        return None
    return (1 + np.round((m - 1) * np.asarray(env, dtype=np.float64))).astype(np.int64)


def frame_dot_sizes(coords: np.ndarray, h: int, w: int, progress: float = 0.0,
                    loops: float = 1.0, stagger: str = "off", ease: str = "sine",
                    dotsize: int = 1):
    """Sizes for one frame (None when dotsize is 1: legacy path untouched)."""
    if max(1, int(dotsize or 1)) <= 1 or int(len(coords)) == 0:
        return None
    st = str(stagger or "off")
    if st not in STAGGER_MODES:
        st = "off"
    delays = stagger_delays(coords, h, w, st)
    env = ease_env(_pinned_frac(progress, loops, delays), ease)
    return dot_sizes(env, dotsize)


def _bayer_rank(ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    """Dither-matrix rank in [0, 1): the bayer8 signature per position."""
    mat = np.asarray(BAYER_8X8, dtype=np.float64)
    return mat[np.mod(ys.astype(np.int64), 8), np.mod(xs.astype(np.int64), 8)] / 64.0


def stagger_delays(coords: np.ndarray, h: int, w: int, stagger: str = "off") -> np.ndarray:
    """Per-particle phase delay in [0, 1), applied joint-pinned.

    frac_i = (frac + delay_i * sin(pi*frac)) % 1: zero shift at both
    joints (holds meet the still, no pop) and full pour waves mid-loop.
    Loop-safe by the %1; deterministic, no RNG. `rank` follows the
    bayer8 matrix order, `radial` pours center-out on gather, `scan`
    runs top-down, `sweep` re-enters left-right.
    """
    n = int(len(coords))
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    st = str(stagger or "off")
    if st not in STAGGER_MODES or st == "off":
        return np.zeros(n, dtype=np.float64)
    f = np.asarray(coords, dtype=np.float64)
    ys, xs = f[:, 0], f[:, 1]
    if st == "rank":
        d = _bayer_rank(ys, xs)
    elif st == "radial":
        d = np.hypot(xs - (w - 1) / 2.0, ys - (h - 1) / 2.0)
        m = float(d.max()) if n else 1.0
        d = d / (m or 1.0)
    elif st == "scan":
        d = ys / max(1.0, float(h - 1))
    else:  # sweep
        d = xs / max(1.0, float(w - 1))
    return np.mod(np.asarray(d, dtype=np.float64), 1.0)


def ease_env(frac, ease: str = "sine") -> np.ndarray:
    """Loop envelope: sine = legacy, cubic = sharper attack/longer dwell,
    linear = constant-speed tent, elastic = wobble riding the breathe,
    bounce = sub-impacts riding the breathe. All satisfy
    env(0) == env(1) == 0 with peak <= 1."""
    f = np.mod(np.asarray(frac, dtype=np.float64), 1.0)
    e = str(ease or "sine")
    if e == "cubic":
        s = np.sin(np.pi * f)
        return s * s * s
    if e == "linear":
        return 1.0 - np.abs(1.0 - 2.0 * f)
    if e == "elastic":
        return np.sin(np.pi * f) * (0.65 + 0.35 * np.cos(6.0 * np.pi * f))
    if e == "bounce":
        return np.sin(np.pi * f) * (0.55 + 0.45 * np.abs(np.sin(3.0 * np.pi * f)))
    return np.sin(np.pi * f)


def _rain_profile(frac: np.ndarray) -> np.ndarray:
    """Drop profile: accelerating fall (frac^2) + folded bounce-back.

    C0 at the joints (0 at both ends, peak mid): the bounce emerges when
    the loop envelope gates it back up. `rise` mirrors it upward.
    """
    g = np.mod(np.asarray(frac, dtype=np.float64), 1.0)
    down = (2.0 * g) ** 2
    up = 1.0 - (2.0 * g - 1.0) ** 2
    return np.where(g < 0.5, down, np.maximum(0.0, up))


def _field_offset(coords: np.ndarray, h: int, w: int, mode: str,
                  wind: tuple[float, float], amt: float, seed: int,
                  frac: np.ndarray, pixel_size: int = 1) -> np.ndarray:
    """Static displacement field (px, pre-envelope): one closed-form vector
    per particle. No integration anywhere (loop-perfect by construction);
    rain/rise carry their drop profile in the field, wave/ripple carry a
    loop-locked traveling phase (integer cycles per loop)."""
    n = int(len(coords))
    f = np.asarray(coords, dtype=np.float32)
    ys, xs = f[:, 0], f[:, 1]
    rng = np.random.default_rng(int(seed))
    if mode == "random":
        return (rng.uniform(-90.0, 90.0, (n, 2)).astype(np.float32) * amt)
    if mode in ("burst", "suction"):
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        dy, dx = ys - cy, xs - cx
        dist = np.maximum(np.hypot(dx, dy), 1e-9).astype(np.float32)
        rank = rng.uniform(0.0, 1.0, n).astype(np.float32)
        speed = ((0.3 + rank) * 140.0 * amt).astype(np.float32)
        sgn = 1.0 if mode == "burst" else -1.0
        ux, uy = (dx / dist * sgn), (dy / dist * sgn)
        return np.stack([uy * speed, ux * speed], axis=1)
    if mode == "vortex":
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        dy, dx = ys - cy, xs - cx
        dist = np.maximum(np.hypot(dx, dy), 1e-9).astype(np.float32)
        pull = 110.0 * amt
        tx, ty = (-dy / dist), (dx / dist)
        ux, uy = (dx / dist), (dy / dist)
        return np.stack([(ty + 0.25 * uy) * pull, (tx + 0.25 * ux) * pull], axis=1)
    if mode in ("rain", "rise"):
        sgn = 1.0 if mode == "rain" else -1.0
        fall = (480.0 * amt * np.asarray(frac, dtype=np.float32) ** 2)
        return np.stack([fall * sgn, np.zeros(n, dtype=np.float32)], axis=1)
    if mode == "wave":
        g = np.asarray(frac, dtype=np.float32)
        ph = 2.0 * math.pi * xs / max(1.0, float(w)) - 4.0 * math.pi * g
        ay = (36.0 * amt * np.sin(ph)).astype(np.float32)
        ax = (12.0 * amt * np.sin(ph + math.pi / 2.0)).astype(np.float32)
        return np.stack([ay, ax], axis=1)
    if mode == "ripple":
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        dy, dx = ys - cy, xs - cx
        dist = np.maximum(np.hypot(dx, dy), 1e-9).astype(np.float32)
        lam = max(8.0, min(float(h), float(w)) / 3.0)
        g = np.asarray(frac, dtype=np.float32)
        wave = (40.0 * amt * np.sin(2.0 * math.pi * dist / lam - 4.0 * math.pi * g))
        return np.stack([(dy / dist) * wave, (dx / dist) * wave], axis=1).astype(np.float32)
    if mode == "flow":
        p1, p2, p3, p4 = rng.uniform(0.0, 2.0 * math.pi, 4).astype(np.float32)
        xn, yn = xs / max(1.0, float(w)), ys / max(1.0, float(h))
        dx = (np.sin(2 * math.pi * (0.7 * xn + 1.3 * yn) + p1)
              + 0.5 * np.sin(2 * math.pi * (1.9 * xn - 0.6 * yn) + p2))
        dy = (np.sin(2 * math.pi * (-1.1 * xn + 0.9 * yn) + p3)
              + 0.5 * np.sin(2 * math.pi * (0.5 * xn + 2.1 * yn) + p4))
        return (np.stack([dy, dx], axis=1).astype(np.float32) * (55.0 * amt))
    # wind (general path: stagger/ease variants of the legacy field)
    wx, wy = float(wind[0]), float(wind[1])
    spread = 28.0 * amt
    turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
    base = np.array([[wy * amt, wx * amt]], dtype=np.float32)
    return base + turb


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


def render_points(positions: np.ndarray, h: int, w: int, sizes=None) -> Image.Image:
    """Rasterize float (y,x) points to a BW RGB image (white bg, black dots).

    `sizes` (per-dot ints, None = legacy 1px): dots swell as kxk blocks
    anchored at the dot, clipped. Grouped fills keep it vectorized.
    """
    canvas = np.full((h, w), 255, dtype=np.uint8)
    if len(positions):
        ys = np.clip(positions[:, 0].astype(np.int32), 0, h - 1)
        xs = np.clip(positions[:, 1].astype(np.int32), 0, w - 1)
        if sizes is None:
            canvas[ys, xs] = 0
        else:
            s = np.asarray(sizes, dtype=np.int64)
            if len(s) != len(ys):
                canvas[ys, xs] = 0
            else:
                for k in np.unique(s):
                    m = s == k
                    yy = np.clip(ys[m], 0, h - 1)
                    xx = np.clip(xs[m], 0, w - 1)
                    kk = max(1, int(k))
                    if kk <= 1:
                        canvas[yy, xx] = 0
                        continue
                    for dy in range(kk):
                        yyc = np.clip(yy + dy, 0, h - 1)
                        for dx in range(kk):
                            canvas[yyc, np.clip(xx + dx, 0, w - 1)] = 0
    return Image.fromarray(canvas, mode="L").convert("RGB")


def iter_dissolve(img: Image.Image, method: str = "bayer8",
                  threshold: float = 128.0, pixel_size: int = 1,
                  frames: int = 8, seed: int = 0xD15C,
                  wind: tuple[float, float] = (120.0, -40.0),
                  mode: str = "wind", loops: float = 1.0,
                  amount: float = 1.0,
                  max_side: int = 480,
                  hold_start: int = 0, hold_end: int = 0,
                  stagger: str = "off", ease: str = "sine",
                  dotsize: int = 1):
    """Yield dissolve frames one by one (streaming: O(1) RAM for long MP4).

    Same pixels as dissolve_frames(), no list kept alive. Lets MP4 stream
    long clips (up to 3600f) without the 256-frame list cap blowing RAM.
    `dotsize` 1..4 swells dots with the envelope (1 = legacy 1px).
    """
    from app.gif import GIF_MAX_FRAMES, GIF_MIN_FRAMES

    n = max(GIF_MIN_FRAMES, min(GIF_MAX_FRAMES, int(frames)))
    side = max(64, min(8000, int(max_side or 480)))
    small = img.convert("RGB")
    r = side / max(small.width, small.height)
    if r < 1.0:
        small = small.resize((max(1, round(small.width * r)),
                              max(1, round(small.height * r))), Image.BICUBIC)
    dithered = dither_bw(small, method=method, threshold=threshold,
                         pixel_size=pixel_size)
    still = dithered.convert("RGB")
    coords, h, w = points_from_dither(dithered)
    for _ in range(max(0, int(hold_start))):
        yield still.copy()
    for i in range(n):
        progress = float(i) / float(n)
        if mode == "blocks":
            mask = block_visible(coords, h, w, progress=progress, loops=loops,
                                 stagger=stagger, ease=ease,
                                 pixel_size=pixel_size, seed=seed)
            pos = coords.astype(np.float32)[mask]
            sizes = frame_dot_sizes(coords, h, w, progress=progress, loops=loops,
                                    stagger=stagger, ease=ease, dotsize=dotsize)
            sizes = None if sizes is None else np.asarray(sizes)[mask]
        else:
            pos = disperse_positions(coords, h, w, progress=progress, seed=seed,
                                     wind=wind, mode=mode, loops=loops, amount=amount,
                                     stagger=stagger, ease=ease, pixel_size=pixel_size)
            sizes = frame_dot_sizes(coords, h, w, progress=progress, loops=loops,
                                    stagger=stagger, ease=ease, dotsize=dotsize)
        yield render_points(pos, h, w, sizes)
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
                    dotsize: int = 1) -> list[Image.Image]:
    """Full disperse loop for one image (assembled -> dispersed -> assembled).

    Dithers once at max_side, then marches progress=i/n. amount 0 returns
    n copies of the dithered still (identity, strict 0=off). hold_start /
    hold_end prepend / append assembled copies so the form reads before
    it bursts (loop joint stays assembled -> seamless). `dotsize` 1..4
    swells dots with the envelope (1 = legacy 1px).
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
                dotsize=dotsize))


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
                 dotsize: int = 1) -> list[Image.Image]:
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
                                 stagger=stagger, ease=ease, dotsize=dotsize)
    return chained


#: Hard cap on chain length (A + up to 5 more).
MAX_MORPH_IMAGES = 6


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
                     dotsize: int = 1):
    """Yield chain frames one by one (streaming: O(1) RAM).

    Same pixels as morph_chain_frames(), no list kept alive.
    With loop=True the last form morphs back into the first (closed
    loop, no hard cut): the closing leg reuses the first form's exact
    dithered still/coords, so the loop joint is byte-identical.
    """
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
    coord_list: list[np.ndarray] = []
    h = w = 0
    for im in fitted:
        d = dither_bw(im, method=method, threshold=threshold, pixel_size=pixel_size)
        coords, hh, ww = points_from_dither(d)
        if not coord_list:
            h, w = hh, ww  # dithered size rules (pixel_size floors odd sides)
        coord_list.append(coords if (hh, ww) == (h, w) else _refit_coords(coords, hh, ww, h, w))
    segs = len(fitted) - 1
    loop_v = bool(loop) and len(fitted) >= 2
    legs = segs + (1 if loop_v else 0)
    base, rem = divmod(n, legs)
    dithered_all = [dither_bw(im, method=method, threshold=threshold,
                              pixel_size=pixel_size).convert("RGB")
                    for im in fitted]
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
        for j in range(nk):
            q = float(j) / float(max(1, nk - 1))
            if mode == "blocks":
                pick = ca if q < 0.5 else cb
                mask = block_visible(pick, h, w, progress=q,
                                     loops=1.0, stagger=stagger, ease=ease,
                                     pixel_size=pixel_size, seed=int(seed) + k)
                pos = pick.astype(np.float32)[mask]
                sizes = frame_dot_sizes(pick, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize)
                sizes = None if sizes is None else np.asarray(sizes)[mask]
            elif q < 0.5:
                pos = disperse_positions(ca, h, w, progress=q, seed=int(seed) + k,
                                         wind=wind, mode=mode, loops=1.0, amount=amount,
                                         stagger=stagger, ease=ease, pixel_size=pixel_size)
                sizes = frame_dot_sizes(ca, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize)
            else:
                pos = disperse_positions(cb, h, w, progress=q, seed=int(seed) + k + 1,
                                         wind=wind, mode=mode, loops=1.0, amount=amount,
                                         stagger=stagger, ease=ease, pixel_size=pixel_size)
                sizes = frame_dot_sizes(cb, h, w, progress=q,
                                        loops=1.0, stagger=stagger, ease=ease,
                                        dotsize=dotsize)
            yield render_points(pos, h, w, sizes)
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
                       dotsize: int = 1) -> list[Image.Image]:
    """Chain swap A -> B -> C ... through particle clouds (v1.8 Fase 1).

    All images fitted to the same HxW (rest cover-fit to A), dithered with
    the same engine. Frames split per segment; each segment marches q over
    [0, 1] inclusive (assembled -> cloud -> assembled) so joints meet
    assembled with no pop. hold_start / hold_end freeze the first / last
    form; hold_joint freezes every interior form so each one reads
    (int = same for all joints, list/tuple = per-joint exact share).
    amount 0 gives hard cuts (strict 0=off). Deterministic per segment
    seed (seed + k). With loop=True the last form morphs back into the
    first (closed loop, no hard cut).
    """
    return list(iter_morph_chain(imgs, method=method, threshold=threshold,
                pixel_size=pixel_size, frames=frames, seed=seed,
                wind=wind, mode=mode, amount=amount,
                max_side=max_side, hold_start=hold_start,
                hold_end=hold_end, hold_joint=hold_joint,
                crops=crops, loop=loop,
                stagger=stagger, ease=ease, dotsize=dotsize))


__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MAX_POINTS", "MAX_MORPH_IMAGES", "dither_bw",
           "points_from_dither", "disperse_positions", "block_visible",
           "stagger_delays", "ease_env", "render_points",
           "dissolve_frames", "morph_frames", "morph_chain_frames",
           "iter_dissolve", "iter_morph_chain"]
