"""TRAKKART particle disperse + morph (dither-boy style, MIT). Numpy + Pillow only.

Single-image loop (dissolve_frames: assembled -> dispersed -> assembled)
plus one-shot swap (morph_frames: A -> B through one shared particle cloud).

Loop-perfect dissolve: the turbulence pattern is fixed per clip (seeded
once) and only its amplitude breathes with sin(pi*frac), so progress 0 == 1.
Deterministic: same inputs + frame = same pixels (default_rng(seed)).
Strict 0=off: amount 0 returns the still (identity; hard cut for morph).

Canonical shim (R2 split): the engine lives in app.particles.* and this
module re-exports the full public API so existing imports keep working.
"""

from __future__ import annotations

from app.particles.color import (darkness_map, dither_bw, inked_points,  # noqa: F401
                                 morph_ink, points_from_dither, sample_colors,
                                 tint_dots, tint_strength, _darkness_of)
from app.particles.engine import (_fit_cover, _refit_coords,  # noqa: F401
                                  dissolve_frames, iter_dissolve, iter_morph_chain,
                                  morph_chain_frames, morph_frames)
from app.particles.fields import (_bayer_rank, _field_offset, _pinned_frac,  # noqa: F401
                                  _rain_profile, ease_env, stagger_delays)
from app.particles.modes import (DISINTEGRATE_MODES, DOT_SHAPES, EASE_MODES, MATCH_MODES,  # noqa: F401
                                 MAX_MORPH_IMAGES,
                                 MAX_POINTS, MAX_POINTS_HARD, MAX_TRAIL, MORPH_PATHS,
                                 POINT_REF_SIDE, STAGGER_MODES, TRAVEL_SPAN, point_cap)
from app.particles.raster import (_paint_layer, dot_sizes, frame_dot_sizes,  # noqa: F401
                                  ghost_entries, render_points, trail_decay)
from app.particles.travel import (_smootherstep, block_visible,  # noqa: F401
                                  disperse_positions, match_travel,
                                  travel_positions)


__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MORPH_PATHS", "MATCH_MODES", "DOT_SHAPES",
           "MAX_POINTS", "MAX_MORPH_IMAGES", "dither_bw",
           "points_from_dither", "disperse_positions", "block_visible",
           "match_travel", "travel_positions",
           "stagger_delays", "ease_env", "render_points",
           "dissolve_frames", "morph_frames", "morph_chain_frames",
           "iter_dissolve", "iter_morph_chain"]
