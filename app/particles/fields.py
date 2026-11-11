"""Particle fields: stagger delays, loop envelope and offset field (R2-p2).

Pure functions moved verbatim from app.disintegrate (no logic change).
app.disintegrate re-exports them so existing imports keep working.
"""

from __future__ import annotations

import math

import numpy as np

from app.ordered_maps import BAYER_8X8
from app.particles.modes import STAGGER_MODES


def _pinned_frac(progress: float, loops: float, delays: np.ndarray) -> np.ndarray:
    """Joint-pinned staggered phase: full pour waves mid-loop, zero shift
    at both joints (holds meet assembled). Loop-safe by the %1."""
    frac = (float(progress) * max(0.25, min(4.0, float(loops or 1.0)))) % 1.0
    return np.mod(frac + np.asarray(delays, dtype=np.float64) * math.sin(math.pi * frac), 1.0)


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
    if mode == "spiral":
        cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
        dy, dx = ys - cy, xs - cx
        dist = np.maximum(np.hypot(dx, dy), 1e-9).astype(np.float32)
        theta = np.arctan2(dy, dx).astype(np.float32)
        wob = 1.0 + 0.5 * np.sin(3.0 * theta).astype(np.float32)
        pull = 90.0 * amt
        tx, ty = (-dy / dist), (dx / dist)
        ux, uy = (dx / dist), (dy / dist)
        return np.stack([(ty * wob + 0.5 * uy) * pull,
                         (tx * wob + 0.5 * ux) * pull], axis=1)
    if mode == "stream":
        ph = float(rng.uniform(0.0, 2.0 * math.pi))
        xn = xs / max(1.0, float(w))
        yn = ys / max(1.0, float(h))
        dx = np.full(n, 130.0 * amt, dtype=np.float32)
        dy = (40.0 * amt * np.sin(2.0 * math.pi * (2.0 * xn + yn) + ph)).astype(np.float32)
        return np.stack([dy, dx], axis=1)
    if mode == "scatter":
        return (rng.uniform(-160.0, 160.0, (n, 2)).astype(np.float32) * amt)
    # wind (general path: stagger/ease variants of the legacy field)
    wx, wy = float(wind[0]), float(wind[1])
    spread = 28.0 * amt
    turb = rng.uniform(-spread, spread, (n, 2)).astype(np.float32)
    base = np.array([[wy * amt, wx * amt]], dtype=np.float32)
    return base + turb


__all__ = ["_pinned_frac", "_bayer_rank", "stagger_delays", "ease_env",
           "_rain_profile", "_field_offset"]
