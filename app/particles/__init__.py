"""Particle engine facade (R2 split step 1).

New import path; app.disintegrate remains the canonical shim so all
existing `from app.disintegrate import ...` call sites keep working.
"""

from __future__ import annotations

from app.particles.fields import (_bayer_rank, _field_offset, _pinned_frac,
                                  _rain_profile, ease_env, stagger_delays)
from app.particles.modes import (DISINTEGRATE_MODES, EASE_MODES, MAX_MORPH_IMAGES,
                                 MAX_POINTS, MAX_TRAIL, STAGGER_MODES, TRAVEL_SPAN)

__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MAX_POINTS", "TRAVEL_SPAN", "MAX_TRAIL", "MAX_MORPH_IMAGES",
           "_pinned_frac", "_bayer_rank", "stagger_delays", "ease_env",
           "_rain_profile", "_field_offset"]
