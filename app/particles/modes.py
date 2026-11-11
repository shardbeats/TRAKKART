"""Particle engine constants (R2 split step 1: zero-dependency leaf).

Single home for mode lists and caps. app.disintegrate imports from
here; external callers keep importing from app.disintegrate (shim).
"""

from __future__ import annotations

DISINTEGRATE_MODES = ("wind", "random", "burst", "suction", "vortex",
                      "rain", "rise", "wave", "ripple", "flow", "blocks",
                      "spiral", "stream", "scatter")
#: Release stagger: per-particle phase shift (loop-safe via %1).
STAGGER_MODES = ("off", "rank", "radial", "scan", "sweep")
#: Loop envelope shape (all close at the joints: env(0) == env(1) == 0).
EASE_MODES = ("sine", "cubic", "linear", "elastic", "bounce")

#: Hard cap on rasterized points per frame (perf: vectorized scatter).
#: The budget is a *density* at POINT_REF_SIDE: bigger canvases get more
#: points (same dots per image area), instead of a fixed count that made
#: a 3000px doc look 3.5x sparser than its 1600px preview.
MAX_POINTS = 120_000
POINT_REF_SIDE = 1200
#: Absolute ceiling (memory/time): reached at 3000px with the 120k budget.
MAX_POINTS_HARD = 900_000


def point_cap(side: int) -> int:
    """Particle cap for a canvas: MAX_POINTS scaled by area, then clamped."""
    s = max(1, int(side or 0))
    scale = (s / float(POINT_REF_SIDE)) ** 2
    return int(min(MAX_POINTS_HARD, max(MAX_POINTS, MAX_POINTS * scale)))


#: Travel pairing for morph legs (F3): morton = legacy Z-order 1:1
#: (tears in spatial blocks mid-flight); smooth = jittered locality
#: pairing (organic pour, no block tear). Joints stay byte-exact either
#: way (any bijection lands assembled).
MATCH_MODES = ("morton", "smooth")
#: Rasterized dot shape for dotsize >= 2 (F2): square = legacy kxk
#: blocks; round = inscribed disc. Dotsize 1 is one pixel either way,
#: so joints stay byte-exact under both shapes.
DOT_SHAPES = ("square", "round")
#: Travel path style for morph legs (F3): pour = straight lerp,
#: arc/swirl/braid add a mid-flight flourish that is exactly zero at
#: both joints (joints stay byte-exact).
MORPH_PATHS = ("pour", "arc", "swirl", "braid")
#: Stagger window for destination travel: qi spans q*(1+S)-d*S so
#: particles pour in waves while both joints stay exact (q=0 -> 0, q=1 -> 1).
TRAVEL_SPAN = 0.5

#: Motion-trail buffer cap (frames of ghost dots per render).
MAX_TRAIL = 8

#: Hard cap on chain length (A + up to 5 more).
MAX_MORPH_IMAGES = 6

__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MORPH_PATHS", "MATCH_MODES", "DOT_SHAPES",
           "MAX_POINTS", "POINT_REF_SIDE", "MAX_POINTS_HARD", "point_cap",
           "TRAVEL_SPAN", "MAX_TRAIL", "MAX_MORPH_IMAGES"]
