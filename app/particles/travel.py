"""Particle movement: travel matching, disperse positions, blocks (R2-p4).

Pure functions moved verbatim from app.disintegrate (no logic change).
app.disintegrate re-exports them so existing imports keep working.
"""

from __future__ import annotations

import hashlib
import math
from collections import OrderedDict

import numpy as np

from app.particles.fields import (_bayer_rank, _field_offset, _pinned_frac,
                                  ease_env, stagger_delays)
from app.particles.modes import (DISINTEGRATE_MODES, EASE_MODES, MORPH_PATHS,
                                 STAGGER_MODES, TRAVEL_SPAN)


def _morton_keys(pts: np.ndarray) -> np.ndarray:
    """Morton (Z-order) keys for (y, x) points: vectorized, O(n)."""
    f = np.asarray(pts, dtype=np.float64)
    yi = np.clip(np.floor(f[:, 0]), 0, 8191).astype(np.int64)
    xi = np.clip(np.floor(f[:, 1]), 0, 8191).astype(np.int64)
    key = np.zeros(len(f), dtype=np.int64)
    for i in range(13):
        key |= ((xi >> i) & 1) << (2 * i)
        key |= ((yi >> i) & 1) << (2 * i + 1)
    return key


_MATCH_CACHE: OrderedDict = OrderedDict()
_MATCH_CACHE_MAX = 8


def _hilbert_keys(pts: np.ndarray, h: int, w: int) -> np.ndarray:
    """Hilbert-curve indices for (y, x) points: vectorized, O(n log S).

    Quantizes to a 2**bits grid covering the canvas (bits <= 13, like
    the Morton keys). Neighbors on the curve are neighbors on canvas,
    so pairing in this order pours like a thread instead of jumping
    across Z-blocks.
    """
    import math

    f = np.asarray(pts, dtype=np.float64)
    side = max(2, int(h), int(w))
    bits = max(1, min(13, int(math.ceil(math.log2(side)))))
    span = 1 << bits
    x = np.clip(np.floor(f[:, 1]), 0, span - 1).astype(np.int64)
    y = np.clip(np.floor(f[:, 0]), 0, span - 1).astype(np.int64)
    d = np.zeros(len(f), dtype=np.int64)
    s = span >> 1
    while s >= 1:
        rx = ((x // s) % 2).astype(np.int64)
        ry = ((y // s) % 2).astype(np.int64)
        d += ((3 * rx) ^ ry) * (s * s)
        x = x % s
        y = y % s
        flip = (ry == 0)
        xi = np.where(flip & (rx == 1), (s - 1) - x, x)
        yi = np.where(flip & (rx == 1), (s - 1) - y, y)
        x = np.where(flip, yi, xi)
        y = np.where(flip, xi, yi)
        s >>= 1
    return d


def _radial_keys(pts: np.ndarray, h: int, w: int,
                 rng: np.random.Generator) -> np.ndarray:
    """Center-out order with a seeded tiebreak (bloom pairing)."""
    f = np.asarray(pts, dtype=np.float64)
    dist = np.hypot(f[:, 1] - (float(w) - 1.0) / 2.0,
                    f[:, 0] - (float(h) - 1.0) / 2.0)
    return dist + rng.normal(0.0, 0.5, len(f))


def _match_cache_key(a: np.ndarray, b: np.ndarray, h: int, w: int,
                     seed: int, match: str = "morton") -> tuple:
    ha = hashlib.sha1(np.ascontiguousarray(a).tobytes()).hexdigest()
    hb = hashlib.sha1(np.ascontiguousarray(b).tobytes()).hexdigest()
    return (ha, hb, int(h), int(w), int(seed), int(len(a)), int(len(b)),
            str(match))


def _smootherstep(t: np.ndarray) -> np.ndarray:
    """Per-particle travel mixer 0 -> 1 (zero velocity at both joints)."""
    x = np.clip(np.asarray(t, dtype=np.float64), 0.0, 1.0)
    return (x * x * x * (x * (x * 6.0 - 15.0) + 10.0)).astype(np.float64)


def match_travel(ca: np.ndarray, cb: np.ndarray, h: int, w: int,
                 seed: int = 0xD15C, match: str = "morton") -> tuple[np.ndarray, np.ndarray]:
    """Seeded 1:1 destination assignment A -> B (F3 pour).

    Returns (src, dst) float32 (y,x) of equal length: the smaller set is
    padded by seeded resampling, then both sets are ordered and paired.
    `match` selects the ordering: "morton" pairs Z-order curves (legacy,
    tears in spatial blocks mid-flight); "smooth" pairs by jittered
    locality order (organic pour); "hilbert" pairs along a Hilbert curve
    (thread-like flow); "radial" pairs center-out (bloom). Any bijection
    keeps the leg joints byte-exact; the pairing only shapes the
    mid-flight pour. Deterministic per seed. Results are cached per
    (contents, h, w, seed, match) so repeated preview/export rebuilds
    pay the match once.
    """
    from app.particles.modes import MATCH_MODES

    m = str(match or "morton")
    m = m if m in MATCH_MODES else "morton"
    a = np.asarray(ca, dtype=np.float32).reshape(-1, 2)
    b = np.asarray(cb, dtype=np.float32).reshape(-1, 2)
    na, nb = int(len(a)), int(len(b))
    if na == 0 or nb == 0:
        return a.copy(), b.copy()
    key = _match_cache_key(a, b, h, w, seed, m)
    hit = _MATCH_CACHE.get(key)
    if hit is not None:
        _MATCH_CACHE.move_to_end(key)
        return hit[0].copy(), hit[1].copy()
    rng = np.random.default_rng(int(seed))
    if na < nb:
        a = np.concatenate([a, a[rng.integers(0, na, nb - na)]])
    elif nb < na:
        b = np.concatenate([b, b[rng.integers(0, nb, na - nb)]])
    n = int(len(a))
    if m == "smooth":
        # Jittered locality order: mostly-nearby pairing with soft
        # seeded noise, so early motion drifts locally instead of
        # tearing along Morton block boundaries.
        span = float(max(int(h), int(w)))
        ja = rng.normal(0.0, span / 6.0, n)
        jb = rng.normal(0.0, span / 6.0, n)
        ka = (a[:, 0] * float(w) + a[:, 1] + ja).astype(np.float64)
        kb = (b[:, 0] * float(w) + b[:, 1] + jb).astype(np.float64)
        oa = np.argsort(ka, kind="stable")
        ob = np.argsort(kb, kind="stable")
    elif m == "hilbert":
        ka = _hilbert_keys(a, h, w)
        kb = _hilbert_keys(b, h, w)
        ja = rng.random(n)
        jb = rng.random(n)
        oa = np.lexsort((ja, ka))
        ob = np.lexsort((jb, kb))
    elif m == "radial":
        ka = _radial_keys(a, h, w, rng)
        kb = _radial_keys(b, h, w, rng)
        oa = np.argsort(ka, kind="stable")
        ob = np.argsort(kb, kind="stable")
    else:
        ka = _morton_keys(a)
        kb = _morton_keys(b)
        ja = rng.random(n)
        jb = rng.random(n)
        oa = np.lexsort((ja, ka))
        ob = np.lexsort((jb, kb))
    src = np.ascontiguousarray(a[oa], dtype=np.float32)
    dst = np.ascontiguousarray(b[ob], dtype=np.float32)
    _MATCH_CACHE[key] = (src, dst)
    if len(_MATCH_CACHE) > _MATCH_CACHE_MAX:
        _MATCH_CACHE.popitem(last=False)
    return src.copy(), dst.copy()


def travel_positions(src: np.ndarray, dst: np.ndarray, h: int, w: int,
                     progress: float = 0.0, seed: int = 0xD15C,
                     wind: tuple[float, float] = (120.0, -40.0),
                     mode: str = "wind", loops: float = 1.0,
                     amount: float = 1.0, stagger: str = "off",
                     ease: str = "sine", travel: float = 1.0,
                     path: str = "pour",
                     pixel_size: int = 1) -> np.ndarray:
    """Pour positions for one morph frame: dots TRAVEL src -> dst.

    Mixer s(q) is a per-particle smootherstep over a stagger-shifted
    q (joints stay exact: s(0) = 0, s(1) = 1 for every particle), plus
    the field cloud gated by the loop envelope (zero at both joints).
    travel scales the pour (1 = full destination matching). amount 0
    is handled by the caller (strict 0=off: hard cut, no travel).
    path adds a mid-flight flourish (pour = straight lerp, arc = lift,
    swirl = perpendicular bow, braid = per-particle weave), all scaled
    by sin(pi*s) so the joints stay exact.
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
    pt = str(path or "pour")
    if pt not in MORPH_PATHS:
        pt = "pour"
    if pt != "pour" and tv > 0 and 0.0 < q < 1.0:
        se = np.sin(np.pi * s).astype(np.float32)
        if pt == "arc":
            base[:, 0] = base[:, 0] - se * (0.25 * float(h))
        elif pt == "swirl":
            d = d0 - s0
            ll = np.hypot(d[:, 1], d[:, 0]) + 1e-9
            px = -d[:, 1] / ll
            py = d[:, 0] / ll
            bow = (0.08 * float(max(int(h), int(w))) * se).astype(np.float32)
            base[:, 0] = base[:, 0] + py * bow
            base[:, 1] = base[:, 1] + px * bow
        elif pt == "braid":
            d = d0 - s0
            ll = np.hypot(d[:, 1], d[:, 0]) + 1e-9
            px = -d[:, 1] / ll
            py = d[:, 0] / ll
            rng_p = np.random.default_rng(int(seed) + 999)
            ph = rng_p.uniform(0.0, 2.0 * math.pi, n).astype(np.float32)
            wv = (np.sin(2.0 * np.pi * s + ph) * se
                  * (0.12 * float(max(int(h), int(w))))).astype(np.float32)
            base[:, 0] = base[:, 0] + py * wv
            base[:, 1] = base[:, 1] + px * wv
    amt = max(0.0, min(2.0, float(amount or 0.0)))
    ce = float(ease_env(np.mod(q, 1.0), ez))
    if amt > 0 and ce > 0 and tv > 0:
        md = str(mode or "wind")
        if md not in DISINTEGRATE_MODES:
            md = "wind"
        off = _field_offset(s0, h, w, md, wind, amt, int(seed), qi,
                            max(1, int(pixel_size or 1)))
        base = base + off * (ce * (1.0 - 0.9 * tv))
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

    progress in [0, 1), loops traversals per clip. Fields x stagger x ease
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


__all__ = ["_smootherstep", "_hilbert_keys", "_radial_keys",
           "match_travel", "travel_positions",
           "disperse_positions", "block_visible"]
