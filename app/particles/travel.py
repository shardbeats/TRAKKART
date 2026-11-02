"""Particle movement: travel matching, disperse positions, blocks (R2-p4).

Pure functions moved verbatim from app.disintegrate (no logic change).
app.disintegrate re-exports them so existing imports keep working.
"""

from __future__ import annotations

import math

import numpy as np

from app.particles.fields import (_bayer_rank, _field_offset, _pinned_frac,
                                  ease_env, stagger_delays)
from app.particles.modes import (DISINTEGRATE_MODES, EASE_MODES, STAGGER_MODES,
                                 TRAVEL_SPAN)


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


__all__ = ["_smootherstep", "match_travel", "travel_positions",
           "disperse_positions", "block_visible"]
