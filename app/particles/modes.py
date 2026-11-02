"""Particle engine constants (R2 split step 1: zero-dependency leaf).

Single home for mode lists and caps. app.disintegrate imports from
here; external callers keep importing from app.disintegrate (shim).
"""

from __future__ import annotations

DISINTEGRATE_MODES = ("wind", "random", "burst", "suction", "vortex",
                      "rain", "rise", "wave", "ripple", "flow", "blocks")
#: Release stagger: per-particle phase shift (loop-safe via %1).
STAGGER_MODES = ("off", "rank", "radial", "scan", "sweep")
#: Loop envelope shape (all close at the joints: env(0) == env(1) == 0).
EASE_MODES = ("sine", "cubic", "linear", "elastic", "bounce")

#: Hard cap on rasterized points per frame (perf: vectorized scatter).
MAX_POINTS = 120_000

#: Stagger window for destination travel: qi spans q*(1+S)-d*S so
#: particles pour in waves while both joints stay exact (q=0 -> 0, q=1 -> 1).
TRAVEL_SPAN = 0.5

#: Motion-trail buffer cap (frames of ghost dots per render).
MAX_TRAIL = 8

#: Hard cap on chain length (A + up to 5 more).
MAX_MORPH_IMAGES = 6

__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MAX_POINTS", "TRAVEL_SPAN", "MAX_TRAIL", "MAX_MORPH_IMAGES"]
