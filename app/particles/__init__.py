"""Particle engine facade (R2 split step 1).

New import path; app.disintegrate remains the canonical shim so all
existing `from app.disintegrate import ...` call sites keep working.
"""

from __future__ import annotations

from app.particles.modes import (DISINTEGRATE_MODES, EASE_MODES, MAX_MORPH_IMAGES,
                                 MAX_POINTS, MAX_TRAIL, STAGGER_MODES, TRAVEL_SPAN)

__all__ = ["DISINTEGRATE_MODES", "STAGGER_MODES", "EASE_MODES",
           "MAX_POINTS", "TRAVEL_SPAN", "MAX_TRAIL", "MAX_MORPH_IMAGES"]
