"""Particle rasterizer: sizes, trails, point painting (R2-p3, verbatim move).

Pure functions moved from app.disintegrate (no logic change).
app.disintegrate re-exports them so existing imports keep working.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.particles.fields import _pinned_frac, ease_env, stagger_delays
from app.particles.modes import STAGGER_MODES


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
                    dotsize: int = 1, shade=None):
    """Sizes for one frame (None when dotsize is 1: legacy path untouched).

    `shade` (per-dot darkness 0..1, None = uniform swell): Heckel-style
    attenuation — dark-origin dots swell to full `dotsize`, light ones
    stay near 1px. Multiplied by the envelope, so joints land at 1px
    either way. Length mismatches fall back to the uniform swell.
    """
    if max(1, int(dotsize or 1)) <= 1 or int(len(coords)) == 0:
        return None
    st = str(stagger or "off")
    if st not in STAGGER_MODES:
        st = "off"
    delays = stagger_delays(coords, h, w, st)
    env = np.asarray(ease_env(_pinned_frac(progress, loops, delays), ease),
                     dtype=np.float64)
    m = max(1, int(dotsize))
    if shade is None:
        return dot_sizes(env, m)
    d = np.asarray(shade, dtype=np.float64)
    if len(d) != len(coords):
        return dot_sizes(env, m)
    return (1 + np.round((m - 1) * np.clip(d, 0.0, 1.0) * env)).astype(np.int64)


def trail_decay(age: int, length: int) -> float:
    """Ghost strength 0..1 for a 1-based age (1 = previous frame).

    Newest ghost reads clearly, oldest barely prints; length 0 (off)
    always yields 0 so the legacy path stays byte-identical.
    """
    n = max(0, int(length))
    a = int(age)
    if n <= 0 or a < 1 or a > n:
        return 0.0
    return float(((n + 1 - a) / (n + 1)) ** 1.5)


def ghost_entries(history, length: int, env: float, color_mode: bool) -> list:
    """Paint-ready ghost layers (oldest -> newest) for one frame.

    `history` holds (pos float32, base-cols-or-None, sizes-or-None) of
    past frames, newest last. Strength = decay(age) x loop envelope,
    normalized by the trail length so long trails stay subtle echoes
    instead of accumulating into the source photo; joints (env 0)
    render ghost-free = byte-exact stills. BW ghosts paint flat gray;
    color ghosts fade base hues toward white.
    """
    out: list = []
    n = max(0, int(length or 0))
    e = max(0.0, min(1.0, float(env)))
    if n <= 0 or e <= 0.0 or not history:
        return out
    items = list(history)[-n:]
    total = len(items)
    share = 1.0 + (max(0, total - 1) / 2.0)
    for idx, (p, base, s) in enumerate(items):
        st = trail_decay(total - idx, n) * e / share
        if st <= 0.0:
            continue
        if color_mode and base is not None:
            b = np.asarray(base, dtype=np.float64)
            if len(b) != len(p):
                continue
            paint = np.clip(np.round(255.0 * (1.0 - st) + b * st),
                            0, 255).astype(np.uint8)
        else:
            paint = int(round(255.0 - 215.0 * st))
            if paint >= 255:
                continue
        out.append((np.asarray(p, dtype=np.float32), paint,
                    None if s is None else np.asarray(s)))
    return out


def _disc_offsets(k: int) -> list[tuple[int, int]]:
    """Offsets of the inscribed disc inside a kxk dot block.

    k=2 keeps all 4 px, k=3 drops the corners (plus), k>=4 a real
    disc. k<=1 is a single pixel either way.
    """
    kk = max(1, int(k))
    if kk <= 2:
        return [(dy, dx) for dy in range(kk) for dx in range(kk)]
    r = kk / 2.0 - 0.25
    c = (kk - 1) / 2.0
    return [(dy, dx) for dy in range(kk) for dx in range(kk)
            if (dy - c) ** 2 + (dx - c) ** 2 <= r * r]


def _paint_layer(canvas: np.ndarray, ys: np.ndarray, xs: np.ndarray,
                 paint, sizes=None, dot_shape: str = "square") -> None:
    """Paint one dot layer (core or ghost) onto a BW or RGB canvas.

    `paint` is a gray int (BW canvas or RGB flat) or an (m,3) uint8
    array (RGB canvas). `sizes` reuses the kxk block expansion (square)
    or its inscribed disc (round); dotsize 1 is one pixel either way.
    """
    is_color = canvas.ndim == 3
    n = int(len(ys))
    if n == 0:
        return
    h, w = canvas.shape[0], canvas.shape[1]
    ys = np.clip(np.asarray(ys, dtype=np.int32), 0, h - 1)
    xs = np.clip(np.asarray(xs, dtype=np.int32), 0, w - 1)
    if isinstance(paint, int):
        flat = paint
        arr = None
    else:
        flat = None
        arr = np.asarray(paint, dtype=np.uint8)
        if len(arr) != n:
            arr = None
            flat = 0 if not is_color else 0
    if sizes is None:
        if is_color:
            canvas[ys, xs] = (flat, flat, flat) if flat is not None else arr
        else:
            canvas[ys, xs] = flat if flat is not None else 0
        return
    s = np.asarray(sizes, dtype=np.int64)
    if len(s) != n:
        if is_color:
            canvas[ys, xs] = (flat, flat, flat) if flat is not None else arr
        else:
            canvas[ys, xs] = flat if flat is not None else 0
        return
    for k in np.unique(s):
        m = s == k
        yy, xx = ys[m], xs[m]
        pp = flat if flat is not None else arr[m]
        kk = max(1, int(k))
        if kk <= 1:
            if is_color:
                canvas[yy, xx] = (pp, pp, pp) if isinstance(pp, int) else pp
            else:
                canvas[yy, xx] = pp if isinstance(pp, int) else 0
            continue
        if str(dot_shape or "square") == "round":
            offs = _disc_offsets(kk)
        else:
            offs = [(dy, dx) for dy in range(kk) for dx in range(kk)]
        rep = len(offs)
        yyy = np.clip((yy[:, None] + np.array([o[0] for o in offs])[None, :]),
                      0, h - 1).reshape(-1)
        xxx = np.clip((xx[:, None] + np.array([o[1] for o in offs])[None, :]),
                      0, w - 1).reshape(-1)
        if is_color:
            if isinstance(pp, int):
                canvas[yyy, xxx] = (pp, pp, pp)
            else:
                canvas[yyy, xxx] = np.repeat(pp, rep, axis=0)
        else:
            if isinstance(pp, int):
                canvas[yyy, xxx] = pp
            else:
                canvas[yyy, xxx] = 0


def render_points(positions: np.ndarray, h: int, w: int, sizes=None,
                  colors=None, trail=None, dot_shape: str = "square") -> Image.Image:
    """Rasterize float (y,x) points to an RGB image (white bg, black dots).

    `sizes` (per-dot ints, None = legacy 1px): dots swell as kxk blocks
    (square) or inscribed discs (round) anchored at the dot, clipped.
    Grouped fills keep it vectorized. `colors` ((n,3) uint8, None =
    black): per-dot tint; None keeps the legacy BW path byte-identical,
    all-black equals it pixel for pixel. `trail` (None or list of
    (tpos, tpaint, tsizes) oldest -> newest): ghost dots painted before
    the core; `tpaint` is a gray int (BW) or an (m,3) uint8 array
    (color). Empty trail renders exactly as None. `dot_shape` square
    keeps every legacy pixel byte-identical.
    """
    shape = str(dot_shape or "square")
    shape = shape if shape in ("square", "round") else "square"
    if colors is None and not trail:
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
                        offs = (_disc_offsets(kk) if shape == "round"
                                else [(dy, dx) for dy in range(kk)
                                      for dx in range(kk)])
                        for dy, dx in offs:
                            yyc = np.clip(yy + dy, 0, h - 1)
                            canvas[yyc, np.clip(xx + dx, 0, w - 1)] = 0
        return Image.fromarray(canvas, mode="L").convert("RGB")
    if colors is None:
        canvas = np.full((h, w), 255, dtype=np.uint8)
        core_paint: object = 0
    else:
        canvas = np.full((h, w, 3), 255, dtype=np.uint8)
        cc = np.asarray(colors, dtype=np.uint8)
        core_paint = cc if len(cc) == len(positions) else 0
    for entry in (trail or []):
        tpos, tpaint, tsizes = entry
        if len(tpos) == 0:
            continue
        _paint_layer(canvas,
                     np.asarray(tpos)[:, 0], np.asarray(tpos)[:, 1],
                     tpaint, tsizes, shape)
    if len(positions):
        _paint_layer(canvas,
                     np.asarray(positions)[:, 0], np.asarray(positions)[:, 1],
                     core_paint, sizes, shape)
    if canvas.ndim == 2:
        return Image.fromarray(canvas, mode="L").convert("RGB")
    return Image.fromarray(canvas, mode="RGB")


__all__ = ["dot_sizes", "frame_dot_sizes", "trail_decay", "ghost_entries",
           "_paint_layer", "_disc_offsets", "render_points"]
