"""UI panel builders (package split of the old panels.py monolith).

Same public names: `from app.ui import panels as P` keeps working.
"""

from __future__ import annotations

from app.ui.panels.document import (
    build_canvas_section,
    build_color_section,
    build_image_section,
    build_method_section,
    build_pixel_section,
    build_preset_section,
)
from app.ui.panels.grade import (
    build_effects_section,
    build_glitch_section,
    build_grade_section,
    build_pre_section,
    build_texture_section,
    build_tint_section,
)
from app.ui.panels.studio import (
    build_custom_palette_section,
    build_drift_section,
    build_fx_stack_section,
    build_mosh_section,
    build_motif_section,
    build_ascii_section,
)
from app.ui.panels.animate import build_video_section
from app.ui.panels.morph import build_morph_section
from app.ui.panels.widgets import (
    labeled_slider,
    make_accordion,
    make_group,
    mini_slider,
    spin_row,
)

__all__ = [
    "make_accordion",
    "make_group",
    "labeled_slider",
    "mini_slider",
    "spin_row",
    "build_image_section",
    "build_preset_section",
    "build_method_section",
    "build_pixel_section",
    "build_color_section",
    "build_canvas_section",
    "build_pre_section",
    "build_effects_section",
    "build_motif_section",
    "build_ascii_section",
    "build_fx_stack_section",
    "build_mosh_section",
    "build_drift_section",
    "build_morph_section",
    "build_grade_section",
    "build_tint_section",
    "build_texture_section",
    "build_glitch_section",
    "build_video_section",
    "build_custom_palette_section",
]
