"""Particle engine facade (R2 split step 1).

New import path; app.disintegrate remains the canonical shim so all
existing `from app.disintegrate import ...` call sites keep working.
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
from app.particles.modes import (DISINTEGRATE_MODES, EASE_MODES, MAX_MORPH_IMAGES,  # noqa: F401
                                 MAX_POINTS, MAX_TRAIL, STAGGER_MODES, TRAVEL_SPAN)
from app.particles.raster import (_paint_layer, dot_sizes, frame_dot_sizes,  # noqa: F401
                                  ghost_entries, render_points, trail_decay)
from app.particles.travel import (_smootherstep, block_visible,  # noqa: F401
                                  disperse_positions, match_travel,
                                  travel_positions)

__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MAX_POINTS", "TRAVEL_SPAN", "MAX_TRAIL", "MAX_MORPH_IMAGES",
           "_pinned_frac", "_bayer_rank", "stagger_delays", "ease_env",
           "_rain_profile", "_field_offset", "_fit_cover", "_refit_coords",
           "iter_dissolve", "dissolve_frames", "morph_frames",
           "iter_morph_chain", "morph_chain_frames",
           "dither_bw", "points_from_dither", "inked_points", "morph_ink",
           "sample_colors", "darkness_map", "tint_strength", "tint_dots",
           "_darkness_of",
           "dot_sizes", "frame_dot_sizes", "trail_decay", "ghost_entries",
           "_paint_layer", "render_points",
           "_smootherstep", "match_travel", "travel_positions",
           "disperse_positions", "block_visible"]
